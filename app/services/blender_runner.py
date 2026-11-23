from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BlenderRunResult:
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    expected_outputs: tuple[Path, ...]

    @property
    def succeeded(self) -> bool:
        return (
            self.exit_code == 0
            and "AI_CARTOON_RENDER_COMPLETE=1" in self.stdout
            and all(path.is_file() and path.stat().st_size > 0 for path in self.expected_outputs)
        )


def blender_candidates() -> list[Path]:
    candidates: list[Path] = []
    from_path = shutil.which("blender")
    if from_path:
        candidates.append(Path(from_path))

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    foundation = program_files / "Blender Foundation"
    if foundation.is_dir():
        candidates.extend(sorted(foundation.glob("Blender */blender.exe"), reverse=True))

    local_programs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
    if local_programs.is_dir():
        candidates.extend(local_programs.glob("**/blender.exe"))
    return candidates


def discover_blender() -> Path | None:
    return next((path.resolve() for path in blender_candidates() if path.is_file()), None)


def build_blender_command(executable: Path, script: Path, output_dir: Path, *, preview_only: bool = False) -> list[str]:
    command = [
        str(executable),
        "--background",
        "--factory-startup",
        "--python",
        str(script),
        "--",
        "--output-dir",
        str(output_dir),
    ]
    if preview_only:
        command.append("--preview-only")
    return command


def run_blender_demo(
    executable: Path,
    script: Path,
    output_dir: Path,
    *,
    preview_only: bool = False,
    timeout_seconds: int = 900,
) -> BlenderRunResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = [output_dir / "forest_fox.blend", output_dir / "preview.png"]
    if not preview_only:
        expected.append(output_dir / "first_cartoon.mp4")
    command = build_blender_command(executable, script, output_dir, preview_only=preview_only)
    started = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, shell=False)
    return BlenderRunResult(
        command=tuple(command),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.perf_counter() - started,
        expected_outputs=tuple(expected),
    )
