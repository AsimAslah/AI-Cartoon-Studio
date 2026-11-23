from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

STORYBOARD_SCHEMA_VERSION = "1.0"
PROJECT_SCHEMA_VERSION = "1.0"
SUPPORTED_CHARACTERS = ["fox"]
SUPPORTED_ENVIRONMENTS = ["magical_forest"]
SUPPORTED_ACTIONS = ["idle", "walk", "turn", "approach", "look", "touch"]

CharacterName = Literal["fox"]
EnvironmentName = Literal["magical_forest"]
ActionName = Literal["idle", "walk", "turn", "approach", "look", "touch"]


class StoryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Story text cannot be blank.")
        return value


class StoryboardScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    scene_id: int = Field(ge=1)
    order: int = Field(default=0, ge=0)
    description: str = Field(default="A fox explores the magical forest.", min_length=1, max_length=500)
    environment: EnvironmentName = Field(
        default="magical_forest", validation_alias=AliasChoices("environment", "location")
    )
    characters: list[CharacterName] = Field(default_factory=lambda: ["fox"], min_length=1, max_length=4)
    action: ActionName
    narration: str = Field(min_length=1)
    dialogue: str | None = Field(default=None, max_length=1_000)
    mood: str = Field(default="wonder", min_length=1, max_length=50)
    duration_seconds: int = Field(default=4, ge=1, le=30)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("description", "narration", "mood")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank.")
        return value

    @field_validator("dialogue")
    @classmethod
    def normalize_dialogue(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("characters")
    @classmethod
    def unique_characters(cls, value: list[CharacterName]) -> list[CharacterName]:
        if len(value) != len(set(value)):
            raise ValueError("Characters must be unique within a scene.")
        return value


class StoryboardDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = STORYBOARD_SCHEMA_VERSION
    title: str = Field(default="Untitled storyboard", min_length=1, max_length=200)
    scenes: list[StoryboardScene] = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Storyboard title cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_scene_identity_and_order(self) -> "StoryboardDocument":
        scene_ids = [scene.scene_id for scene in self.scenes]
        orders = [scene.order for scene in self.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("Every scene_id must be unique.")
        if len(orders) != len(set(orders)):
            raise ValueError("Every scene order must be unique.")
        expected = list(range(len(self.scenes)))
        if sorted(orders) != expected:
            raise ValueError(f"Scene order must be contiguous from 0 to {len(self.scenes) - 1}.")
        return self

    def ordered_scenes(self) -> list[StoryboardScene]:
        return sorted(self.scenes, key=lambda scene: scene.order)


class StoryboardResponse(BaseModel):
    scenes: list[StoryboardScene]
    global_warnings: list[str] = Field(default_factory=list)
    schema_version: str = STORYBOARD_SCHEMA_VERSION
    supported_characters: list[str] = Field(default_factory=lambda: SUPPORTED_CHARACTERS.copy())
    supported_locations: list[str] = Field(default_factory=lambda: SUPPORTED_ENVIRONMENTS.copy())
    supported_actions: list[str] = Field(default_factory=lambda: SUPPORTED_ACTIONS.copy())

    def as_document(self, title: str = "Generated storyboard") -> StoryboardDocument:
        return StoryboardDocument(title=title, scenes=self.scenes)


class StoryboardValidationResponse(BaseModel):
    valid: Literal[True] = True
    storyboard: StoryboardDocument
    warnings: list[str] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    story_text: str = Field(default="", max_length=100_000)
    storyboard: StoryboardDocument

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value


class ProjectUpdateRequest(ProjectCreateRequest):
    pass


class ProjectRecord(ProjectCreateRequest):
    schema_version: Literal["1.0"] = PROJECT_SCHEMA_VERSION
    project_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    project_id: UUID
    name: str
    scene_count: int
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummary]
    warnings: list[str] = Field(default_factory=list)


class RenderState(str, Enum):
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    STARTING_BLENDER = "STARTING_BLENDER"
    RENDERING = "RENDERING"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RenderSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storyboard: StoryboardDocument | None = None
    project_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "RenderSubmissionRequest":
        if (self.storyboard is None) == (self.project_id is None):
            raise ValueError("Provide exactly one of storyboard or project_id.")
        return self


class RenderJobResponse(BaseModel):
    job_id: UUID
    state: RenderState
    message: str
    created_at: datetime
    updated_at: datetime
    scene_count: int
    state_history: list[RenderState] = Field(default_factory=lambda: [RenderState.QUEUED])
    output_filename: str | None = None
    error: str | None = None
