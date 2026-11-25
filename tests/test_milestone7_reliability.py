from __future__ import annotations

import subprocess
import threading
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import Settings
from app.services.timeline.contracts import (
    TimelineClip,
    TimelineExportState,
    TimelineMediaKind,
    TimelineProjectDraft,
)
from app.services.timeline.export import TimelineExportManager
from app.services.timeline.media import ProbedMedia
from app.services.timeline.projects import TimelineProjectStore
from tests.test_timeline import create_clip, media_store, mp4_bytes


def _manager(tmp_path: Path, runner):
    media = media_store(tmp_path)
    clip = create_clip(media, tmp_path)
    projects = TimelineProjectStore(tmp_path / "projects")
    project = projects.create(
        TimelineProjectDraft(
            name="Reliability",
            clips=[TimelineClip(media_id=clip.media_id, order=0, trim_end_seconds=1.0)],
        )
    )

    def probe(path: Path, _ffprobe: Path) -> ProbedMedia:
        assert path.is_file()
        return ProbedMedia(1.0, 1280, 720, 30.0, "h264", True)

    manager = TimelineExportManager(
        tmp_path / "exports",
        projects,
        media,
        ffmpeg=Path("ffmpeg"),
        ffprobe=Path("ffprobe"),
        runner=runner,
        probe=probe,
    )
    return manager, project


def test_runtime_root_isolates_all_mutable_data(monkeypatch, tmp_path):
    isolated = tmp_path / "isolated-runtime"
    monkeypatch.setenv("AI_CARTOON_RUNTIME_ROOT", str(isolated))
    configured = Settings()

    assert configured.runtime_root == isolated.resolve()
    assert configured.output_dir == isolated.resolve() / "output"
    assert configured.project_data_dir == isolated.resolve() / "project_data"
    assert configured.timeline_exports_dir.is_relative_to(isolated.resolve())
    assert configured.timeline_media_dir.is_relative_to(isolated.resolve())
    assert configured.timeline_projects_dir.is_relative_to(isolated.resolve())


def test_duplicate_concurrent_exports_share_one_active_job(tmp_path):
    started = threading.Event()
    release = threading.Event()
    commands: list[list[str]] = []

    def runner(command: list[str], _timeout: int):
        commands.append(command)
        started.set()
        assert release.wait(5), "test export was not released"
        Path(command[-1]).write_bytes(mp4_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    manager, project = _manager(tmp_path, runner)
    try:
        first = manager.submit(project.project_id)
        assert started.wait(5)
        with ThreadPoolExecutor(max_workers=6) as pool:
            duplicates = list(pool.map(lambda _index: manager.submit(project.project_id), range(6)))
        assert {response.job_id for response in duplicates} == {first.job_id}
        assert all("already active" in response.message for response in duplicates)
        release.set()
        completed = manager.wait(first.job_id)
        assert completed.state == TimelineExportState.COMPLETED
        assert len(manager._jobs) == 1
    finally:
        release.set()
        manager.shutdown()


def test_failed_export_cleans_intermediates_and_can_retry(tmp_path):
    calls = 0

    def runner(command: list[str], _timeout: int):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(command, 1, "", "synthetic local failure")
        Path(command[-1]).write_bytes(mp4_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    manager, project = _manager(tmp_path, runner)
    try:
        failed = manager.submit(project.project_id)
        failed = manager.wait(failed.job_id)
        assert failed.state == TimelineExportState.FAILED
        failed_directory = tmp_path / "exports" / str(failed.job_id)
        assert not list(failed_directory.glob("normalized-*.mp4"))
        assert not list(failed_directory.glob("*.txt"))

        retried = manager.submit(project.project_id)
        assert retried.job_id != failed.job_id
        completed = manager.wait(retried.job_id)
        assert completed.state == TimelineExportState.COMPLETED
        assert manager.output_path(retried.job_id).is_file()
    finally:
        manager.shutdown()


def test_representative_media_copy_has_bounded_python_memory(tmp_path):
    store = media_store(tmp_path)
    source = tmp_path / "representative.mp4"
    with source.open("wb") as handle:
        handle.write(mp4_bytes())
        handle.truncate(12 * 1024 * 1024)

    tracemalloc.start()
    try:
        record = store.create_from_path(source.name, source, TimelineMediaKind.CLIP)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    stored, _metadata = store.media_path(record.media_id)
    assert stored.stat().st_size == source.stat().st_size
    assert peak < 6 * 1024 * 1024
