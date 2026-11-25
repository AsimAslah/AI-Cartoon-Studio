# Roadmap

## Released

- **v0.1.0 — Working 3D cartoon foundation (released 2026-11-23):** Blender discovery, procedural fox and forest, basic animation, editable `.blend`, PNG/MP4 demonstration output, story extraction, tests, CI, and the first public release.
- **v0.6.0 — Professional Video Editing Studio (released 2026-11-25):** all Milestones 1–6 below, versioned project compatibility, local FFmpeg editing, and verified 720p/1080p output.

## Included in v0.6.0

- **Storyboard editor and project persistence:** versioned scene editing, validation, reordering, atomic UUID JSON project storage, single-scene deterministic rendering, and process-backed render states. Multi-scene storyboard editing is supported; the Blender renderer still accepts exactly one supported scene per job.
- **Malayalam lip-sync preparation:** local-only image/video/audio validation, UUID storage, browser previews, provider discovery, and truthful background-job contracts. No configured real provider, verified anthropomorphic-animal synchronization, or production-ready lip-sync output is claimed.
- **AI Video Studio Milestones 2–2.7:** secure reference uploads, an allowlisted LTX-2.5 Gradio adapter, explicit remote consent, provider schema verification, quota diagnostics, truthful jobs, and independent FFprobe output gating. One real 1024×576 MP4 is technically verified, but it has composition and character-consistency limitations.
- **Video Timeline Studio — Milestone 4:** local MP4 upload/import, FFprobe metadata, thumbnails, reorder/trim/preview, optional voice/music mixing, versioned persistence, and independently verified 720p/1080p FFmpeg export.
- **Cinematic Advertisement Workflow — Milestone 5:** optional ten-scene WOODORA planner, still-image scenes, safe titles/text/logo overlays, fades/crossfades, visual adjustments, audio offsets, character-reference records, and additive schema `1.1` persistence. Planned scenes are never represented as generated media.
- **Professional Video Editing Studio — Milestone 6:** interactive multi-track timeline, pointer reordering, zoom/ruler/playhead, non-destructive split/trim, shortcuts, bounded undo/redo, waveforms, synchronized voice/music with fades and sidechain ducking, export-accurate rendered preview, advanced transitions, color effects, validated 3D `.cube` LUTs, animated branding, and additive schema `1.2` persistence. Schemas `1.0` and `1.1` remain readable.

## Milestone 7 — End-to-End Testing and Production Reliability

- Add isolated Playwright automation for Chromium, Firefox, WebKit, desktop layouts, and a mobile Chromium viewport.
- Exercise real mouse, touch, and keyboard timeline interactions; project save/reopen/reload; upload security; and local rendered previews/exports.
- Verify deterministic 720p and 1080p H.264/AAC exports independently with FFprobe.
- Prevent duplicate active exports for a project and verify retry cleanup, bounded media-copy memory, invalid projects, missing media, and remote-inference consent.
- Upload browser screenshots, video, and traces only when GitHub Actions E2E coverage fails.

This work is on `feat/browser-e2e-reliability` and is not part of the published v0.6.0 tag until separately reviewed and merged.

## Future development

- More than one voice/music track, arbitrary timeline gaps, and persisted undo history.
- Shot-level character-consistency tooling and reviewed reusable asset packs.
- Creative assembly and approval of the complete WOODORA advertisement from intended source clips.
- A real, licensed lip-sync provider with verified Malayalam timing and visible mouth synchronization on the target anthropomorphic character.
- Additional video providers only after hardware, privacy, cost, schema, and license review.
- **v1.0:** reproducible setup, stable compatibility commitments, polished UX, expanded browser coverage, and fully documented limitations.
