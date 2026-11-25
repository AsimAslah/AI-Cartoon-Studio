from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    PROJECT_SCHEMA_VERSION,
    STORYBOARD_SCHEMA_VERSION,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectRecord,
    ProjectUpdateRequest,
    RenderJobResponse,
    RenderSubmissionRequest,
    StoryRequest,
    StoryboardDocument,
    StoryboardResponse,
    StoryboardValidationResponse,
)
from app.services.blender_runner import discover_blender, run_blender_demo, run_blender_storyboard
from app.services.project_store import (
    CorruptProjectError,
    InvalidProjectIdError,
    ProjectNotFoundError,
    ProjectStore,
    UnsupportedProjectVersionError,
)
from app.services.render_jobs import (
    RenderJobError,
    RenderJobManager,
    RenderJobNotFoundError,
    UnsupportedStoryboardRenderError,
)
from app.services.story_parser import StoryExtractionError, extract_story, safe_display_name
from app.services.storyboard_generator import generate_storyboard

from app.services.lipsync_http import router as lipsync_router
from app.services.timeline.http import router as timeline_router
from app.services.video_generation.http import router as video_generation_router

app = FastAPI(title="AI Cartoon Studio 3D", version="0.6.0")
app.mount("/static", StaticFiles(directory=settings.project_root / "app" / "static"), name="static")
app.include_router(lipsync_router)
app.include_router(video_generation_router)
app.include_router(timeline_router)

project_store = ProjectStore(settings.project_data_dir)


def _render_scene(scene, output_dir: Path):
    blender = discover_blender()
    if not blender:
        raise RuntimeError("Blender executable was not found.")
    return run_blender_storyboard(
        blender,
        settings.project_root / "scripts" / "fox_scene.py",
        output_dir,
        action=scene.action,
        duration_seconds=scene.duration_seconds,
    )


render_job_manager = RenderJobManager(settings.render_jobs_dir, _render_scene, max_workers=1)


def _project_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, InvalidProjectIdError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, UnsupportedProjectVersionError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, CorruptProjectError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Project storage failed.")


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
        "storyboard_schema_version": STORYBOARD_SCHEMA_VERSION,
        "project_schema_version": PROJECT_SCHEMA_VERSION,
        "render_limitations": ["Exactly one supported scene", "1–10 seconds", "one concurrent render"],
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


@app.post("/api/storyboard/validate", response_model=StoryboardValidationResponse)
def validate_storyboard(storyboard: StoryboardDocument) -> StoryboardValidationResponse:
    warnings = [warning for scene in storyboard.scenes for warning in scene.warnings]
    if len(storyboard.scenes) > 1:
        warnings.append("Multi-scene storyboards can be edited and saved, but rendering currently accepts one scene.")
    if any(scene.duration_seconds > 10 for scene in storyboard.scenes):
        warnings.append("Laptop renders currently accept scene durations from 1 to 10 seconds.")
    return StoryboardValidationResponse(storyboard=storyboard, warnings=warnings)


@app.post("/api/projects", response_model=ProjectRecord, status_code=status.HTTP_201_CREATED)
def create_project(request: ProjectCreateRequest) -> ProjectRecord:
    return project_store.create(request)


@app.get("/api/projects", response_model=ProjectListResponse)
def list_projects() -> ProjectListResponse:
    projects, warnings = project_store.list()
    return ProjectListResponse(projects=projects, warnings=warnings)


@app.get("/api/projects/{project_id}", response_model=ProjectRecord)
def get_project(project_id: str) -> ProjectRecord:
    try:
        return project_store.get(project_id)
    except (ProjectNotFoundError, InvalidProjectIdError, CorruptProjectError, UnsupportedProjectVersionError) as exc:
        raise _project_error(exc) from exc


@app.put("/api/projects/{project_id}", response_model=ProjectRecord)
def update_project(project_id: str, request: ProjectUpdateRequest) -> ProjectRecord:
    try:
        return project_store.update(project_id, request)
    except (ProjectNotFoundError, InvalidProjectIdError, CorruptProjectError, UnsupportedProjectVersionError) as exc:
        raise _project_error(exc) from exc


@app.post("/api/renders", response_model=RenderJobResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_render(request: RenderSubmissionRequest) -> RenderJobResponse:
    storyboard_document = request.storyboard
    if request.project_id is not None:
        try:
            storyboard_document = project_store.get(request.project_id).storyboard
        except (ProjectNotFoundError, InvalidProjectIdError, CorruptProjectError, UnsupportedProjectVersionError) as exc:
            raise _project_error(exc) from exc
    assert storyboard_document is not None
    if not discover_blender():
        raise HTTPException(status_code=503, detail="Blender executable was not found.")
    try:
        return render_job_manager.submit(storyboard_document)
    except UnsupportedStoryboardRenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/renders/{job_id}", response_model=RenderJobResponse)
def render_status(job_id: str) -> RenderJobResponse:
    try:
        return render_job_manager.get(job_id)
    except RenderJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/renders/{job_id}/output")
def render_output(job_id: str) -> FileResponse:
    try:
        path = render_job_manager.output_path(job_id)
    except RenderJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RenderJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(path, filename=f"cartoon-{job_id}.mp4", media_type="video/mp4")


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
