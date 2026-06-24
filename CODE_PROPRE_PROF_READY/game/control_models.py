from __future__ import annotations

from dataclasses import dataclass


HUMAN_CONTROL_MODE = "human"
AI_CONTROL_MODE = "ai"
AI_NAME_PREFIX = "[IA] "
AI_DIFFICULTY_DISPLAY_BY_CODE = {
    "cadet": "Cadet",
    "standard": "Standard",
    "champion": "Champion",
}
AI_DIFFICULTY_CODE_BY_DISPLAY = {
    label: code
    for code, label in AI_DIFFICULTY_DISPLAY_BY_CODE.items()
}
LOCAL_VS_AI_HUMAN_CONTROL_PRIORITY = (2, 1, 3, 4, 5, 6)


@dataclass(frozen=True)
class MovementIntent:
    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False

    def is_active(self) -> bool:
        return self.up or self.down or self.left or self.right


def is_ai_name(name: str) -> bool:
    return str(name or "").strip().startswith(AI_NAME_PREFIX)
