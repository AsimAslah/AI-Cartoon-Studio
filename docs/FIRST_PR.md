# Pull request: feat: implement AI Cartoon Studio 3D foundation

## Summary

Establishes the local-first v0.1 foundation for AI Cartoon Studio 3D: a FastAPI workflow, safe story extraction, deterministic storyboard generation, Blender discovery and subprocess execution, a procedural fox and magical forest, genuine renders, tests, CI, and accurate documentation.

## Implemented features

- Responsive story-entry and upload interface
- TXT, text-PDF, and DOCX extraction with validation and a 5 MB limit
- Typed rule-based storyboard schema with explicit unsupported-content warnings
- Windows Blender discovery and safe `shell=False` background execution
- Procedural fox, forest, glowing stone, lighting, camera, and keyframed motion
- Editable `.blend`, genuine 640×360 PNG, and three-second H.264 MP4
- Explicit render-completion marker and expected-output verification
- Lightweight unit/API tests and least-privilege Windows CI

## Verification evidence

- `python -m pytest`: 13 passed on Python 3.10.11
- `python -m compileall -q app scripts`: completed locally
- Blender 5.3/Eevee integration: completed locally
- PNG: 640×360 and visually inspected
- MP4: decoded by Blender as 640×360, 72 frames, 24 FPS
- Generated render outputs and `.venv` confirmed ignored

## Known limitations

- The working asset library contains one fox and one forest.
- Story understanding is constrained and deterministic, not general AI comprehension.
- The Blender demo is not yet driven by an edited multi-scene storyboard.
- Storyboard editing, persistence, audio, lip sync, and durable render progress are planned.
- Scanned PDFs require future OCR support.

## Reviewer instructions

1. Install dependencies with `python -m pip install -r requirements.txt`.
2. Run `python -m pytest`.
3. Run `python -m compileall -q app scripts`.
4. Start `uvicorn app.main:app --reload` and exercise text/upload/storyboard endpoints.
5. Optionally run the documented Blender smoke test locally; Blender is intentionally omitted from CI.
6. Confirm the tracked preview is genuine and generated render artifacts remain ignored.

## Checklist

- [x] Local tests pass
- [x] Genuine render outputs verified
- [x] Documentation distinguishes current and planned features
- [x] No secrets or generated video/Blend files are tracked
- [ ] GitHub Actions passes on this pull request
- [ ] Human review and merge approval

The published PR body will close the actual foundation issue number once that issue exists.
