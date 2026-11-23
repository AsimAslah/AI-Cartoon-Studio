# AI Video Studio — Milestone 2

## Status

- **Implemented:** secure reference-image upload, prompt and supported LTX settings, explicit remote-processing consent, provider capability reporting, one-worker jobs, truthful queue states, verified MP4 gating, metadata, preview, and download.
- **Tested with mocks:** exact Gradio request mapping, schema-change detection, authentication/quota/timeout failures, job lifecycle, storage safety, and HTTP API compatibility.
- **Not verified with real inference:** no quota-consuming request was submitted. No generated MP4 or visual Woodora quality claim is made.

This feature uses real remote inference when configured. It does not substitute Blender motion, CSS animation, zooming, panning, duplicated frames, or interpolation for AI video generation.

## Provider

The only allowlisted Milestone 2 provider is the official `Lightricks/LTX-2.5` Hugging Face Gradio Space, using its named `/run` endpoint and `Lightricks/LTX-2.5-Diffusers` model identity. The server validates the Space's published schema before every submission and refuses unknown Spaces or endpoints.

Supported inputs mirror the reviewed API schema:

- PNG, JPEG, or WebP reference image, at most 20 MB
- prompt, 10–4,000 characters
- 512–1536 pixel width and height in multiples of 64
- 1–5 second duration
- `diffusion` or `conv` decoder
- seed/randomize seed, automatic prompt length, and prompt enhancement

The provider does not expose a negative prompt or audio-generation control through this endpoint, so the UI does not invent them.

## Install and configure

The application remains usable without this optional provider. Install only the lightweight client; this does not download LTX model weights:

```powershell
cd C:\Users\asima\Documents\AI-Cartoon-Studio
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-video.txt
```

Install FFmpeg separately and make `ffprobe.exe` available on `PATH`, or set an exact executable path. Then set configuration in the same terminal:

```powershell
$env:AI_CARTOON_ENABLE_REMOTE_VIDEO = '1'
$env:AI_CARTOON_HF_TOKEN = 'hf_your_token_here'
$env:AI_CARTOON_FFPROBE_PATH = 'C:\path\to\ffprobe.exe'
$env:AI_CARTOON_VIDEO_TIMEOUT_SECONDS = '900'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`AI_CARTOON_HF_SPACE` may be omitted; its safe default is `Lightricks/LTX-2.5`. `AI_CARTOON_HF_API_NAME` may be omitted; its safe default is `/run`. Any other value is rejected in this milestone. The token must be provided explicitly: the application does not fall back to Hugging Face credentials cached by another program. Never put the token in JavaScript, Git, `.env` files committed to Git, screenshots, or issue text.

Generation remains unavailable unless all of these are true:

1. remote generation is explicitly enabled;
2. `AI_CARTOON_HF_TOKEN` is set;
3. `gradio_client` is installed; and
4. `ffprobe` is available.

## User workflow

1. Open `http://127.0.0.1:8000`.
2. Drop a PNG/JPEG/WebP into **AI Video Studio**. The original bytes are stored locally under a UUID directory.
3. Describe motion and choose only settings supported by LTX-2.5.
4. Read and select the remote-processing consent checkbox. This is the point at which the user authorizes sending the image and prompt to Hugging Face.
5. Select **GENERATE VIDEO**. Nothing is submitted on startup or page load.
6. Watch actual lifecycle states. No invented percentage is displayed.
7. On success, inspect provider/model/job identifiers, prompt, seed, duration, resolution, frame rate, and codec; then preview or download the MP4.

`COMPLETED` is recorded only after the returned file is local, nonempty, MP4-shaped, inside its job directory, and successfully decoded by `ffprobe`. An HTTP success response alone is insufficient.

## Character-consistency guidance

Use one clear subject description, repeat identity-defining facial/fur features and clothing, describe accessories precisely, request a continuous shot and subtle physically plausible movement, and explicitly discourage additional characters or scene changes in the prompt. LTX can still change faces, limbs, clothing, props, or backgrounds. Single-image conditioning cannot guarantee identity consistency; multi-reference conditioning is a future milestone.

## Quotas, cost, privacy, and licensing

The Hugging Face Space runs on server-side GPU infrastructure. Availability, queues, ZeroGPU quota, and prepaid usage are controlled by Hugging Face and can change. A job may consume daily quota or paid credits. The application never creates paid infrastructure, retries indefinitely, or starts a generation without a user click.

The reference image and prompt leave the local computer. Do not upload media you lack permission to share. Application code and model weights can have different licenses; review the current LTX model card/community license and Hugging Face terms before commercial use. This repository's MIT license does not grant rights to provider services, model weights, input media, or generated content.

## Manual verification

No live request was made during implementation. After approving quota use, perform one short 1–3 second request first. Confirm that the UI shows a real provider event ID, the returned MP4 plays, metadata matches `ffprobe`, and the output is genuinely synthesized motion rather than a static transform. For the Woodora proof of concept, visually check Sheru Bhai, the wristwatch motion, Doberman identity, vehicle interior, moving exterior, and absence of unexpected characters. Record failures as model-quality findings; do not relabel them as passing.

## Data locations

- uploads: `project_data/video_generation_uploads/<uuid>/`
- jobs and verified results: `project_data/video_generation_jobs/<uuid>/`

Both locations are local, ignored runtime data. Existing Blender projects, lip-sync uploads, and generated videos are not deleted or overwritten.
