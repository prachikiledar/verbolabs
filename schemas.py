from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# Existing schemas from app.py
class CueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start: float
    end: float
    duration: float
    text: str
    start_formatted: Optional[str] = None
    end_formatted: Optional[str] = None
    char_count: Optional[int] = 0
    word_count: Optional[int] = 0
    cps: Optional[float] = 0.0


class ShiftRequest(BaseModel):
    cues: List[CueItem]
    delta: float
    video_duration: Optional[float] = 0.0
    subtitle_id: Optional[int] = None


class ExportRequest(BaseModel):
    cues: List[CueItem]
    format: str = "srt"


class ClipAudioRequest(BaseModel):
    audio_filename: str
    start: float
    end: float
    cue_id: Optional[int] = None


class RawSubtitleRequest(BaseModel):
    text: str
    video_duration: Optional[float] = 0.0
    project_id: Optional[int] = None


# Extended CRUD Schemas
class ProjectBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class MediaFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int] = None
    media_type: str
    filename: str
    file_path: str
    file_url: str
    mime_type: Optional[str] = None
    duration: float
    size_mb: float
    parent_media_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SubtitleTrackSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int] = None
    media_file_id: Optional[int] = None
    filename: Optional[str] = None
    language: str
    format: str
    total_cues: int
    total_speech_duration: float
    total_words: int
    total_characters: int
    avg_cps: float
    avg_wpm: float
    coverage_percent: float
    created_at: datetime
    updated_at: datetime


class SubtitleTrackResponse(SubtitleTrackSummary):
    cues: List[CueItem] = []


class SubtitleTrackUpdate(BaseModel):
    filename: Optional[str] = None
    language: Optional[str] = None
    format: Optional[str] = None


class CueCreate(BaseModel):
    start: float
    end: float
    text: str


class CueUpdate(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    text: Optional[str] = None


class BatchCuesSaveRequest(BaseModel):
    cues: List[CueItem]
    video_duration: Optional[float] = 0.0


class AudioClipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cue_id: Optional[int] = None
    source_filename: str
    clip_filename: str
    clip_path: str
    clip_url: str
    start_time: float
    end_time: float
    duration: float
    created_at: datetime


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    media_files: List[MediaFileResponse] = []
    subtitle_tracks: List[SubtitleTrackSummary] = []
