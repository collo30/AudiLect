import os
import time
import argparse
import cv2
import numpy as np
import mss
import imageio_ffmpeg
import subprocess
from typing import Optional, Callable


class ScreenRecorder:
    """
    Local Screen Recorder for Audilect.
    Captures display frames at high fidelity for lecture recording.
    """

    def __init__(self, fps: int = 15, monitor_idx: int = 1):
        self.fps = fps
        self.monitor_idx = monitor_idx
        self.is_recording = False

    def record_to_file(
        self,
        output_path: str,
        duration_sec: Optional[float] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[float, int], None]] = None
    ) -> str:
        """
        Records the screen to an MP4 video file.
        
        Args:
            output_path: Path to target MP4 file
            duration_sec: Optional duration in seconds
            stop_check: Optional callback returning True when recording should stop
            progress_callback: Optional callback receiving (elapsed_sec, frames_captured)
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with mss.mss() as sct:
            monitors = sct.monitors
            mon = monitors[self.monitor_idx if self.monitor_idx < len(monitors) else 0]
            width, height = mon["width"], mon["height"]

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            temp_raw = output_path.replace(".mp4", "_raw.mp4")
            writer = cv2.VideoWriter(temp_raw, fourcc, self.fps, (width, height))

            self.is_recording = True
            start_time = time.time()
            frame_interval = 1.0 / self.fps
            frame_count = 0

            try:
                while self.is_recording:
                    loop_start = time.time()

                    if duration_sec and (loop_start - start_time) >= duration_sec:
                        break
                    if stop_check and stop_check():
                        break

                    img = sct.grab(mon)
                    frame = np.array(img)
                    # Convert BGRA to BGR
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    writer.write(frame_bgr)
                    frame_count += 1

                    elapsed = time.time() - start_time
                    if progress_callback and frame_count % self.fps == 0:
                        progress_callback(elapsed, frame_count)

                    time_spent = time.time() - loop_start
                    to_sleep = frame_interval - time_spent
                    if to_sleep > 0:
                        time.sleep(to_sleep)
            finally:
                writer.release()
                self.is_recording = False

            # Remux with ffmpeg for web playback compatibility (H.264 / faststart)
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg, "-y",
                "-i", temp_raw,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(temp_raw):
                try:
                    os.remove(temp_raw)
                except OSError:
                    pass

        return output_path


def main():
    parser = argparse.ArgumentParser(description="Audilect CLI Screen Recorder")
    parser.add_argument("--output", default="data/recordings/lecture_rec.mp4", help="Output file path")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration in seconds (default 10s)")
    parser.add_argument("--fps", type=int, default=15, help="Framerate (default 15)")

    args = parser.parse_args()
    print(f"[*] Starting Screen Recording ({args.duration}s @ {args.fps}fps)... Press Ctrl+C to stop.")

    recorder = ScreenRecorder(fps=args.fps)
    def callback(elapsed, frames):
        print(f"    Recording: {elapsed:.1f}s | {frames} frames captured")

    out = recorder.record_to_file(args.output, duration_sec=args.duration, progress_callback=callback)
    print(f"[+] Screen recording saved to: {out}")


if __name__ == "__main__":
    main()
