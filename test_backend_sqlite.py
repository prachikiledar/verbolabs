import os
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test database path before importing app
TEST_DB_PATH = Path(__file__).resolve().parent / "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from database import Base, get_db, init_db, engine
from app import app
import models
import crud

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    # Initialize DB
    init_db()
    yield
    # Cleanup after test session
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def test_db_tables_created():
    """Verify that all tables are created on database init"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "projects" in tables
    assert "media_files" in tables
    assert "subtitle_tracks" in tables
    assert "subtitle_cues" in tables
    assert "audio_clips" in tables


def test_index_page():
    """Verify root endpoint serves HTML"""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_load_sample_endpoint():
    """Verify /api/load-sample seeds and persists data in SQLite"""
    response = client.get("/api/load-sample")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["project_id"] is not None
    assert data["subtitle_id"] is not None
    assert len(data["cues"]) > 0
    assert data["video_filename"] == "demo_sample.mp4"
    assert data["audio_filename"] == "demo_sample_extracted.mp3"

    # Confirm persistence by checking projects API
    proj_resp = client.get(f"/api/projects/{data['project_id']}")
    assert proj_resp.status_code == 200
    proj_data = proj_resp.json()
    assert proj_data["title"] == "Demo Sample Project"
    assert len(proj_data["media_files"]) == 2
    assert len(proj_data["subtitle_tracks"]) >= 1


def test_projects_crud():
    """Test project create, read, update, list pagination, and delete"""
    # 1. Create project
    create_resp = client.post("/api/projects", json={
        "title": "Test Documentary",
        "description": "Documentary test subtitles"
    })
    assert create_resp.status_code == 201
    created_proj = create_resp.json()
    proj_id = created_proj["id"]
    assert created_proj["title"] == "Test Documentary"

    # 2. List projects with pagination
    list_resp = client.get("/api/projects?skip=0&limit=10")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert any(p["id"] == proj_id for p in projects)

    # 3. Update project
    update_resp = client.put(f"/api/projects/{proj_id}", json={
        "title": "Test Documentary Updated",
        "description": "Updated description"
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Test Documentary Updated"

    # 4. Get by ID
    get_resp = client.get(f"/api/projects/{proj_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Test Documentary Updated"

    # 5. Delete project
    del_resp = client.delete(f"/api/projects/{proj_id}")
    assert del_resp.status_code == 200
    assert client.get(f"/api/projects/{proj_id}").status_code == 404


def test_raw_subtitles_parsing_and_persistence():
    """Test /api/parse-subtitles-raw saves subtitle tracks and cues to SQLite"""
    raw_srt = (
        "1\n00:00:01,000 --> 00:00:03,500\nHello world!\n\n"
        "2\n00:00:04,000 --> 00:00:07,200\nThis is subtitle studio in Python.\n"
    )

    resp = client.post("/api/parse-subtitles-raw", json={
        "text": raw_srt,
        "video_duration": 10.0
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "subtitle_id" in data
    sub_id = data["subtitle_id"]
    assert len(data["cues"]) == 2

    # Check that subtitle track and cues exist in database
    track_resp = client.get(f"/api/subtitles/{sub_id}")
    assert track_resp.status_code == 200
    track_data = track_resp.json()
    assert track_data["id"] == sub_id
    assert len(track_data["cues"]) == 2
    assert track_data["cues"][0]["text"] == "Hello world!"
    assert track_data["cues"][1]["text"] == "This is subtitle studio in Python."


def test_cue_crud_operations():
    """Test adding, updating, and deleting individual cues on a track"""
    # Create a track
    resp = client.post("/api/parse-subtitles-raw", json={
        "text": "1\n00:00:01,000 --> 00:00:03,000\nInitial Line\n",
        "video_duration": 5.0
    })
    sub_id = resp.json()["subtitle_id"]

    # 1. Add Cue
    add_resp = client.post(f"/api/subtitles/{sub_id}/cues", json={
        "start": 3.5,
        "end": 5.0,
        "text": "Appended Line"
    })
    assert add_resp.status_code == 201
    cue_added = add_resp.json()["cue"]
    assert cue_added["text"] == "Appended Line"

    # Verify track has 2 cues now
    track_resp = client.get(f"/api/subtitles/{sub_id}")
    assert len(track_resp.json()["cues"]) == 2

    # 2. Update Cue
    update_resp = client.put(f"/api/subtitles/{sub_id}/cues/2", json={
        "text": "Updated Appended Line",
        "start": 3.6,
        "end": 5.2
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["cue"]["text"] == "Updated Appended Line"

    # 3. Delete Cue
    del_resp = client.delete(f"/api/subtitles/{sub_id}/cues/2")
    assert del_resp.status_code == 200

    # Verify track has 1 cue remaining
    track_resp2 = client.get(f"/api/subtitles/{sub_id}")
    assert len(track_resp2.json()["cues"]) == 1


def test_shift_subtitles():
    """Test shifting cues and updating in SQLite"""
    cues = [
        {"id": 1, "start": 1.0, "end": 3.0, "duration": 2.0, "text": "Shift me", "char_count": 8, "word_count": 2, "cps": 4.0}
    ]
    resp = client.post("/api/shift-subtitles", json={
        "cues": cues,
        "delta": 1.5,
        "video_duration": 5.0
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["cues"][0]["start"] == 2.5
    assert data["cues"][0]["end"] == 4.5


def test_export_subtitles():
    """Test exporting subtitles to SRT, VTT, JSON, TXT"""
    cues = [
        {"id": 1, "start": 1.0, "end": 3.0, "duration": 2.0, "text": "Hello world", "char_count": 11, "word_count": 2, "cps": 5.5}
    ]
    for fmt in ["srt", "vtt", "json", "txt"]:
        resp = client.post("/api/export-subtitles", json={"cues": cues, "format": fmt})
        assert resp.status_code == 200
        assert len(resp.content) > 0


def test_stream_media_and_sample_clip():
    """Test streaming media and clipping audio with SQLite recording"""
    # 1. Stream demo_sample.mp4
    resp = client.get("/media/demo_sample.mp4")
    assert resp.status_code == 200
    assert "video/mp4" in resp.headers["content-type"]

    # 2. Clip audio snippet
    clip_resp = client.post("/api/clip-audio", json={
        "audio_filename": "demo_sample_extracted.mp3",
        "start": 1.0,
        "end": 2.5
    })
    assert clip_resp.status_code == 200
    clip_data = clip_resp.json()
    assert clip_data["success"] is True
    assert "clip_filename" in clip_data
    clip_id = clip_data["clip_id"]

    # 3. Check audio clips list endpoint
    list_clips = client.get("/api/audio-clips")
    assert list_clips.status_code == 200
    clips = list_clips.json()
    assert any(c["id"] == clip_id for c in clips)

    # 4. Stream clipped audio
    stream_clip = client.get(clip_data["clip_url"])
    assert stream_clip.status_code == 200

    # 5. Delete clip
    del_clip = client.delete(f"/api/audio-clips/{clip_id}")
    assert del_clip.status_code == 200


def test_upload_subtitles_file():
    """Test /api/upload-subtitles-file endpoint with a real SRT file"""
    srt_path = Path(__file__).resolve().parent / "sample_data" / "demo_sample.srt"
    assert srt_path.exists()

    with open(srt_path, "rb") as f:
        response = client.post(
            "/api/upload-subtitles-file",
            files={"file": ("test_upload.srt", f, "text/plain")},
            data={"video_duration": "8.0"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "subtitle_id" in data
    assert len(data["cues"]) > 0

    # Verify track in DB
    sub_resp = client.get(f"/api/subtitles/{data['subtitle_id']}")
    assert sub_resp.status_code == 200
    assert len(sub_resp.json()["cues"]) == len(data["cues"])


def test_upload_video_file():
    """Test /api/upload-video endpoint with a sample mp4"""
    mp4_path = Path(__file__).resolve().parent / "sample_data" / "demo_sample.mp4"
    assert mp4_path.exists()

    with open(mp4_path, "rb") as f:
        response = client.post(
            "/api/upload-video",
            files={"file": ("upload_test_video.mp4", f, "video/mp4")},
            data={"title": "Uploaded MP4 Test"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "project_id" in data
    assert "video_id" in data
    assert "audio_id" in data
    assert data["video_filename"].endswith(".mp4")
    assert data["audio_filename"].endswith(".mp3")

    # Clean up uploaded test files
    up_dir = Path(__file__).resolve().parent / "uploads"
    for f in up_dir.glob("*upload_test_video*"):
        f.unlink(missing_ok=True)


def test_database_persistence_across_connection_reconnect():
    """Directly open a fresh SQLite connection to confirm data persists on disk"""
    fresh_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
    FreshSession = sessionmaker(bind=fresh_engine)
    db = FreshSession()
    try:
        projects = db.query(models.Project).all()
        assert len(projects) >= 1
        subtitles = db.query(models.SubtitleTrack).all()
        assert len(subtitles) >= 1
        cues = db.query(models.SubtitleCue).all()
        assert len(cues) >= 1
    finally:
        db.close()


def test_save_subtitles_endpoint_without_word_count():
    """Verify that /api/subtitles/save does not raise KeyError: 'word_count' when cues lack metrics"""
    # 1. Test when cues only contain id, start, end, text (no word_count or char_count)
    payload = {
        "cues": [
            {"id": 1, "start": 0.5, "end": 2.5, "text": "Testing cue save without word count"},
            {"id": 2, "start": 3.0, "end": 5.0, "text": "Second test line here"}
        ],
        "video_duration": 10.0
    }
    resp = client.post("/api/subtitles/save", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["cue_count"] == 2
    sub_id = data["subtitle_id"]

    # 2. Test saving again (syncing existing track)
    payload_update = {
        "subtitle_id": sub_id,
        "cues": [
            {"id": 1, "start": 1.0, "end": 3.0, "text": "Updated line without extra keys"}
        ],
        "video_duration": 10.0
    }
    resp_update = client.post("/api/subtitles/save", json=payload_update)
    assert resp_update.status_code == 200
    update_data = resp_update.json()
    assert update_data["success"] is True
    assert update_data["cue_count"] == 1

    # Verify track in DB has properly calculated metrics
    track_resp = client.get(f"/api/subtitles/{sub_id}")
    assert track_resp.status_code == 200
    track_info = track_resp.json()
    assert track_info["stats"]["total_words"] == 5
    assert len(track_info["cues"]) == 1

