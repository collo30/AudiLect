import os
import cv2
import imagehash
from PIL import Image
from typing import List, Dict, Any, Optional, Callable


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    secs = int(seconds)
    mins = secs // 60
    secs = secs % 60
    hours = mins // 60
    mins = mins % 60
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def detect_slides_from_video(
    video_path: str,
    output_dir: str,
    sample_interval_sec: float = 1.0,
    hash_diff_threshold: int = 12,
    min_slide_duration_sec: float = 2.0,
    max_duration_sec: Optional[float] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Scans a lecture video using Perceptual Hashing (pHash) to detect slide changes.
    Saves high-res keyframe images and thumbnails for each detected slide.
    
    Args:
        video_path: Path to lecture video
        output_dir: Directory to save slide keyframes
        sample_interval_sec: Interval in seconds between sampled frames (default 1.0s)
        hash_diff_threshold: Hamming distance threshold (default 12 bits)
        min_slide_duration_sec: Minimum duration for a slide to prevent duplicate frames
        max_duration_sec: Optional limit for testing/partial scanning
        progress_callback: Callback receiving (percentage, status_text)
        
    Returns:
        List of slide dictionaries with timestamps, filenames, and hashes.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    os.makedirs(output_dir, exist_ok=True)
    thumb_dir = os.path.join(output_dir, "thumbs")
    os.makedirs(thumb_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    video_duration = total_frames / fps if fps > 0 else 0.0

    if max_duration_sec and max_duration_sec < video_duration:
        video_duration = max_duration_sec

    slides: List[Dict[str, Any]] = []
    prev_hash = None
    last_slide_time = -999.0
    slide_index = 0

    curr_time = 0.0
    step_sec = sample_interval_sec

    while curr_time <= video_duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, curr_time * 1000)
        ret, frame = cap.read()
        if not ret:
            break

        # Convert frame for pHash
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        curr_hash = imagehash.phash(pil_img)

        is_new_slide = False
        diff = 0

        if prev_hash is None:
            # First frame is always slide 1
            is_new_slide = True
        else:
            diff = curr_hash - prev_hash
            if diff >= hash_diff_threshold and (curr_time - last_slide_time) >= min_slide_duration_sec:
                is_new_slide = True

        if is_new_slide:
            slide_index += 1
            slide_filename = f"slide_{slide_index:03d}_{int(curr_time)}s.jpg"
            thumb_filename = f"thumb_{slide_index:03d}_{int(curr_time)}s.jpg"
            
            slide_path = os.path.join(output_dir, slide_filename)
            thumb_path = os.path.join(thumb_dir, thumb_filename)

            # Save full keyframe
            cv2.imwrite(slide_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

            # Save high-density thumbnail (width 320px)
            h, w = frame.shape[:2]
            thumb_w = 320
            thumb_h = int(h * (thumb_w / w))
            thumb_frame = cv2.resize(frame, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
            cv2.imwrite(thumb_path, thumb_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            slide_data = {
                "id": slide_index,
                "timestamp": round(curr_time, 2),
                "formatted_time": format_seconds(curr_time),
                "filename": slide_filename,
                "thumb_filename": f"thumbs/{thumb_filename}",
                "hash_diff": diff,
                "title": f"Slide {slide_index} ({format_seconds(curr_time)})"
            }
            slides.append(slide_data)
            last_slide_time = curr_time
            prev_hash = curr_hash

        if progress_callback and video_duration > 0:
            pct = min(100.0, (curr_time / video_duration) * 100)
            progress_callback(pct, f"Scanning video frames: {curr_time:.0f}s / {video_duration:.0f}s ({len(slides)} slides)")

        curr_time += step_sec

    cap.release()

    # Calculate end timestamps and durations for each slide
    for i, slide in enumerate(slides):
        if i + 1 < len(slides):
            slide["end_timestamp"] = slides[i + 1]["timestamp"]
            slide["duration"] = round(slide["end_timestamp"] - slide["timestamp"], 2)
        else:
            slide["end_timestamp"] = round(video_duration, 2)
            slide["duration"] = round(video_duration - slide["timestamp"], 2)

    return slides
