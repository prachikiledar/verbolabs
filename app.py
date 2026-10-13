import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    Depends,
    Query,
    status
)
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, init_db
import models
import crud
from schemas import (
    CueItem,
    ShiftRequest,
    ExportRequest,
    ClipAudioRequest,
    RawSubtitleRequest,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    SubtitleTrackSummary,
    SubtitleTrackResponse,
    SubtitleTrackUpdate,
    CueCreate,
    CueUpdate,
    BatchCuesSaveRequest,
    AudioClipResponse,
    MediaFileResponse
)
from audio_extractor import extract_audio, clip_audio, get_media_duration
from subtitle_engine import (
    parse_subtitles_text,
    validate_subtitles,
    calculate_subtitle_analytics,
    shift_cues,
    export_to_format,
    seconds_to_srt_time
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
SAMPLE_DIR = BASE_DIR / "sample_data"
STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables on startup
    init_db()
    yield


app = FastAPI(
    title="Subtitle Studio",
    description="Python system for video audio extraction and subtitle workspace with SQLite persistence",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# Streaming Media Endpoint (supporting HTTP Range)
# -------------------------------------------------------------
@app.get("/media/{file_name}")
async def stream_media(file_name: str, request: Request, db: Session = Depends(get_db)):
    """
    Streams media files with HTTP Range header support.
    Verifies against DB registry and falls back to disk folders.
    """
    # 1. Check DB first for registered media file or audio clip
    media_rec = crud.get_media_file_by_filename(db, file_name)
    file_path = None
    if media_rec and Path(media_rec.file_path).exists():
        file_path = Path(media_rec.file_path)
    else:
        clip_rec = db.query(models.AudioClip).filter(models.AudioClip.clip_filename == file_name).first()
        if clip_rec and Path(clip_rec.clip_path).exists():
            file_path = Path(clip_rec.clip_path)

    # 2. Check upload dir, then sample dir as fallback
    if not file_path or not file_path.exists():
        file_path = UPLOAD_DIR / file_name
        if not file_path.exists():
            file_path = SAMPLE_DIR / file_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")

    ext = file_path.suffix.lower()
    content_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".srt": "text/plain",
        ".vtt": "text/vtt"
    }
    content_type = content_types.get(ext, "application/octet-stream")

    if range_header:
        try:
            range_val = range_header.replace("bytes=", "")
            start_str, end_str = range_val.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            if end >= file_size:
                end = file_size - 1
            chunk_length = (end - start) + 1

            with open(file_path, "rb") as f:
                f.seek(start)
                data = f.read(chunk_length)

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_length),
                "Content-Type": content_type,
            }
            return Response(data, status_code=206, headers=headers)
        except Exception:
            pass

    return FileResponse(file_path, media_type=content_type)


