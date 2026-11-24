"""One-time safe registration of the Step 3 lip-sync router in app/main.py.

Run from the repository root. The installer adds only one import and one
include_router() call; it does not replace the user's existing FastAPI app.
"""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import tempfile

IMPORT = "from app.services.lipsync_http import router as lipsync_router"
INCLUDE = "app.include_router(lipsync_router)"


def install(root: Path) -> str:
    main = root / "app" / "main.py"
    contract = root / "app" / "services" / "lipsync_contract.py"
    http = root / "app" / "services" / "lipsync_http.py"
    if not (main.is_file() and contract.is_file() and http.is_file()):
        raise RuntimeError("Expected app/main.py and both lip-sync service modules in the project.")

    original = main.read_bytes()
    text = original.decode("utf-8-sig")
    imported = IMPORT in text
    included = INCLUDE in text
    if imported and included:
        return "Already installed. No changes made."
    if imported or included:
        raise RuntimeError("A partial lip-sync registration exists. Inspect app/main.py before retrying.")
    eol = "\r\n" if b"\r\n" in original else "\n"
    lines = text.splitlines(keepends=True)

    app_def = [i for i, line in enumerate(lines) if line.startswith("app = FastAPI(")]
    mount = [i for i, line in enumerate(lines) if line.startswith('app.mount("/static",')]
    if len(app_def) != 1 or len(mount) != 1 or app_def[0] >= mount[0]:
        raise RuntimeError("Expected a single FastAPI app and /static mount; refusing to edit unknown structure.")

    lines.insert(app_def[0], IMPORT + eol + eol)
    # Find mount again after inserting the import.
    mount_idx = next(i for i, line in enumerate(lines) if line.startswith('app.mount("/static",'))
    lines.insert(mount_idx + 1, INCLUDE + eol)
    result = "".join(lines)
    ast.parse(result, filename=str(main))

    fd, temp = tempfile.mkstemp(dir=main.parent, prefix=".main-lipsync-step3-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(result.encode("utf-8"))
        os.replace(temp, main)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return "Registered lip-sync API router in app/main.py."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root (default: current directory)")
    args = parser.parse_args()
    print(install(args.root.resolve()))


if __name__ == "__main__":
    main()
