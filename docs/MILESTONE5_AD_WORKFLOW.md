# Milestone 5 — Cinematic Advertisement Production Workflow

## Working scope

Milestone 5 extends Video Timeline Studio with a reusable local advertisement workflow. It does not create AI footage and never calls Hugging Face or another remote provider.

The optional **WOODORA — Sheru Bhai Grand Arrival** template contains ten ordered plans:

1. Highway Arrival
2. Sheru Checks His Watch
3. Showroom Approach
4. Grand Entrance
5. Chauffeur Opens Door
6. Sheru Steps Out
7. Entering WOODORA
8. Furniture Showcase
9. Malayalam Dialogue
10. WOODORA Brand Reveal

The first nine scenes contain descriptions but no media. The tenth is a configured local text card. The interface labels missing assets as `PLANNED`, saves them without fabrication, skips them during the lightweight browser sequence preview, and refuses final export until every video/still scene has actual assigned media. The Malayalam-dialogue slot additionally requires an explicit visible-lip-sync verification flag; storing audio or passing validation is not accepted as lip-sync evidence.

## Media and cinematic editing

- Upload or import MP4 scenes without overwriting originals.
- Upload PNG, JPEG, or WebP scene images and assign a validated duration.
- Assign new media to an empty planned slot or append it as a generic scene.
- Reorder, trim, preview, and control original scene-audio volume.
- Create opening-title and final-branding cards from explicit text.
- Add fixed-position validated image/logo overlays.
- Add UTF-8 text overlays through job-local text files and a trusted discovered system font; user font paths and filter expressions are not accepted.
- Apply bounded fade-in/fade-out, fade crossfades, brightness, and contrast.
- Mix one preserved Malayalam voice track and one music track at independent volumes and validated start offsets.
- Export H.264/YUV420P video with 48 kHz stereo AAC at 720p or 1080p.

All inputs are normalized before concatenation or crossfade composition. A final MP4 is exposed only after envelope and independent FFprobe resolution, duration, codec, and frame-rate validation.

## Character Reference Library

Schema `1.0` character records contain a name, visual description, clothing/accessories, notes, and zero or more validated reference-image UUIDs. Sheru Bhai and the Doberman chauffeur are optional form starters. Users can create unrelated characters with the same generic fields.

References live under `project_data/character_references/` and are attached to advertisement schema `1.1` projects by canonical UUID. They are organizational assets only. Saving them does not trigger inference and does not guarantee identity consistency in generated video.

## Persistence and compatibility

Advertisement project schema `1.1` adds project kind, template identity, planned scene metadata, cinematic settings, logo references, character references, and audio offsets. The loader continues to accept Milestone 4 schema `1.0`; absent fields receive backward-compatible defaults. Unknown versions remain rejected.

Original uploads remain under UUID media directories. Projects are atomically replaced. Export jobs use isolated UUID output directories. No existing generated video, image, Malayalam audio, Blender file, or saved timeline project is overwritten or deleted.

## Verified local integration

A synthetic local test exercised a title card, PNG still scene with Malayalam text, MP4 scene with original audio, brand card, repeated logo overlays, two crossfades, fades, brightness/contrast, and offset voice/music. The one-worker pipeline completed every real stage and FFprobe independently verified a 1280×720, 30 fps H.264 result with AAC audio.

## Remaining limitations

- No WOODORA source pack was supplied or assembled during implementation; the complete advertisement is still a production task.
- Browser sequence preview shows available source scenes and configured cards, but does not simulate crossfades, overlays, color adjustments, or the final mixed voice/music. Review the verified export for those effects.
- One voice and one music track are supported. There is no waveform editor, keyframed volume, ducking, multi-track mixing, or fade curve selection.
- Crossfade uses one fixed fade style. Logo position and text styling are deliberately constrained.
- There are no motion effects for stills, subtitles, LUTs, color grading, or drag-and-drop ordering.
- Character references do not control generation and do not establish character consistency.
