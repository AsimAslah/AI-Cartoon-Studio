# AI Cartoon Studio 3D

[![CI](https://github.com/AsimAslah/AI-Cartoon-Studio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AsimAslah/AI-Cartoon-Studio/actions/workflows/ci.yml)

An open-source, local-first 3D cartoon creation studio powered by Blender, Python, and FastAPI. This v0.1 foundation creates a reusable procedural fox and magical forest, extracts TXT/PDF/DOCX story text, generates a constrained rule-based storyboard, and invokes Blender for genuine renders.

> Development status: early working foundation. This project does **not** implement arbitrary text-to-3D generation, natural motion capture, lip sync, or universal story understanding.

![Genuine Blender preview](images/preview.png)

## Working features

- Automatic Blender discovery on Windows and safe background subprocess execution
- Procedural orange fox with white belly, eyes, four legs, tail, and blue backpack
- Procedural magical forest, glowing stone, lighting, camera, and keyframed motion
- Genuine editable `.blend`, 640×360 PNG, and short MP4 output
- Direct story entry and validated TXT, text-PDF, and DOCX upload (5 MB limit)
- Deterministic storyboard for one fox, one forest, and six basic actions
- Responsive FastAPI web interface and lightweight pytest suite

## Windows setup

Requirements: Windows 11, Python 3.10+, and Blender 4.2+ or 5.x. No CUDA GPU is required.

```powershell
cd C:\Users\asima\Documents\AI-Cartoon-Studio
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Upload or edit a story, generate the storyboard, then render a preview. Scanned PDFs need OCR and are rejected when no selectable text is present.

## Render the demonstration

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe' --background --factory-startup --python scripts\fox_scene.py -- --output-dir output
```

This writes `output/forest_fox.blend`, `output/preview.png`, and `output/first_cartoon.mp4`. Rendering is intentionally short and low resolution for laptop hardware. Blender bundles the FFmpeg encoder used by this script; a separate FFmpeg executable is not required for this milestone.

## Tests

```powershell
python -m pytest
```

Unit tests do not run expensive Blender renders. The command above is the local end-to-end smoke test.

## Architecture

FastAPI owns validation and the browser workflow. Deterministic services extract documents and map supported phrases into a typed storyboard. The Blender runner launches a self-contained `bpy` script, which creates assets, animation, and verified output. See [architecture](docs/ARCHITECTURE.md) and the [roadmap](docs/ROADMAP.md).

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE). The CI badge reflects GitHub Actions status only; it is not a GitHub profile achievement.
