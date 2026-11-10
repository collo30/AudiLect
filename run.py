import argparse
import uvicorn
import os
import sys

# Ensure current directory is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    default_host = "0.0.0.0" if os.environ.get("SPACE_ID") else "127.0.0.1"
    default_port = int(os.environ.get("PORT", 7860 if os.environ.get("SPACE_ID") else 8000))

    parser = argparse.ArgumentParser(description="Audilect: Local-First Active Learning Copilot")
    parser.add_argument("--host", default=default_host, help=f"Host interface (default {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to listen on (default {default_port})")
    parser.add_argument("--process", type=str, default=None, help="Process a lecture video file immediately before launching")
    parser.add_argument("--limit-sec", type=float, default=None, help="Optional duration limit in seconds for processing")

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

    print(f"================================================================")
    print(f"  AUDILECT ACTIVE COGNITIVE COCKPIT")
    print(f"  URL: http://localhost:{args.port}")
    print(f"================================================================")

    uvicorn.run("audilect.server.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
