from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship

from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False, default="Untitled Project")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    media_files = relationship("MediaFile", back_populates="project", cascade="all, delete-orphan")
    subtitle_tracks = relationship("SubtitleTrack", back_populates="project", cascade="all, delete-orphan")


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    media_type = Column(String(50), nullable=False)  # 'video', 'audio', 'clip'
    filename = Column(String(255), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    file_url = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=True)
    duration = Column(Float, nullable=False, default=0.0)
    size_mb = Column(Float, nullable=False, default=0.0)
    parent_media_id = Column(Integer, ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="media_files")

    __table_args__ = (
        Index("ix_media_files_project_type", "project_id", "media_type"),
    )


class SubtitleTrack(Base):
    __tablename__ = "subtitle_tracks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    media_file_id = Column(Integer, ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True, index=True)
    filename = Column(String(255), nullable=True)
    language = Column(String(50), nullable=False, default="en")
    format = Column(String(20), nullable=False, default="srt")
    total_cues = Column(Integer, nullable=False, default=0)
    total_speech_duration = Column(Float, nullable=False, default=0.0)
    total_words = Column(Integer, nullable=False, default=0)
    total_characters = Column(Integer, nullable=False, default=0)
    avg_cps = Column(Float, nullable=False, default=0.0)
    avg_wpm = Column(Float, nullable=False, default=0.0)
    coverage_percent = Column(Float, nullable=False, default=0.0)
    raw_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="subtitle_tracks")
    cues = relationship("SubtitleCue", back_populates="track", cascade="all, delete-orphan", order_by="SubtitleCue.cue_index")


class SubtitleCue(Base):
    __tablename__ = "subtitle_cues"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subtitle_id = Column(Integer, ForeignKey("subtitle_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    cue_index = Column(Integer, nullable=False, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    start_formatted = Column(String(30), nullable=True)
    end_formatted = Column(String(30), nullable=True)
    char_count = Column(Integer, nullable=False, default=0)
    word_count = Column(Integer, nullable=False, default=0)
    cps = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    track = relationship("SubtitleTrack", back_populates="cues")
    audio_clips = relationship("AudioClip", back_populates="cue")

    __table_args__ = (
        Index("ix_cues_track_index", "subtitle_id", "cue_index"),
        Index("ix_cues_start_time", "subtitle_id", "start_time"),
    )


class AudioClip(Base):
    __tablename__ = "audio_clips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cue_id = Column(Integer, ForeignKey("subtitle_cues.id", ondelete="SET NULL"), nullable=True, index=True)
    source_filename = Column(String(255), nullable=False)
    clip_filename = Column(String(255), nullable=False, index=True)
    clip_path = Column(String(512), nullable=False)
    clip_url = Column(String(512), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    cue = relationship("SubtitleCue", back_populates="audio_clips")
