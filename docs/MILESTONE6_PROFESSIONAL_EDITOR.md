# Milestone 6 — Professional Video Editing Studio

## Verified working scope

Milestone 6 upgrades the existing local timeline without replacing its media stores, project manifests, or exporter. It remains generic: advertisement plans, animated stories, cartoons, educational scenes, and user-uploaded characters all use the same editor.

### Interactive timeline

- Video, voice, and music tracks
- Time ruler, adjustable pixel-per-second zoom, and seekable playhead
- Pointer Events drag/reorder for mouse and touch-capable browsers
- Non-destructive split at playhead and existing numeric trim controls
- Space, S, Delete/Backspace, arrow, Ctrl/Cmd+Z, and Ctrl/Cmd+Y shortcuts
- 50-step in-memory undo/redo history
- Persisted zoom and playhead with schema `1.2`

Splitting creates a second project segment referencing the same preserved media UUID and divides only trim or duration metadata.

### Audio production

FFmpeg creates a 1200×160 waveform PNG when voice or music is preserved. Voice supports source dialogue markers, an absolute timeline start/end, ±10-second synchronization adjustment, fades, volume, and scene assignment. Music supports timeline start/end, synchronization adjustment, fades, and volume.

When enabled, automatic ducking uses FFmpeg `sidechaincompress` with a bounded intensity mapped to compressor ratio. Browser preview approximates ducking with a constant reduction while voice is configured; rendered preview/final export uses the actual voice signal.

### Preview modes

- **Approximate browser preview:** ordering, trims, seeking, available scenes, basic CSS color effects, branding, transition cues, and separate local voice/music playback.
- **Export-accurate rendered preview:** the exact saved project runs through the same FFmpeg normalization, transitions, LUTs, overlays, sidechain audio graph, encoding, and FFprobe verification as final export.

Real-time parity is not claimed. Rendered preview is the authority for production review.

### Transitions, effects, and branding

Allowlisted transition presets are cut, crossfade, fade to black, fade to white, dissolve, slide left, slide right, and zoom. A transition must be shorter than both adjacent scenes, and the last scene must use cut.

Effects include brightness, contrast, saturation, exposure, and color temperature. Optional `.cube` LUTs have a 5 MB limit, canonical UUID storage, UTF-8 decoding, bounded size declaration, finite numeric values, and an exact `size³` row count. Effect reset restores neutral values without changing source media.

Branding supports secure Malayalam-compatible system fonts, title/lower-third/custom positions, fade/slide text animations, and logo fade-in/out. User-provided fonts and arbitrary filter expressions are not accepted.

## Compatibility

- Schema `1.0`: accepted with professional defaults.
- Schema `1.1`: accepted with professional defaults.
- Schema `1.2`: stores professional editing state.
- Unknown versions: rejected.

Opening an older project does not rewrite it. Saving after professional edits writes the explicit `1.2` document selected by the browser.

## Security and performance

- All FFmpeg/FFprobe invocations use argument lists and `shell=False`.
- Upload suffixes, signatures or LUT structure, decoded media, sizes, UUIDs, and configured roots are validated.
- No remote URL, arbitrary path, filter expression, or font path is accepted.
- One CPU-friendly export worker runs at a time.
- Originals are copied, never overwritten or deleted.
- Job intermediates are removed only from their verified UUID job directory; final MP4s remain.
- No paid API, model inference, or GPU quota is used.

## Real local verification

A synthetic project exercised generated waveforms, source/timeline audio markers, sync offsets, audio fades, sidechain ducking, Malayalam text, logo animation, saturation/exposure/temperature, a validated identity LUT, and dissolve/slide/zoom transitions.

- 720p result: 1280×720, 30 fps, H.264/AAC, 2.8 seconds, 2,553,335 bytes.
- 1080p result: 1920×1080, 30 fps, H.264/AAC, 2.8 seconds, 5,591,940 bytes.

Both completed the process-backed stages and passed independent FFprobe validation.

## Honest limitations

- Browser preview is approximate and does not evaluate `.cube` LUTs or signal-driven sidechain compression exactly.
- Waveforms are static visual summaries, not editable sample displays.
- One voice and one music track are supported; there is no arbitrary track count, waveform cutting, keyframed automation, or audio effects rack.
- Dragging reorders scenes; it does not create free-position gaps on the video track.
- Undo/redo history is not persisted across browser reloads or project reopen.
- Transition style parameters beyond type and duration are fixed.
- Text motion presets are fade, slide up, and slide left; arbitrary keyframes are not implemented.
- LUTs must be 3D `.cube` files; 1D LUTs are rejected.
- Lip-sync status is explicit metadata only. No automatic lip-sync generation is implemented or claimed.
