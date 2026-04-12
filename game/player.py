import math

import pygame

from game.arena import draw_player_avatar
from game.arena_layout import circle_collides_with_rect
from game.control_models import HUMAN_CONTROL_MODE, MovementIntent
from game.settings import (
    ORB_COMBO_BONUS_CAP,
    ORB_COMBO_WINDOW_MS,
    PLAYER_RADIUS,
    PLAYER_SPEED,
    TRAP_SLOW_DURATION_MS,
    TRAP_SLOW_MULTIPLIER,
)


KEY_MAP = {
    "z": pygame.K_z,
    "q": pygame.K_q,
    "s": pygame.K_s,
    "d": pygame.K_d,
    "w": pygame.K_w,
    "a": pygame.K_a,
    "x": pygame.K_x,
    "c": pygame.K_c,
    "t": pygame.K_t,
    "f": pygame.K_f,
    "g": pygame.K_g,
    "h": pygame.K_h,
    "i": pygame.K_i,
    "j": pygame.K_j,
    "k": pygame.K_k,
    "l": pygame.K_l,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "kp8": pygame.K_KP8,
    "kp5": pygame.K_KP5,
    "kp4": pygame.K_KP4,
    "kp6": pygame.K_KP6,
}


class Player:
    def __init__(
        self,
        name,
        x,
        y,
        color,
        controls,
        team_code="A",
        control_mode=HUMAN_CONTROL_MODE,
        sprite_id=None,
    ):
        self.name = name
        self.x = float(x)
        self.y = float(y)
        self.color = color
        self.radius = PLAYER_RADIUS
        self.speed = PLAYER_SPEED
        self.score = 0
        self.team_code = team_code
        self.control_mode = str(control_mode or HUMAN_CONTROL_MODE)
        if team_code == "A":
            default_sprite_id = "skeleton_fighter_ember"
        else:
            default_sprite_id = "skeleton_fighter_aether"
        self.sprite_id = sprite_id or default_sprite_id
        self.facing = 1 if team_code == "A" else -1
        self.direction_name = "right" if self.facing >= 0 else "left"
        self.is_moving = False
        self.combo_count = 0
        self.combo_expires_at_ms = 0.0
        self.trap_slowed_until_ms = 0.0
        self.trap_slow_multiplier = 1.0

        self.controls = None
        if controls is not None:
            self.controls = {
                "up": KEY_MAP[controls["up"]],
                "down": KEY_MAP[controls["down"]],
                "left": KEY_MAP[controls["left"]],
                "right": KEY_MAP[controls["right"]],
            }

    def get_rect(self, x=None, y=None):
        px = self.x if x is None else x
        py = self.y if y is None else y
        return pygame.Rect(
            int(px - self.radius),
            int(py - self.radius),
            self.radius * 2,
            self.radius * 2,
        )

    def _collides_with_obstacles(self, x, y, obstacles):
        test_rect = self.get_rect(x, y)
        for obstacle in obstacles:
            if test_rect.colliderect(obstacle):
                return True
        return False

    def intent_from_keys(self, keys):
        if not self.controls:
            return MovementIntent()

        return MovementIntent(
            up=bool(keys[self.controls["up"]]),
            down=bool(keys[self.controls["down"]]),
            left=bool(keys[self.controls["left"]]),
            right=bool(keys[self.controls["right"]]),
        )

    def update(self, keys, arena_rect, obstacles, elapsed_ms: float | None = None):
        self.update_from_intent(
            self.intent_from_keys(keys),
            arena_rect,
            obstacles,
            elapsed_ms=elapsed_ms,
        )

    def _update_direction_name(self, dx: float, dy: float):
        active_directions = []
        if dy < 0:
            active_directions.append("up")
        elif dy > 0:
            active_directions.append("down")

        if dx < 0:
            active_directions.append("left")
        elif dx > 0:
            active_directions.append("right")

        if not active_directions:
            return

        if len(active_directions) == 1:
            next_direction = active_directions[0]
        elif self.direction_name in active_directions:
            next_direction = self.direction_name
        elif dx != 0:
            next_direction = "right" if dx > 0 else "left"
        else:
            next_direction = "down" if dy > 0 else "up"

        self.direction_name = next_direction
        if next_direction == "right":
            self.facing = 1
        elif next_direction == "left":
            self.facing = -1

    def get_speed_multiplier(self, elapsed_ms: float) -> float:
        if elapsed_ms < self.trap_slowed_until_ms:
            return self.trap_slow_multiplier
        self.trap_slow_multiplier = 1.0
        return 1.0

    def trigger_trap(
        self,
        elapsed_ms: float,
        *,
        slow_duration_ms: int = TRAP_SLOW_DURATION_MS,
        slow_multiplier: float = TRAP_SLOW_MULTIPLIER,
    ) -> bool:
        if elapsed_ms < self.trap_slowed_until_ms:
            return False

        self.trap_slowed_until_ms = elapsed_ms + max(0, int(slow_duration_ms))
        self.trap_slow_multiplier = max(0.25, min(1.0, float(slow_multiplier)))
        self.combo_count = 0
        self.combo_expires_at_ms = 0.0
        return True

    def collides_with_trap(self, trap_rect) -> bool:
        return circle_collides_with_rect(self.x, self.y, self.radius, trap_rect)

    def update_from_intent(
        self,
        intent,
        arena_rect,
        obstacles,
        elapsed_ms: float | None = None,
    ):
        intent = intent or MovementIntent()
        active_elapsed_ms = (
            pygame.time.get_ticks() if elapsed_ms is None else float(elapsed_ms)
        )
        current_speed = self.speed * self.get_speed_multiplier(active_elapsed_ms)
        dx = 0
        dy = 0

        if intent.up:
            dy -= current_speed
        if intent.down:
            dy += current_speed
        if intent.left:
            dx -= current_speed
        if intent.right:
            dx += current_speed

        if dx != 0 and dy != 0:
            factor = 1 / math.sqrt(2)
            dx *= factor
            dy *= factor

        self.is_moving = dx != 0 or dy != 0
        # La pose reste fixe tant que la direction d'entrée ne change pas.
        self._update_direction_name(dx, dy)

        # Déplacement X
        new_x = self.x + dx
        min_x = arena_rect.left + self.radius
        max_x = arena_rect.right - self.radius
        new_x = max(min_x, min(new_x, max_x))

        if not self._collides_with_obstacles(new_x, self.y, obstacles):
            self.x = new_x

        # Déplacement Y
        new_y = self.y + dy
        min_y = arena_rect.top + self.radius
        max_y = arena_rect.bottom - self.radius
        new_y = max(min_y, min(new_y, max_y))

        if not self._collides_with_obstacles(self.x, new_y, obstacles):
            self.y = new_y

    def get_combo_remaining_ms(self, elapsed_ms: float) -> int:
        remaining_ms = int(self.combo_expires_at_ms - elapsed_ms)
        if remaining_ms > 0 and self.combo_count > 1:
            return remaining_ms

        if elapsed_ms >= self.combo_expires_at_ms:
            self.combo_count = 0
            self.combo_expires_at_ms = 0.0
        return 0

    def register_orb_pickup(
        self, elapsed_ms: float, base_value: int
    ) -> tuple[int, int]:
        if elapsed_ms <= self.combo_expires_at_ms:
            self.combo_count += 1
        else:
            self.combo_count = 1

        self.combo_expires_at_ms = elapsed_ms + ORB_COMBO_WINDOW_MS
        combo_bonus = min(
            ORB_COMBO_BONUS_CAP,
            max(0, self.combo_count - 1),
        )
        awarded_value = int(base_value) + combo_bonus
        self.score += awarded_value
        return awarded_value, combo_bonus

    def draw(self, surface, name_font):
        elapsed_ms = pygame.time.get_ticks()
        draw_player_avatar(
            surface,
            name=self.name,
            x=self.x,
            y=self.y,
            radius=self.radius,
            accent_color=self.color,
            name_font=name_font,
            sprite_id=self.sprite_id,
            team_code=self.team_code,
            facing=self.facing,
            direction_name=self.direction_name,
            elapsed_ms=elapsed_ms,
            moving=self.is_moving,
            combo_count=self.combo_count,
            combo_remaining_ms=self.get_combo_remaining_ms(elapsed_ms),
        )

    def collides_with_orb(self, orb):
        distance_sq = (self.x - orb.x) ** 2 + (self.y - orb.y) ** 2
        radius_sum = self.radius + orb.radius
        return distance_sq <= radius_sum**2
