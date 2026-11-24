# API reference — v0.6.0

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
| `GET` | `/api/video/quota` | Read the cached ZeroGPU quota/authentication state without contacting Hugging Face |
| `POST` | `/api/video/quota/refresh` | Perform one read-only authenticated ZeroGPU quota refresh; never starts inference |
| `POST` | `/api/video/uploads` | Validate and atomically store one PNG/JPEG/WebP under a UUID (`201`) |
| `GET` | `/api/video/uploads/{upload_id}` | Retrieve upload schema `1.0` metadata |
| `GET` | `/api/video/uploads/{upload_id}/image` | Preview the exact stored reference image |
| `POST` | `/api/video/jobs` | Submit an explicitly consented request to a configured provider (`202`) |
| `GET` | `/api/video/jobs/{job_id}` | Read provider-backed state, history, errors, identifiers, prompt, seed, and verified metadata |
| `GET` | `/api/video/jobs/{job_id}/output` | Download only a completed, independently verified MP4 |

Mutation and media endpoints are loopback-only. The only allowlisted provider is the official `Lightricks/LTX-2.5` Gradio Space at `/run`; arbitrary URLs, Spaces, and endpoint names are rejected. A job is unavailable unless remote processing, an explicit Hugging Face token, the optional client, and `ffprobe` are configured. `remote_processing_consent` must be literal `true`. See [VIDEO_GENERATION_MILESTONE2.md](VIDEO_GENERATION_MILESTONE2.md).

Upload records and original reference images live under `project_data/video_generation_uploads/<uuid>/`. In-memory job status is scoped to the running server, while downloaded and verified job artifacts live under `output/video_generation_jobs/<uuid>/`. Restarting clears job status, so an existing output is not exposed as completed without its corresponding live verified job record.

Quota responses include total and remaining GPU-seconds, reset timestamp, last successful refresh, and authentication/permission state. They omit over-quota/billing usage. Failed jobs expose a sanitized `error_code`, `diagnostic_code`, and public message; raw upstream exception bodies are not returned. See [MILESTONE2_6_GENERATION_DIAGNOSTICS.md](MILESTONE2_6_GENERATION_DIAGNOSTICS.md).

## Video Timeline Studio

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/timeline/capabilities` | Read local FFmpeg availability, profiles, limits, known generated-job IDs, and preview limitations |
| `POST` | `/api/timeline/media` | Validate and preserve an MP4, image, logo, character reference, voice/music track, or 3D LUT; generate applicable thumbnails/waveforms (`201`) |
| `POST` | `/api/timeline/import-generated` | Copy one fixed UUID AI-video job output into timeline storage (`201`) |
| `GET` | `/api/timeline/media/{media_id}` | Read schema `1.0` media metadata |
| `GET` | `/api/timeline/media/{media_id}/file` | Preview the preserved media bytes |
| `GET` | `/api/timeline/media/{media_id}/thumbnail` | Read a generated JPEG clip thumbnail |
| `POST` | `/api/timeline/projects` | Validate referenced media and create an atomic UUID manifest (`201`) |
| `GET` | `/api/timeline/projects` | List valid timeline manifests and skipped-corruption warnings |
| `GET` | `/api/timeline/projects/{project_id}` | Reopen a manifest only when all referenced media remains valid |
| `PUT` | `/api/timeline/projects/{project_id}` | Validate and atomically update a manifest |
| `POST` | `/api/timeline/exports` | Queue a saved project for one-worker local FFmpeg export (`202`) |
| `GET` | `/api/timeline/exports/{job_id}` | Read the actual local processing stage and sanitized error |
| `GET` | `/api/timeline/exports/{job_id}/output` | Download only a completed independently verified MP4 |

Timeline routes are loopback-only. Uploads are bounded and streamed to temporary local files; filenames never select paths. Project/media identifiers must be canonical UUIDs. The only generated-video import source is `output/video_generation_jobs/<uuid>/generated.mp4`; arbitrary local and remote paths are not accepted. Runtime media and exports are ignored by Git.

Milestone 5 adds `image`, `logo`, and `character_reference` media kinds for validated PNG/JPEG/WebP uploads, plus these routes:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/timeline/templates/woodora-grand-arrival` | Return the ten-scene unassigned WOODORA plan and optional character starters |
| `GET` | `/api/timeline/character-templates` | Return generic optional character-metadata starters |
| `POST` | `/api/timeline/characters` | Create an atomic schema `1.0` character record from validated reference-image UUIDs |
| `GET` | `/api/timeline/characters` | List valid character records and corrupt-file warnings |
| `GET` | `/api/timeline/characters/{reference_id}` | Reopen a character record |
| `PUT` | `/api/timeline/characters/{reference_id}` | Validate and atomically update a character record |

Advertisement manifests use additive schema `1.1` while schema `1.0` remains readable. They can contain unassigned planned scene slots, but export requires actual media for every video/still scene. All cinematic editing values are typed backend fields; no endpoint accepts an FFmpeg expression, font path, local path, or URL.

### Professional editor additions

Schema `1.2` adds professional transition/effect fields, `.cube` LUT references, logo/text animation parameters, voice/music source and timeline markers, sync offsets, fades, dialogue scene references, ducking, timeline zoom, and playhead state. Schemas `1.0` and `1.1` remain accepted.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/timeline/media/{media_id}/waveform` | Retrieve the locally rendered waveform PNG for a voice or music UUID |
| `POST` | `/api/timeline/previews` | Queue an export-accurate rendered preview through the exact final FFmpeg pipeline (`202`) |

`POST /api/timeline/media` also accepts the `lut` kind only for a bounded UTF-8 `.cube` file whose `LUT_3D_SIZE` and exact numeric row count validate. Professional capabilities report schema `1.2`, allowlisted transition names, waveform support, audio ducking, rendered preview, LUT support, and undo/redo availability. The rendered-preview result is retrieved through the existing export status/output routes.
