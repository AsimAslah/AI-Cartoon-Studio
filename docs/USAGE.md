# User guide

Start the local server as described in [INSTALLATION.md](INSTALLATION.md), then open `http://127.0.0.1:8000`.

## Storyboard and 3D cartoon workflow

1. Enter a story or upload a bounded TXT, selectable-text PDF, or DOCX file.
2. Generate the constrained storyboard and edit supported scene fields.
3. Validate and save the project. Projects use canonical UUIDs and atomic JSON writes under `project_data/`.
4. Submit one supported fox/forest scene to Blender and download only the verified output.

Multi-scene storyboards can be edited and saved, but the deterministic Blender renderer still accepts exactly one supported scene per render job. It does not silently replace unsupported work with a demonstration.

## Characters and advertisement planning

The Character Reference Library accepts validated local images with names, descriptions, clothing/accessories, and notes. It organizes references; it does not guarantee identity consistency in generated media.

The optional WOODORA template creates planned scene slots. Unassigned slots remain visibly unassigned, and export rejects required video/still slots without actual media. The system remains generic and also supports cartoons, stories, educational videos, and other advertisements.

## AI image-to-video

AI Video Studio accepts a validated local reference image and reviewed LTX-2.5 settings. Remote submission remains disabled until the optional client, explicit credential, provider availability, quota, and literal consent are present. A response is not successful until the downloaded MP4 passes independent FFprobe validation.

One real MP4 has been technically verified, but it does not prove reliable character identity, composition control, or production readiness. Never refresh diagnostics or submit inference unless you intend to contact the provider and understand quota implications.

## Professional timeline

1. Upload MP4 clips and images, or import an already verified generated clip.
2. Reorder with pointer drag, adjust zoom, seek with the playhead, and split or trim non-destructively.
3. Add a Malayalam voice recording and optional music. Adjust source/timeline markers, synchronization offsets, fades, volume, scene alignment, and ducking intensity.
4. Add validated transitions, brightness/contrast/saturation/exposure/temperature changes, an optional 3D `.cube` LUT, titles, lower thirds, logos, and animation presets.
5. Save the versioned timeline project.
6. Use browser preview for an approximation. Use rendered preview for the authoritative FFmpeg result.
7. Export the saved project as normalized H.264/AAC at 720p or 1080p. The output is exposed only after independent validation.

Original media is copied into UUID-backed stores or referenced non-destructively; editing does not overwrite the source.

## Malayalam production

Malayalam text is written to UTF-8 text files and rendered with a trusted available local font. Malayalam voice uploads are preserved exactly and can be aligned to scenes through timeline controls.

The lip-sync preparation screen validates and stores image/video plus audio inputs, but automatic lip-sync is not configured. Mark footage verified only after visibly reviewing mouth synchronization on the actual target character. Audio attachment, remuxing, or a passing file validation is not lip-sync.

## Preview and history limitations

- Browser preview is approximate and does not reproduce signal-driven ducking, LUT processing, or every FFmpeg filter exactly.
- Rendered preview and final export use the authoritative local FFmpeg pipeline.
- Undo/redo is bounded to 50 snapshots and resets on project reopen or browser reload; saved project state remains consistent.
- One voice and one music track are supported, and video clips cannot be placed with arbitrary timeline gaps.
- Automated browser E2E testing is incomplete.
