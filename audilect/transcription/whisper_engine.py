import os
import json
import base64
import urllib.request
import subprocess
from typing import List, Dict, Any, Optional, Callable
import imageio_ffmpeg


class SpeechEngine:
    """
    Intelligent Hybrid Speech Engine:
    1. Cloud AI Transcription (Google Gemini / Groq Whisper API) for ultra-fast, zero-GPU cloud transcription.
    2. Local CTranslate2 INT8 faster-whisper fallback when offline or no API key is provided.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        config_path: str = "data/config.json"
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.config_path = config_path
        self.local_model = None

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def load_local_model(self):
        if self.local_model is None:
            from faster_whisper import WhisperModel
            self.local_model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self.local_model

    def transcribe(
        self,
        audio_path: str,
        beam_size: int = 1,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Transcribes audio into timestamped segments and word tokens.
        Automatically uses Cloud AI if API keys are configured, falling back to local faster-whisper.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        cfg = self._load_config()
        groq_key = cfg.get("groq_api_key", "").strip()
        gemini_key = cfg.get("gemini_api_key", "").strip()

        # 1. Try Groq Cloud Whisper API if key is present (Flagship whisper-large-v3, ~3 seconds)
        if groq_key:
            try:
                if progress_callback:
                    progress_callback(10.0, "Transcribing with Cloud AI Whisper (Groq large-v3-turbo)...")
                res = self._transcribe_groq(audio_path, groq_key, progress_callback)
                if res and res.get("segments"):
                    return res
            except Exception as e:
                print(f"[*] Cloud Groq transcription failed, trying next provider: {e}")

        # 2. Try Google Gemini Audio Transcription if key is present (gemini-2.5-flash / gemini-3.5-flash)
        if gemini_key:
            try:
                if progress_callback:
                    progress_callback(20.0, "Transcribing with Google Gemini Cloud Speech Intelligence...")
                res = self._transcribe_gemini(audio_path, gemini_key, progress_callback)
                if res and res.get("segments"):
                    return res
            except Exception as e:
                print(f"[*] Cloud Gemini transcription failed, falling back to local faster-whisper: {e}")

        # 3. Fallback to Local faster-whisper (CTranslate2 INT8)
        if progress_callback:
            progress_callback(30.0, "Running local speech transcription (faster-whisper INT8)...")
        return self._transcribe_local(audio_path, beam_size, language, progress_callback)

    def _transcribe_groq(
        self,
        audio_path: str,
        api_key: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribe using Groq's high-speed Whisper Large v3 Turbo API."""
        import requests
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}

        # Check file size. Groq limit is 25MB. Compress to 64k mp3 if needed.
        upload_path = audio_path
        temp_mp3 = None
        if os.path.getsize(audio_path) > 20 * 1024 * 1024 or not audio_path.endswith(".mp3"):
            temp_mp3 = audio_path + ".temp.mp3"
            ff_bin = imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run([ff_bin, "-y", "-i", audio_path, "-b:a", "64k", temp_mp3],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            upload_path = temp_mp3

        try:
            with open(upload_path, "rb") as f:
                files = {"file": (os.path.basename(upload_path), f, "audio/mpeg")}
                data = {
                    "model": "whisper-large-v3-turbo",
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": ["word", "segment"]
                }
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=90.0)
                if resp.status_code != 200:
                    raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")

                res_json = resp.json()
                raw_segs = res_json.get("segments", [])
                segments_list = []
                for idx, s in enumerate(raw_segs):
                    seg_text = s.get("text", "").strip()
                    s_start = round(float(s.get("start", 0.0)), 2)
                    s_end = round(float(s.get("end", s_start + 1.0)), 2)

                    words = []
                    raw_words = s.get("words", [])
                    if raw_words:
                        for w in raw_words:
                            words.append({
                                "word": w.get("word", "").strip(),
                                "start": round(float(w.get("start", s_start)), 2),
                                "end": round(float(w.get("end", s_end)), 2)
                            })
                    else:
                        tokens = seg_text.split()
                        dur = max(0.1, s_end - s_start)
                        w_dur = dur / max(1, len(tokens))
                        for i, tok in enumerate(tokens):
                            words.append({
                                "word": tok,
                                "start": round(s_start + (i * w_dur), 2),
                                "end": round(s_start + ((i + 1) * w_dur), 2)
                            })

                    segments_list.append({
                        "id": idx + 1,
                        "start": s_start,
                        "end": s_end,
                        "text": seg_text,
                        "words": words
                    })

                total_dur = segments_list[-1]["end"] if segments_list else 1.0
                return {
                    "language": res_json.get("language", "en"),
                    "language_probability": 0.99,
                    "duration": total_dur,
                    "segments": segments_list,
                    "total_segments": len(segments_list)
                }
        finally:
            if temp_mp3 and os.path.exists(temp_mp3):
                os.remove(temp_mp3)

    def _transcribe_gemini(
        self,
        audio_path: str,
        api_key: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribe using Google Gemini Multimodal Audio Intelligence."""
        # Convert to compact 64k mono mp3
        temp_mp3 = audio_path + ".gemini.mp3"
        ff_bin = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff_bin, "-y", "-i", audio_path, "-b:a", "64k", temp_mp3],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            with open(temp_mp3, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")

            prompt = """You are an expert audio transcription system.
Transcribe the speech in this audio recording verbatim, maintaining chronological order.
Output strictly valid JSON with an array of segment objects:
[
  {
    "start": 0.0,
    "end": 3.8,
    "text": "Exact spoken sentence here."
  }
]
Rules:
- Keep timestamps in decimal seconds.
- Group by natural sentence boundaries (3-8 seconds per segment).
- Do not summarize or skip words. Transcribe accurately.
"""
            payload = {
                "contents": [{
                    "parts": [
                        {"inline_data": {"mime_type": "audio/mp3", "data": audio_b64}},
                        {"text": prompt}
                    ]
                }],
                "generationConfig": {"response_mime_type": "application/json"}
            }

            candidates = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash"]
            parsed_segments = None

            for model_name in candidates:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=60.0) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        text_content = res["candidates"][0]["content"]["parts"][0]["text"]
                        raw_data = json.loads(text_content)
                        if isinstance(raw_data, dict) and "segments" in raw_data:
                            raw_data = raw_data["segments"]
                        if isinstance(raw_data, list) and len(raw_data) > 0:
                            parsed_segments = raw_data
                            break
                except Exception as ex:
                    print(f"[*] Gemini transcription attempt on {model_name} failed: {ex}")

            if not parsed_segments:
                return None

            segments_list = []
            for idx, s in enumerate(parsed_segments):
                seg_text = s.get("text", "").strip()
                s_start = round(float(s.get("start", 0.0)), 2)
                s_end = round(float(s.get("end", s_start + 2.0)), 2)

                tokens = seg_text.split()
                dur = max(0.1, s_end - s_start)
                w_dur = dur / max(1, len(tokens))
                words = []
                for i, tok in enumerate(tokens):
                    words.append({
                        "word": tok,
                        "start": round(s_start + (i * w_dur), 2),
                        "end": round(s_start + ((i + 1) * w_dur), 2)
                    })

                segments_list.append({
                    "id": idx + 1,
                    "start": s_start,
                    "end": s_end,
                    "text": seg_text,
                    "words": words
                })

            total_dur = segments_list[-1]["end"] if segments_list else 1.0
            return {
                "language": "en",
                "language_probability": 0.99,
                "duration": total_dur,
                "segments": segments_list,
                "total_segments": len(segments_list)
            }
        finally:
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)

    def _transcribe_local(
        self,
        audio_path: str,
        beam_size: int = 1,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """Local faster-whisper transcription fallback."""
        model = self.load_local_model()

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

            segments_list.append({
                "id": idx + 1,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": words_data
            })

            if progress_callback:
                pct = min(100.0, (seg.end / total_duration) * 100)
                progress_callback(pct, f"Local Transcribe [{seg.start:.0f}s -> {seg.end:.0f}s]: {seg.text[:35]}...")

        return {
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(total_duration, 2),
            "segments": segments_list,
            "total_segments": len(segments_list)
        }
