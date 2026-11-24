# AI Cartoon Studio 3D v0.6.0 — Professional Video Editing Studio

Status: release candidate prepared from Milestones 1–6; not tagged or published.

v0.6.0 consolidates all merged work since v0.1.0 into a local-first cartoon and video production environment. It preserves the deterministic Blender foundation while adding versioned project editing, reviewed AI-video integration, advertisement planning, and a professional FFmpeg timeline.

## Highlights since v0.1.0

### Storyboards, projects, and Blender

- Edit, validate, add, remove, and reorder versioned storyboard scenes.
- Save and reopen canonical UUID projects through atomic replacement under `project_data/`.
- Queue a supported single scene for genuine Blender rendering with process-backed stages and verified outputs.
- Preserve the procedural fox, magical forest, editable `.blend`, preview PNG, and demonstration MP4 workflow.

### Local media and character organization

- Upload validated user images, MP4 clips, voice recordings, music, logos, and LUTs into isolated UUID stores.
- Organize generic character references with descriptions, clothing/accessories, notes, and validated images.
- Preserve originals and reject arbitrary remote URLs, unsafe paths, changed files, corrupt metadata, and unknown schemas.

### AI Video Studio

- Store validated PNG/JPEG/WebP references and expose only reviewed LTX-2.5 settings.
- Require explicit remote-processing consent and protected provider credentials.
- Report real provider states, quota diagnostics, sanitized failures, and event identifiers.
- Mark downloaded output complete only after independent FFprobe validation.
- Document one technically verified 1024×576 MP4 without claiming reliable composition or character consistency.

### Advertisement and professional timeline

- Plan advertisements with unassigned scene slots, still images, title/branding cards, overlays, and optional character references.
- Upload or import multiple clips, inspect thumbnails/durations, reorder, trim, split, and save timeline projects.
- Use video, voice, and music tracks with waveforms, source/timeline markers, synchronization offsets, fades, volume, scene alignment, and adjustable sidechain ducking.
- Apply crossfade, black/white fade, dissolve, slide, and zoom transitions with duration validation.
- Adjust brightness, contrast, saturation, exposure, and temperature; optionally apply a validated local 3D `.cube` LUT.
- Add logo fades, title cards, lower thirds, text motion presets, custom positions, and Malayalam-compatible UTF-8 text rendering.
- Distinguish approximate browser preview from export-accurate rendered preview.
- Export independently validated H.264/AAC MP4 at 1280×720 or 1920×1080.

### Compatibility and safety

- Timeline schemas `1.0`, `1.1`, and `1.2` remain readable with additive defaults.
- Unknown schemas are rejected rather than guessed or rewritten.
- FFmpeg, FFprobe, and Blender subprocesses use argument lists with `shell=False`.
- Original media, saved projects, generated outputs, and Blender files are preserved.
- CPU-only local editing/export is supported; no paid API or GPU inference is required for the editor.

## Installation

See [INSTALLATION.md](INSTALLATION.md), then start the server on `127.0.0.1`. The optional remote provider dependencies are separate and should be installed only after privacy, quota, cost, and license review.

## Verification baseline

- 154 automated tests
- Python compilation
- JavaScript syntax and DOM-independent timeline-model checks
- Schema `1.0`, `1.1`, and `1.2` compatibility
- Real local FFmpeg/FFprobe verification at 720p and 1080p
- GitHub Actions on Windows/Python 3.11

Final release publication must record the exact verification results from the reviewed release commit.

## Remaining limitations

- Automated browser E2E testing remains incomplete; DOM/model checks do not prove cross-browser pointer, touch, playback, or focus behavior.
- Browser preview is approximate; rendered preview/final export is authoritative.
- Only one voice and one music track are supported.
- Video tracks do not support arbitrary gaps.
- Undo history is bounded and is not persisted across reopen/reload.
- Transition parameters and text motion are preset-based rather than arbitrary keyframes.
- LUT import supports validated 3D `.cube` files only.
- Automatic Malayalam lip-sync is not implemented. Verification remains manual and must visibly demonstrate mouth synchronization on the target character.
- The real AI-video pipeline has produced one verified clip but does not guarantee composition or character identity.
- The complete WOODORA advertisement is not assembled or creatively approved.

## Upgrade notes

- Back up `project_data/`, `output/`, `images/`, `videos/`, and `audio/` before moving or replacing a checkout.
- Install the base dependencies from `requirements.txt` in the existing or recreated virtual environment.
- Confirm Blender and FFmpeg/FFprobe discovery after upgrading.
- Existing timeline schemas `1.0` and `1.1` open with backward-compatible defaults; opening alone does not rewrite them.
