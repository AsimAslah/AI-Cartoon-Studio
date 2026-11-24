# Malayalam Lip-Sync Studio — Milestone 1

Milestone 1 provides a working local preparation workflow and honest provider boundary. It does **not** perform lip-sync inference.

## Working workflow

1. Select `portrait` for PNG/JPEG or `video` for MP4.
2. Select the original Malayalam WAV/MP3. The language contract is fixed to `ml`; the application does not translate or replace it.
3. Preview both files in the browser.
4. Select **Validate media** for filename, extension, size, and common signature checks.
5. Select **Save prepared upload** to persist the exact bytes under `project_data/lipsync_uploads/<uuid>/` and preview them through safe UUID routes.
6. Inspect provider availability. Generation is disabled when no real provider is configured.

A `VALIDATED` result means only that the upload envelope passed preliminary checks. It does not mean the media was fully decoded, a face was detected, audio duration was confirmed, or lip-sync occurred.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/lipsync/capabilities` | Modes, limits, candidate providers, availability, cost and animal-support warnings |
| `POST` | `/api/lipsync/validate` | Validate source and Malayalam audio without saving |
| `POST` | `/api/lipsync/uploads` | Validate and atomically save a prepared upload (`201`) |
| `GET` | `/api/lipsync/uploads/{upload_id}` | Read validated metadata |
| `GET` | `/api/lipsync/uploads/{upload_id}/media/source` | Local preview of the stored image/video |
| `GET` | `/api/lipsync/uploads/{upload_id}/media/audio` | Local playback of the unchanged audio |
| `POST` | `/api/lipsync/jobs` | Submit only to a registered real provider; currently returns `503` before creating a job |
| `GET` | `/api/lipsync/jobs/{job_id}` | Read truthful state for a real submitted job |
| `GET` | `/api/lipsync/jobs/{job_id}/output` | Download only a completed, verified MP4 |

Upload and preview routes accept loopback clients only. Run `uvicorn app.main:app --reload` on its default `127.0.0.1`; do not expose the development server publicly.

## Job contract

The provider-neutral lifecycle is `QUEUED → PREPARING → SUBMITTING → PROCESSING → VERIFYING → COMPLETED`, with `FAILED` on any captured exception. There are no invented percentages. A provider must declare real inference and compatible input modes before a job ID is created. The output must remain inside its UUID job directory and pass MP4-envelope validation.

Production currently registers no provider runtime. Unit tests inject a fake adapter to test state transitions and failure handling; those tests are not model inference.

## Security and storage

- Source limits: 10 MB image or 100 MB MP4; audio limit: 20 MB.
- Only safe basenames and PNG/JPEG/MP4 plus WAV/MP3 signatures are accepted.
- Canonical UUIDs select records; filenames never select arbitrary paths.
- Files are written through same-directory temporary files and `os.replace`.
- Stored byte counts are checked before preview or inference.
- Uploaded media is never executed.
- No credentials are stored, no provider receives media, and no charge can occur in this milestone.

## Known limitations

- Signature checks are not full codec, frame, duration, or playability decoding.
- No local CUDA-compatible GPU is present.
- No external endpoint or API key is configured.
- Human-face model behavior does not establish support for lions, goats, tigers, or dogs.
- No successful WOODORA mouth-motion demonstration has occurred.

## Verification

```powershell
python -m pytest tests/test_lipsync_contract.py tests/test_lipsync_api.py tests/test_lipsync_store.py tests/test_lipsync_jobs.py
python -m pytest
python -m compileall -q app scripts tests
uvicorn app.main:app --reload
```

