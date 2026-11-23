# AI Cartoon Studio 3D v0.1.0 — First Working 3D Cartoon

Status: prepared, not published. Publish only after the foundation pull request is merged, CI passes, and `main` contains the implementation.

## Highlights

- Blender 5.3 discovery and safe background invocation on Windows
- Reusable procedural orange fox with a white belly, expressive eyes, four legs, a bushy tail, and a blue backpack
- Stylized magical forest with a path, trees, flowers, lighting, and a glowing stone
- Basic walk, leg, tail, head, light, and camera keyframes
- Editable Blender project plus genuine 640×360 PNG and three-second H.264 MP4 outputs
- FastAPI web interface for direct story entry and validated TXT, PDF, and DOCX extraction
- Deterministic typed storyboard generation with explicit unsupported-content warnings
- Lightweight unit/API tests and least-privilege GitHub Actions CI

## Verification

- Local test suite: 13 passed on Python 3.10.11
- Blender: 5.3.0, Eevee
- PNG: 640×360
- MP4: 640×360, 72 frames, 24 FPS
- Render success requires a Blender completion marker and nonempty expected output files

## Known limitations

- One procedural fox and one magical forest are supported.
- Story understanding is constrained and rule-based, not general AI comprehension.
- Rendering currently uses a fixed demonstration scene rather than the edited storyboard.
- Storyboard scene editing, project persistence, queued progress reporting, narration, audio mixing, lip sync, and multi-scene composition are not included.
- Scanned PDFs require future OCR support.
- Full-HD rendering is intentionally not the default on integrated-GPU laptops.

## Tagging instructions

After the approved foundation PR is merged and CI is green:

```powershell
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "AI Cartoon Studio 3D v0.1.0"
git push origin v0.1.0
```

Create the GitHub release from tag `v0.1.0`, use the title above, and paste the release sections from this file. Final publication requires explicit user approval.
