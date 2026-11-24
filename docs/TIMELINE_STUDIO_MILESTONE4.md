# Milestone 4 — Video Timeline Studio

## Implemented workflow

Video Timeline Studio provides a local, browser-based path from preserved MP4 clips to one verified timeline export:

1. Upload multiple MP4 files or import a previously generated AI-video job.
2. Inspect FFprobe-derived duration, dimensions, frame rate, codec, audio presence, and a generated thumbnail.
3. Reorder clips, set trim boundaries and clip volume, and preview an individual clip or the trimmed sequence.
4. Optionally add one original Malayalam voice recording and one background-music track in WAV, MP3, or M4A form and set their volumes.
5. Save and reopen a schema `1.0` UUID-backed project.
6. Export locally at 720p or 1080p and preview/download only the independently verified result.

The implementation never calls Hugging Face or another inference provider. It does not consume GPU quota and does not modify the original uploaded, generated, Blender, audio, or image media.

## Storage and safety

- Timeline media is copied to `project_data/timeline_media/<uuid>/`; project manifests are atomically replaced under `project_data/timeline_projects/`.
- Export jobs are isolated under `output/timeline_exports/<uuid>/`.
- Only basenames, allowlisted formats/signatures, canonical UUIDs, and configured roots are accepted.
- Generated-video import is restricted to `output/video_generation_jobs/<uuid>/generated.mp4`; no arbitrary path or URL input exists.
- FFmpeg and FFprobe receive explicit argument lists with `shell=False`.
- Unknown manifest or media schema versions are rejected.
- Source files are rechecked against their recorded byte size before use.

## Export pipeline

The one-worker export manager reports only actual stages: `QUEUED`, `VALIDATING`, `NORMALIZING`, `CONCATENATING`, optional `MIXING_AUDIO`, `VERIFYING`, `COMPLETED`, or `FAILED`.

Each trimmed clip is normalized to the selected frame size, 30 fps, H.264/YUV420P video, and stereo 48 kHz AAC audio. Silent stereo audio is supplied when a clip has no audio so normalized streams remain concat-compatible. Voice and music, when present, are resampled and mixed with the concatenated clip audio at their selected volumes. The final file must pass both an MP4-envelope check and independent FFprobe validation of duration, codec, frame rate, and selected resolution.

## Honest limitations

- The lightweight browser sequence preview switches between source clips and honors trim bounds, but it does not mix voice or music. Use the final exported preview to review the complete audio mix.
- One voice track and one music track are supported; both currently begin at timeline time zero. There are no fades, transitions, titles, color correction, waveform editing, or per-track start controls.
- Clip ordering uses accessible up/down controls rather than drag-and-drop.
- Export status survives only while the server process is running, although completed files remain in the ignored output directory.
- Timeline editing is not lip-sync. No visible Malayalam mouth synchronization is claimed.
- The tools can assemble selected clips, but this milestone does not claim that the complete WOODORA advertisement has been assembled or creatively approved.
