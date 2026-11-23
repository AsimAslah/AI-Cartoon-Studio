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
