from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.services.timeline.http as http_module
from app.services.timeline.contracts import (
    TimelineAudioTrack,
    TimelineClip,
    TimelineMediaKind,
    TimelineExportResponse, TimelineExportState, TimelineProjectDraft,
    TimelineSceneType,
    TimelineTextAnimation,
    TimelineTextPosition,
    TimelineTransition,
)
from app.services.timeline.export import TRANSITION_FILTERS, TimelineExportError, TimelineExportManager
from app.services.timeline.http import router
from app.services.timeline.media import TimelineMediaError
from app.services.timeline.projects import TimelineProjectStore
from tests.test_advertisement_workflow import create_media, png_bytes, wav_bytes
from tests.test_timeline import media_store, mp4_bytes


def cube_bytes(size: int = 2) -> bytes:
    rows = ["0 0 0", "0 0 1", "0 1 0", "0 1 1", "1 0 0", "1 0 1", "1 1 0", "1 1 1"]
    assert size == 2
    return ("TITLE \"Test\"\nLUT_3D_SIZE 2\n" + "\n".join(rows) + "\n").encode()


def manager_for(tmp_path, projects, media, **kwargs):
    font = tmp_path / "trusted.ttf"
    font.write_bytes(b"font")
    return TimelineExportManager(
        tmp_path / "exports", projects, media,
        ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), font_path=font, **kwargs,
    )


def test_schema_10_11_and_12_projects_reopen_with_defaults(tmp_path):
    store = TimelineProjectStore(tmp_path / "projects")
    for version in ("1.0", "1.1", "1.2"):
        record = store.create(TimelineProjectDraft(schema_version=version, name=f"Schema {version}"))
        reopened = store.get(record.project_id)
        assert reopened.schema_version == version
        assert reopened.ducking_enabled is True
        assert reopened.timeline_zoom == 80


def test_audio_markers_and_scene_alignment_are_validated():
    with pytest.raises(ValidationError, match="timeline end"):
        TimelineAudioTrack(media_id="00000000-0000-0000-0000-000000000001", start_seconds=2, end_seconds=1)
    with pytest.raises(ValidationError, match="source end"):
        TimelineAudioTrack(media_id="00000000-0000-0000-0000-000000000001", source_start_seconds=2, source_end_seconds=1)
    with pytest.raises(ValidationError, match="before zero"):
        TimelineAudioTrack(media_id="00000000-0000-0000-0000-000000000001", sync_offset_seconds=-1)


def test_cube_lut_validation_and_preservation(tmp_path):
    store = media_store(tmp_path)
    valid = create_media(store, tmp_path, "cinematic.cube", cube_bytes(), TimelineMediaKind.LUT)
    path, record = store.media_path(valid.media_id)
    assert path.read_bytes() == cube_bytes()
    assert record.codec == "cube"
    bad = tmp_path / "bad.cube"
    bad.write_text("LUT_3D_SIZE 2\n0 0 0\n", encoding="utf-8")
    with pytest.raises(TimelineMediaError, match="count"):
        store.create_from_path(bad.name, bad, TimelineMediaKind.LUT)


@pytest.mark.parametrize("transition", list(TRANSITION_FILTERS))
def test_professional_transition_presets_build_allowlisted_xfade(tmp_path, transition):
    media = media_store(tmp_path)
    projects = TimelineProjectStore(tmp_path / "projects")
    project = projects.create(TimelineProjectDraft(
        name="Transitions",
        clips=[
            TimelineClip(order=0, scene_type=TimelineSceneType.TITLE_CARD, title_text="A", transition_to_next=transition, transition_duration_seconds=.4),
            TimelineClip(order=1, scene_type=TimelineSceneType.TITLE_CARD, title_text="B"),
        ],
    ))
    manager = manager_for(tmp_path, projects, media)
    try:
        command = manager._transition_command(project, [tmp_path / "a.mp4", tmp_path / "b.mp4"], [3, 3], tmp_path / "out.mp4")
        assert f"xfade=transition={TRANSITION_FILTERS[transition]}" in " ".join(command)
        assert "acrossfade=d=0.400000" in " ".join(command)
    finally:
        manager.shutdown()


def test_color_lut_branding_animation_build_validated_filters(tmp_path):
    media = media_store(tmp_path)
    image = create_media(media, tmp_path, "scene.png", png_bytes(), TimelineMediaKind.IMAGE)
    lut = create_media(media, tmp_path, "look.cube", cube_bytes(), TimelineMediaKind.LUT)
    projects = TimelineProjectStore(tmp_path / "projects")
    manager = manager_for(tmp_path, projects, media)
    title = tmp_path / "title.txt"
    title.write_text("മലയാളം", encoding="utf-8")
    clip = TimelineClip(
        order=0, media_id=image.media_id, scene_type=TimelineSceneType.STILL,
        saturation=1.4, exposure=.5, color_temperature=-.4, lut_media_id=lut.media_id,
        title_text="മലയാളം", text_position=TimelineTextPosition.CUSTOM,
        text_x=.25, text_y=.3, text_animation=TimelineTextAnimation.SLIDE_UP,
    )
    try:
        image_path, _ = media.media_path(image.media_id)
        lut_path, _ = media.media_path(lut.media_id)
        command = manager._normalize_command(
            image_path, tmp_path / "out.mp4", clip=clip, start=0, duration=3,
            has_audio=False, width=1280, height=720, title_file=title, lut_path=lut_path,
        )
        joined = " ".join(command)
        assert "saturation=1.4000" in joined
        assert "exposure=exposure=0.5000" in joined
        assert "colortemperature=temperature=5100" in joined
        assert "lut3d=file=" in joined
        assert "min(t/0.5000\\,1)" in joined
        assert clip.title_text not in joined
    finally:
        manager.shutdown()


