"""
Build script to compile AudiLect into a standalone Windows executable.
Usage:
    python build_exe.py
"""

import os
import sys
import shutil
import subprocess
import PyInstaller.__main__
import imageio_ffmpeg

def build():
    print("[*] Starting AudiLect Windows Executable Build...")
    
    # Locate ffmpeg binary
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"[*] Found bundled ffmpeg: {ffmpeg_exe}")

    static_dir = os.path.abspath("audilect/server/static")
    config_example = os.path.abspath("data/config.example.json")

    datas = [
        f"{static_dir};audilect/server/static",
    ]
    if os.path.exists(config_example):
        datas.append(f"{config_example};data")

    # Include ffmpeg binary directory
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    binaries = [
        f"{ffmpeg_exe};imageio_ffmpeg/binaries",
    ]

    hidden_imports = [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespans",
        "uvicorn.lifespans.on",
        "fastapi",
        "pydantic",
        "starlette",
        "reportlab",
        "reportlab.lib",
        "reportlab.platypus",
        "imagehash",
        "PIL",
        "sounddevice",
        "faster_whisper",
        "ctranslate2",
        "imageio_ffmpeg",
    ]

    args = [
        "run.py",
        "--name=AudiLect",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--collect-all=imageio_ffmpeg",
        "--collect-all=faster_whisper",
        "--collect-all=ctranslate2",
    ]

    for d in datas:
        args.extend(["--add-data", d])

    for b in binaries:
        args.extend(["--add-binary", b])

    for hi in hidden_imports:
        args.extend(["--hidden-import", hi])

    print("[*] Running PyInstaller with arguments:")
    print(" ".join(args))

    PyInstaller.__main__.run(args)
    print("\n[+] Build finished successfully!")
    print("[+] Output directory: dist/AudiLect")
    print("[+] Launch executable: dist/AudiLect/AudiLect.exe")

if __name__ == "__main__":
    build()
