# Milestone 7 — End-to-End Testing and Production Reliability

Milestone 7 adds real browser and local-media verification without changing the v0.6.0 feature claims. The test harness never calls paid APIs, remote inference, Blender, or user-owned runtime directories.

## Browser matrix

- Chromium desktop
- Firefox desktop
- WebKit desktop
- Chromium mobile viewport with touch enabled

Cross-browser smoke tests verify startup, responsive layout, labelled controls, keyboard focus, and accessible timeline semantics. The full editing, persistence, security, and export paths run once in Chromium to keep CPU and CI time bounded. Mouse drag/reorder, touch seeking, and keyboard editing are real Playwright input events rather than direct model calls.

## Covered workflows

- Upload two deterministic MP4 fixtures and import a preserved generated-job clip.
- Drag/reorder, zoom, seek, split, trim, undo/redo, and use keyboard shortcuts.
- Apply transitions, overlays, saturation, logo media, and a validated identity LUT.
- Upload voice/music fixtures and configure offsets, synchronization, fades, and ducking.
- Save, reload, reopen, and edit a schema 1.2 project; existing Python coverage continues to verify schemas 1.0 and 1.1.
- Reject and report a corrupt unknown-schema project while leaving its bytes unchanged.
- Run approximate preview and export-accurate rendered preview.
- Export real 1280×720 and 1920×1080 MP4 files and verify H.264 video, AAC audio, duration, resolution, and frame rate with FFprobe.
- Reject invalid extensions, oversized media, traversal identifiers, command-like filenames, and remote inference without explicit consent.
- Verify duplicate active export submissions share one job, failed jobs clean temporary state and remain retryable, and representative media copies stay within a bounded Python allocation budget.

## Isolation and evidence

Run tests through the wrapper:

```powershell
npm ci
npx playwright install chromium firefox webkit
npm run test:e2e
```

The wrapper creates `AI_CARTOON_E2E_ROOT` beneath the operating-system temporary directory before the server starts. Application runtime storage, fixtures, projects, uploads, and exports all stay beneath that root. Global teardown removes it. The repository's `images/`, `videos/`, `audio/`, `output/`, and `project_data/` are not test targets.

Playwright retains a screenshot, trace, and video for a failure. GitHub Actions uploads those ignored paths only when the browser job fails.

## Reliability behavior

Only one queued or running export is allowed per saved timeline project. A duplicate submission returns the existing job identifier. A completed or failed job never prevents a deliberate retry. Export status remains stage-based; no synthetic percentages are introduced.

## Dependency warning review

The local environment contains both `httpx` (used by optional Gradio tooling) and `httpx2` (used by the current FastAPI/Starlette test client). They have different downstream consumers and are not forcibly substituted. Milestone 7 does not suppress dependency warnings; the verification report records any warning that actually appears.

## Known limits

- Cross-browser smoke coverage is broader than the full workflow, which runs once in Chromium.
- Mobile automation verifies touch seeking and responsive usability; it does not claim exhaustive physical-device drag behavior.
- Browser preview remains approximate. Rendered preview/final export is authoritative for FFmpeg filters and audio.
- Only one voice and one music track are supported; arbitrary video-track gaps and persisted undo history remain unsupported.
- Automatic Malayalam lip-sync remains unimplemented and requires manual visible verification on the target character.
