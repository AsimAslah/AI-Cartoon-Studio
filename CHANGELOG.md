# Changelog

All notable project changes are documented here. Versions follow semantic versioning while the project remains pre-1.0.

## [0.6.0] - Unreleased

### Added

- Versioned storyboard editing, validation, reordering, UUID project persistence, and a safe single-scene Blender render queue.
- Local Malayalam source/audio preparation with validated storage, previews, provider capability discovery, and truthful job states.
- Allowlisted LTX-2.5 image-to-video integration with explicit remote consent, quota diagnostics, sanitized provider errors, and independent FFprobe output verification.
- Local Video Timeline Studio with MP4 import/upload, thumbnails, trimming, reordering, voice/music mixing, project persistence, and verified 720p/1080p export.
- Generic advertisement workflow with planned scenes, still images, title and branding cards, overlays, character-reference organization, and schema `1.1` compatibility.
- Professional editor with interactive tracks, ruler, zoom, playhead, non-destructive splitting, keyboard shortcuts, bounded undo/redo, waveforms, audio fades and synchronization, sidechain ducking, advanced transitions, visual effects, validated 3D LUTs, animated branding, and schema `1.2` compatibility.
- Installation, usage, troubleshooting, compatibility, and comprehensive v0.6.0 release documentation.

### Changed

- Application, package, OpenAPI, and UI version references are synchronized at `0.6.0`.
- Browser preview documentation now distinguishes approximate playback from the export-accurate rendered-preview pipeline.
- README and roadmap now reflect that Milestones 1–6 are merged into `main`.

### Compatibility

- Timeline project schemas `1.0`, `1.1`, and `1.2` remain readable.
- Original media, generated outputs, Blender projects, character references, and saved project files remain non-destructive local assets.
- Unknown schema versions continue to be rejected instead of guessed or silently migrated.

### Known limitations

- Browser end-to-end interaction coverage is incomplete; JavaScript model and DOM checks are not equivalent to cross-browser E2E tests.
- Browser preview is approximate. Rendered preview or final export is authoritative for transitions, LUTs, overlays, ducking, synchronization, and audio.
- The timeline supports one voice and one music track, has no arbitrary video-track gaps, and does not persist undo history across reopen/reload.
- Automatic Malayalam lip-sync and production-grade anthropomorphic character consistency are not implemented or claimed.
- The complete WOODORA advertisement still requires source-clip selection, creative editing, review, and approval.

## [0.1.0] - 2026-11-23

- First published working foundation with Blender discovery, procedural fox/forest generation, basic animation, story extraction, constrained storyboards, genuine `.blend`/PNG/MP4 outputs, tests, CI, and documentation.

[0.6.0]: https://github.com/AsimAslah/AI-Cartoon-Studio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AsimAslah/AI-Cartoon-Studio/releases/tag/v0.1.0
