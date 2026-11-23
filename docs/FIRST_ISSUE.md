# Issue: Build the v0.1 procedural fox rendering foundation

## Goal

Create a CPU-friendly Blender demonstration that produces an editable fox scene, genuine preview, and short MP4, with a safe Python runner and tests.

## Acceptance criteria

- Blender is discovered without importing `bpy` in the app environment.
- A named procedural fox, forest, camera, lighting, and basic keyframes are created.
- Blender saves `forest_fox.blend`, renders `preview.png`, and encodes `first_cartoon.mp4`.
- Expected outputs are nonempty and format-verified.
- Unit tests cover command construction, story validation, extraction, storyboard warnings, and output checks.
- Documentation clearly separates working procedural features from future AI features.
