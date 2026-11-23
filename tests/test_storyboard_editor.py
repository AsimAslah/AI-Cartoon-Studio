import pytest
from pydantic import ValidationError

from app.models import StoryboardDocument, StoryboardScene
from app.services.storyboard_editor import StoryboardEditError, add_scene, delete_scene, move_scene


def scene(scene_id: int, order: int, action: str = "idle") -> StoryboardScene:
    return StoryboardScene(
        scene_id=scene_id,
        order=order,
        description=f"Scene {scene_id}",
        environment="magical_forest",
        characters=["fox"],
        action=action,
        narration=f"Narration {scene_id}",
    )


def test_adds_deletes_and_reorders_scenes():
    document = StoryboardDocument(title="Fox", scenes=[scene(1, 0)])
    document = add_scene(document, scene(2, 0, "walk"))
    assert [(item.scene_id, item.order) for item in document.scenes] == [(1, 0), (2, 1)]

    document = move_scene(document, 2, "up")
    assert [(item.scene_id, item.order) for item in document.scenes] == [(2, 0), (1, 1)]

    document = delete_scene(document, 2)
    assert [item.scene_id for item in document.scenes] == [1]


def test_rejects_duplicate_ids_and_deleting_last_scene():
    document = StoryboardDocument(title="Fox", scenes=[scene(1, 0)])
    with pytest.raises(StoryboardEditError, match="already exists"):
        add_scene(document, scene(1, 0))
    with pytest.raises(StoryboardEditError, match="at least one"):
        delete_scene(document, 1)


def test_schema_rejects_duplicate_and_noncontiguous_order():
    with pytest.raises(ValidationError, match="scene_id"):
        StoryboardDocument(title="Fox", scenes=[scene(1, 0), scene(1, 1)])
    with pytest.raises(ValidationError, match="contiguous"):
        StoryboardDocument(title="Fox", scenes=[scene(1, 0), scene(2, 3)])


def test_rejects_unsupported_character_action_and_extra_fields():
    payload = scene(1, 0).model_dump()
    payload["characters"] = ["dragon"]
    with pytest.raises(ValidationError, match="fox"):
        StoryboardScene.model_validate(payload)
    payload = scene(1, 0).model_dump()
    payload["action"] = "fly"
    with pytest.raises(ValidationError, match="idle"):
        StoryboardScene.model_validate(payload)
    payload = scene(1, 0).model_dump()
    payload["unsafe"] = "ignored?"
    with pytest.raises(ValidationError, match="Extra inputs"):
        StoryboardScene.model_validate(payload)
