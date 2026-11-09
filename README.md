# Audilect

> **Open-source, local-first active learning assistant for lectures.**  
> Transforms dense lecture videos (Zoom, Google Meet, YouTube, MP4/MKV) into an interactive study cockpit with synchronized slides, active recall checkpoints, conceptual micro-primers, and publication-grade PDF study guides.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Local First](https://img.shields.io/badge/Local--First-100%25%20Private-emerald.svg)](#privacy--local-first-guarantee)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com)

---

## Overview

Traditional lecture summaries often produce passive walls of text that students skim without retaining. **Audilect** is built on cognitive science principles—active recall, spaced testing, and visual anchoring:

- **Local Video & Audio Pipeline**: Extracts audio and detects slide/board transitions locally with zero cloud upload delays.
- **Word-Level Timeline Synchronization**: Read along with the spoken lecture text synced down to the exact word token.
- **Enriched Knowledge Callouts**: Automatically injects outside knowledge blocks (`KEY CONCEPT`, `COMMON MISCONCEPTION`, `PRACTICAL APPLICATION`) into the timeline.
- **Socratic Active Recall**: Generates interactive multiple-choice checkpoints that prompt students at critical moments with explanatory feedback.
- **Publication-Grade PDF Study Guide**: One-click generation of a multi-page, formatted PDF with topic roadmaps, concept glossaries, annotated transcripts, and answer keys.
- **Deterministic Study Artifacts**: Exports directly to **Anki Flashcards** (`.csv` with Cloze deletions) and **Cornell Notes** (`.md`).

---

## Key Capabilities

### 1. Dual Ingest Engine
* **Recorded Video Mode** (`.mp4`, `.mkv`, `.mov`, `.webm`): Instant audio demuxing and 16kHz mono conversion via bundled `imageio-ffmpeg`.
* **Live Tab & Screen Capture**: Stream live online classes directly from browser tabs (Zoom, Google Meet, YouTube) using the browser Screen Capture API.

### 2. Slide Detection (Perceptual Hashing)
* Analyzes video keyframes using perceptual hashing (`imagehash.phash`) with Hamming distance thresholds.
* Detects visual shifts (slide transitions, board erasures, diagram additions) and bookmarks high-resolution thumbnails mapped to the timeline.

### 3. High-Accuracy Speech Recognition
* Powered by `faster-whisper` (CTranslate2 INT8 quantized), providing fast, local speech-to-text with word-level timestamps and Voice Activity Detection (VAD).

### 4. Robust AI Intelligence (Gemini & Groq)
* **Bring Your Own Key**: Free tier Google Gemini (`gemini-3.5-flash-lite`, `gemini-3.5-flash`) or Groq (`llama-3.3-70b-versatile`).
* **Multi-Model Dynamic Failover**: Automatically cascades across model endpoints upon encountering HTTP 429 (rate limit) or HTTP 503 (service overload) without pipeline stalls.
* **Offline NLU Fallback**: Gracefully degrades to local heuristic synthesis if no API key is provided or when offline.

---

## Quick Start

### Prerequisites
* Python 3.9 or higher
* FFmpeg (automatically handled via `imageio-ffmpeg`)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/audilect.git
cd audilect

# 2. Install dependencies
pip install -r requirements.txt
```

### Running the Web Cockpit

**Windows**:
Double-click `start_windows.bat`, or run:
```bash
python run.py --port 8000
```

**macOS / Linux**:
```bash
chmod +x start_linux.sh
./start_linux.sh
```

Open **`http://localhost:8000`** in your browser.

---

## CLI Processing

You can also process a video directly from your terminal:

```bash
# Process a video directly via CLI
python run.py --process "path/to/lecture.mp4"
```

---

## UI Architecture & Themes

Audilect features a clean, layered design system with:
- **Clean Editorial Light Mode** (Default) for long reading comfort.
- **Obsidian / Zinc Dark Mode** with seamless contrast switching.
- **Vector SVG Iconography** (Lucide specification) across all buttons, controls, and navigation items.
- **Word-Level Timeline Interaction**: Click any word in the transcript to jump playback to that exact second.

---

## Privacy & Local-First Guarantee

- **Your videos and audio never leave your computer.**
- All transcription and slide image hashing are executed strictly on your local hardware.
- Cloud AI calls only send text transcript chunks to your configured API provider (Gemini or Groq) using your own private API key.
- API keys are stored locally in `data/config.json` and are strictly ignored by `.gitignore`.

---

## Contributing

Contributions, bug reports, and pull requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
