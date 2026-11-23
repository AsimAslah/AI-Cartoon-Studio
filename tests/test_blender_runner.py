from pathlib import Path

from app.services.blender_runner import BlenderRunResult, build_blender_command, build_storyboard_render_command


def test_builds_argument_list_without_shell():
    command = build_blender_command(Path("blender.exe"), Path("fox_scene.py"), Path("output"), preview_only=True)
    assert command[:3] == ["blender.exe", "--background", "--factory-startup"]
    assert command[-1] == "--preview-only"


def test_builds_deterministic_storyboard_render_arguments():
    command = build_storyboard_render_command(
        Path("blender.exe"), Path("fox_scene.py"), Path("job-output"), action="turn", duration_seconds=3
    )
    assert command[-4:] == ["--action", "turn", "--duration-seconds", "3"]


def test_success_requires_all_real_outputs(tmp_path):
    expected = tmp_path / "preview.png"
    result = BlenderRunResult(("blender",), 0, "AI_CARTOON_RENDER_COMPLETE=1", "", 1.0, (expected,))
    assert not result.succeeded
    expected.write_bytes(b"real")
    assert result.succeeded


def test_success_rejects_blender_zero_exit_without_completion_marker(tmp_path):
    expected = tmp_path / "preview.png"
    expected.write_bytes(b"stale")
    result = BlenderRunResult(("blender",), 0, "Python traceback", "", 1.0, (expected,))
    assert not result.succeeded
