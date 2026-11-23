# Architecture

The browser calls a FastAPI application. Upload bytes are size-limited, never executed, and passed directly to format-specific extractors. A deterministic storyboard service maps explicit supported words into typed Pydantic scenes and reports unsupported content instead of silently substituting it.

The application Python environment does not import `bpy`. `blender_runner.py` discovers Blender and launches it with an explicit argument list and `shell=False`. Inside Blender, `scripts/fox_scene.py` creates reusable named objects, keyframes, lighting, camera motion, and output. Success requires a zero exit code and nonempty expected files.

Current rendering is procedural asset construction and animation—not generative text-to-3D AI. A future provider interface may add optional local language models without making them mandatory.

## v0.2 storyboard and persistence

`StoryboardDocument` is schema version `1.0`. It enforces unique scene IDs, unique contiguous order values, supported fox/forest/action literals, bounded durations, and nonblank text. The browser edits a local document and sends the complete result to `/api/storyboard/validate`; invalid data cannot reach storage or rendering.

`ProjectStore` owns `project_data/`. Only canonical UUID filenames are accepted. JSON is validated before use, unknown schema versions are rejected, corrupt files are reported, and writes use a temporary file plus `os.replace` for atomic updates. The data directory is ignored by Git except for `.gitkeep`.

## Render jobs

`RenderJobManager` uses a `ThreadPoolExecutor` with one worker, appropriate for a 16 GB integrated-GPU laptop. The FastAPI request returns a UUID job immediately while Blender runs off the event loop. State transitions are recorded from queueing through verification; exceptions become `FAILED` with captured diagnostics.

The current renderer deterministically accepts one validated fox/forest scene lasting 1–10 seconds. It passes the selected action and duration to Blender, stores job outputs under `output/jobs/<uuid>/`, and exposes an MP4 only after the Blender completion marker, PNG signature/dimensions, and MP4 header pass verification. Multi-scene documents are editable and persistent, but rendering rejects them explicitly until sequencing is implemented.
