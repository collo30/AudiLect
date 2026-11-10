import os
import json
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, Optional

import sys
import subprocess
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import imageio_ffmpeg

from audilect.pipeline import ProcessingPipeline
from audilect.audio.wasapi import list_audio_devices, get_default_wasapi_loopback_device

app = FastAPI(title="Audilect Web Cockpit", version="0.1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "audilect" / "server" / "static").exists():
        STATIC_DIR = Path(meipass) / "audilect" / "server" / "static"
    elif meipass and (Path(meipass) / "static").exists():
        STATIC_DIR = Path(meipass) / "static"
    else:
        STATIC_DIR = Path(__file__).resolve().parent / "static"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    STATIC_DIR = Path(__file__).resolve().parent / "static"

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR = DATA_DIR / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

pipeline = ProcessingPipeline(sessions_dir=str(SESSIONS_DIR))

# In-memory progress tracker
active_jobs: Dict[str, Dict[str, Any]] = {}


class ProcessRequest(BaseModel):
    video_path: str
    max_duration_sec: Optional[float] = None
    whisper_model: Optional[str] = "base"


class AnswerRequest(BaseModel):
    session_id: str
    checkpoint_id: str
    selected_index: int


class AIConfigRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None


class AITestRequest(BaseModel):
    provider: str
    api_key: str
    model_name: str


class ReprocessRequest(BaseModel):
    mode: str = "ai"  # "ai" or "full"




def send_range_video(file_path: str, range_header: str):
    """Streams video file with HTTP 206 Partial Content support for seeking."""
    file_size = os.path.getsize(file_path)
    
    # Parse range header e.g. "bytes=0-1048576"
    byte1, byte2 = 0, None
    m = range_header.replace("bytes=", "").split("-")
    if m[0]:
        byte1 = int(m[0])
    if len(m) > 1 and m[1]:
        byte2 = int(m[1])

    length = file_size - byte1
    if byte2 is not None:
        length = byte2 - byte1 + 1

    chunk_size = 1024 * 1024  # 1MB chunk

    def file_stream():
        with open(file_path, "rb") as f:
            f.seek(byte1)
            remaining = length
            while remaining > 0:
                read_bytes = min(chunk_size, remaining)
                data = f.read(read_bytes)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {byte1}-{byte1 + length - 1}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(file_stream(), status_code=206, headers=headers)


@app.get("/api/status")
async def get_system_status():
    """Returns engine health, audio devices, and active jobs."""
    try:
        devices = list_audio_devices()
        loopback_dev = get_default_wasapi_loopback_device()
    except Exception:
        devices = []
        loopback_dev = None

    return {
        "status": "healthy",
        "whisper_model": pipeline.speech_engine.model_size,
        "whisper_compute": pipeline.speech_engine.compute_type,
        "default_loopback_device": loopback_dev,
        "audio_devices_count": len(devices),
        "active_jobs": active_jobs
    }


@app.get("/api/sessions")
async def list_sessions():
    """List all processed sessions."""
    sessions = []
    if SESSIONS_DIR.exists():
        for d in SESSIONS_DIR.iterdir():
            if d.is_dir():
                meta_file = d / "session.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            sessions.append({
                                "session_id": data.get("session_id"),
                                "video_title": data.get("video_title"),
                                "duration_formatted": data.get("duration_formatted"),
                                "total_slides": data.get("total_slides"),
                                "total_words": data.get("total_words"),
                                "created_at": data.get("created_at")
                            })
                    except Exception:
                        pass
    sessions.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return sessions


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve full data for a session."""
    meta_file = SESSIONS_DIR / session_id / "session.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    with open(meta_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/session/{session_id}/reprocess")
async def reprocess_session_endpoint(
    session_id: str,
    req: ReprocessRequest,
    bg_tasks: BackgroundTasks
):
    """
    Reprocesses an existing session:
    - 'ai': Fast AI re-synthesis (~2-3s) using active Gemini/Groq model on existing transcript.
    - 'full': Full reprocessing of original video source (audio + pHash + whisper + AI).
    """
    meta_file = SESSIONS_DIR / session_id / "session.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    if req.mode == "ai":
        try:
            updated = pipeline.reprocess_session_ai(session_id)
            return {"status": "completed", "session_id": session_id, "session": updated}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI reprocessing failed: {e}")

    elif req.mode == "full":
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        video_path = meta.get("video_path")
        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=400, detail=f"Original video file not found at: {video_path}")

        job_id = f"reprocess_{int(asyncio.get_event_loop().time())}_{session_id[:8]}"
        active_jobs[job_id] = {
            "job_id": job_id,
            "video_path": video_path,
            "status": "processing",
            "progress": 0.0,
            "status_message": "Starting full session reprocessing...",
            "error": None
        }

        def _reprocess_bg():
            def callback(pct: float, msg: str):
                active_jobs[job_id]["progress"] = round(pct, 1)
                active_jobs[job_id]["status_message"] = msg
            try:
                pipeline.run_file_pipeline(
                    video_path=video_path,
                    session_id=session_id,
                    progress_callback=callback
                )
                active_jobs[job_id]["status"] = "completed"
                active_jobs[job_id]["progress"] = 100.0
                active_jobs[job_id]["session_id"] = session_id
            except Exception as err:
                active_jobs[job_id]["status"] = "error"
                active_jobs[job_id]["error"] = str(err)

        bg_tasks.add_task(_reprocess_bg)
        return {"job_id": job_id, "status": "processing", "session_id": session_id}
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Choose 'ai' or 'full'")


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status and progress of a running processing job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return active_jobs[job_id]


def _run_processing_task(job_id: str, video_path: str, max_duration_sec: Optional[float]):
    def callback(pct: float, msg: str):
        active_jobs[job_id]["progress"] = round(pct, 1)
        active_jobs[job_id]["status_message"] = msg

    try:
        session_data = pipeline.run_file_pipeline(
            video_path=video_path,
            session_id=job_id,
            max_duration_sec=max_duration_sec,
            progress_callback=callback
        )
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["progress"] = 100.0
        active_jobs[job_id]["session_id"] = session_data["session_id"]
    except Exception as e:
        active_jobs[job_id]["status"] = "error"
        active_jobs[job_id]["error"] = str(e)


@app.post("/api/process")
async def start_process(req: ProcessRequest, bg_tasks: BackgroundTasks):
    """Trigger processing of a video file."""
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=400, detail=f"File not found: {req.video_path}")

    job_id = f"audilect_{int(asyncio.get_event_loop().time())}_{os.path.basename(req.video_path)[:8]}"
    active_jobs[job_id] = {
        "job_id": job_id,
        "video_path": req.video_path,
        "status": "processing",
        "progress": 0.0,
        "status_message": "Queued for processing...",
        "error": None
    }

    bg_tasks.add_task(_run_processing_task, job_id, req.video_path, req.max_duration_sec)
    return {"job_id": job_id, "status": "processing"}


@app.post("/api/record/upload")
async def upload_recorded_lecture(
    bg_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form("Recorded Lecture")
):
    """
    Receives screen recording from web cockpit, converts/remuxes to seekable MP4,
    and runs the active cognitive pipeline immediately.
    """
    timestamp_str = int(asyncio.get_event_loop().time())
    orig_ext = Path(file.filename or "recording.webm").suffix.lower() or ".webm"
    temp_in = str(RECORDINGS_DIR / f"raw_rec_{timestamp_str}{orig_ext}")
    final_mp4 = str(RECORDINGS_DIR / f"lecture_rec_{timestamp_str}.mp4")

    # Save uploaded video
    with open(temp_in, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    # Remux/transcode to standard seekable MP4
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", temp_in,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        final_mp4
    ]
    remux_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    target_video = final_mp4 if (remux_res.returncode == 0 and os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 0) else temp_in

    job_id = f"audilect_rec_{timestamp_str}"
    active_jobs[job_id] = {
        "job_id": job_id,
        "video_path": target_video,
        "status": "processing",
        "progress": 0.0,
        "status_message": "Screen recording ingested. Starting pipeline...",
        "error": None
    }

    bg_tasks.add_task(_run_processing_task, job_id, target_video, None)
    return {"job_id": job_id, "status": "processing", "video_path": target_video}


@app.get("/api/video/{session_id}")
async def stream_video(session_id: str, request: Request):
    """Stream video file with range support."""
    meta_file = SESSIONS_DIR / session_id / "session.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    video_path = meta.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video source file not found on disk")

    range_header = request.headers.get("range")
    if range_header:
        return send_range_video(video_path, range_header)
    return FileResponse(video_path, media_type="video/mp4")


@app.get("/api/slides/{session_id}/{path:path}")
async def get_slide_image(session_id: str, path: str):
    """Serve slide keyframes and thumbnails."""
    img_path = SESSIONS_DIR / session_id / "slides" / path
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Slide image not found")
    return FileResponse(img_path, media_type="image/jpeg")


@app.get("/api/export/anki/{session_id}")
async def export_anki(session_id: str):
    """Download Anki flashcards CSV."""
    file_path = SESSIONS_DIR / session_id / "anki_deck.csv"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Anki export not found")
    return FileResponse(
        file_path,
        filename=f"anki_deck_{session_id}.csv",
        media_type="text/csv"
    )


@app.get("/api/export/cornell/{session_id}")
async def export_cornell(session_id: str):
    """Download Cornell Markdown notes."""
    file_path = SESSIONS_DIR / session_id / "cornell_notes.md"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Cornell notes not found")
    return FileResponse(
        file_path,
        filename=f"cornell_notes_{session_id}.md",
        media_type="text/markdown"
    )


@app.get("/api/export/pdf/{session_id}")
async def export_pdf(session_id: str):
    """Download one clear, complete, detailed study guide PDF."""
    session_dir = SESSIONS_DIR / session_id
    meta_file = session_dir / "session.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_path = session_dir / "study_guide.pdf"

    # Regenerate if missing or older than session metadata
    need_generate = True
    if pdf_path.exists():
        if pdf_path.stat().st_mtime >= meta_file.stat().st_mtime:
            need_generate = False

    if need_generate:
        with open(meta_file, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        try:
            from audilect.exporters.pdf_export import generate_pdf_study_guide
            generate_pdf_study_guide(session_data, str(pdf_path))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate study guide PDF: {e}")

    with open(meta_file, "r", encoding="utf-8") as f:
        session_data = json.load(f)
    title = session_data.get("video_title", "Lecture")
    safe_title = re.sub(r'[^a-zA-Z0-9_\- ]+', '', title).strip().replace(' ', '_')
    filename = f"{safe_title}_Study_Guide.pdf" if safe_title else f"Audilect_Study_Guide_{session_id}.pdf"

    return FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf"
    )


@app.post("/api/checkpoint/answer")
async def answer_checkpoint(req: AnswerRequest):
    """Submit student's answer to Socratic checkpoint and return evaluation."""
    meta_file = SESSIONS_DIR / req.session_id / "session.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    with open(meta_file, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    for chk in session_data.get("checkpoints", []):
        if chk["id"] == req.checkpoint_id:
            is_correct = (req.selected_index == chk["correct_index"])
            return {
                "checkpoint_id": req.checkpoint_id,
                "is_correct": is_correct,
                "correct_index": chk["correct_index"],
                "explanation": chk["explanation"],
                "options": chk["options"]
            }

    raise HTTPException(status_code=404, detail="Checkpoint ID not found")


