import re
from typing import List, Dict, Any, Tuple

def parse_time_to_seconds(time_str: str) -> float:
    """
    Parses timestamp string into seconds.
    Supports formats:
    - 00:01:23,456 (SRT)
    - 00:01:23.456 (VTT)
    - 01:23.456 (Short VTT)
    - 01:23,456
    """
    time_str = time_str.strip().replace(",", ".")
    parts = time_str.split(":")
    if len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return round(hours * 3600 + minutes * 60 + seconds, 3)
    elif len(parts) == 2:
        minutes = float(parts[0])
        seconds = float(parts[1])
        return round(minutes * 60 + seconds, 3)
    elif len(parts) == 1:
        return round(float(parts[0]), 3)
    return 0.0

def seconds_to_srt_time(seconds: float) -> str:
    """Format seconds into SRT timecode: HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def seconds_to_vtt_time(seconds: float) -> str:
    """Format seconds into WebVTT timecode: HH:MM:SS.mmm"""
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def parse_subtitles_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    Robust subtitle parser supporting SRT, WebVTT, and simple timestamped text formats.
    """
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    
    # Remove WEBVTT header if present
    if text.startswith("WEBVTT"):
        lines = text.split("\n")
        # Skip header lines until empty line
        idx = 0
        while idx < len(lines) and lines[idx].strip() != "":
            idx += 1
        text = "\n".join(lines[idx:]).strip()

    # Split into blocks by double newlines or cue delimiters
    blocks = re.split(r'\n\s*\n', text)
    cues = []
    cue_id = 1

    # Regex for timestamp line: 00:00:01,000 --> 00:00:04,000 or 00:01.000 --> 00:04.000
    timestamp_pattern = re.compile(
        r'((?:\d{1,2}:)?\d{1,2}:\d{2}[,\.]\d{1,3})\s*-->\s*((?:\d{1,2}:)?\d{1,2}:\d{2}[,\.]\d{1,3})'
    )

    for block in blocks:
        block_lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not block_lines:
            continue

        start_time = None
        end_time = None
        content_lines = []

        for line in block_lines:
            match = timestamp_pattern.search(line)
            if match:
                start_time = parse_time_to_seconds(match.group(1))
                end_time = parse_time_to_seconds(match.group(2))
            elif start_time is not None:
                # Any lines after timestamp are subtitle content
                content_lines.append(line)
            elif not line.isdigit():
                # Line before timestamp (unless it's an integer cue number)
                # Keep in case text is unconventional
                pass

        if start_time is not None and end_time is not None:
            cue_text = " ".join(content_lines).strip()
            duration = max(0.1, round(end_time - start_time, 2))
            clean_text = re.sub(r'<[^>]+>', '', cue_text) # strip HTML tags
            char_count = len(clean_text)
            words = len(clean_text.split()) if clean_text else 0
            cps = round(char_count / duration, 1) if duration > 0 else 0.0

            cues.append({
                "id": cue_id,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "duration": duration,
                "text": cue_text,
                "start_formatted": seconds_to_srt_time(start_time),
                "end_formatted": seconds_to_srt_time(end_time),
                "char_count": char_count,
                "word_count": words,
                "cps": cps
            })
            cue_id += 1

    # Fallback: If no standard timestamp blocks were found, attempt line-by-line fallback
    if not cues and raw_text.strip():
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
        curr_time = 0.0
        for l in lines:
            duration = 3.0
            cues.append({
                "id": cue_id,
                "start": round(curr_time, 3),
                "end": round(curr_time + duration, 3),
                "duration": duration,
                "text": l,
                "start_formatted": seconds_to_srt_time(curr_time),
                "end_formatted": seconds_to_srt_time(curr_time + duration),
                "char_count": len(l),
                "word_count": len(l.split()),
                "cps": round(len(l) / duration, 1)
            })
            curr_time += duration + 0.5
            cue_id += 1

    return cues

def _get_cue_field(c: Any, key: str, default: Any = None) -> Any:
    if isinstance(c, dict):
        return c.get(key, default)
    return getattr(c, key, default)

