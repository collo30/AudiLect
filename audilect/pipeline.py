import os
import json
import time
import uuid
from typing import Dict, Any, Optional, Callable

from audilect.audio.extractor import extract_audio
from audilect.vision.slide_detector import detect_slides_from_video, format_seconds
from audilect.transcription.whisper_engine import SpeechEngine
from audilect.engine.semantic import CognitiveEngine
from audilect.engine.llm import AIEngine, annotate_transcript_elaborations
from audilect.exporters.anki import export_anki_csv
from audilect.exporters.cornell import export_cornell_markdown


class ProcessingPipeline:
    def __init__(
        self,
        sessions_dir: str = "data/sessions",
        whisper_model_size: str = "base",
        whisper_device: str = "cpu",
        whisper_compute_type: str = "int8"
    ):
        self.sessions_dir = sessions_dir
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.speech_engine = SpeechEngine(
            model_size=whisper_model_size,
            device=whisper_device,
            compute_type=whisper_compute_type
        )
        self.cognitive_engine = CognitiveEngine()
        self.ai_engine = AIEngine()

    def run_file_pipeline(
        self,
        video_path: str,
        session_id: Optional[str] = None,
        max_duration_sec: Optional[float] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end processing of a lecture video:
        1. Extract audio
        2. Detect slides via pHash
        3. Transcribe with word timestamps via faster-whisper
        4. Synthesize Socratic checkpoints and concept anchors
        5. Generate study artifacts
        """
        start_wall_time = time.time()
        video_path = os.path.abspath(video_path)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not session_id:
            session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        session_dir = os.path.join(self.sessions_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        slides_dir = os.path.join(session_dir, "slides")
        os.makedirs(slides_dir, exist_ok=True)

        audio_wav = os.path.join(session_dir, "audio.wav")

        # Step 1: Audio Extraction
        if progress_callback:
            progress_callback(10.0, "Extracting 16kHz mono audio from video...")
        extract_audio(video_path, audio_wav, duration=max_duration_sec)

        # Step 2: Perceptual Hash Slide Detection
        if progress_callback:
            progress_callback(25.0, "Detecting slide keyframes via pHash...")
        slides = detect_slides_from_video(
            video_path=video_path,
            output_dir=slides_dir,
            sample_interval_sec=1.0,
            hash_diff_threshold=12,
            max_duration_sec=max_duration_sec,
            progress_callback=lambda pct, msg: progress_callback(25.0 + (pct * 0.25), msg) if progress_callback else None
        )

        # Step 3: Transcription with word-level timestamps
        if progress_callback:
            progress_callback(55.0, "Running faster-whisper CTranslate2 INT8 speech transcription...")
        transcription_res = self.speech_engine.transcribe(
            audio_path=audio_wav,
            progress_callback=lambda pct, msg: progress_callback(55.0 + (pct * 0.30), msg) if progress_callback else None
        )
        # Step 4: Semantic Topic Boundaries & Socratic Engine
        if progress_callback:
            progress_callback(90.0, "Synthesizing deep Socratic checkpoints & outside AI knowledge...")

        video_title = os.path.splitext(os.path.basename(video_path))[0]
        raw_segments = transcription_res.get("segments", [])
        topic_blocks = self.cognitive_engine.link_slides_and_transcripts(slides, raw_segments)
        concept_anchors = self.ai_engine.generate_clear_concepts(topic_blocks, lecture_title=video_title)
        checkpoints = self.ai_engine.generate_intelligent_checkpoints(topic_blocks, lecture_title=video_title)
        segments = self.ai_engine.enrich_transcript_with_external_knowledge(raw_segments, topic_blocks, lecture_title=video_title)



        duration = transcription_res.get("duration", 0.0)

        # Step 5: Export artifacts
        anki_csv = export_anki_csv(topic_blocks, concept_anchors, checkpoints, deck_name=f"Audilect::{video_title}")
        cornell_md = export_cornell_markdown(
            title=video_title,
            duration_str=format_seconds(duration),
            topic_blocks=topic_blocks,
            concept_anchors=concept_anchors,
            checkpoints=checkpoints
        )

        with open(os.path.join(session_dir, "anki_deck.csv"), "w", encoding="utf-8") as f:
            f.write(anki_csv)
        with open(os.path.join(session_dir, "cornell_notes.md"), "w", encoding="utf-8") as f:
            f.write(cornell_md)

        # Compile session metadata
        total_words = sum(len(seg["text"].split()) for seg in segments)
        total_time_taken = round(time.time() - start_wall_time, 2)

        session_data = {
            "session_id": session_id,
            "created_at": time.time(),
            "video_path": video_path,
            "video_filename": os.path.basename(video_path),
            "video_title": video_title,
            "duration": duration,
            "duration_formatted": format_seconds(duration),
            "total_slides": len(slides),
            "total_words": total_words,
            "total_segments": len(segments),
            "processing_time_sec": total_time_taken,
            "whisper_model": self.speech_engine.model_size,
            "whisper_compute": self.speech_engine.compute_type,
            "slides": slides,
            "segments": segments,
            "topic_blocks": topic_blocks,
            "concept_anchors": concept_anchors,
            "checkpoints": checkpoints
        }

        # Save session file
        session_file = os.path.join(session_dir, "session.json")
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        # Generate publication-grade PDF study guide
        try:
            from audilect.exporters.pdf_export import generate_pdf_study_guide
            generate_pdf_study_guide(session_data, os.path.join(session_dir, "study_guide.pdf"))
        except Exception as e:
            print(f"[*] PDF export failed: {e}")

        if progress_callback:
            progress_callback(100.0, f"Processing complete in {total_time_taken}s.")

        return session_data

    def reprocess_session_ai(
        self,
        session_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Fast AI-only reprocessing (~2-5s).
        Takes an existing session's extracted slides and transcript segments,
        re-evaluates with the active AI engine (Gemini/Groq), and re-exports Anki/Cornell notes.
        """
        session_dir = os.path.join(self.sessions_dir, session_id)
        session_file = os.path.join(session_dir, "session.json")
        if not os.path.exists(session_file):
            raise FileNotFoundError(f"Session not found: {session_id}")

        if progress_callback:
            progress_callback(10.0, "Loading session data...")

        with open(session_file, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        slides = session_data.get("slides", [])
        raw_segments = session_data.get("segments", [])
        video_title = session_data.get("video_title", "Lecture")
        duration = session_data.get("duration", 0.0)

        # 1. Re-link topic blocks
        if progress_callback:
            progress_callback(25.0, "Linking lecture timeline...")
        topic_blocks = self.cognitive_engine.link_slides_and_transcripts(slides, raw_segments)

        # 2. Re-extract clear concepts with active AI engine
        self.ai_engine.reload_config()
        if progress_callback:
            progress_callback(45.0, "Extracting study concepts...")
        concept_anchors = self.ai_engine.generate_clear_concepts(topic_blocks, lecture_title=video_title)

        # 3. Generate concise, high-density Socratic checkpoints
        if progress_callback:
            progress_callback(65.0, "Generating active recall questions...")
        checkpoints = self.ai_engine.generate_intelligent_checkpoints(topic_blocks, lecture_title=video_title)

        # 4. Enrich transcript with external AI knowledge callouts
        if progress_callback:
            progress_callback(85.0, "Enriching transcript with outside knowledge...")
        annotated_segments = self.ai_engine.enrich_transcript_with_external_knowledge(raw_segments, topic_blocks, lecture_title=video_title)



        # 5. Re-export Anki & Cornell notes
        anki_csv = export_anki_csv(topic_blocks, concept_anchors, checkpoints, deck_name=f"Audilect::{video_title}")
        cornell_md = export_cornell_markdown(
            title=video_title,
            duration_str=format_seconds(duration),
            topic_blocks=topic_blocks,
            concept_anchors=concept_anchors,
            checkpoints=checkpoints
        )

        with open(os.path.join(session_dir, "anki_deck.csv"), "w", encoding="utf-8") as f:
            f.write(anki_csv)
        with open(os.path.join(session_dir, "cornell_notes.md"), "w", encoding="utf-8") as f:
            f.write(cornell_md)

        # Update session data
        session_data["segments"] = annotated_segments
        session_data["topic_blocks"] = topic_blocks
        session_data["concept_anchors"] = concept_anchors
        session_data["checkpoints"] = checkpoints
        session_data["reprocessed_at"] = time.time()

        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        # Regenerate publication-grade PDF study guide
        try:
            from audilect.exporters.pdf_export import generate_pdf_study_guide
            generate_pdf_study_guide(session_data, os.path.join(session_dir, "study_guide.pdf"))
        except Exception as e:
            print(f"[*] PDF export failed: {e}")

        if progress_callback:
            progress_callback(100.0, "Reprocessing complete.")

        return session_data

    def reprocess_session_full(
        self,
        session_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Full reprocessing of an existing session.
        Re-extracts audio, pHash slides, whisper transcription, and AI cognition.
        """
        session_dir = os.path.join(self.sessions_dir, session_id)
        session_file = os.path.join(session_dir, "session.json")
        if not os.path.exists(session_file):
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(session_file, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        video_path = session_data.get("video_path")
        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError(f"Original video source not found at: {video_path}")

        return self.run_file_pipeline(
            video_path=video_path,
            session_id=session_id,
            progress_callback=progress_callback
        )

