from app.services.storyboard_generator import generate_storyboard


def test_generates_ordered_scenes_and_actions():
    result = generate_storyboard("A fox walks in the forest. The fox touches a stone.")
    assert [scene.scene_id for scene in result.scenes] == [1, 2]
    assert [scene.action for scene in result.scenes] == ["walk", "touch"]


def test_reports_unsupported_action_and_environment_constraint():
    result = generate_storyboard("A rabbit jumps on the moon.")
    assert result.global_warnings
    assert "Unsupported action" in result.scenes[0].warnings[0]
