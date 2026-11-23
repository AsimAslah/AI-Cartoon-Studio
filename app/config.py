from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[1]
    max_upload_bytes: int = 5 * 1024 * 1024
    preview_width: int = 640
    preview_height: int = 360
    preview_fps: int = 24

    @property
    def output_dir(self) -> Path:
        return self.project_root / "output"

    @property
    def project_data_dir(self) -> Path:
        return self.project_root / "project_data"

    @property
    def render_jobs_dir(self) -> Path:
        return self.output_dir / "jobs"

    @property
    def lipsync_data_dir(self) -> Path:
        return self.project_data_dir / "lipsync_uploads"

    @property
    def lipsync_jobs_dir(self) -> Path:
        return self.output_dir / "lipsync_jobs"


settings = Settings()
