import argparse
import uvicorn
import os
import sys
import time
import threading
import subprocess
import webbrowser
import multiprocessing

# 1. Handle Windows GUI mode (when sys.stdout/sys.stderr are None under --noconsole)
if sys.stdout is None:
    try:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        log_dir = os.path.join(appdata, "AudiLect", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = open(os.path.join(log_dir, "audilect.log"), "a", encoding="utf-8")
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

# 2. Ensure current directory is on PYTHONPATH & working dir is correct
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(exe_dir)
    sys.path.insert(0, exe_dir)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def launch_native_window(url: str):
    """
    Launches AudiLect in dedicated native app window mode (borderless, no URL/tab bar)
    using Microsoft Edge or Chrome, with fallback to standard default browser.
    """
    time.sleep(1.2)

    candidates = [
        # Microsoft Edge (present on all modern Windows installations)
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        # Google Chrome
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]

    for browser_exe in candidates:
        if os.path.isfile(browser_exe):
            try:
                subprocess.Popen([browser_exe, f"--app={url}"])
                return
            except Exception:
                pass

    # Fallback to default browser
    try:
        webbrowser.open_new_tab(url)
    except Exception:
        pass


def install_windows_shortcuts():
    """Installs Windows shortcuts on Desktop and Start Menu for instant access."""
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        work_dir = os.path.dirname(exe_path)
    else:
        exe_path = os.path.abspath(__file__)
        work_dir = os.path.dirname(exe_path)

    icon_path = os.path.join(work_dir, "icon.ico")
    if not os.path.isfile(icon_path):
        icon_path = exe_path

    ps_script = f"""
    $ws = New-Object -ComObject WScript.Shell
    
    # Desktop
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    $deskLnk = Join-Path $desktopPath 'AudiLect.lnk'
    $s1 = $ws.CreateShortcut($deskLnk)
    $s1.TargetPath = '{exe_path}'
    $s1.WorkingDirectory = '{work_dir}'
    $s1.IconLocation = '{icon_path},0'
    $s1.Description = 'AudiLect - Active Cognitive Lecture Copilot'
    $s1.Save()

    # Start Menu Programs
    $progPath = [Environment]::GetFolderPath('Programs')
    $startLnk = Join-Path $progPath 'AudiLect.lnk'
    $s2 = $ws.CreateShortcut($startLnk)
    $s2.TargetPath = '{exe_path}'
    $s2.WorkingDirectory = '{work_dir}'
    $s2.IconLocation = '{icon_path},0'
    $s2.Description = 'AudiLect - Active Cognitive Lecture Copilot'
    $s2.Save()
    """
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
        print("[+] Windows shortcuts installed successfully to Desktop and Start Menu!")
    except Exception as e:
        print(f"[!] Failed to install shortcuts: {e}")


def main():
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="Audilect: Local-First Active Learning Copilot")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    parser.add_argument("--process", type=str, default=None, help="Process a lecture video file immediately before launching")
    parser.add_argument("--limit-sec", type=float, default=None, help="Optional duration limit in seconds for processing")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open default web browser")
    parser.add_argument("--install-shortcuts", action="store_true", help="Install Windows Desktop and Start Menu shortcuts")

    args = parser.parse_args()

    if args.install_shortcuts:
        install_windows_shortcuts()
        return

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

    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Thread(target=launch_native_window, args=(url,), daemon=True).start()

    from audilect.server.app import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
