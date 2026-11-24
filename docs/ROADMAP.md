# Roadmap

## Released

- **v0.1.0 — Working 3D cartoon foundation (released 2026-11-23):** Blender discovery, procedural fox and forest, basic animation, editable `.blend`, PNG/MP4 demonstration output, story extraction, tests, CI, and the first public release.

## Merged into `main` and included in the v0.6.0 release candidate

- **Storyboard editor and project persistence:** versioned scene editing, validation, reordering, atomic UUID JSON project storage, single-scene deterministic rendering, and process-backed render states. Multi-scene storyboard editing is supported; the Blender renderer still accepts exactly one supported scene per job.
- **Malayalam lip-sync preparation:** local-only image/video/audio validation, UUID storage, browser previews, provider discovery, and truthful background-job contracts. No configured real provider, verified anthropomorphic-animal synchronization, or production-ready lip-sync output is claimed.
- **AI Video Studio Milestones 2–2.7:** secure reference uploads, an allowlisted LTX-2.5 Gradio adapter, explicit remote consent, provider schema verification, quota diagnostics, truthful jobs, and independent FFprobe output gating. One real 1024×576 MP4 is technically verified, but it has composition and character-consistency limitations.
- **Video Timeline Studio — Milestone 4:** local MP4 upload/import, FFprobe metadata, thumbnails, reorder/trim/preview, optional voice/music mixing, versioned persistence, and independently verified 720p/1080p FFmpeg export.
- **Cinematic Advertisement Workflow — Milestone 5:** optional ten-scene WOODORA planner, still-image scenes, safe titles/text/logo overlays, fades/crossfades, visual adjustments, audio offsets, character-reference records, and additive schema `1.1` persistence. Planned scenes are never represented as generated media.
- **Professional Video Editing Studio — Milestone 6:** interactive multi-track timeline, pointer reordering, zoom/ruler/playhead, non-destructive split/trim, shortcuts, bounded undo/redo, waveforms, synchronized voice/music with fades and sidechain ducking, export-accurate rendered preview, advanced transitions, color effects, validated 3D `.cube` LUTs, animated branding, and additive schema `1.2` persistence. Schemas `1.0` and `1.1` remain readable.

## v0.6.0 release preparation

- Synchronize application and package version metadata.
- Publish accurate installation, usage, API, troubleshooting, compatibility, and limitation documentation.
- Verify all automated tests, compilation, JavaScript syntax, dependency consistency, credentials, and generated-asset exclusions.
- Prepare release notes covering every merged change since v0.1.0.

Only v0.1.0 is currently published. v0.6.0 must not be tagged or published until its release-preparation pull request is reviewed and separately approved.

## Future development

- Cross-browser end-to-end tests for pointer/touch timeline editing, playback, keyboard focus, and persistence workflows.
- More than one voice/music track, arbitrary timeline gaps, and persisted undo history.
- Shot-level character-consistency tooling and reviewed reusable asset packs.
- Creative assembly and approval of the complete WOODORA advertisement from intended source clips.
- A real, licensed lip-sync provider with verified Malayalam timing and visible mouth synchronization on the target anthropomorphic character.
- Additional video providers only after hardware, privacy, cost, schema, and license review.
- **v1.0:** reproducible setup, stable compatibility commitments, polished UX, expanded browser coverage, and fully documented limitations.
