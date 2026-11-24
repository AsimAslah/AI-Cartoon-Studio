# Professional Editor User Guide

## Start or reopen a project

Open the application on `http://127.0.0.1:8000`. Choose an existing saved project, start a blank project, or load the optional WOODORA plan. Older Timeline Studio projects remain usable.

## Build the timeline

1. Upload MP4 scenes or PNG/JPEG/WebP stills, or import a previously generated verified clip.
2. Assign new media to a planned slot or append it as a new scene.
3. Drag a scene block on the Video track to reorder it. Pointer dragging works with a mouse and with touch where the browser provides Pointer Events.
4. Adjust zoom to inspect timing. Click the ruler or empty track area to place the playhead.
5. Press **S** or select **Split at playhead** to split the scene non-destructively.
6. Use the Scene inspector for precise trims, duration, transition, effects, text, logo, and explicit lip-sync status.

Use Undo/Redo or Ctrl/Cmd+Z and Ctrl/Cmd+Y for timeline edits. The history holds the most recent 50 snapshots and resets when opening or starting a project.

## Edit voice and music

Upload one Malayalam voice file and one music file. Their waveforms appear on separate tracks.

- **Start offset:** absolute timeline start.
- **Sync adjustment:** small positive or negative correction without changing the saved start marker.
- **Timeline end:** optional absolute stop.
- **Dialogue source start/end:** trim the voice source non-destructively.
- **Scene alignment:** selects a scene and moves voice start to that scene boundary.
- **Fade in/out and volume:** processed locally during render.
- **Automatic ducking:** reduces music using the actual voice signal in rendered output; intensity controls the compressor ratio.

Checking lip-sync verification records a manual status only. It does not generate or prove synchronization automatically.

## Add transitions and effects

Choose a transition on every scene except the last and keep its duration shorter than both neighboring scenes. Use neutral **Reset visual effects** before comparing color changes. A `.cube` LUT must be a valid 3D LUT; the editor copies it to local UUID storage and never edits the original.

Text uses a trusted installed Malayalam-capable font. Select top, center, lower third, or custom normalized position and an optional fade/slide animation. Logos use a fixed safe overlay position with optional fades.

## Preview and export

- **Play approximate browser preview** for fast ordering, trim, and basic design checks.
- **Render export-accurate preview** before approval. This uses local FFmpeg and shows the exact transition, LUT, overlay, ducking, synchronization, and audio mix.
- **Export timeline MP4** for the final independently verified H.264/AAC file.

Do not treat the approximate browser preview as rendering parity. Only the rendered preview/final export passes the production FFmpeg and FFprobe pipeline.
