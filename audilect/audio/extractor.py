import os
import subprocess
import wave
from pathlib import Path
from typing import Optional, Callable
import imageio_ffmpeg


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def get_ffmpeg_path() -> str:
    """Return path to ffmpeg executable."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def create_silent_wav(
    output_wav_path: str,
    duration_sec: float = 10.0,
    sample_rate: int = 16000,
    channels: int = 1
) -> str:
    """Creates a standard 16-bit PCM silent WAV file natively without external processes."""
    output_dir = os.path.dirname(os.path.abspath(output_wav_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    duration_sec = max(1.0, float(duration_sec))
    num_samples = int(sample_rate * duration_sec)
    with wave.open(output_wav_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * (num_samples * 2 * channels))
    return output_wav_path


def extract_audio(
    video_path: str,
    output_wav_path: str,
    sample_rate: int = 16000,
    channels: int = 1,
    start_time: Optional[float] = None,
    duration: Optional[float] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Extracts audio from video_path and converts it to a standard PCM 16-bit WAV file.
    If the video has no audio tracks (e.g. window captures), smoothly synthesizes
    a silent WAV matching the video duration so slide analysis and downstream pipelines succeed.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir = os.path.dirname(output_wav_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    ffmpeg_bin = get_ffmpeg_path()

    cmd = [ffmpeg_bin, "-y"]
    if start_time is not None and start_time > 0:
        cmd.extend(["-ss", str(start_time)])
    if duration is not None and duration > 0:
        cmd.extend(["-t", str(duration)])

    cmd.extend([
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        output_wav_path
    ])

    if progress_callback:
        progress_callback(f"Extracting audio from {os.path.basename(video_path)}...")

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=CREATE_NO_WINDOW)
    if result.returncode != 0:
        stderr_text = (result.stderr or "").lower()
        # Handle videos/recordings without audio tracks gracefully
        is_missing_stream = (
            "does not contain any stream" in stderr_text
            or "matches no streams" in stderr_text
            or "invalid argument" in stderr_text
            or "error opening output files" in stderr_text
        )
        if is_missing_stream:
            if progress_callback:
                progress_callback(f"No audio track found in {os.path.basename(video_path)}. Generating silent audio track...")
            
            # Determine video duration
            vid_dur = 10.0
            dur_cmd = [ffmpeg_bin, "-i", video_path]
            dur_res = subprocess.run(dur_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=CREATE_NO_WINDOW)
            import re
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", dur_res.stderr or "")
            if m:
                vid_dur = float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
            else:
                try:
                    import cv2
                    cap = cv2.VideoCapture(video_path)
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                    if frames > 0 and fps > 0:
                        vid_dur = frames / fps
                    cap.release()
                except Exception:
                    pass

            if duration is not None and duration > 0:
                vid_dur = min(vid_dur, duration)
            vid_dur = max(1.0, vid_dur)

            # Native, 100% reliable silent WAV generation
            create_silent_wav(output_wav_path, duration_sec=vid_dur, sample_rate=sample_rate, channels=channels)
            if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
                if progress_callback:
                    progress_callback("Silent audio track created. Proceeding with visual slide extraction.")
                return output_wav_path

        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
        raise RuntimeError(f"Audio file was not created or is empty: {output_wav_path}")

    if progress_callback:
        progress_callback("Audio extraction complete.")

    return output_wav_path
