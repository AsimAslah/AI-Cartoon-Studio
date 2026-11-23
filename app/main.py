from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import StoryRequest, StoryboardResponse
from app.services.blender_runner import discover_blender, run_blender_demo
from app.services.story_parser import StoryExtractionError, extract_story, safe_display_name
from app.services.storyboard_generator import generate_storyboard

app = FastAPI(title="AI Cartoon Studio 3D", version="0.1.0")
app.mount("/static", StaticFiles(directory=settings.project_root / "app" / "static"), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(settings.project_root / "app" / "templates" / "index.html")


@app.get("/api/capabilities")
def capabilities() -> dict[str, object]:
    blender = discover_blender()
    return {
        "blender_available": blender is not None,
        "blender_path": str(blender) if blender else None,
        "characters": ["fox"],
        "environments": ["magical_forest"],
        "actions": ["idle", "walk", "turn", "approach", "look", "touch"],
    }


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)) -> dict[str, str]:
    content = await file.read(settings.max_upload_bytes + 1)
    try:
        text = extract_story(file.filename or "story", content, settings.max_upload_bytes)
    except StoryExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"filename": safe_display_name(file.filename or "story"), "text": text}


@app.post("/api/storyboard", response_model=StoryboardResponse)
def storyboard(request: StoryRequest) -> StoryboardResponse:
    return generate_storyboard(request.text)


@app.post("/api/render/demo")
def render_demo(preview_only: bool = True) -> dict[str, object]:
    blender = discover_blender()
    if not blender:
        raise HTTPException(status_code=503, detail="Blender executable was not found.")
    result = run_blender_demo(
        blender,
        settings.project_root / "scripts" / "fox_scene.py",
        settings.output_dir,
        preview_only=preview_only,
    )
    if not result.succeeded:
        raise HTTPException(
            status_code=500,
            detail={"message": "Blender render failed or outputs were missing.", "stderr": result.stderr[-4000:]},
        )
    return {
        "status": "completed",
        "duration_seconds": round(result.duration_seconds, 2),
        "outputs": [path.name for path in result.expected_outputs],
    }


@app.get("/api/output/{filename}")
def output_file(filename: str) -> FileResponse:
    allowed = {"preview.png", "first_cartoon.mp4", "forest_fox.blend"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Output not found.")
    path = settings.output_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Output has not been generated yet.")
    return FileResponse(path, filename=filename)
