# Agent guidance

- Preserve user-authored media in `images/`, `videos/`, `audio/`, and `output/`.
- Keep Blender subprocess calls argument-based with `shell=False`.
- Do not claim a render succeeded unless expected files are present and verified.
- Keep default renders CPU/integrated-GPU friendly and low resolution.
- Separate deterministic working features from future AI-assisted capabilities.
- Never push, merge, publish, or change remote repository settings without explicit approval.
- Keep storyboard and project schema versions explicit; reject unknown versions instead of guessing migrations.
- Project IDs must remain canonical UUIDs and project writes must stay inside `project_data/` using atomic replacement.
- Do not report render percentages; expose only process-backed render stages and verified outputs.
- Multi-scene editing and persistence are supported, but do not claim multi-scene video sequencing until implemented.
- Preserve Malayalam text and audio exactly; never translate, replace, or synthesize it without an explicit user action.
- Do not call audio attachment, remuxing, mocks, or passing validation "lip-sync". Completion requires a real provider and verified MP4 output.
- Keep lip-sync uploads in canonical UUID directories under `project_data/lipsync_uploads/`; never execute uploaded media.
- Do not enable paid or external inference without explicit approval, cost disclosure, credential protection, and provider/license review.
- Treat anthropomorphic animal lip-sync as experimental until visible mouth synchronization is demonstrated on the target character.
- Keep AI-video uploads and jobs in canonical UUID directories under `project_data/video_generation_*`; preserve original images and never fetch arbitrary remote URLs.
- Allowlist and runtime-verify remote inference schemas. Never reuse cached credentials implicitly, expose tokens to the browser, submit on startup, or call provider inference without explicit user consent.
- Do not call a remote response successful until its local MP4 passes independent `ffprobe` metadata validation, and do not claim character consistency without visual inspection.
