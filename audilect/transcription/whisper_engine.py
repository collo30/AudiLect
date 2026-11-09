import os
from typing import List, Dict, Any, Optional, Callable
from faster_whisper import WhisperModel


class SpeechEngine:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        """
        Initializes the faster-whisper CTranslate2 speech engine.
        
        Args:
            model_size: Model size ('tiny', 'base', 'small', 'medium', 'large-v3')
            device: 'cpu' or 'cuda'
            compute_type: Quantization mode ('int8', 'float16', 'float32', etc.)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def load_model(self):
        if self.model is None:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self.model

    def transcribe(
        self,
        audio_path: str,
        beam_size: int = 1,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Transcribes an audio file into timestamped segments and word-level timing data.
        
        Args:
            audio_path: Path to .wav or audio file
            beam_size: Beam search width (1 is fast and accurate for INT8)
            language: Optional language code (e.g. 'en')
            progress_callback: Optional callback for transcription progress
            
        Returns:
            Dictionary with transcription segments, word tokens, and language info.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self.load_model()

        if progress_callback:
            progress_callback(0.0, "Running faster-whisper transcription (CTranslate2 INT8)...")

        segments_generator, info = model.transcribe(
            audio_path,
            beam_size=beam_size,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            language=language
        )

        segments_list: List[Dict[str, Any]] = []
        total_duration = info.duration or 1.0

        for idx, seg in enumerate(segments_generator):
            words_data = []
            if seg.words:
                for w in seg.words:
                    words_data.append({
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 3)
                    })

            segment_dict = {
                "id": idx + 1,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": words_data
            }
            segments_list.append(segment_dict)

            if progress_callback:
                pct = min(100.0, (seg.end / total_duration) * 100)
                progress_callback(pct, f"Transcribing [{seg.start:.0f}s -> {seg.end:.0f}s]: {seg.text[:40]}...")

        return {
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(total_duration, 2),
            "segments": segments_list,
            "total_segments": len(segments_list)
        }
