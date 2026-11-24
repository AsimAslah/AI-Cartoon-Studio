from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.services.timeline.http as http_module
from app.services.timeline.contracts import (
    TimelineClip,
    TimelineExportProfile,
    TimelineExportState,
    TimelineMediaKind,
    TimelineProjectDraft,
)
from app.services.timeline.export import TimelineExportManager
from app.services.timeline.http import router
from app.services.timeline.media import (
    CorruptTimelineMedia,
    InvalidTimelineMediaId,
    ProbedMedia,
    TimelineMediaStore,
)
from app.services.timeline.projects import CorruptTimelineProject, TimelineProjectStore


def mp4_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypisom" + (b"\x00" * 2048)


def fake_probe(path: Path, _ffprobe: Path) -> ProbedMedia:
    assert path.is_file()
    return ProbedMedia(
        duration_seconds=2.0,
        width=1280,
        height=720,
        frame_rate=30.0,
        codec="h264",
        has_audio=True,
    )


def fake_thumbnail(source: Path, destination: Path, _ffmpeg: Path) -> None:
    assert source.is_file()
    destination.write_bytes(b"jpeg thumbnail")


def fake_waveform(source: Path, destination: Path, _ffmpeg: Path) -> None:
    assert source.is_file()
    destination.write_bytes(b"png waveform")


def media_store(tmp_path: Path) -> TimelineMediaStore:
    return TimelineMediaStore(
        tmp_path / "media",
        ffprobe=Path("ffprobe"),
        ffmpeg=Path("ffmpeg"),
        probe=fake_probe,
        thumbnailer=fake_thumbnail,
        waveform_renderer=fake_waveform,
    )


def create_clip(store: TimelineMediaStore, tmp_path: Path, name: str = "clip.mp4"):
    source = tmp_path / name
    source.write_bytes(mp4_bytes())
    return store.create_from_path(name, source, TimelineMediaKind.CLIP)


def test_project_contract_rejects_non_contiguous_order_and_invalid_trim():
    media_id = uuid4()
    with pytest.raises(ValidationError, match="contiguous"):
        TimelineProjectDraft(name="WOODORA", clips=[TimelineClip(media_id=media_id, order=1)])
    with pytest.raises(ValidationError, match="trim end"):
        TimelineClip(media_id=media_id, order=0, trim_start_seconds=1, trim_end_seconds=1)


def test_media_store_preserves_source_and_uses_uuid_directory(tmp_path):
    store = media_store(tmp_path)
    source = tmp_path / "original.mp4"
    source.write_bytes(mp4_bytes())

    record = store.create_from_path(source.name, source, TimelineMediaKind.CLIP)
    stored, loaded = store.media_path(record.media_id)

    assert source.read_bytes() == mp4_bytes()
    assert stored.read_bytes() == source.read_bytes()
    assert stored.parent.name == str(record.media_id)
    assert loaded == record
    assert store.thumbnail_path(record.media_id).is_file()


@pytest.mark.parametrize("unsafe", ["../clip.mp4", "folder/clip.mp4", "folder\\clip.mp4"])
def test_media_store_rejects_filename_paths(tmp_path, unsafe):
    store = media_store(tmp_path)
    source = tmp_path / "clip.mp4"
    source.write_bytes(mp4_bytes())
    with pytest.raises(Exception, match="filename"):
        store.create_from_path(unsafe, source, TimelineMediaKind.CLIP)


def test_media_store_rejects_noncanonical_id_and_nonobject_metadata(tmp_path):
    store = media_store(tmp_path)
    with pytest.raises(InvalidTimelineMediaId):
        store.get("../outside")
    record = create_clip(store, tmp_path)
    metadata = store.data_dir / str(record.media_id) / "metadata.json"
    metadata.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(CorruptTimelineMedia):
        store.get(record.media_id)


def test_project_store_round_trip_update_and_unknown_schema_rejection(tmp_path):
    store = TimelineProjectStore(tmp_path / "projects")
    draft = TimelineProjectDraft(name="WOODORA Timeline", export_profile=TimelineExportProfile.HD_720P)
    created = store.create(draft)
    updated = store.update(created.project_id, draft.model_copy(update={"name": "WOODORA Final"}))
    assert updated.project_id == created.project_id
    assert updated.created_at == created.created_at
    assert store.list().projects[0].name == "WOODORA Final"

    path = store.data_dir / f"{created.project_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "99.0"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorruptTimelineProject, match="Unsupported"):
        store.get(created.project_id)


