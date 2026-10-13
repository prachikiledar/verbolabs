import subprocess
import os
from pathlib import Path
import json
import imageio_ffmpeg

FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()

def extract_audio(
    video_path: str,
    output_audio_path: str = None,
    output_format: str = "mp3",
    bitrate: str = "192k",
    sample_rate: int = 44100
) -> dict:
    """
    Extracts audio from video using imageio-ffmpeg bundled binary.
    Supports mp3, wav, aac.
    """
    video_p = Path(video_path)
    if not video_p.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_audio_path is None:
        output_audio_path = str(video_p.parent / f"{video_p.stem}_extracted.{output_format}")

    output_p = Path(output_audio_path)
    output_p.parent.mkdir(parents=True, exist_ok=True)

    # Build ffmpeg command
    cmd = [
        FFMPEG_BIN,
        "-y",               # Overwrite existing
        "-i", str(video_p), # Input video
        "-vn",              # Disable video recording
    ]

    if output_format.lower() == "mp3":
        cmd.extend(["-acodec", "libmp3lame", "-b:a", bitrate, "-ar", str(sample_rate)])
    elif output_format.lower() == "wav":
        cmd.extend(["-acodec", "pcm_s16le", "-ar", str(sample_rate)])
    elif output_format.lower() == "aac":
        cmd.extend(["-acodec", "aac", "-b:a", bitrate, "-ar", str(sample_rate)])
    else:
        cmd.extend(["-b:a", bitrate])

    cmd.append(str(output_p))

    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {process.stderr}")

    duration = get_media_duration(output_p)
    file_size_mb = round(output_p.stat().st_size / (1024 * 1024), 2)

    return {
        "audio_path": str(output_p),
        "filename": output_p.name,
        "format": output_format,
        "duration": duration,
        "size_mb": file_size_mb,
        "status": "success"
    }

def clip_audio(
    source_audio_path: str,
    start_sec: float,
    end_sec: float,
    output_clip_path: str = None
) -> dict:
    """
    Clips a section of audio between start_sec and end_sec.
    """
    src_p = Path(source_audio_path)
    if not src_p.exists():
        raise FileNotFoundError(f"Audio file not found: {source_audio_path}")

    duration = max(0.1, end_sec - start_sec)
    if output_clip_path is None:
        output_clip_path = str(src_p.parent / f"{src_p.stem}_clip_{start_sec:.2f}_{end_sec:.2f}.mp3")

    out_p = Path(output_clip_path)

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(max(0, start_sec)),
        "-t", str(duration),
        "-i", str(src_p),
        "-acodec", "libmp3lame",
        "-b:a", "192k",
        str(out_p)
    ]

    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg audio clip failed: {process.stderr}")

    return {
        "clip_path": str(out_p),
        "filename": out_p.name,
        "duration": duration,
        "start": start_sec,
        "end": end_sec
    }

def get_media_duration(media_path: Path) -> float:
    """
    Probes media duration using ffmpeg output.
    """
    cmd = [FFMPEG_BIN, "-i", str(media_path)]
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # FFmpeg writes info to stderr
    for line in process.stderr.splitlines():
        if "Duration:" in line:
            parts = line.split("Duration:")[1].split(",")[0].strip()
            # Format: 00:00:08.00
            try:
                h, m, s = parts.split(":")
                return round(float(h) * 3600 + float(m) * 60 + float(s), 2)
            except Exception:
                pass
    return 0.0
