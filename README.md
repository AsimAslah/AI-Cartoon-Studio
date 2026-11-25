# AI Cartoon Studio 3D

[![CI](https://github.com/AsimAslah/AI-Cartoon-Studio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AsimAslah/AI-Cartoon-Studio/actions/workflows/ci.yml)

An open-source, local-first 3D cartoon and video production studio powered by Blender, Python, FastAPI, FFmpeg, and FFprobe. It combines deterministic 3D rendering, versioned storyboards and projects, explicitly consented AI-video integration, and a non-destructive professional video timeline.

> Release status: [v0.6.0](https://github.com/AsimAslah/AI-Cartoon-Studio/releases/tag/v0.6.0) is the current stable release and contains Milestones 1–6. Milestone 7 browser E2E and reliability work is under development. **One real LTX-2.5 MP4 is technically verified; automatic Malayalam lip-sync, production-grade character consistency, and the completed WOODORA advertisement remain unfinished.**

![Genuine Blender preview](images/preview.png)

## Working features

- Automatic Blender discovery on Windows and safe background subprocess execution
- Procedural orange fox with white belly, eyes, four legs, tail, and blue backpack
- Procedural magical forest, glowing stone, lighting, camera, and keyframed motion
- Genuine editable `.blend`, 640×360 PNG, and short MP4 output
- Direct story entry and validated TXT, text-PDF, and DOCX upload (5 MB limit)
- Deterministic storyboard editing, schema validation, UUID project persistence, and a safe single-scene Blender render queue
- Validated user uploads for characters, images, MP4 clips, Malayalam voice audio, music, logos, and 3D `.cube` LUTs
- Optional, explicitly consented LTX-2.5 image-to-video integration with independent FFprobe output validation
- Advertisement planning, character-reference organization, title/branding cards, and non-destructive timeline projects
- Professional timeline editing with trimming, splitting, transitions, waveforms, audio synchronization, ducking, visual effects, and animated branding
- Independently validated local H.264/AAC exports at 720p and 1080p
- Responsive FastAPI web interface, 154 stable-release Python tests, and an isolated Milestone 7 browser/reliability test suite

## Storyboard editor and project persistence

The versioned storyboard and project workflow is merged into `main` and included in v0.6.0:

- Edit descriptions, narration, optional dialogue, supported characters/actions, environments, and durations
- Add, delete, and reorder scenes with versioned schema validation
- Create, list, reopen, and update local JSON projects using UUIDs and atomic writes
- Reject corrupt data, unsupported schema versions, unsafe project IDs, unsupported assets, and invalid scene order
- Submit a validated single scene to a one-worker Blender render queue
- Report honest `QUEUED`, `PREPARING`, `STARTING_BLENDER`, `RENDERING`, `FINALIZING`, `COMPLETED`, and `FAILED` states
- Preview and download an MP4 only after genuine output validation

## Project status

- **RELEASED:** v0.6.0 contains the procedural Blender foundation and Milestones 1–6.
- **MERGED:** Storyboard editing, versioned validation, atomic UUID project persistence, and the safe single-scene render queue.
- **MERGED, EXPERIMENTAL:** Malayalam lip-sync preparation—validated local uploads, previews, provider discovery, and truthful job contracts. No real lip-sync provider output is claimed.
- **TECHNICALLY VERIFIED, VISUALLY LIMITED:** AI Video Studio produced one genuine LTX-2.5 MP4 that passed independent `ffprobe` validation and frame inspection. The short convoy clip has visible identity and composition limitations.
- **MERGED:** Video Timeline Studio imports or uploads multiple MP4 clips, reorders and trims them, mixes optional voice/music, persists timeline manifests, and exports normalized 720p or 1080p MP4 files with local FFmpeg.
- **MERGED:** Milestone 5 adds a reusable advertisement scene planner, still-image scenes, fades/crossfades, title and brand cards, text/logo overlays, audio offsets, and an organizational character-reference library.
- **MERGED:** Milestone 6 adds a generic professional editor with interactive tracks, pointer drag/reorder, ruler/zoom/playhead, non-destructive splitting, waveforms, audio fades/synchronization/ducking, advanced transitions, color controls, validated LUTs, animated branding, and bounded undo/redo.
- **IN DEVELOPMENT:** Milestone 7 adds Playwright coverage for Chromium, Firefox, WebKit, desktop/mobile layouts, real pointer/touch/keyboard interaction, persistence, security, and independently probed local FFmpeg exports.
- **PLANNED:** shot-level character-consistency work, assembling the final reviewed WOODORA edit from the intended source clips, more reusable assets, and additional reviewed providers.

## Malayalam Lip-Sync Studio — Milestone 1

The browser can validate and preview either a character image or MP4 together with the original Malayalam WAV/MP3. **Save prepared upload** stores the exact validated bytes under an ignored UUID directory in `project_data/lipsync_uploads/`. Filenames, size limits, signatures, UUID paths, metadata, and preview retrieval are validated.

The provider selector reports researched LatentSync, MuseTalk, and external-GPU options, but none is configured on the default integrated-Radeon system. Generation stays disabled and no model is downloaded, no cloud media is sent, and no paid call is made. A passing validation is not proof of lip-sync. See [Milestone 1](docs/LIPSYNC_MILESTONE1.md) and [provider research](docs/LIPSYNC_PROVIDER_RESEARCH.md).

## AI Video Studio — Milestone 2

The new studio securely stores a PNG/JPEG/WebP reference, accepts a motion prompt, exposes only settings published by the official `Lightricks/LTX-2.5` Gradio `/run` endpoint, and requires explicit consent before remote submission. Jobs record genuine provider states and event IDs. A returned MP4 is not marked complete until `ffprobe` verifies its stream, resolution, frame rate, duration, and codec.

The adapter is disabled by default and unit-tested with mocks. A separately approved real request has now produced one 1024×576, approximately one-second H.264 MP4. The file passed independent FFprobe and frame-level inspection, but the exterior convoy shot does not satisfy all requested interior composition, wristwatch-action, or character-consistency goals. See [Milestone 2.7 real-generation evidence](docs/MILESTONE2_7_REAL_GENERATION.md), [Milestone 2 setup](docs/VIDEO_GENERATION_MILESTONE2.md), and [provider research](docs/VIDEO_PROVIDER_RESEARCH.md).

Milestone 2.6 adds a read-only ZeroGPU quota display, precise sanitized provider-error categories, and a one-attempt low-resource diagnostic preset. Selecting or refreshing diagnostics never starts inference. The first failed live attempts did not produce an MP4, and their earlier combined error message is insufficient to prove whether quota, reservation size, rate limiting, or queue capacity was responsible. See [generation diagnostics](docs/MILESTONE2_6_GENERATION_DIAGNOSTICS.md).

## Video Timeline Studio — Milestone 4

The web interface can upload multiple MP4 clips or copy previously verified AI-video job outputs into isolated UUID media directories without modifying the originals. It shows FFmpeg-derived duration, dimensions, codec, and a generated thumbnail; clips can be reordered, trimmed, volume-adjusted, and previewed individually or as a browser-driven sequence.

Timeline projects use manifest schema `1.0` and atomic local JSON writes. Export normalizes every clip to 30 fps, stereo AAC, H.264, and either 1280×720 or 1920×1080 before concatenation. Optional Malayalam voice recordings and background music are mixed at user-selected volumes. The result is exposed only after MP4-envelope and independent FFprobe validation. Export stages are process-backed and do not invent percentages. See [Milestone 4 documentation](docs/TIMELINE_STUDIO_MILESTONE4.md).

This is a local editor, not Malayalam lip-sync. The current browser sequence preview provides an approximate voice/music mix; it does not reproduce signal-driven ducking, LUT processing, or every FFmpeg transition exactly. Use **Rendered preview** or final export for authoritative review. The feature does not claim that the final WOODORA advertisement has been assembled or creatively approved.

## Cinematic Advertisement Workflow — Milestone 5

Milestone 5 extends the existing Timeline Studio rather than replacing it. An optional **WOODORA — Sheru Bhai Grand Arrival** template creates ten ordered scene slots with the requested descriptions. Nine media scenes begin explicitly unassigned; the final brand card contains only configured text. Saving a plan never generates footage, and export rejects every unassigned media scene. The Malayalam-dialogue slot also rejects assigned footage unless the user explicitly confirms that visible lip-sync was actually verified.

PNG, JPEG, and WebP images can be assigned as duration-controlled scenes alongside MP4 clips. Local FFmpeg supports bounded fades, fade crossfades, fixed-position logo overlays, safe text-file overlays using a trusted system font, title/branding cards, and bounded brightness/contrast. Original scene audio, one Malayalam voice recording, and one music track have independent volume controls; voice and music can start at validated timeline offsets.

The generic Character Reference Library stores names, descriptions, clothing/accessories, notes, and validated images. Sheru Bhai and the Doberman chauffeur are optional starter metadata, not hardcoded generation subjects. References organize assets and do not guarantee identity consistency. See [Milestone 5](docs/MILESTONE5_AD_WORKFLOW.md).

## Professional Video Editing Studio — Milestone 6

Milestone 6 remains local and non-destructive while making the editor useful beyond advertisements: cartoons, animated stories, educational videos, and generic uploaded characters use the same scene and track model. The visual timeline includes a time ruler, adjustable zoom, playhead seeking, pointer-based mouse/touch reordering, non-destructive splitting, keyboard shortcuts, video/voice/music tracks, and a bounded 50-step undo/redo history.

Voice and music uploads receive local waveform images. Audio settings now include source and timeline markers, sync offsets, fades, scene alignment, volumes, and optional automatic sidechain music ducking during voice. Visual controls include saturation, exposure, temperature, seven validated transition presets, local `.cube` LUTs, logo fades, animated text presets, lower thirds, and custom normalized text positions.

The browser preview is intentionally labeled **approximate**. It previews ordering, trims, seeking, basic effects, branding, and an approximate audio mix. **Rendered preview** runs the exact FFmpeg export pipeline and is the authoritative review for transitions, LUTs, overlays, ducking, synchronization, and final audio. See the [Milestone 6 technical notes](docs/MILESTONE6_PROFESSIONAL_EDITOR.md) and [user guide](docs/PROFESSIONAL_EDITOR_USER_GUIDE.md).

## Installation and requirements

The tested desktop environment is Windows 11 with Python 3.10 or newer. Blender 4.2+ or 5.x is required for deterministic 3D rendering. FFmpeg and FFprobe on `PATH` are required for timeline import, waveform generation, rendered previews, and 720p/1080p export. CPU-only editing and export are supported; CUDA is not required.

```powershell
cd C:\path\to\AI-Cartoon-Studio
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Keep the server bound to loopback; lip-sync and AI-video mutation endpoints reject non-local clients. The optional remote AI-video client is installed separately from `requirements-video.txt` and still requires explicit configuration, consent, provider/license review, and available quota. Scanned PDFs need OCR and are rejected when no selectable text is present.

Detailed instructions:

- [Installation and requirements](docs/INSTALLATION.md)
- [User guide](docs/USAGE.md)
- [Professional editor guide](docs/PROFESSIONAL_EDITOR_USER_GUIDE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

### Storyboard and saved projects

Generate scenes, edit their fields, use the arrow controls to reorder them, then select **Validate storyboard**. Project JSON files are stored locally in the ignored `project_data/` directory. **Save project** creates a UUID-backed project; subsequent saves update it atomically. **New copy** creates a new ID on the next save.

Rendering currently accepts exactly one supported scene lasting 1–10 seconds. Multi-scene storyboards can be edited and saved, but video sequencing is not yet implemented and is never silently replaced by the fixed demonstration.

## Render the demonstration

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe' --background --factory-startup --python scripts\fox_scene.py -- --output-dir output
```

This writes `output/forest_fox.blend`, `output/preview.png`, and `output/first_cartoon.mp4`. Rendering is intentionally short and low resolution for laptop hardware. Blender bundles the FFmpeg encoder used by this script; a separate FFmpeg executable is not required for this milestone.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
python -m compileall -q app scripts tests
node --check app/static/js/app.js
node --check app/static/js/timeline-model.js
node --check app/static/js/timeline.js
```

The verified v0.6.0 baseline contains 154 Python tests. Milestone 7 adds reliability tests plus real browser automation in isolated operating-system temporary directories:

```powershell
npm ci
npx playwright install chromium firefox webkit
npm run test:e2e
```

The Playwright suite covers all three browser engines, a mobile Chromium viewport, real mouse/touch/keyboard input, project reload, validation failures, and real 720p/1080p FFmpeg exports checked with FFprobe. Comprehensive editing and export scenarios run once in Chromium while cross-browser smoke, accessibility, and responsive checks run in Chromium, Firefox, and WebKit. Tests do not run Blender or call remote inference.

## Architecture

FastAPI owns validation and the browser workflow. Deterministic services extract documents and map supported phrases into a typed storyboard. The Blender runner launches a self-contained `bpy` script, which creates assets, animation, and verified output. See [architecture](docs/ARCHITECTURE.md) and the [roadmap](docs/ROADMAP.md).

The versioned HTTP API is documented in [docs/API.md](docs/API.md). Lip-sync preparation and AI Video Milestone 2 have dedicated documentation. Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs` while the server is running. Release history is recorded in [CHANGELOG.md](CHANGELOG.md).

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE). The CI badge reflects GitHub Actions status only; it is not a GitHub profile achievement.
