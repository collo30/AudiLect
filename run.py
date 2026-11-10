import argparse
import uvicorn
import os
import sys

# Ensure current directory is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Audilect: Local-First Active Learning Copilot")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
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
