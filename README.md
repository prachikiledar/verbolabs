# Subtitle Studio 🎬

A modern, high-performance Python application designed to work on **subtitles** with automatic **video audio extraction**.

---

## 🌟 Key Features

1. **Automatic Audio Extraction**:
   - Upload any video (`.mp4`, `.mov`, `.webm`, `.mkv`, etc.).
   - Automatically extracts a high-quality audio track (`.mp3` @ 192kbps, 44.1kHz) using bundled FFmpeg.
   - Listen to the extracted audio track directly with live waveform visualization, or download it with 1 click.

2. **Manual Subtitle Workspace ("Subtitles Only")**:
   - **Upload Subtitles**: Drag-and-drop your manual `.srt`, `.vtt`, or `.txt` subtitle files.
   - **Paste / Type Subtitles**: Type or paste raw subtitle text in the built-in editor.
   - **Synchronized Video & Subtitles**: Play the video with Netflix-style on-screen caption overlays.
   - **Interactive Cue Tracker**: As video/audio plays, the active subtitle cue card glows cyan and auto-scrolls into view.
   - **Click to Seek**: Click any subtitle cue card to instantly jump the video/audio to that exact timestamp.

3. **Subtitle Editing & Tools**:
   - **Inline Text & Timestamp Editing**: Modify dialogue, start/end timestamps, and duration on the fly.
   - **Time-Shift Alignment**: One-click alignment buttons (`-1.0s`, `-0.5s`, `+0.5s`, `+1.0s`, custom) to sync subtitles with audio perfectly.
   - **Quality & Pace Health Checker**: Flags overlapping timestamps and fast reading speeds (> 20 characters per second).
   - **Audio Snippet Clipper**: Export and download an isolated audio clip for any individual subtitle cue!
   - **Add New Cue at Playhead**: Instantly insert a new dialogue line at the current video position.
   - **Export Anywhere**: Download updated subtitles in SubRip (`.SRT`), WebVTT (`.VTT`), Plain Text (`.TXT`), or JSON (`.JSON`).

---

## 🚀 How to Run

From this directory:

```bash
# 1. Activate the virtual environment
source venv/bin/activate

# 2. Launch the application
python app.py
# or: uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Then open your browser at:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Quick Test

Click the **"Load Demo Video & Subtitles"** button in the top navigation bar to test the full video playback, audio waveform, and synchronized subtitles immediately!
