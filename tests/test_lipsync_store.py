import json
from uuid import uuid4

import pytest

from app.services.lipsync_contract import LipSyncRequest
from app.services.lipsync_store import (
    CorruptUploadError,
    InvalidUploadIdError,
    LipSyncUploadStore,
    UploadNotFoundError,
)


PNG = b"\x89PNG\r\n\x1a\nprepared portrait"
WAV = b"RIFF" + b"\x00" * 4 + b"WAVEfmt prepared audio"


def request():
    return LipSyncRequest(mode="portrait", source_filename="sheru.png", audio_filename="malayalam.wav")


def test_persists_validated_media_with_uuid_and_byte_integrity(tmp_path):
    store = LipSyncUploadStore(tmp_path)
    created = store.create(request(), PNG, WAV)
    loaded = store.get(created.upload_id)
    source, source_type = store.media_path(created.upload_id, "source")
    audio, audio_type = store.media_path(created.upload_id, "audio")
    assert loaded == created
    assert source.read_bytes() == PNG
    assert audio.read_bytes() == WAV
    assert source_type == "image/png"
    assert audio_type == "audio/wav"
    assert not list(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize("upload_id", ["../outside", "not-a-uuid", "00000000-0000-0000-0000-000000000000.json"])
def test_rejects_unsafe_upload_ids(tmp_path, upload_id):
    store = LipSyncUploadStore(tmp_path)
    with pytest.raises(InvalidUploadIdError):
        store.get(upload_id)


def test_reports_missing_and_corrupt_uploads(tmp_path):
    store = LipSyncUploadStore(tmp_path)
    with pytest.raises(UploadNotFoundError):
        store.get(uuid4())

    created = store.create(request(), PNG, WAV)
    metadata = tmp_path / str(created.upload_id) / "metadata.json"
    metadata.write_text("{broken", encoding="utf-8")
    with pytest.raises(CorruptUploadError):
        store.get(created.upload_id)


def test_rejects_changed_media_and_schema(tmp_path):
    store = LipSyncUploadStore(tmp_path)
    created = store.create(request(), PNG, WAV)
    source, _ = store.media_path(created.upload_id, "source")
    source.write_bytes(b"changed")
    with pytest.raises(CorruptUploadError, match="changed"):
        store.media_path(created.upload_id, "source")

    metadata = tmp_path / str(created.upload_id) / "metadata.json"
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    payload["schema_version"] = "99.0"
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorruptUploadError, match="schema"):
        store.get(created.upload_id)
