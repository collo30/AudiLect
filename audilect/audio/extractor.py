import os
import subprocess
from pathlib import Path
from typing import Optional, Callable
import imageio_ffmpeg


def get_ffmpeg_path() -> str:
    """Return path to ffmpeg executable."""
    return imageio_ffmpeg.get_ffmpeg_exe()


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
    
    Args:
        video_path: Path to source video (.mp4, .mkv, .mov, etc.)
        output_wav_path: Destination path for extracted .wav
        sample_rate: Target sample rate (16000Hz optimal for Whisper)
        channels: Target channels (1 = mono)
        start_time: Optional start offset in seconds
        duration: Optional duration limit in seconds
        progress_callback: Optional status callback
    
    Returns:
        Path to output_wav_path
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

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
        raise RuntimeError(f"Audio file was not created or is empty: {output_wav_path}")

    if progress_callback:
        progress_callback("Audio extraction complete.")

    return output_wav_path
