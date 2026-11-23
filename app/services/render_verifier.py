from __future__ import annotations

import struct
from pathlib import Path


def verify_png(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 24:
        return False
    with path.open("rb") as handle:
        header = handle.read(24)
    return header[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", header[16:24]) == (640, 360)


def verify_mp4(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 1024:
        return False
    with path.open("rb") as handle:
        header = handle.read(64)
    return b"ftyp" in header
