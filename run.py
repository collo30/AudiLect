import argparse
import uvicorn
import os
import sys
import time
import socket
import urllib.request
import threading
import subprocess
import webbrowser
import multiprocessing
import ctypes

# 1. Set explicit Windows App User Model ID so taskbar groups & displays icon properly
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Audilect.Cockpit.ActiveLearning.1.0")
except Exception:
    pass

# 2. Handle Windows GUI mode (when sys.stdout/sys.stderr are None under --noconsole)
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

# 3. Ensure current directory is on PYTHONPATH & working dir is correct
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(exe_dir)
    sys.path.insert(0, exe_dir)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def is_audilect_running(port: int) -> bool:
    """Checks if an AudiLect instance is already active and serving on the specified port."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/sessions", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def find_available_port(start_port: int = 8000) -> int:
    """Finds first available TCP port on localhost starting from start_port."""
    port = start_port
    while port < start_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port


def launch_native_window(url: str, server_ref=None):
    """
    Waits for the AudiLect server to be fully ready, then launches AudiLect
    in dedicated native app window mode using Microsoft Edge or Chrome.
    Monitors the window process and cleanly stops the server when the user closes the window.
    """
    # Wait until the backend server is responding with HTTP 200 (max 25s)
    start = time.time()
    while time.time() - start < 25.0:
        try:
            req = urllib.request.Request(f"{url}/api/sessions", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
        time.sleep(0.35)

    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    profile_dir = os.path.join(appdata, "AudiLect", "profile")
    os.makedirs(profile_dir, exist_ok=True)

    candidates = [
        # Microsoft Edge (standard on modern Windows)
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
                cmd = [
                    browser_exe,
                    f"--app={url}",
                    f"--user-data-dir={profile_dir}",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
                proc = subprocess.Popen(cmd)
                # Wait for user to close window to trigger clean server shutdown
                proc.wait()
                if server_ref is not None:
                    server_ref.should_exit = True
                return
            except Exception:
                pass

    # Fallback to standard default browser
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

    # 1. Check if AudiLect is already running on the requested port
    if is_audilect_running(args.port):
        print(f"[*] AudiLect is already running on port {args.port}. Bringing up cockpit...")
        if not args.no_browser:
            launch_native_window(f"http://127.0.0.1:{args.port}")
        return

    # 2. If port is occupied by another process, find next available port
    target_port = args.port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if s.connect_ex(("127.0.0.1", target_port)) == 0:
            target_port = find_available_port(target_port + 1)
            print(f"[*] Port {args.port} was busy. Switched to port {target_port}.")

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
    print(f"  URL: http://localhost:{target_port}")
    print("================================================================")

    from audilect.server.app import app
    config = uvicorn.Config(app, host=args.host, port=target_port, log_level="info")
    server = uvicorn.Server(config)

    url = f"http://127.0.0.1:{target_port}"
    if not args.no_browser:
        threading.Thread(target=launch_native_window, args=(url, server), daemon=True).start()

    server.run()


if __name__ == "__main__":
    main()
