# Issue: Build the initial Blender-powered 3D cartoon generation pipeline

## Context

The repository needs a verified, CPU-friendly foundation for creating a real 3D cartoon locally on Windows without CUDA or paid cloud services. The implementation was prepared and tested locally before this issue was published; the issue records that completed foundation work transparently for review.

## Expected functionality

- Discover Blender without importing `bpy` in the application environment.
- Launch Blender safely in background mode with explicit arguments and captured output.
- Create a procedural orange fox, magical forest, animation, lighting, camera, and glowing stone.
- Save an editable Blender project and render genuine PNG and MP4 outputs.
- Accept direct story text and validated TXT, text-PDF, and DOCX uploads.
- Generate a constrained deterministic storyboard with explicit warnings.
- Provide a responsive FastAPI browser interface.

## Technical requirements

- Support Windows 11, Python 3.10+, Blender 5.3, and CPU/integrated-GPU rendering.
- Require no mandatory API keys, paid services, or external assets.
- Use subprocess argument lists with `shell=False`.
- Size-limit uploads and never execute uploaded content.
- Require explicit Blender completion plus valid expected outputs before reporting success.

## Acceptance criteria

- [x] Blender executable discovery is implemented.
- [x] Named procedural fox, forest, lighting, camera, and keyframes are created.
- [x] `forest_fox.blend`, `preview.png`, and `first_cartoon.mp4` are generated locally.
- [x] PNG is 640×360 and MP4 is 640×360, 72 frames, 24 FPS.
- [x] Story extraction, validation, and constrained storyboard generation work.
- [x] Unsupported content is reported rather than silently substituted.
- [x] Generated render media and the virtual environment are excluded from Git.

## Testing and rendering requirements

- Unit/API tests cover command construction, extraction, validation, storyboard warnings, output verification, and false-success prevention.
- CI remains lightweight and does not install Blender.
- Blender integration is verified locally with genuine output inspection.

## Documentation requirements

- README distinguishes working procedural features from future AI-assisted functionality.
- Architecture, roadmap, contribution, workflow, and achievement documentation are included.
- GitHub achievement claims remain limited to user-confirmed status.
