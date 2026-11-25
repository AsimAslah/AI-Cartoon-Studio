# Installation and requirements

## Supported environment

- Windows 11 is the currently tested desktop platform.
- Python 3.10 or newer is required; CI verifies Python 3.11.
- Blender 4.2+ or 5.x is required only for deterministic 3D scene rendering.
- FFmpeg and FFprobe on `PATH` are required for timeline media validation, thumbnails, waveforms, rendered previews, and MP4 export.
- Node.js 24 is used for JavaScript checks and Playwright browser E2E tests.
- CPU-only operation is supported. CUDA is not required for Blender foundation renders or local FFmpeg editing.

Remote AI video is optional and disabled unless explicitly configured. It can consume external quota and send media to a provider. Review provider pricing, privacy, model licensing, and credentials before enabling it.

## Install

```powershell
git clone https://github.com/AsimAslah/AI-Cartoon-Studio.git
cd AI-Cartoon-Studio
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Confirm local tools where applicable:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

Blender may be discovered from the standard Windows installation directory. Keep renders CPU/integrated-GPU friendly unless you intentionally change the Blender scene settings.

## Optional AI-video client

Install the optional client only if you intend to use the reviewed remote integration:

```powershell
python -m pip install -r requirements-video.txt
```

This does not enable inference by itself. The application requires an explicit token, allowlisted provider configuration, literal user consent for a request, sufficient quota, and FFprobe. Never commit tokens or place them in browser code.

## Start locally

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Do not expose mutation endpoints publicly; the sensitive media workflows are designed for loopback use.

## Verify the installation

```powershell
python -m pytest
python -m compileall -q app scripts tests
node --check app/static/js/app.js
node --check app/static/js/timeline-model.js
node --check app/static/js/timeline.js
```

The stable v0.6.0 baseline contains 154 Python tests. To install and run the Milestone 7 browser suite:

```powershell
npm ci
npx playwright install chromium firefox webkit
npm run test:e2e
```

Playwright downloads separate browser binaries. The suite requires local FFmpeg and FFprobe, creates deterministic media fixtures beneath an operating-system temporary directory, and removes that directory after the run. It does not use paid inference, remote GPU services, or expensive Blender renders.

## Local data

- Saved projects and uploaded references live under `project_data/`.
- Generated and rendered outputs live under `output/`.
- User-authored source folders include `images/`, `videos/`, and `audio/`.

These paths are not installation caches. Back them up before moving the repository, and never delete them as part of dependency troubleshooting.