def validate_subtitles(cues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Checks for common subtitle quality issues:
    - Overlapping cues
    - Reading pace too high (CPS > 21)
    - Too short (< 0.8s) or too long (> 7.0s)
    - Inverted timestamps (end <= start)
    """
    warnings = []
    for i, cue in enumerate(cues):
        cue_warns = []
        cue_id = _get_cue_field(cue, "id", i + 1)
        start = float(_get_cue_field(cue, "start", 0.0) or 0.0)
        end = float(_get_cue_field(cue, "end", 0.0) or 0.0)
        dur = _get_cue_field(cue, "duration")
        duration = float(dur) if dur is not None and float(dur) > 0 else max(0.0, round(end - start, 2))
        text = str(_get_cue_field(cue, "text", "") or "")
        char_cnt = _get_cue_field(cue, "char_count")
        char_count = int(char_cnt) if char_cnt is not None else len(text)
        cps_val = _get_cue_field(cue, "cps")
        cps = float(cps_val) if cps_val is not None else (round(char_count / duration, 1) if duration > 0 else 0.0)

        if end <= start:
            cue_warns.append("End timestamp is before or equal to start timestamp.")
        if cps > 21:
            cue_warns.append(f"Fast reading pace: {cps} chars/sec (standard is < 20).")
        if duration < 0.6:
            cue_warns.append(f"Very short duration ({duration}s).")
        elif duration > 7.0:
            cue_warns.append(f"Long duration ({duration}s). Consider splitting.")

        # Check overlap with next cue
        if i < len(cues) - 1:
            next_cue = cues[i + 1]
            next_start = float(_get_cue_field(next_cue, "start", 0.0) or 0.0)
            next_id = _get_cue_field(next_cue, "id", i + 2)
            if end > next_start:
                overlap_time = round(end - next_start, 2)
                cue_warns.append(f"Overlaps with next cue #{next_id} by {overlap_time}s.")

        if cue_warns:
            warnings.append({
                "cue_id": cue_id,
                "issues": cue_warns
            })

    return warnings

def calculate_subtitle_analytics(cues: List[Dict[str, Any]], video_duration: float = 0.0) -> Dict[str, Any]:
    """
    Computes analytics on subtitle track. Handles missing word_count, char_count, duration gracefully.
    """
    if not cues:
        return {
            "total_cues": 0,
            "total_speech_duration": 0.0,
            "total_words": 0,
            "total_characters": 0,
            "avg_cps": 0.0,
            "avg_wpm": 0.0,
            "coverage_percent": 0.0
        }

    total_speech = 0.0
    total_words = 0
    total_chars = 0

    for c in cues:
        start = float(_get_cue_field(c, "start", 0.0) or 0.0)
        end = float(_get_cue_field(c, "end", 0.0) or 0.0)
        dur = _get_cue_field(c, "duration")
        duration = float(dur) if dur is not None and float(dur) > 0 else max(0.0, round(end - start, 2))
        text = str(_get_cue_field(c, "text", "") or "")

        words = _get_cue_field(c, "word_count")
        word_count = int(words) if words is not None and words > 0 else len(text.split())

        chars = _get_cue_field(c, "char_count")
        char_count = int(chars) if chars is not None and chars > 0 else len(text)

        total_speech += duration
        total_words += word_count
        total_chars += char_count

    total_speech = round(total_speech, 2)
    avg_cps = round(total_chars / total_speech, 1) if total_speech > 0 else 0.0
    avg_wpm = round((total_words / (total_speech / 60)), 1) if total_speech > 0 else 0.0
    coverage = round((total_speech / video_duration) * 100, 1) if video_duration > 0 else 0.0

    return {
        "total_cues": len(cues),
        "total_speech_duration": total_speech,
        "total_words": total_words,
        "total_characters": total_chars,
        "avg_cps": avg_cps,
        "avg_wpm": avg_wpm,
        "coverage_percent": min(100.0, coverage)
    }

def shift_cues(cues: List[Dict[str, Any]], delta_seconds: float) -> List[Dict[str, Any]]:
    """
    Shifts all cues by delta_seconds.
    """
    shifted = []
    for cue in cues:
        start = float(_get_cue_field(cue, "start", 0.0) or 0.0)
        end = float(_get_cue_field(cue, "end", 0.0) or 0.0)
        text = str(_get_cue_field(cue, "text", "") or "")
        char_cnt = _get_cue_field(cue, "char_count")
        char_count = int(char_cnt) if char_cnt is not None else len(text)
        word_cnt = _get_cue_field(cue, "word_count")
        word_count = int(word_cnt) if word_cnt is not None else len(text.split())

        new_start = max(0.0, round(start + delta_seconds, 3))
        new_end = max(new_start + 0.1, round(end + delta_seconds, 3))
        duration = round(new_end - new_start, 2)
        cps = round(char_count / duration, 1) if duration > 0 else 0.0

        base_dict = dict(cue) if isinstance(cue, dict) else (cue.model_dump() if hasattr(cue, "model_dump") else cue.__dict__.copy())
        base_dict.update({
            "start": new_start,
            "end": new_end,
            "duration": duration,
            "start_formatted": seconds_to_srt_time(new_start),
            "end_formatted": seconds_to_srt_time(new_end),
            "char_count": char_count,
            "word_count": word_count,
            "cps": cps
        })
        shifted.append(base_dict)
    return shifted

def export_to_format(cues: List[Dict[str, Any]], format_type: str = "srt") -> Tuple[str, str, str]:
    """
    Exports cues into formatted string, filename extension, and mime-type.
    """
    format_type = format_type.lower()

    if format_type == "srt":
        output = []
        for i, cue in enumerate(cues, 1):
            start = float(_get_cue_field(cue, "start", 0.0) or 0.0)
            end = float(_get_cue_field(cue, "end", 0.0) or 0.0)
            text = str(_get_cue_field(cue, "text", "") or "")
            s_time = seconds_to_srt_time(start)
            e_time = seconds_to_srt_time(end)
            output.append(f"{i}\n{s_time} --> {e_time}\n{text}\n")
        return "\n".join(output), "subtitles.srt", "application/x-subrip"

    elif format_type == "vtt":
        output = ["WEBVTT\n"]
        for i, cue in enumerate(cues, 1):
            start = float(_get_cue_field(cue, "start", 0.0) or 0.0)
            end = float(_get_cue_field(cue, "end", 0.0) or 0.0)
            text = str(_get_cue_field(cue, "text", "") or "")
            s_time = seconds_to_vtt_time(start)
            e_time = seconds_to_vtt_time(end)
            output.append(f"{i}\n{s_time} --> {e_time}\n{text}\n")
        return "\n".join(output), "subtitles.vtt", "text/vtt"

    elif format_type == "txt":
        output = []
        for cue in cues:
            start = float(_get_cue_field(cue, "start", 0.0) or 0.0)
            text = str(_get_cue_field(cue, "text", "") or "")
            s_time = seconds_to_srt_time(start)
            output.append(f"[{s_time}] {text}")
        return "\n".join(output), "subtitles.txt", "text/plain"

    elif format_type == "json":
        import json
        cues_serializable = [
            c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.__dict__)
            for c in cues
        ]
        return json.dumps(cues_serializable, indent=2), "subtitles.json", "application/json"

    else:
        raise ValueError(f"Unsupported format: {format_type}")