# -------------------------------------------------------------
# Video Upload & Audio Extraction
# -------------------------------------------------------------
@app.post("/api/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Uploads a video, extracts audio, and persists project + media records in SQLite.
    Backward-compatible response format.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    safe_stem = Path(file.filename).stem
    safe_ext = Path(file.filename).suffix.lower()
    unique_prefix = uuid.uuid4().hex[:8]
    saved_video_name = f"{unique_prefix}_{safe_stem}{safe_ext}"
    video_path = UPLOAD_DIR / saved_video_name

    try:
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded video: {str(e)}")

    try:
        extraction_res = extract_audio(
            video_path=str(video_path),
            output_format="mp3",
            bitrate="192k"
        )
    except Exception as e:
        if video_path.exists():
            video_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")

    video_duration = get_media_duration(video_path)
    video_size_mb = round(video_path.stat().st_size / (1024 * 1024), 2)

    # Persist in database within a transaction
    try:
        project_title = title.strip() if title and title.strip() else safe_stem
        project = crud.create_project(db, title=project_title)

        video_media = crud.create_media_file(
            db=db,
            filename=saved_video_name,
            file_path=str(video_path),
            file_url=f"/media/{saved_video_name}",
            media_type="video",
            duration=video_duration,
            size_mb=video_size_mb,
            project_id=project.id,
            mime_type=f"video/{safe_ext.replace('.', '')}"
        )

        audio_media = crud.create_media_file(
            db=db,
            filename=extraction_res["filename"],
            file_path=extraction_res["audio_path"],
            file_url=f"/media/{extraction_res['filename']}",
            media_type="audio",
            duration=extraction_res["duration"],
            size_mb=extraction_res["size_mb"],
            project_id=project.id,
            parent_media_id=video_media.id,
            mime_type="audio/mpeg"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database transaction failed: {str(e)}")

    return {
        "success": True,
        "project_id": project.id,
        "video_id": video_media.id,
        "audio_id": audio_media.id,
        "video_filename": saved_video_name,
        "video_url": f"/media/{saved_video_name}",
        "audio_filename": extraction_res["filename"],
        "audio_url": f"/media/{extraction_res['filename']}",
        "duration": video_duration or extraction_res["duration"],
        "video_size_mb": video_size_mb,
        "audio_size_mb": extraction_res["size_mb"]
    }


# -------------------------------------------------------------
# Subtitle File Upload
# -------------------------------------------------------------
@app.post("/api/upload-subtitles-file")
async def upload_subtitles_file(
    file: UploadFile = File(...),
    video_duration: float = Form(0.0),
    project_id: Optional[int] = Form(None),
    media_file_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a manual subtitle file (.srt, .vtt, .txt), parses cues, and saves to SQLite.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")

    cues = parse_subtitles_text(text)
    if not cues:
        raise HTTPException(status_code=400, detail="Could not parse subtitles from uploaded file.")

    stats = calculate_subtitle_analytics(cues, video_duration)
    warnings = validate_subtitles(cues)

    # Persist in SQLite
    try:
        # Validate project_id if provided
        if project_id and not crud.get_project(db, project_id):
            project_id = None

        track = crud.create_subtitle_track(
            db=db,
            filename=file.filename,
            cues=cues,
            stats=stats,
            raw_content=text,
            project_id=project_id,
            media_file_id=media_file_id,
            format_type=Path(file.filename).suffix.replace(".", "").lower() or "srt"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to persist subtitle track: {str(e)}")

    return {
        "success": True,
        "subtitle_id": track.id,
        "project_id": track.project_id,
        "filename": file.filename,
        "cues": cues,
        "stats": stats,
        "warnings": warnings
    }


# -------------------------------------------------------------
# Parse Raw Subtitles
# -------------------------------------------------------------
@app.post("/api/parse-subtitles-raw")
async def parse_subtitles_raw(
    payload: RawSubtitleRequest,
    db: Session = Depends(get_db)
):
    """
    Parses pasted/manually typed subtitle text and persists to SQLite.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Subtitle text cannot be empty.")

    cues = parse_subtitles_text(payload.text)
    if not cues:
        raise HTTPException(status_code=400, detail="Failed to parse valid cues from text.")

    stats = calculate_subtitle_analytics(cues, payload.video_duration)
    warnings = validate_subtitles(cues)

    # Persist in SQLite
    try:
        project_id = payload.project_id
        if project_id and not crud.get_project(db, project_id):
            project_id = None

        track = crud.create_subtitle_track(
            db=db,
            filename="Pasted Subtitles",
            cues=cues,
            stats=stats,
            raw_content=payload.text,
            project_id=project_id,
            format_type="srt"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save subtitle track: {str(e)}")

    return {
        "success": True,
        "subtitle_id": track.id,
        "project_id": track.project_id,
        "cues": cues,
        "stats": stats,
        "warnings": warnings
    }


# -------------------------------------------------------------
# Shift Subtitles Timestamps
# -------------------------------------------------------------
@app.post("/api/shift-subtitles")
async def shift_subtitles_endpoint(
    payload: ShiftRequest,
    db: Session = Depends(get_db)
):
    """
    Time shifts all subtitle timestamps by delta seconds.
    Updates the database record if subtitle_id is provided.
    """
    cues_dict = [cue.model_dump() for cue in payload.cues]
    shifted = shift_cues(cues_dict, payload.delta)
    stats = calculate_subtitle_analytics(shifted, payload.video_duration)
    warnings = validate_subtitles(shifted)

    # If subtitle_id is provided, persist updated cues
    if payload.subtitle_id:
        track = crud.get_subtitle_track(db, payload.subtitle_id)
        if track:
            try:
                crud.sync_track_cues(db, track, shifted, payload.video_duration)
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to persist shifted cues: {str(e)}")

    return {
        "success": True,
        "subtitle_id": payload.subtitle_id,
        "cues": shifted,
        "stats": stats,
        "warnings": warnings
    }


# -------------------------------------------------------------
# Export Subtitles
# -------------------------------------------------------------
@app.post("/api/export-subtitles")
async def export_subtitles_endpoint(payload: ExportRequest):
    """
    Exports current subtitle track to SRT, VTT, JSON, or TXT file.
    """
    cues_dict = [cue.model_dump() for cue in payload.cues]
    try:
        content, filename, mime_type = export_to_format(cues_dict, payload.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -------------------------------------------------------------
# Clip Audio Snippet
# -------------------------------------------------------------
@app.post("/api/clip-audio")
async def clip_audio_endpoint(
    payload: ClipAudioRequest,
    db: Session = Depends(get_db)
):
    """
    Extracts an isolated audio clip matching a subtitle line and records it in SQLite.
    """
    audio_path = UPLOAD_DIR / payload.audio_filename
    if not audio_path.exists():
        audio_path = SAMPLE_DIR / payload.audio_filename

    if not audio_path.exists():
        # Check DB for media file path
        media = crud.get_media_file_by_filename(db, payload.audio_filename)
        if media and Path(media.file_path).exists():
            audio_path = Path(media.file_path)

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        res = clip_audio(
            source_audio_path=str(audio_path),
            start_sec=payload.start,
            end_sec=payload.end
        )
        clip_name = Path(res["clip_path"]).name

        # Persist clip record in SQLite
        clip_rec = crud.create_audio_clip(
            db=db,
            source_filename=payload.audio_filename,
            clip_filename=clip_name,
            clip_path=res["clip_path"],
            clip_url=f"/media/{clip_name}",
            start_time=payload.start,
            end_time=payload.end,
            duration=res["duration"],
            cue_id=payload.cue_id
        )

        return {
            "success": True,
            "clip_id": clip_rec.id,
            "clip_filename": clip_name,
            "clip_url": f"/media/{clip_name}",
            "duration": res["duration"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio clip failed: {str(e)}")


# -------------------------------------------------------------
# Load Built-in Demo Sample
# -------------------------------------------------------------
@app.get("/api/load-sample")
async def load_sample_endpoint(db: Session = Depends(get_db)):
    """
    Loads pre-built demo video, audio, and subtitle track, ensuring DB persistence.
    """
    video_name = "demo_sample.mp4"
    audio_name = "demo_sample_extracted.mp3"
    srt_name = "demo_sample.srt"

    video_path = SAMPLE_DIR / video_name
    audio_path = SAMPLE_DIR / audio_name
    srt_path = SAMPLE_DIR / srt_name

    if not srt_path.exists():
        raise HTTPException(status_code=404, detail="Sample files not found on server")

    with open(srt_path, "r", encoding="utf-8") as f:
        srt_text = f.read()

    cues = parse_subtitles_text(srt_text)
    stats = calculate_subtitle_analytics(cues, 8.0)
    warnings = validate_subtitles(cues)

    # Check if demo project already exists in SQLite
    demo_project = db.query(models.Project).filter(models.Project.title == "Demo Sample Project").first()
    if not demo_project:
        try:
            demo_project = crud.create_project(
                db=db,
                title="Demo Sample Project",
                description="Pre-packaged demo with synchronized video, audio, and subtitles"
            )

            vid_size = round(video_path.stat().st_size / (1024 * 1024), 2) if video_path.exists() else 0.18
            demo_video = crud.create_media_file(
                db=db,
                filename=video_name,
                file_path=str(video_path),
                file_url=f"/media/{video_name}",
                media_type="video",
                duration=8.0,
                size_mb=vid_size,
                project_id=demo_project.id,
                mime_type="video/mp4"
            )

            aud_size = round(audio_path.stat().st_size / (1024 * 1024), 2) if audio_path.exists() else 0.19
            crud.create_media_file(
                db=db,
                filename=audio_name,
                file_path=str(audio_path),
                file_url=f"/media/{audio_name}",
                media_type="audio",
                duration=8.0,
                size_mb=aud_size,
                project_id=demo_project.id,
                parent_media_id=demo_video.id,
                mime_type="audio/mpeg"
            )

            demo_track = crud.create_subtitle_track(
                db=db,
                filename=srt_name,
                cues=cues,
                stats=stats,
                raw_content=srt_text,
                project_id=demo_project.id,
                media_file_id=demo_video.id,
                language="en",
                format_type="srt"
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to seed demo data in DB: {str(e)}")
    else:
        demo_track = db.query(models.SubtitleTrack).filter(models.SubtitleTrack.project_id == demo_project.id).first()

    return {
        "success": True,
        "project_id": demo_project.id,
        "subtitle_id": demo_track.id if demo_track else None,
        "video_filename": video_name,
        "video_url": f"/media/{video_name}",
        "audio_filename": audio_name,
        "audio_url": f"/media/{audio_name}",
        "duration": 8.0,
        "cues": cues,
        "stats": stats,
        "warnings": warnings
    }


# =============================================================
# NEW RESTful CRUD ENDPOINTS
# =============================================================

# -------------------------------------------------------------
# Projects CRUD
# -------------------------------------------------------------
@app.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all projects with pagination.
    """
    projects = crud.list_projects(db, skip=skip, limit=limit)
    return projects


@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_new_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new project.
    """
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Project title cannot be empty")
    project = crud.create_project(db, title=payload.title, description=payload.description)
    return project


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project_by_id(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single project by ID with its media files and subtitle tracks.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project_by_id(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """
    Update project details.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    updated = crud.update_project(db, project, title=payload.title, description=payload.description)
    return updated


@app.delete("/api/projects/{project_id}")
async def delete_project_by_id(
    project_id: int,
    delete_files: bool = Query(False, description="Whether to also delete disk media files"),
    db: Session = Depends(get_db)
):
    """
    Delete a project and cascade-delete its media files, subtitle tracks, and cues.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if delete_files:
        for media in project.media_files:
            p = Path(media.file_path)
            if p.exists() and p.is_file() and p.parent == UPLOAD_DIR:
                p.unlink(missing_ok=True)

    crud.delete_project(db, project)
    return {"success": True, "message": f"Project {project_id} deleted successfully"}


# -------------------------------------------------------------
# Subtitle Tracks & Cues CRUD
# -------------------------------------------------------------
@app.get("/api/subtitles", response_model=List[SubtitleTrackSummary])
async def list_subtitle_tracks_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    List all subtitle tracks with pagination.
    """
    tracks = crud.list_subtitle_tracks(db, skip=skip, limit=limit, project_id=project_id)
    return tracks


@app.get("/api/subtitles/{subtitle_id}")
async def get_subtitle_track_details(
    subtitle_id: int,
    db: Session = Depends(get_db)
):
    """
    Get subtitle track by ID including full cue list, statistics, and validation warnings.
    """
    track = crud.get_subtitle_track(db, subtitle_id)
    if not track:
        raise HTTPException(status_code=404, detail="Subtitle track not found")

    cues_list = crud.cues_to_dict_list(track.cues)
    stats = calculate_subtitle_analytics(cues_list)
    warnings = validate_subtitles(cues_list)

    return {
        "success": True,
        "id": track.id,
        "project_id": track.project_id,
        "media_file_id": track.media_file_id,
        "filename": track.filename,
        "language": track.language,
        "format": track.format,
        "cues": cues_list,
        "stats": stats,
        "warnings": warnings,
        "created_at": track.created_at,
        "updated_at": track.updated_at
    }


@app.put("/api/subtitles/{subtitle_id}", response_model=SubtitleTrackSummary)
async def update_subtitle_track_metadata(
    subtitle_id: int,
    payload: SubtitleTrackUpdate,
    db: Session = Depends(get_db)
):
    """
    Update subtitle track metadata (filename, language, format).
    """
    track = crud.get_subtitle_track(db, subtitle_id)
    if not track:
        raise HTTPException(status_code=404, detail="Subtitle track not found")
    updated = crud.update_subtitle_track(
        db,
        track,
        filename=payload.filename,
        language=payload.language,
        format_type=payload.format
    )
    return updated


@app.delete("/api/subtitles/{subtitle_id}")
async def delete_subtitle_track_endpoint(
    subtitle_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a subtitle track and all of its cues.
    """
    track = crud.get_subtitle_track(db, subtitle_id)
    if not track:
        raise HTTPException(status_code=404, detail="Subtitle track not found")
    crud.delete_subtitle_track(db, track)
    return {"success": True, "message": f"Subtitle track {subtitle_id} deleted successfully"}


@app.put("/api/subtitles/{subtitle_id}/save")
async def save_track_cues_batch(
    subtitle_id: int,
    payload: BatchCuesSaveRequest,
    db: Session = Depends(get_db)
):
    """
    Batch save/sync all cues from the frontend editor to the database in one transaction.
    """
    track = crud.get_subtitle_track(db, subtitle_id)
    if not track:
        raise HTTPException(status_code=404, detail="Subtitle track not found")

    cues_dict = [c.model_dump() for c in payload.cues]
    try:
        updated_track = crud.sync_track_cues(db, track, cues_dict, payload.video_duration)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to sync cues: {str(e)}")

    cues_list = crud.cues_to_dict_list(updated_track.cues)
    stats = calculate_subtitle_analytics(cues_list, payload.video_duration)
    warnings = validate_subtitles(cues_list)

    return {
        "success": True,
        "subtitle_id": updated_track.id,
        "cues": cues_list,
        "stats": stats,
        "warnings": warnings
    }


@app.post("/api/subtitles/{subtitle_id}/cues", status_code=status.HTTP_201_CREATED)
async def add_cue_to_track_endpoint(
    subtitle_id: int,
    payload: CueCreate,
    video_duration: float = Query(0.0),
    db: Session = Depends(get_db)
):
    """
    Add a new cue to an existing subtitle track.
    """
    track = crud.get_subtitle_track(db, subtitle_id)
    if not track:
        raise HTTPException(status_code=404, detail="Subtitle track not found")

    if payload.end <= payload.start:
        raise HTTPException(status_code=422, detail="End time must be greater than start time")

    new_cue = crud.add_cue_to_track(
        db,
        track,
        start=payload.start,
        end=payload.end,
        text=payload.text,
        video_duration=video_duration
    )
    return {
        "success": True,
        "cue": {
            "id": new_cue.cue_index,
            "db_id": new_cue.id,
            "start": new_cue.start_time,
            "end": new_cue.end_time,
            "duration": new_cue.duration,
            "text": new_cue.text,
            "start_formatted": new_cue.start_formatted,
            "end_formatted": new_cue.end_formatted,
            "char_count": new_cue.char_count,
            "word_count": new_cue.word_count,
            "cps": new_cue.cps
        }
    }


@app.put("/api/subtitles/{subtitle_id}/cues/{cue_id}")
async def update_single_cue_endpoint(
    subtitle_id: int,
    cue_id: int,
    payload: CueUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a single cue's start time, end time, or text.
    """
    cue = db.query(models.SubtitleCue).filter(
        models.SubtitleCue.subtitle_id == subtitle_id,
        (models.SubtitleCue.id == cue_id) | (models.SubtitleCue.cue_index == cue_id)
    ).first()

    if not cue:
        raise HTTPException(status_code=404, detail="Cue not found")

    if payload.start is not None and payload.end is not None and payload.end <= payload.start:
        raise HTTPException(status_code=422, detail="End time must be greater than start time")

    updated_cue = crud.update_cue(
        db,
        cue,
        start=payload.start,
        end=payload.end,
        text=payload.text
    )

    return {
        "success": True,
        "cue": {
            "id": updated_cue.cue_index,
            "db_id": updated_cue.id,
            "start": updated_cue.start_time,
            "end": updated_cue.end_time,
            "duration": updated_cue.duration,
            "text": updated_cue.text,
            "start_formatted": updated_cue.start_formatted,
            "end_formatted": updated_cue.end_formatted,
            "char_count": updated_cue.char_count,
            "word_count": updated_cue.word_count,
            "cps": updated_cue.cps
        }
    }


@app.delete("/api/subtitles/{subtitle_id}/cues/{cue_id}")
async def delete_single_cue_endpoint(
    subtitle_id: int,
    cue_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a single cue and renumber remaining cues.
    """
    cue = db.query(models.SubtitleCue).filter(
        models.SubtitleCue.subtitle_id == subtitle_id,
        (models.SubtitleCue.id == cue_id) | (models.SubtitleCue.cue_index == cue_id)
    ).first()

    if not cue:
        raise HTTPException(status_code=404, detail="Cue not found")

    crud.delete_cue(db, cue)
    return {"success": True, "message": f"Cue {cue_id} deleted successfully"}


# -------------------------------------------------------------
# Media Files & Audio Clips List Endpoints
# -------------------------------------------------------------
@app.get("/api/media-files", response_model=List[MediaFileResponse])
async def list_media_files_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    media_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    List all media files registered in the database.
    """
    return crud.list_media_files(db, skip=skip, limit=limit, media_type=media_type)


@app.get("/api/audio-clips", response_model=List[AudioClipResponse])
async def list_audio_clips_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all audio clips with pagination.
    """
    return crud.list_audio_clips(db, skip=skip, limit=limit)


@app.delete("/api/audio-clips/{clip_id}")
async def delete_audio_clip_endpoint(
    clip_id: int,
    delete_file: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Delete an audio clip record and optionally remove the file from disk.
    """
    clip = crud.get_audio_clip(db, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Audio clip not found")

    if delete_file:
        p = Path(clip.clip_path)
        if p.exists() and p.is_file() and p.parent == UPLOAD_DIR:
            p.unlink(missing_ok=True)

    crud.delete_audio_clip(db, clip)
    return {"success": True, "message": f"Audio clip {clip_id} deleted successfully"}


# -------------------------------------------------------------
# Static Frontend Assets
# -------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Subtitle Studio backend running. Please create static/index.html</h1>"
