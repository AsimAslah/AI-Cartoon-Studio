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