def test_waveform_audio_sync_fades_and_ducking_commands(tmp_path):
    media = media_store(tmp_path)
    voice = create_media(media, tmp_path, "voice.wav", wav_bytes(), TimelineMediaKind.VOICE)
    music = create_media(media, tmp_path, "music.wav", wav_bytes(), TimelineMediaKind.MUSIC)
    assert media.waveform_path(voice.media_id).is_file()
    assert media.waveform_path(music.media_id).is_file()
    projects = TimelineProjectStore(tmp_path / "projects")
    project = projects.create(TimelineProjectDraft(
        name="Audio",
        clips=[TimelineClip(order=0, scene_type=TimelineSceneType.TITLE_CARD, title_text="Audio", duration_seconds=2)],
        voice_track=TimelineAudioTrack(
            media_id=voice.media_id, start_seconds=.4, sync_offset_seconds=.1,
            source_start_seconds=.2, source_end_seconds=1.5, fade_in_seconds=.1, fade_out_seconds=.2,
        ),
        music_track=TimelineAudioTrack(media_id=music.media_id, fade_in_seconds=.1),
        ducking_enabled=True,
        ducking_intensity=.75,
    ))
    manager = manager_for(tmp_path, projects, media)
    try:
        command = " ".join(manager._mix_command(project, tmp_path / "joined.mp4", tmp_path / "final.mp4", 2))
        assert "atrim=start=0.200000:end=1.500000" in command
        assert "adelay=delays=500:all=1" in command
        assert "afade=t=in" in command and "afade=t=out" in command
        assert "sidechaincompress=" in command and "ratio=15.5000" in command
    finally:
        manager.shutdown()


def test_transition_duration_cannot_consume_adjacent_scene(tmp_path):
    projects = TimelineProjectStore(tmp_path / "projects")
    project = projects.create(TimelineProjectDraft(
        name="Invalid transition",
        clips=[
            TimelineClip(order=0, scene_type=TimelineSceneType.TITLE_CARD, title_text="A", duration_seconds=1, transition_to_next=TimelineTransition.ZOOM, transition_duration_seconds=1),
            TimelineClip(order=1, scene_type=TimelineSceneType.TITLE_CARD, title_text="B", duration_seconds=1),
        ],
    ))
    manager = manager_for(tmp_path, projects, media_store(tmp_path))
    try:
        with pytest.raises(TimelineExportError, match="shorter"):
            manager.validate_project(project)
    finally:
        manager.shutdown()


def test_waveform_and_rendered_preview_api_are_local_and_explicit(tmp_path, monkeypatch):
    media = media_store(tmp_path)
    voice = create_media(media, tmp_path, "voice.wav", wav_bytes(), TimelineMediaKind.VOICE)
    project_id = uuid4()

    class PreviewExports:
        def submit(self, submitted_project_id):
            now = datetime.now(timezone.utc)
            return TimelineExportResponse(
                job_id=uuid4(), project_id=submitted_project_id,
                state=TimelineExportState.QUEUED, message="Exact local preview queued.",
                created_at=now, updated_at=now,
            )

    monkeypatch.setattr(http_module, "_media", media)
    monkeypatch.setattr(http_module, "_exports", PreviewExports())
    monkeypatch.setattr(http_module, "_generated_job_ids", lambda: [])
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        metadata = client.get(f"/api/timeline/media/{voice.media_id}")
        waveform = client.get(metadata.json()["waveform_url"])
        preview = client.post("/api/timeline/previews", json={"project_id": str(project_id)})
        capabilities = client.get("/api/timeline/capabilities")
    assert metadata.status_code == 200
    assert waveform.status_code == 200 and waveform.headers["content-type"].startswith("image/png")
    assert preview.status_code == 202 and preview.json()["state"] == "QUEUED"
    assert capabilities.json()["professional_editor_schema_version"] == "1.2"
    assert "zoom" in capabilities.json()["transition_presets"]


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required for browser-model checks")
def test_timeline_model_drag_split_and_bounded_history():
    script = r"""
const assert = require('assert');
const model = require('./app/static/js/timeline-model.js');
const media = {duration_seconds: 4};
const clips = [
  {clip_id:'a', order:0, scene_type:'video', media, trim_start_seconds:0, trim_end_seconds:4, transition_to_next:'cut'},
  {clip_id:'b', order:1, scene_type:'still', media:{}, duration_seconds:2, transition_to_next:'cut'}
];
assert.deepStrictEqual(model.reorder(clips, 0, 1).map(c => c.clip_id), ['b','a']);
const split = model.splitAt(clips, 1.5, () => 'new-id');
assert.strictEqual(split.length, 3);
assert.strictEqual(split[0].trim_end_seconds, 1.5);
assert.strictEqual(split[1].trim_start_seconds, 1.5);
const history = new model.History(2);
history.record({value:1}); history.record({value:2}); history.record({value:3});
assert.strictEqual(history.undoStack.length, 2);
assert.strictEqual(history.undo({value:4}).value, 3);
assert.strictEqual(history.redo({value:3}).value, 4);
"""
    completed = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
