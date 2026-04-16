from __future__ import annotations

import math
import random

from game.control_models import (
    AI_CONTROL_MODE,
    HUMAN_CONTROL_MODE,
    LOCAL_VS_AI_HUMAN_CONTROL_PRIORITY,
    MovementIntent,
)


AI_TEAM_SLOT_PRIORITY = {
    "A": (1, 3, 5),
    "B": (2, 4, 6),
}

AI_TEAM_NAMES = {
    "A": (
        "[IA] Sentinelle braise",
        "[IA] Oracle braise",
        "[IA] Vigie braise",
    ),
    "B": (
        "[IA] Sentinelle azur",
        "[IA] Oracle azur",
        "[IA] Vigie azur",
    ),
}

AI_TEAM_DEFAULT_SPRITES = {
    "A": "skeleton_fighter_ember",
    "B": "skeleton_fighter_aether",
}

AI_DIFFICULTY_SETTINGS = {
    "cadet": {
        "retarget_delay_ms": 620,
        "decision_interval_ms": 190,
        "contest_weight": 0.12,
        "contest_cap": 70.0,
        "rare_value_weight": 15.0,
        "axis_threshold": 14.0,
        "escape_after_frames": 18,
        "escape_duration_ms": 320,
    },
    "standard": {
        "retarget_delay_ms": 260,
        "decision_interval_ms": 95,
        "contest_weight": 0.35,
        "contest_cap": 140.0,
        "rare_value_weight": 34.0,
        "axis_threshold": 8.0,
        "escape_after_frames": 10,
        "escape_duration_ms": 220,
    },
    "champion": {
        "retarget_delay_ms": 110,
        "decision_interval_ms": 35,
        "contest_weight": 0.62,
        "contest_cap": 230.0,
        "rare_value_weight": 62.0,
        "axis_threshold": 4.0,
        "escape_after_frames": 7,
        "escape_duration_ms": 190,
    },
}


def get_opposite_team(team_code: str) -> str:
    return "B" if str(team_code).upper() == "A" else "A"


def build_human_vs_ai_players(
    human_players: list[dict],
    *,
    human_team: str = "A",
    ai_team: str | None = None,
    difficulty: str = "standard",
    prefer_arrow_controls: bool = True,
) -> list[dict]:
    human_team = str(human_team or "A").upper()
    ai_team = str(ai_team or get_opposite_team(human_team)).upper()
    control_slots = _pick_human_control_slots(
        len(human_players),
        prefer_arrow_controls=prefer_arrow_controls,
    )

    normalized_humans = []
    for index, player in enumerate(
        sorted(human_players, key=lambda item: int(item["slot"]))
    ):
        normalized_humans.append(
            {
                **player,
                "slot": control_slots[index],
                "ui_slot": int(player["slot"]),
                "team": human_team,
                "control_mode": HUMAN_CONTROL_MODE,
            }
        )

    ai_players = _build_ai_team(
        normalized_humans,
        ai_team=ai_team,
        difficulty=difficulty,
    )
    return normalized_humans + ai_players


def _build_ai_team(
    human_players: list[dict],
    *,
    ai_team: str,
    difficulty: str,
) -> list[dict]:
    team_size = len(human_players)
    used_slots = {
        int(player.get("slot", 0))
        for player in human_players
        if int(player.get("slot", 0)) > 0
    }
    preferred_slots = [
        slot
        for slot in AI_TEAM_SLOT_PRIORITY.get(ai_team, ())
        if slot not in used_slots
    ]
    fallback_slots = [
        slot
        for slot in range(1, 7)
        if slot not in used_slots and slot not in preferred_slots
    ]
    available_slots = preferred_slots + fallback_slots

    used_names = {str(player.get("name", "")).strip() for player in human_players}
    roster = []
    for index in range(team_size):
        slot = available_slots[index]
        name = _pick_ai_name(index, ai_team, used_names)
        used_names.add(name)
        roster.append(
            {
                "slot": slot,
                "name": name,
                "team": ai_team,
                "control_mode": AI_CONTROL_MODE,
                "ai_profile": "orb_hunter",
                "ai_difficulty": difficulty,
                "sprite_id": AI_TEAM_DEFAULT_SPRITES.get(
                    ai_team,
                    AI_TEAM_DEFAULT_SPRITES["B"],
                ),
            }
        )

    return roster


def _pick_human_control_slots(
    player_count: int,
    *,
    prefer_arrow_controls: bool,
) -> list[int]:
    slot_priority = list(range(1, 7))
    if prefer_arrow_controls:
        slot_priority = list(LOCAL_VS_AI_HUMAN_CONTROL_PRIORITY)

    return slot_priority[:player_count]