@app.get("/api/config/ai")
async def get_ai_config():
    """Returns current active AI provider, masked key, and model status."""
    return pipeline.ai_engine.get_status_info()


@app.post("/api/config/ai")
async def update_ai_config(req: AIConfigRequest):
    """Updates AI configuration and reloads engine."""
    from audilect.engine.llm import save_ai_config
    update_data = {"provider": req.provider}
    if req.provider == "gemini":
        if req.api_key is not None and req.api_key != "":
            update_data["gemini_api_key"] = req.api_key.strip()
        if req.model_name:
            update_data["gemini_model"] = req.model_name
    elif req.provider == "groq":
        if req.api_key is not None and req.api_key != "":
            update_data["groq_api_key"] = req.api_key.strip()
        if req.model_name:
            update_data["groq_model"] = req.model_name

    save_ai_config(update_data)
    pipeline.ai_engine.reload_config()
    return pipeline.ai_engine.get_status_info()


@app.post("/api/config/ai/test")
async def test_ai_config(req: AITestRequest):
    """Tests connection to chosen AI provider."""
    return pipeline.ai_engine.test_provider_connection(
        provider=req.provider,
        api_key=req.api_key,
        model_name=req.model_name
    )


# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Audilect Cockpit - Index not found</h1>", status_code=404)
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)
