from __future__ import annotations

import re

from app.models import StoryboardResponse, StoryboardScene

SUPPORTED_ACTIONS = {
    "walk": ("walk", "walk"),
    "walks": ("walk", "walk"),
    "walking": ("walk", "walk"),
    "approach": ("approach", "approach"),
    "approaches": ("approach", "approach"),
    "turn": ("turn", "turn"),
    "turns": ("turn", "turn"),
    "look": ("look", "look"),
    "looks": ("look", "look"),
    "touch": ("touch", "touch"),
    "touches": ("touch", "touch"),
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|[\r\n]+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def generate_storyboard(text: str) -> StoryboardResponse:
    text = text.strip()
    if not text:
        raise ValueError("Story text cannot be blank.")

    scenes: list[StoryboardScene] = []
    global_warnings: list[str] = []
    lower_story = text.lower()
    if "fox" not in lower_story:
        global_warnings.append("Only the procedural fox is currently supported; add 'fox' or edit the storyboard manually.")
    if not any(word in lower_story for word in ("forest", "tree", "woods")):
        global_warnings.append("Only the magical forest environment is currently supported.")

    for index, sentence in enumerate(_sentences(text), start=1):
        lower = sentence.lower()
        action = "idle"
        for word, (candidate, _label) in SUPPORTED_ACTIONS.items():
            if re.search(rf"\b{re.escape(word)}\b", lower):
                action = candidate
                break

        warnings: list[str] = []
        action_words = re.findall(r"\b(?:runs?|jumps?|flies?|dances?|swims?|drives?)\b", lower)
        if action_words:
            warnings.append(
                f"Unsupported action '{action_words[0]}'; choose idle, walk, turn, approach, look, or touch."
            )

        mood = "joy" if any(word in lower for word in ("happy", "happily", "smile")) else "wonder"
        scenes.append(
            StoryboardScene(
                scene_id=index,
                order=index - 1,
                description=sentence,
                environment="magical_forest",
                characters=["fox"],
                action=action,
                narration=sentence,
                mood=mood,
                warnings=warnings,
            )
        )

    return StoryboardResponse(scenes=scenes, global_warnings=global_warnings)
