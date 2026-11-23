# Malayalam Lip-Sync Engine — Step 3: FastAPI integration

> Historical Step 3 document. The router now also supports local UUID upload storage and previews; the complete current behavior is documented in [LIPSYNC_MILESTONE1.md](LIPSYNC_MILESTONE1.md). The provider-unavailable guarantee remains unchanged.

This adds a **validation-only** local FastAPI router, not a lip-sync model.
It preserves the existing Blender/storyboard application. The upstream
`Open-Generative-AI` project informed the two supported input modes, but this
step is original Python code. No MuAPI credentials, cloud calls, paid providers,
or media generation are used.

## API endpoints

- `GET /api/lipsync/capabilities`: Shows input modes, max sizes, and an explicitly
  **unconfigured** provider. `real_generation_enabled` is always `false`.
- `POST /api/lipsync/validate`: multipart fields `mode=portrait|video`,
  `source` (PNG/JPG for portrait, MP4 for video), `audio` (WAV/MP3), optional
  `character_id=sheru_bhai`, `language=ml`. Validates input metadata, preliminary
  file signatures and file-size caps. Does not save the files or create a job.
- `POST /api/lipsync/jobs`: reserved for later model integration. For valid
  input it currently responds HTTP **503**, explicitly indicating **no job
  created, no video generated, and no charge**. Invalid files respond 422.

Only local loopback clients can access upload endpoints. Run Uvicorn on the
default `127.0.0.1`, **not** `0.0.0.0` and never expose it to the internet.
No authentication has been implemented yet. API tokens, paid provider selection,
queued job management and confirmed video output are separate future work.

## Installation

Extract the Step 3 ZIP into the project's root **while on the feature branch**.
Then register the router once with `python scripts/install_lipsync_api_step3.py`.
The installer inserts a single import and `app.include_router()` into the
existing `app/main.py`, refuses unknown app layouts, and is idempotent.

Run `python -m pytest tests/test_lipsync_contract.py tests/test_lipsync_api.py -v`.
Then run the entire suite with `python -m pytest`.

To check the API manually, launch `uvicorn app.main:app --reload` from the
repository root and open `http://127.0.0.1:8000/docs` to inspect the
`/api/lipsync` endpoints. A **successful validation response does not mean
lip-sync video generation is available**.

## Security and actual model work (future)

- Current signature checks are not full media decoding. Validate actual codecs,
  audio duration, media dimensions, and frame count before any future inference.
- Uploaded multipart request bodies can reach Starlette's parser before the
  endpoint's per-file read caps. Only run this development server locally and
  add middleware/proxy request-size enforcement before public deployment.
- Build genuine job state transitions, safe media storage, cancellation,
  a verified output MP4 and provider availability checks before changing `/jobs`.
- Test Malayalam phonemes and animal-shaped muzzles. Human-face lip-sync
  models may fail on lion/goat/dog characters.
- Confirm the inference model's commercial-use license before WOODORA release.
