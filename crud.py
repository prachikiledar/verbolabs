from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import Project, MediaFile, SubtitleTrack, SubtitleCue, AudioClip
from subtitle_engine import seconds_to_srt_time, calculate_subtitle_analytics, validate_subtitles


# -------------------------------------------------------------
# Project CRUD
# -------------------------------------------------------------
def create_project(db: Session, title: str, description: Optional[str] = None) -> Project:
    project = Project(title=title, description=description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: int) -> Optional[Project]:
    return db.query(Project).filter(Project.id == project_id).first()


def list_projects(db: Session, skip: int = 0, limit: int = 50) -> List[Project]:
    return db.query(Project).order_by(desc(Project.created_at)).offset(skip).limit(limit).all()


def update_project(db: Session, project: Project, title: Optional[str] = None, description: Optional[str] = None) -> Project:
    if title is not None:
        project.title = title
    if description is not None:
        project.description = description
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    db.delete(project)
    db.commit()


# -------------------------------------------------------------
# MediaFile CRUD
# -------------------------------------------------------------
def create_media_file(
    db: Session,
    filename: str,
    file_path: str,
    file_url: str,
    media_type: str,
    duration: float = 0.0,
    size_mb: float = 0.0,
    project_id: Optional[int] = None,
    parent_media_id: Optional[int] = None,
    mime_type: Optional[str] = None
) -> MediaFile:
    media = MediaFile(
        filename=filename,
        file_path=file_path,
        file_url=file_url,
        media_type=media_type,
        duration=duration,
        size_mb=size_mb,
        project_id=project_id,
        parent_media_id=parent_media_id,
        mime_type=mime_type
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def get_media_file_by_filename(db: Session, filename: str) -> Optional[MediaFile]:
    return db.query(MediaFile).filter(MediaFile.filename == filename).first()


def get_media_file(db: Session, media_id: int) -> Optional[MediaFile]:
    return db.query(MediaFile).filter(MediaFile.id == media_id).first()


def list_media_files(db: Session, skip: int = 0, limit: int = 50, media_type: Optional[str] = None) -> List[MediaFile]:
    query = db.query(MediaFile)
    if media_type:
        query = query.filter(MediaFile.media_type == media_type)
    return query.order_by(desc(MediaFile.created_at)).offset(skip).limit(limit).all()


def delete_media_file(db: Session, media_file: MediaFile) -> None:
    db.delete(media_file)
    db.commit()


# -------------------------------------------------------------
# SubtitleTrack & SubtitleCue CRUD
# -------------------------------------------------------------
def create_subtitle_track(
    db: Session,
    filename: Optional[str],
    cues: List[Dict[str, Any]],
    stats: Optional[Dict[str, Any]] = None,
    raw_content: Optional[str] = None,
    project_id: Optional[int] = None,
    media_file_id: Optional[int] = None,
    language: str = "en",
    format_type: str = "srt"
) -> SubtitleTrack:
    if stats is None:
        stats = calculate_subtitle_analytics(cues)

    track = SubtitleTrack(
        project_id=project_id,
        media_file_id=media_file_id,
        filename=filename,
        language=language,
        format=format_type,
        total_cues=len(cues),
        total_speech_duration=stats.get("total_speech_duration", 0.0),
        total_words=stats.get("total_words", 0),
        total_characters=stats.get("total_characters", 0),
        avg_cps=stats.get("avg_cps", 0.0),
        avg_wpm=stats.get("avg_wpm", 0.0),
        coverage_percent=stats.get("coverage_percent", 0.0),
        raw_content=raw_content
    )
    db.add(track)
    db.flush()  # assign track.id before adding cues

    for idx, raw_cue in enumerate(cues, start=1):
        cue_data = raw_cue if isinstance(raw_cue, dict) else (raw_cue.model_dump() if hasattr(raw_cue, "model_dump") else raw_cue.__dict__)
        start = float(cue_data.get("start", 0.0) or 0.0)
        end = float(cue_data.get("end", 0.0) or 0.0)
        dur = cue_data.get("duration")
        duration = float(dur) if dur is not None and float(dur) > 0 else max(0.0, round(end - start, 2))
        text = str(cue_data.get("text", "") or "")
        char_val = cue_data.get("char_count")
        char_count = int(char_val) if char_val is not None and char_val > 0 else len(text)
        word_val = cue_data.get("word_count")
        words = int(word_val) if word_val is not None and word_val > 0 else len(text.split())
        cps_val = cue_data.get("cps")
        cps = float(cps_val) if cps_val is not None else (round(char_count / duration, 1) if duration > 0 else 0.0)
        start_fmt = cue_data.get("start_formatted") or seconds_to_srt_time(start)
        end_fmt = cue_data.get("end_formatted") or seconds_to_srt_time(end)

        cue = SubtitleCue(
            subtitle_id=track.id,
            cue_index=idx,
            start_time=start,
            end_time=end,
            duration=duration,
            text=text,
            start_formatted=start_fmt,
            end_formatted=end_fmt,
            char_count=char_count,
            word_count=words,
            cps=cps
        )
        db.add(cue)

    db.commit()
    db.refresh(track)
    return track


def get_subtitle_track(db: Session, track_id: int) -> Optional[SubtitleTrack]:
    return db.query(SubtitleTrack).filter(SubtitleTrack.id == track_id).first()


def list_subtitle_tracks(db: Session, skip: int = 0, limit: int = 50, project_id: Optional[int] = None) -> List[SubtitleTrack]:
    query = db.query(SubtitleTrack)
    if project_id is not None:
        query = query.filter(SubtitleTrack.project_id == project_id)
    return query.order_by(desc(SubtitleTrack.created_at)).offset(skip).limit(limit).all()


def update_subtitle_track(
    db: Session,
    track: SubtitleTrack,
    filename: Optional[Any] = None,
    language: Optional[str] = None,
    format_type: Optional[str] = None
) -> SubtitleTrack:
    if hasattr(filename, "filename"):
        if filename.filename is not None:
            track.filename = str(filename.filename)
        if hasattr(filename, "language") and filename.language is not None:
            track.language = str(filename.language)
        if hasattr(filename, "format") and filename.format is not None:
            track.format = str(filename.format)
    elif filename is not None:
        track.filename = str(filename)
    if language is not None:
        track.language = str(language)
    if format_type is not None:
        track.format = str(format_type)
    track.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(track)
    return track


def delete_subtitle_track(db: Session, track: SubtitleTrack) -> None:
    db.delete(track)
    db.commit()


def sync_track_cues(
    db: Session,
    track: SubtitleTrack,
    cues_data: List[Dict[str, Any]],
    video_duration: float = 0.0,
    raw_content: Optional[str] = None
) -> SubtitleTrack:
    """
    Replaces existing cues with the updated cue list in an atomic transaction,
    recalculating track analytics.
    """
    # Delete existing cues
    db.query(SubtitleCue).filter(SubtitleCue.subtitle_id == track.id).delete()

    stats = calculate_subtitle_analytics(cues_data, video_duration)

    for idx, raw_item in enumerate(cues_data, start=1):
        cue_item = raw_item if isinstance(raw_item, dict) else (raw_item.model_dump() if hasattr(raw_item, "model_dump") else raw_item.__dict__)
        start = float(cue_item.get("start", 0.0) or 0.0)
        end = float(cue_item.get("end", 0.0) or 0.0)
        dur = cue_item.get("duration")
        duration = float(dur) if dur is not None and float(dur) > 0 else max(0.0, round(end - start, 2))
        text = str(cue_item.get("text", "") or "")
        char_val = cue_item.get("char_count")
        char_count = int(char_val) if char_val is not None and char_val > 0 else len(text)
        word_val = cue_item.get("word_count")
        words = int(word_val) if word_val is not None and word_val > 0 else len(text.split())
        cps_val = cue_item.get("cps")
        cps = float(cps_val) if cps_val is not None else (round(char_count / duration, 1) if duration > 0 else 0.0)
        start_fmt = cue_item.get("start_formatted") or seconds_to_srt_time(start)
        end_fmt = cue_item.get("end_formatted") or seconds_to_srt_time(end)

        cue = SubtitleCue(
            subtitle_id=track.id,
            cue_index=idx,
            start_time=start,
            end_time=end,
            duration=duration,
            text=text,
            start_formatted=start_fmt,
            end_formatted=end_fmt,
            char_count=char_count,
            word_count=words,
            cps=cps
        )
        db.add(cue)

    track.total_cues = len(cues_data)
    track.total_speech_duration = stats.get("total_speech_duration", 0.0)
    track.total_words = stats.get("total_words", 0)
    track.total_characters = stats.get("total_characters", 0)
    track.avg_cps = stats.get("avg_cps", 0.0)
    track.avg_wpm = stats.get("avg_wpm", 0.0)
    track.coverage_percent = stats.get("coverage_percent", 0.0)
    if raw_content is not None:
        track.raw_content = raw_content
    track.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(track)
    return track


def add_cue_to_track(
    db: Session,
    track: SubtitleTrack,
    start: float,
    end: float,
    text: str,
    video_duration: float = 0.0
) -> SubtitleCue:
    max_idx = db.query(SubtitleCue).filter(SubtitleCue.subtitle_id == track.id).count()
    duration = max(0.1, round(end - start, 2))
    char_count = len(text)
    word_count = len(text.split())
    cps = round(char_count / duration, 1) if duration > 0 else 0.0

    new_cue = SubtitleCue(
        subtitle_id=track.id,
        cue_index=max_idx + 1,
        start_time=start,
        end_time=end,
        duration=duration,
        text=text,
        start_formatted=seconds_to_srt_time(start),
        end_formatted=seconds_to_srt_time(end),
        char_count=char_count,
        word_count=word_count,
        cps=cps
    )
    db.add(new_cue)
    db.commit()
    db.refresh(new_cue)

    # Re-calculate track analytics
    all_cues = cues_to_dict_list(track.cues)
    stats = calculate_subtitle_analytics(all_cues, video_duration)
    track.total_cues = len(all_cues)
    track.total_speech_duration = stats.get("total_speech_duration", 0.0)
    track.total_words = stats.get("total_words", 0)
    track.total_characters = stats.get("total_characters", 0)
    track.avg_cps = stats.get("avg_cps", 0.0)
    track.avg_wpm = stats.get("avg_wpm", 0.0)
    track.coverage_percent = stats.get("coverage_percent", 0.0)
    track.updated_at = datetime.utcnow()
    db.commit()

    return new_cue


def update_cue(
    db: Session,
    cue: SubtitleCue,
    start: Optional[float] = None,
    end: Optional[float] = None,
    text: Optional[str] = None
) -> SubtitleCue:
    if start is not None:
        cue.start_time = max(0.0, round(start, 3))
        cue.start_formatted = seconds_to_srt_time(cue.start_time)
    if end is not None:
        cue.end_time = max(cue.start_time + 0.1, round(end, 3))
        cue.end_formatted = seconds_to_srt_time(cue.end_time)
    if text is not None:
        cue.text = text
        cue.char_count = len(text)
        cue.word_count = len(text.split())

    cue.duration = max(0.1, round(cue.end_time - cue.start_time, 2))
    cue.cps = round(cue.char_count / cue.duration, 1) if cue.duration > 0 else 0.0
    cue.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(cue)
    return cue


def delete_cue(db: Session, cue: SubtitleCue) -> None:
    subtitle_id = cue.subtitle_id
    db.delete(cue)
    db.commit()

    # Renumber remaining cues
    remaining = db.query(SubtitleCue).filter(
        SubtitleCue.subtitle_id == subtitle_id
    ).order_by(SubtitleCue.start_time).all()

    for idx, c in enumerate(remaining, start=1):
        c.cue_index = idx
    db.commit()


def cues_to_dict_list(cues: List[SubtitleCue]) -> List[Dict[str, Any]]:
    return [
        {
            "id": cue.cue_index,  # Match frontend expectation of 1-based sequential cue id
            "db_id": cue.id,
            "start": cue.start_time,
            "end": cue.end_time,
            "duration": cue.duration,
            "text": cue.text,
            "start_formatted": cue.start_formatted or seconds_to_srt_time(cue.start_time),
            "end_formatted": cue.end_formatted or seconds_to_srt_time(cue.end_time),
            "char_count": cue.char_count,
            "word_count": cue.word_count,
            "cps": cue.cps
        }
        for cue in cues
    ]


# -------------------------------------------------------------
# AudioClip CRUD
# -------------------------------------------------------------
def create_audio_clip(
    db: Session,
    source_filename: str,
    clip_filename: str,
    clip_path: str,
    clip_url: str,
    start_time: float,
    end_time: float,
    duration: float,
    cue_id: Optional[int] = None
) -> AudioClip:
    clip = AudioClip(
        source_filename=source_filename,
        clip_filename=clip_filename,
        clip_path=clip_path,
        clip_url=clip_url,
        start_time=start_time,
        end_time=end_time,
        duration=duration,
        cue_id=cue_id
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def list_audio_clips(db: Session, skip: int = 0, limit: int = 50) -> List[AudioClip]:
    return db.query(AudioClip).order_by(desc(AudioClip.created_at)).offset(skip).limit(limit).all()


def get_audio_clip(db: Session, clip_id: int) -> Optional[AudioClip]:
    return db.query(AudioClip).filter(AudioClip.id == clip_id).first()


def delete_audio_clip(db: Session, clip: AudioClip) -> None:
    db.delete(clip)
    db.commit()
