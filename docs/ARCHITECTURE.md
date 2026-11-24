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

## Malayalam lip-sync Milestone 1

`lipsync_contract.py` defines input modes, Malayalam-only request metadata, provider capabilities, upload records, and generation-job states. `lipsync_store.py` writes validated source and audio bytes atomically into `project_data/lipsync_uploads/<uuid>/`; callers can retrieve only the `source` or `audio` member of a canonical UUID record. Metadata is schema version `1.0`, and changed or corrupt files are rejected.

`lipsync_http.py` keeps upload, preview, and job endpoints loopback-only. Validation checks bounded size, safe basename, allowed extension, and common format signatures. It does not claim codec decoding, duration verification, face detection, or inference. The browser previews the selected or stored media and clearly distinguishes `VALIDATED` from generated output.

`LipSyncJobManager` is a one-worker provider-neutral executor. A provider must advertise configured real inference before a UUID job can exist. Its output must remain inside the job directory and pass MP4 verification before `COMPLETED`. The production registry is empty, so the current integrated-Radeon installation creates no generation jobs. Tests inject a fake provider solely to verify lifecycle and failure handling; this is not evidence of model inference.

## AI Video Studio Milestone 2

`video_generation/contracts.py` defines provider capabilities, exact LTX settings, schema-versioned uploads, truthful job states, and result metadata. `store.py` preserves the original validated image in a canonical UUID directory with atomic metadata writes. `http.py` keeps uploads, jobs, and media local-only and requires literal remote consent before dispatch.

`HuggingFaceLTXProvider` is restricted to the reviewed official `Lightricks/LTX-2.5` Space and `/run` endpoint. It requires an explicit token, lazily imports the optional Gradio client, verifies the live published parameter schema, submits the local image with `handle_file`, captures the real queue event ID, maps queue states without fabricated percentages, and applies a bounded timeout/cancellation path. It never accepts a caller-provided remote URL.

`VideoGenerationJobManager` has one worker. Original reference images remain under `project_data/video_generation_uploads/<uuid>/`; downloaded provider results and verified job artifacts are isolated under `output/video_generation_jobs/<uuid>/`. The manager maintains the provider lifecycle independently of the FastAPI event loop and exposes output only after canonical-path checks, MP4 envelope checks, and independent `ffprobe` decoding of dimensions, duration, frame rate, and codec. Mocked tests prove the contract and failure paths, not real model quality. A live inference and visual Woodora review still require explicit quota approval.

`HuggingFaceQuotaService` holds only an explicit environment token and an in-memory sanitized quota snapshot. Its refresh path calls the official read-only quota API, never the generation endpoint. Provider exceptions are classified using exception types, HTTP status, and structured error signals, but only stable public messages and diagnostic codes cross the API boundary. Unknown upstream bodies are discarded rather than echoed.

## Video Timeline Studio Milestone 4

`timeline/contracts.py` defines schema `1.0` media and project records, ordered clips, bounded trim/volume values, two fixed export profiles, and process-backed export states. `TimelineMediaStore` copies validated MP4/WAV/MP3/M4A sources into `project_data/timeline_media/<uuid>/`, records FFprobe metadata, and creates thumbnails. It accepts only a basename, canonical UUIDs, allowlisted signatures, and configured local media roots; generated clips can be imported only from the fixed `output/video_generation_jobs/<uuid>/generated.mp4` location.

`TimelineProjectStore` writes manifests atomically under `project_data/timeline_projects/` and rejects unknown versions instead of attempting migration. The browser stores only UUID references and presents individual or sequential trimmed previews. This pre-export sequence preview does not simulate audio mixing.

`TimelineExportManager` owns one local worker and writes each job under `output/timeline_exports/<uuid>/`. Every clip is normalized with argument-based `shell=False` FFmpeg calls to the selected dimensions, 30 fps H.264, YUV420P, 48 kHz stereo AAC, and a safe timestamp base. Controlled normalized filenames are concatenated; optional voice and music are resampled, volume-adjusted, padded/trimmed to the timeline, and mixed with the clip audio. Output is available only after MP4-envelope and independent FFprobe validation. The manager exposes discrete validation, normalization, concatenation, mixing, verification, completion, and failure stages—never fabricated percentages.
