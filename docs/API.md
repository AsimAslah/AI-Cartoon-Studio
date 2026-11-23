# API reference — v0.2.0

FastAPI also publishes interactive OpenAPI documentation at `/docs`.

## Story input and validation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/capabilities` | Blender availability, schema versions, supported assets/actions, and render limitations |
| `POST` | `/api/extract` | Extract bounded TXT, text-PDF, or DOCX uploads |
| `POST` | `/api/storyboard` | Generate a constrained rule-based storyboard from text |
| `POST` | `/api/storyboard/validate` | Validate schema `1.0`, IDs, order, fields, and supported literals |

## Projects

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/projects` | Create a UUID-backed project (`201`) |
| `GET` | `/api/projects` | List valid projects and warnings for skipped corrupt files |
| `GET` | `/api/projects/{project_id}` | Load and validate a project |
| `PUT` | `/api/projects/{project_id}` | Atomically update an existing project |

Invalid IDs return `422`, missing projects return `404`, and corrupt or unsupported-version projects return `409`. Project IDs cannot contain paths and never select arbitrary files.

## Rendering

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/renders` | Submit exactly one storyboard or project ID (`202`) |
| `GET` | `/api/renders/{job_id}` | Read the real stage, message, history, and captured failure |
| `GET` | `/api/renders/{job_id}/output` | Download the validated MP4 after completion |
| `POST` | `/api/render/demo` | Backward-compatible v0.1 demo renderer |
| `GET` | `/api/output/{filename}` | Retrieve allowlisted v0.1 outputs |

Render submission accepts exactly one supported `fox` scene in `magical_forest`, an action from `idle`, `walk`, `turn`, `approach`, `look`, or `touch`, and a duration from 1–10 seconds. Multiple scenes return `422`; no fixed video is substituted.

Jobs are stored in memory for the running server, and completed media lives under ignored `output/jobs/`. Restarting the server clears job status history but does not delete rendered files.

## Malayalam lip-sync preparation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/lipsync/capabilities` | List modes, limits, provider availability, hardware requirements, and warnings |
| `POST` | `/api/lipsync/validate` | Preliminary validation without saving or inference |
| `POST` | `/api/lipsync/uploads` | Atomically store validated source and Malayalam audio under a UUID (`201`) |
| `GET` | `/api/lipsync/uploads/{upload_id}` | Retrieve schema `1.0` upload metadata |
| `GET` | `/api/lipsync/uploads/{upload_id}/media/{source|audio}` | Preview only an allowlisted member of that UUID record |
| `POST` | `/api/lipsync/jobs` | Submit to a configured real provider (`202`); currently returns `503` before job creation |
| `GET` | `/api/lipsync/jobs/{job_id}` | Read real provider-backed job state |
| `GET` | `/api/lipsync/jobs/{job_id}/output` | Download only a completed verified MP4 |

These endpoints are loopback-only. Current validation checks envelope data and common signatures, not full decoding. No production inference provider is registered and no successful lip-sync output is claimed. See [LIPSYNC_MILESTONE1.md](LIPSYNC_MILESTONE1.md).

## AI image-to-video generation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/video/capabilities` | Read reviewed provider identity, supported settings, configuration state, privacy/cost disclosure, and prompt guidance |
| `POST` | `/api/video/uploads` | Validate and atomically store one PNG/JPEG/WebP under a UUID (`201`) |
| `GET` | `/api/video/uploads/{upload_id}` | Retrieve upload schema `1.0` metadata |
| `GET` | `/api/video/uploads/{upload_id}/image` | Preview the exact stored reference image |
| `POST` | `/api/video/jobs` | Submit an explicitly consented request to a configured provider (`202`) |
| `GET` | `/api/video/jobs/{job_id}` | Read provider-backed state, history, errors, identifiers, prompt, seed, and verified metadata |
| `GET` | `/api/video/jobs/{job_id}/output` | Download only a completed, independently verified MP4 |

Mutation and media endpoints are loopback-only. The only allowlisted provider is the official `Lightricks/LTX-2.5` Gradio Space at `/run`; arbitrary URLs, Spaces, and endpoint names are rejected. A job is unavailable unless remote processing, an explicit Hugging Face token, the optional client, and `ffprobe` are configured. `remote_processing_consent` must be literal `true`. See [VIDEO_GENERATION_MILESTONE2.md](VIDEO_GENERATION_MILESTONE2.md).

Upload records and original reference images live under `project_data/video_generation_uploads/<uuid>/`. In-memory job status is scoped to the running server, while downloaded and verified job artifacts live under `output/video_generation_jobs/<uuid>/`. Restarting clears job status, so an existing output is not exposed as completed without its corresponding live verified job record.
