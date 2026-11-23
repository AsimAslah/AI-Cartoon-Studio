from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    scene_id: int = Field(ge=1)
    location: Literal["magical_forest"]
    characters: list[Literal["fox"]]
    action: Literal["idle", "walk", "turn", "approach", "look", "touch"]
    narration: str = Field(min_length=1)
    dialogue: str | None = None
    mood: str = "wonder"
    duration_seconds: int = Field(default=4, ge=1, le=30)
    warnings: list[str] = Field(default_factory=list)


class StoryboardResponse(BaseModel):
    scenes: list[StoryboardScene]
    global_warnings: list[str] = Field(default_factory=list)
    supported_characters: list[str] = ["fox"]
    supported_locations: list[str] = ["magical_forest"]
    supported_actions: list[str] = ["idle", "walk", "turn", "approach", "look", "touch"]
