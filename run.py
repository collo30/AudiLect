import argparse
import uvicorn
import os
import sys
import time
import threading
import webbrowser
import multiprocessing

# Ensure current directory is on PYTHONPATH
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(exe_dir)
    sys.path.insert(0, exe_dir)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="Audilect: Local-First Active Learning Copilot")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    parser.add_argument("--process", type=str, default=None, help="Process a lecture video file immediately before launching")
    parser.add_argument("--limit-sec", type=float, default=None, help="Optional duration limit in seconds for processing")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open default web browser")

    args = parser.parse_args()

    if args.process:
        print(f"[*] Pre-processing lecture video: {args.process}")
        from audilect.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline()
        def callback(pct, msg):
            print(f"[{pct:5.1f}%] {msg}")
        pipeline.run_file_pipeline(
            video_path=args.process,
            max_duration_sec=args.limit_sec,
            progress_callback=callback
        )
        print("[+] Processing complete. Launching cockpit...")

    print("================================================================")
    print("  AUDILECT ACTIVE COGNITIVE COCKPIT")
    print(f"  URL: http://localhost:{args.port}")
    print("================================================================")

    if not args.no_browser:
        def open_browser():
            time.sleep(1.2)
            try:
                webbrowser.open_new_tab(f"http://127.0.0.1:{args.port}")
            except Exception:
                pass
        threading.Thread(target=open_browser, daemon=True).start()

    from audilect.server.app import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