def _pick_ai_name(index: int, team_code: str, used_names: set[str]) -> str:
    name_pool = AI_TEAM_NAMES.get(team_code, AI_TEAM_NAMES["B"])
    base_name = name_pool[index % len(name_pool)]
    candidate = base_name
    suffix = 2

    while candidate in used_names:
        candidate = f"{base_name} #{suffix}"
        suffix += 1

    return candidate


class BotController:
    def __init__(
        self,
        *,
        profile: str = "orb_hunter",
        difficulty: str = "standard",
        seed: int = 0,
    ):
        self.profile = profile
        self.difficulty = self._normalize_difficulty(difficulty)
        self.settings = AI_DIFFICULTY_SETTINGS[self.difficulty]
        self.rng = random.Random(seed)
        self.target_orb = None
        self.retarget_at_ms = 0
        self.last_position: tuple[float, float] | None = None
        self.last_intent = MovementIntent()
        self.stuck_frames = 0
        self.escape_until_ms = 0
        self.next_decision_at_ms = 0
        self.escape_intent = MovementIntent()
        self.avoidance_axis: str | None = None
        self.avoidance_direction = 0

    def get_movement_intent(
        self,
        *,
        player,
        players,
        orbs,
        obstacles=None,
        elapsed_ms: int,
    ) -> MovementIntent:
        self._update_stuck_state(player)

        if not orbs:
            self.next_decision_at_ms = 0
            self.last_intent = MovementIntent()
            return self.last_intent

        if self.target_orb is None or elapsed_ms >= self.retarget_at_ms:
            self.target_orb = self._pick_target_orb(player, players, orbs)
            self.retarget_at_ms = elapsed_ms + self.settings["retarget_delay_ms"]

        if self.target_orb is None:
            self.next_decision_at_ms = 0
            self.last_intent = MovementIntent()
            return self.last_intent

        if elapsed_ms < self.escape_until_ms:
            self.last_intent = self.escape_intent
            return self.last_intent

        if elapsed_ms < self.next_decision_at_ms and self.last_intent.is_active():
            return self.last_intent

        dx = float(self.target_orb.x) - float(player.x)
        dy = float(self.target_orb.y) - float(player.y)

        if self.stuck_frames >= self.settings["escape_after_frames"]:
            self._clear_avoidance()
            self._enter_escape_mode(dx, dy, elapsed_ms)
            self.stuck_frames = 0
            self.last_intent = self.escape_intent
            return self.last_intent

        self.last_intent = self._build_intent_to_point(dx, dy)
        self.last_intent = self._adjust_for_obstacles(
            player,
            self.last_intent,
            dx,
            dy,
            obstacles or (),
        )
        self.next_decision_at_ms = elapsed_ms + self.settings["decision_interval_ms"]
        return self.last_intent

    @staticmethod
    def _normalize_difficulty(difficulty: str) -> str:
        normalized = str(difficulty or "standard").strip().lower()
        if normalized in AI_DIFFICULTY_SETTINGS:
            return normalized
        return "standard"

    def _update_stuck_state(self, player) -> None:
        if self.last_position is None:
            self.last_position = (float(player.x), float(player.y))
            return

        last_x, last_y = self.last_position
        moved_distance = math.hypot(
            float(player.x) - last_x,
            float(player.y) - last_y,
        )

        if self.last_intent.is_active() and moved_distance < 0.45:
            self.stuck_frames += 1
        else:
            self.stuck_frames = max(0, self.stuck_frames - 1)

        self.last_position = (float(player.x), float(player.y))

    def _pick_target_orb(self, player, players, orbs):
        enemies = [other for other in players if other.team_code != player.team_code]
        best_orb = None
        best_score = None

        for orb in orbs:
            player_distance = math.hypot(
                float(orb.x) - float(player.x),
                float(orb.y) - float(player.y),
            )
            enemy_distance = min(
                (
                    math.hypot(
                        float(orb.x) - float(enemy.x),
                        float(orb.y) - float(enemy.y),
                    )
                    for enemy in enemies
                ),
                default=player_distance + 180.0,
            )
            score = player_distance - min(
                self.settings["contest_cap"],
                enemy_distance * self.settings["contest_weight"],
            )
            score -= (
                max(0, int(getattr(orb, "value", 1)) - 1)
                * self.settings["rare_value_weight"]
            )

            if best_score is None or score < best_score:
                best_score = score
                best_orb = orb

        return best_orb

    def _build_intent_to_point(self, dx: float, dy: float) -> MovementIntent:
        threshold = self.settings["axis_threshold"]
        move_left = dx < -threshold
        move_right = dx > threshold
        move_up = dy < -threshold
        move_down = dy > threshold

        if abs(dx) > abs(dy) * 1.75:
            move_up = False
            move_down = False
        elif abs(dy) > abs(dx) * 1.75:
            move_left = False
            move_right = False

        return MovementIntent(
            up=move_up,
            down=move_down,
            left=move_left,
            right=move_right,
        )

    def _adjust_for_obstacles(
        self,
        player,
        direct_intent: MovementIntent,
        dx: float,
        dy: float,
        obstacles,
    ) -> MovementIntent:
        if not direct_intent.is_active() or not obstacles:
            self._clear_avoidance()
            return direct_intent

        blocking_obstacle = self._get_colliding_obstacle(
            player,
            direct_intent,
            obstacles,
        )
        if blocking_obstacle is None:
            self._clear_avoidance()
            return direct_intent

        if self.avoidance_axis is None or self.avoidance_direction == 0:
            self._start_avoidance(player, blocking_obstacle, dx, dy)

        candidate_intents = self._build_avoidance_candidates(direct_intent)

        for candidate in candidate_intents:
            if not self._would_collide(player, candidate, obstacles):
                return candidate

        alternate_candidates = self._build_avoidance_candidates(
            direct_intent,
            direction_override=-self.avoidance_direction,
        )
        for candidate in alternate_candidates:
            if not self._would_collide(player, candidate, obstacles):
                self.avoidance_direction *= -1
                return candidate

        return direct_intent

    def _build_avoidance_candidates(
        self,
        direct_intent: MovementIntent,
        *,
        direction_override: int | None = None,
    ) -> list[MovementIntent]:
        direction = direction_override or self.avoidance_direction or 1

        if self.avoidance_axis == "vertical":
            side_intent = MovementIntent(
                up=direction < 0,
                down=direction > 0,
            )
            return [
                MovementIntent(
                    left=direct_intent.left,
                    right=direct_intent.right,
                    up=side_intent.up,
                    down=side_intent.down,
                ),
                side_intent,
            ]

        side_intent = MovementIntent(
            left=direction < 0,
            right=direction > 0,
        )
        return [
            MovementIntent(
                up=direct_intent.up,
                down=direct_intent.down,
                left=side_intent.left,
                right=side_intent.right,
            ),
            side_intent,
        ]

    def _start_avoidance(self, player, obstacle, dx: float, dy: float) -> None:
        if abs(dx) >= abs(dy):
            self.avoidance_axis = "vertical"
            self.avoidance_direction = self._pick_vertical_avoidance(
                player,
                obstacle,
                dy,
            )
            return

        self.avoidance_axis = "horizontal"
        self.avoidance_direction = self._pick_horizontal_avoidance(
            player,
            obstacle,
            dx,
        )

    def _pick_vertical_avoidance(self, player, obstacle, dy: float) -> int:
        clearance_padding = player.radius + 12
        top_clearance = abs(player.y - (obstacle.top - clearance_padding))
        bottom_clearance = abs((obstacle.bottom + clearance_padding) - player.y)

        if abs(dy) > self.settings["axis_threshold"]:
            return -1 if dy < 0 else 1

        return -1 if top_clearance <= bottom_clearance else 1

    def _pick_horizontal_avoidance(self, player, obstacle, dx: float) -> int:
        clearance_padding = player.radius + 12
        left_clearance = abs(player.x - (obstacle.left - clearance_padding))
        right_clearance = abs((obstacle.right + clearance_padding) - player.x)

        if abs(dx) > self.settings["axis_threshold"]:
            return -1 if dx < 0 else 1

        return -1 if left_clearance <= right_clearance else 1

    def _clear_avoidance(self) -> None:
        self.avoidance_axis = None
        self.avoidance_direction = 0

    def _get_colliding_obstacle(
        self,
        player,
        intent: MovementIntent,
        obstacles,
    ):
        step_x = 0.0
        step_y = 0.0

        if intent.up:
            step_y -= player.speed
        if intent.down:
            step_y += player.speed
        if intent.left:
            step_x -= player.speed
        if intent.right:
            step_x += player.speed

        if step_x and step_y:
            factor = 1 / math.sqrt(2)
            step_x *= factor
            step_y *= factor

        test_rect = player.get_rect(player.x + step_x, player.y + step_y)
        for obstacle in obstacles:
            if test_rect.colliderect(obstacle):
                return obstacle
        return None

    def _would_collide(
        self,
        player,
        intent: MovementIntent,
        obstacles,
    ) -> bool:
        return self._get_colliding_obstacle(player, intent, obstacles) is not None

    def _enter_escape_mode(
        self,
        dx: float,
        dy: float,
        elapsed_ms: int,
    ) -> None:
        if abs(dx) >= abs(dy):
            go_up = self.rng.random() < 0.5
            self.escape_intent = MovementIntent(
                up=go_up,
                down=not go_up,
                left=dx < 0,
                right=dx > 0,
            )
        else:
            go_left = self.rng.random() < 0.5
            self.escape_intent = MovementIntent(
                up=dy < 0,
                down=dy > 0,
                left=go_left,
                right=not go_left,
            )

        self.escape_until_ms = elapsed_ms + self.settings["escape_duration_ms"]
