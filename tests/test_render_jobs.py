import struct

import pytest

from app.models import RenderState, StoryboardDocument, StoryboardScene
from app.services.blender_runner import BlenderRunResult
from app.services.render_jobs import RenderJobManager, UnsupportedStoryboardRenderError


def storyboard(scene_count: int = 1, duration: int = 2) -> StoryboardDocument:
    scenes = [
        StoryboardScene(
            scene_id=index + 1,
            order=index,
            description="A supported fox scene.",
            environment="magical_forest",
            characters=["fox"],
            action="walk",
            narration="The fox walks.",
            duration_seconds=duration,
        )
        for index in range(scene_count)
    ]
    return StoryboardDocument(title="Render", scenes=scenes)


def successful_renderer(scene, output_dir):
    blend = output_dir / "forest_fox.blend"
    preview = output_dir / "preview.png"
    video = output_dir / "first_cartoon.mp4"
    blend.write_bytes(b"BLENDER")
    preview.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 640, 360))
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1100)
    return BlenderRunResult(
        ("blender",), 0, "AI_CARTOON_RENDER_COMPLETE=1", "", 1.0, (blend, preview, video)
    )


def test_render_job_completes_with_honest_state_history(tmp_path):
    manager = RenderJobManager(tmp_path, successful_renderer)
    job = manager.submit(storyboard())
    completed = manager.wait(job.job_id)
    assert completed.state == RenderState.COMPLETED
    assert completed.state_history == [
        RenderState.QUEUED,
        RenderState.PREPARING,
        RenderState.STARTING_BLENDER,
        RenderState.RENDERING,
        RenderState.FINALIZING,
        RenderState.COMPLETED,
    ]
    assert manager.output_path(job.job_id).name == "first_cartoon.mp4"
    manager.shutdown()


def test_render_job_captures_failure(tmp_path):
    def failing_renderer(scene, output_dir):
        raise RuntimeError("Blender exploded safely")

    manager = RenderJobManager(tmp_path, failing_renderer)
    job = manager.submit(storyboard())
    failed = manager.wait(job.job_id)
    assert failed.state == RenderState.FAILED
    assert "exploded safely" in failed.error
    assert failed.state_history[-1] == RenderState.FAILED
    manager.shutdown()


def test_rejects_multiscene_and_expensive_duration(tmp_path):
    manager = RenderJobManager(tmp_path, successful_renderer)
    with pytest.raises(UnsupportedStoryboardRenderError, match="exactly one"):
        manager.submit(storyboard(scene_count=2))
    with pytest.raises(UnsupportedStoryboardRenderError, match="1 to 10"):
        manager.submit(storyboard(duration=11))
    manager.shutdown()