@pytest.mark.parametrize(
    ("profile", "expected_width", "expected_height"),
    [
        (TimelineExportProfile.HD_720P, 1280, 720),
        (TimelineExportProfile.FULL_HD_1080P, 1920, 1080),
    ],
)
def test_export_manager_normalizes_concatenates_and_verifies(
    tmp_path, profile, expected_width, expected_height
):
    media = media_store(tmp_path)
    first = create_clip(media, tmp_path, "first.mp4")
    second = create_clip(media, tmp_path, "second.mp4")
    projects = TimelineProjectStore(tmp_path / "projects")
    project = projects.create(
        TimelineProjectDraft(
            name="WOODORA",
            export_profile=profile,
            clips=[
                TimelineClip(media_id=first.media_id, order=0, trim_end_seconds=1.25),
                TimelineClip(media_id=second.media_id, order=1, trim_start_seconds=0.25),
            ],
        )
    )
    commands: list[list[str]] = []

    def fake_runner(command: list[str], _timeout: int):
        commands.append(command)
        Path(command[-1]).write_bytes(mp4_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    def output_probe(path: Path, _ffprobe: Path) -> ProbedMedia:
        assert path.is_file()
        return ProbedMedia(
            duration_seconds=2.0,
            width=expected_width,
            height=expected_height,
            frame_rate=30.0,
            codec="h264",
            has_audio=True,
        )

    manager = TimelineExportManager(
        tmp_path / "exports",
        projects,
        media,
        ffmpeg=Path("ffmpeg"),
        ffprobe=Path("ffprobe"),
        runner=fake_runner,
        probe=output_probe,
    )
    try:
        submitted = manager.submit(project.project_id)
        completed = manager.wait(submitted.job_id)
        assert completed.state == TimelineExportState.COMPLETED
        assert completed.metadata is not None
        assert (completed.metadata.width, completed.metadata.height) == (expected_width, expected_height)
        assert completed.state_history == [
            TimelineExportState.QUEUED,
            TimelineExportState.VALIDATING,
            TimelineExportState.NORMALIZING,
            TimelineExportState.CONCATENATING,
            TimelineExportState.VERIFYING,
            TimelineExportState.COMPLETED,
        ]
        assert manager.output_path(submitted.job_id).is_file()
        job_directory = (tmp_path / "exports" / str(submitted.job_id))
        assert not list(job_directory.glob("normalized-*.mp4"))
        assert not (job_directory / "concat.txt").exists()
        assert not (job_directory / "joined.mp4").exists()
        assert len(commands) == 3
        assert all(isinstance(argument, str) for command in commands for argument in command)
        assert f"scale={expected_width}:{expected_height}" in " ".join(commands[0])
    finally:
        manager.shutdown()


def test_timeline_api_saves_valid_project_and_blocks_remote_clients(tmp_path, monkeypatch):
    media = media_store(tmp_path)
    clip = create_clip(media, tmp_path)
    monkeypatch.setattr(http_module, "_media", media)
    monkeypatch.setattr(http_module, "_projects", TimelineProjectStore(tmp_path / "projects"))
    monkeypatch.setattr(http_module, "_generated_job_ids", lambda: [])

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        capabilities = client.get("/api/timeline/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["schema_version"] == "1.0"
        created = client.post(
            "/api/timeline/projects",
            json={
                "schema_version": "1.0",
                "name": "WOODORA Timeline",
                "clips": [{"media_id": str(clip.media_id), "order": 0}],
                "export_profile": "720p",
            },
        )
        assert created.status_code == 201
        assert client.get(f"/api/timeline/projects/{created.json()['project_id']}").status_code == 200

    with TestClient(app, client=("192.0.2.80", 1234)) as external:
        assert external.get("/api/timeline/capabilities").status_code == 403
        assert external.get("/api/timeline/projects").status_code == 403
