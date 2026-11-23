from __future__ import annotations

from typing import Literal

from app.models import StoryboardDocument, StoryboardScene


class StoryboardEditError(ValueError):
    pass


def _rebuilt(document: StoryboardDocument, scenes: list[StoryboardScene]) -> StoryboardDocument:
    normalized = [scene.model_copy(update={"order": index}) for index, scene in enumerate(scenes)]
    return StoryboardDocument(schema_version=document.schema_version, title=document.title, scenes=normalized)


def add_scene(document: StoryboardDocument, scene: StoryboardScene) -> StoryboardDocument:
    if any(existing.scene_id == scene.scene_id for existing in document.scenes):
        raise StoryboardEditError(f"Scene ID {scene.scene_id} already exists.")
    return _rebuilt(document, [*document.ordered_scenes(), scene])


def delete_scene(document: StoryboardDocument, scene_id: int) -> StoryboardDocument:
    if len(document.scenes) == 1:
        raise StoryboardEditError("A storyboard must contain at least one scene.")
    scenes = [scene for scene in document.ordered_scenes() if scene.scene_id != scene_id]
    if len(scenes) == len(document.scenes):
        raise StoryboardEditError(f"Scene ID {scene_id} was not found.")
    return _rebuilt(document, scenes)


def move_scene(
    document: StoryboardDocument, scene_id: int, direction: Literal["up", "down"]
) -> StoryboardDocument:
    scenes = document.ordered_scenes()
    try:
        index = next(index for index, scene in enumerate(scenes) if scene.scene_id == scene_id)
    except StopIteration as exc:
        raise StoryboardEditError(f"Scene ID {scene_id} was not found.") from exc
    destination = index - 1 if direction == "up" else index + 1
    if destination < 0 or destination >= len(scenes):
        raise StoryboardEditError(f"Scene ID {scene_id} cannot move {direction}.")
    scenes[index], scenes[destination] = scenes[destination], scenes[index]
    return _rebuilt(document, scenes)
