import json
from uuid import uuid4

import pytest

from app.models import ProjectCreateRequest, ProjectUpdateRequest, StoryboardDocument, StoryboardScene
from app.services.project_store import (
    CorruptProjectError,
    InvalidProjectIdError,
    ProjectNotFoundError,
    ProjectStore,
    UnsupportedProjectVersionError,
)


def request(name: str = "Fox project") -> ProjectCreateRequest:
    storyboard = StoryboardDocument(
        title=name,
        scenes=[
            StoryboardScene(
                scene_id=1,
                order=0,
                description="The fox walks.",
                environment="magical_forest",
                characters=["fox"],
                action="walk",
                narration="The fox walks.",
            )
        ],
    )
    return ProjectCreateRequest(name=name, story_text="A fox walks.", storyboard=storyboard)


def test_create_load_update_and_list_project(tmp_path):
    store = ProjectStore(tmp_path)
    created = store.create(request())
    loaded = store.get(created.project_id)
    assert loaded == created
    assert not list(tmp_path.glob("*.tmp"))

    updated = store.update(created.project_id, ProjectUpdateRequest(**request("Updated").model_dump()))
    assert updated.name == "Updated"
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at

    projects, warnings = store.list()
    assert not warnings
    assert [project.project_id for project in projects] == [created.project_id]


@pytest.mark.parametrize("project_id", ["../secrets", "not-a-uuid", "00000000-0000-0000-0000-000000000000.json"])
def test_rejects_invalid_project_ids_and_path_traversal(tmp_path, project_id):
    store = ProjectStore(tmp_path)
    with pytest.raises(InvalidProjectIdError):
        store.get(project_id)
    assert not (tmp_path.parent / "secrets.json").exists()


def test_handles_missing_corrupt_and_unsupported_projects(tmp_path):
    store = ProjectStore(tmp_path)
    missing = uuid4()
    with pytest.raises(ProjectNotFoundError):
        store.get(missing)

    corrupt = uuid4()
    (tmp_path / f"{corrupt}.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(CorruptProjectError):
        store.get(corrupt)

    unsupported = uuid4()
    payload = json.loads(store.create(request()).model_dump_json())
    payload["project_id"] = str(unsupported)
    payload["schema_version"] = "99.0"
    (tmp_path / f"{unsupported}.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(UnsupportedProjectVersionError):
        store.get(unsupported)

    projects, warnings = store.list()
    assert projects
    assert len(warnings) == 2
