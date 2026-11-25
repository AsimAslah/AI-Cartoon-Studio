# Troubleshooting

## Python cannot import a dependency

Activate the repository environment before running the application or tests:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Confirm `python -c "import sys; print(sys.executable)"` points inside `.venv`. Do not solve dependency problems by deleting `project_data/`, `output/`, or media folders.

## Blender is unavailable

Install a supported Blender version in its standard Windows location or verify the configured executable. The web editor and timeline can still start without Blender, but deterministic 3D render actions remain unavailable. A render is successful only when the expected output exists and validates.

## FFmpeg or FFprobe is unavailable

Run `ffmpeg -version` and `ffprobe -version` in the same activated shell used to start Uvicorn. Add the trusted installation directory to `PATH`, restart the shell, and reload capabilities. Timeline upload, waveforms, rendered preview, and export require these tools.

## Text does not render correctly

Malayalam overlays require a trusted installed font such as Nirmala UI on Windows or DejaVu Sans where its glyph coverage is sufficient. The application does not accept arbitrary uploaded font paths. Render a short preview and visually inspect the result before final export.

## Browser preview differs from export

This is expected for LUTs, exact transitions, signal-driven ducking, audio mixing, and some overlay timing. Browser preview is approximate. Use **Rendered preview** or final export for authoritative review.

## Timeline export fails

- Confirm every required video/still scene has validated media.
- Keep trims, transitions, fades, audio markers, and synchronization offsets within source and timeline duration.
- Confirm LUT files are bounded UTF-8 3D `.cube` files with an exact row count.
- Check free disk space in `output/` and confirm FFmpeg/FFprobe remain available.
- Preserve source assets; retry with a new export job rather than overwriting originals.

## An older project will not open

Timeline schemas `1.0`, `1.1`, and `1.2` are supported. Unknown or corrupt schemas are rejected intentionally. Do not edit a version field to bypass validation. Restore a known-good backup or inspect the validation warning while preserving the original file.

## Remote AI video is unavailable

The provider is optional and disabled by default. Verify the optional dependencies, explicit token, allowlisted provider schema, quota, FFprobe, and the consent disclosure. Do not reuse cached credentials implicitly. Quota or provider errors do not justify repeated submissions without reviewing cost and limits.

## Lip-sync generation is unavailable

This is an expected limitation. The current feature prepares validated local inputs and provider contracts; it does not include a production-ready real lip-sync provider. Do not describe audio attachment or validation as lip-sync.

## Pointer or keyboard editing behaves differently across browsers

Milestone 7 exercises current Playwright Chromium, Firefox, and WebKit engines, including mobile Chromium touch input. This does not guarantee every vendor build or device. Save the project frequently, use rendered preview for production review, and report the browser/version and exact interaction. Failure screenshots, video, and traces are retained locally and uploaded by CI only when the E2E job fails.

If browser tests cannot start, run `npx playwright install chromium firefox webkit`, confirm Node.js 24, and confirm FFmpeg/FFprobe are on `PATH`. `npm run test:e2e` must be used so the isolated runtime directory is created automatically.
