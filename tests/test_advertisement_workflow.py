from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.services.timeline.http as http_module
from app.config import Settings
from app.services.timeline.characters import CharacterReferenceStore, CorruptCharacterReference
from app.services.timeline.contracts import (
    CharacterReferenceDraft,
    TimelineAudioTrack,
    TimelineClip,
    TimelineMediaKind,
    TimelineProjectDraft,
    TimelineSceneType,
    TimelineTransition,
)
from app.services.timeline.export import TimelineExportError, TimelineExportManager
from app.services.timeline.http import router
from app.services.timeline.projects import TimelineProjectStore
from tests.test_timeline import fake_probe, fake_thumbnail, media_store, mp4_bytes


def png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (b"\x00" * 256)


def wav_bytes() -> bytes:
    return b"RIFF\x24\x00\x00\x00WAVEfmt " + (b"\x00" * 256)


def create_media(store, tmp_path, filename, content, kind):
    source = tmp_path / filename
    source.write_bytes(content)
    return store.create_from_path(filename, source, kind)


def test_image_upload_api_validates_preserves_and_rejects_bad_signature(tmp_path, monkeypatch):
    store = media_store(tmp_path)
    monkeypatch.setattr(http_module, "settings", Settings(project_root=tmp_path))
    monkeypatch.setattr(http_module, "_media", store)
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        accepted = client.post(
            "/api/timeline/media",
            data={"kind": "image"},
            files={"media": ("showroom.png", png_bytes(), "image/png")},
        )
        rejected = client.post(
            "/api/timeline/media",
            data={"kind": "image"},
            files={"media": ("fake.png", b"not a png", "image/png")},
        )

    assert accepted.status_code == 201
    assert accepted.json()["kind"] == "image"
    assert store.media_path(accepted.json()["media_id"])[0].read_bytes() == png_bytes()
    assert rejected.status_code == 422


def test_woodora_template_is_a_ten_scene_plan_and_can_be_reopened(tmp_path, monkeypatch):
    monkeypatch.setattr(http_module, "_media", media_store(tmp_path))
    monkeypatch.setattr(http_module, "_projects", TimelineProjectStore(tmp_path / "projects"))
    monkeypatch.setattr(http_module, "_characters", CharacterReferenceStore(tmp_path / "characters"))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        template = client.get("/api/timeline/templates/woodora-grand-arrival")
        assert template.status_code == 200
        project = template.json()["project"]
        assert len(project["clips"]) == 10
        assert all(clip["media_id"] is None for clip in project["clips"])
        assert project["clips"][8]["requires_verified_lipsync"] is True
        assert project["clips"][9]["scene_type"] == "branding_card"
        created = client.post("/api/timeline/projects", json=project)
        reopened = client.get(f"/api/timeline/projects/{created.json()['project_id']}")
    assert created.status_code == 201
    assert reopened.status_code == 200
    assert reopened.json()["template_id"] == "woodora-sheru-bhai-grand-arrival"


def test_planned_media_and_unverified_lipsync_are_never_exportable(tmp_path):
    manager = TimelineExportManager(
        tmp_path / "exports",
        TimelineProjectStore(tmp_path / "projects"),
        media_store(tmp_path),
        ffmpeg=Path("ffmpeg"),
        ffprobe=Path("ffprobe"),
    )
    projects = manager.projects
    planned = projects.create(TimelineProjectDraft(name="Plan", clips=[TimelineClip(order=0, slot_title="Missing")]))
    try:
        with pytest.raises(TimelineExportError, match="Assign actual media"):
            manager.validate_project(planned)
        with pytest.raises(ValidationError, match="verified lip-sync"):
            TimelineClip(order=0, media_id=uuid4(), requires_verified_lipsync=True)
    finally:
        manager.shutdown()


def test_character_reference_round_trip_and_unknown_version_rejection(tmp_path):
    store = CharacterReferenceStore(tmp_path / "characters")
    image_id = uuid4()
    record = store.create(CharacterReferenceDraft(
        name="Sheru Bhai",
        visual_description="White anthropomorphic lion with a thick white mane.",
        clothing_accessories="Ivory suit, sunglasses, gold wristwatch.",
        image_media_ids=[image_id],
    ))
    reopened = store.get(record.reference_id)
    assert reopened.image_media_ids == [image_id]
    assert store.list().references[0].name == "Sheru Bhai"

    path = store.data_dir / f"{record.reference_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "99.0"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorruptCharacterReference, match="Unsupported"):
        store.get(record.reference_id)


def test_still_title_logo_transition_and_audio_offset_build_only_validated_filters(tmp_path):
    media = media_store(tmp_path)
    image = create_media(media, tmp_path, "scene.png", png_bytes(), TimelineMediaKind.IMAGE)
    logo = create_media(media, tmp_path, "logo.png", png_bytes(), TimelineMediaKind.LOGO)
    voice = create_media(media, tmp_path, "voice.wav", wav_bytes(), TimelineMediaKind.VOICE)
    projects = TimelineProjectStore(tmp_path / "projects")
    first = TimelineClip(
        order=0,
        media_id=image.media_id,
        scene_type=TimelineSceneType.STILL,
        duration_seconds=2,
        fade_in_seconds=.2,
        fade_out_seconds=.2,
        transition_to_next=TimelineTransition.CROSSFADE,
        transition_duration_seconds=.4,
        title_text="WOODORA: 100% local; no filter injection",
        logo_media_id=logo.media_id,
        brightness=.1,
        contrast=1.1,
    )
    second = TimelineClip(order=1, scene_type=TimelineSceneType.BRANDING_CARD, title_text="WOODORA")
    project = projects.create(TimelineProjectDraft(
        name="Cinematic ad",
        clips=[first, second],
        voice_track=TimelineAudioTrack(media_id=voice.media_id, start_seconds=.75),
    ))
    font = tmp_path / "trusted.ttf"
    font.write_bytes(b"test font")
    manager = TimelineExportManager(
        tmp_path / "exports", projects, media,
        ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), font_path=font,
    )
    try:
        title_file = tmp_path / "title.txt"
        title_file.write_text(first.title_text or "", encoding="utf-8")
        image_path, _ = media.media_path(image.media_id)
        logo_path, _ = media.media_path(logo.media_id)
        normalize = manager._normalize_command(
            image_path, tmp_path / "normalized.mp4", clip=first, start=0, duration=2,
            has_audio=False, width=1280, height=720, title_file=title_file, logo_path=logo_path,
        )
        transition = manager._transition_command(
            project, [tmp_path / "one.mp4", tmp_path / "two.mp4"], [2, 3], tmp_path / "joined.mp4"
        )
        mix = manager._mix_command(project, tmp_path / "joined.mp4", tmp_path / "final.mp4", 4.6)
        combined = " ".join(normalize)
        assert "-loop 1" in combined
        assert "drawtext=" in combined and "textfile=" in combined
        assert first.title_text not in combined
        assert "overlay=" in combined and "eq=brightness=0.1000:contrast=1.1000" in combined
        assert "xfade=transition=fade" in " ".join(transition)
        assert "acrossfade=" in " ".join(transition)
        assert "adelay=delays=750:all=1" in " ".join(mix)
        assert all(isinstance(argument, str) for command in (normalize, transition, mix) for argument in command)
    finally:
        manager.shutdown()
