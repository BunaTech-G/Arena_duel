import math

import pygame

from game.arena import draw_player_avatar
from game.control_models import HUMAN_CONTROL_MODE, MovementIntent
from game.settings import PLAYER_RADIUS, PLAYER_SPEED


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
        self.facing = 1 if team_code == "A" else -1
        self.is_moving = False

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
            self.radius * 2
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

    def update(self, keys, arena_rect, obstacles):
        self.update_from_intent(
            self.intent_from_keys(keys),
            arena_rect,
            obstacles,
        )

    def update_from_intent(self, intent, arena_rect, obstacles):
        intent = intent or MovementIntent()
        dx = 0
        dy = 0

        if intent.up:
            dy -= self.speed
        if intent.down:
            dy += self.speed
        if intent.left:
            dx -= self.speed
        if intent.right:
            dx += self.speed

        if dx != 0 and dy != 0:
            factor = 1 / math.sqrt(2)
            dx *= factor
            dy *= factor

        self.is_moving = dx != 0 or dy != 0

        if dx > 0:
            self.facing = 1
        elif dx < 0:
            self.facing = -1

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

    def draw(self, surface, name_font):
        draw_player_avatar(
            surface,
            name=self.name,
            x=self.x,
            y=self.y,
            radius=self.radius,
            accent_color=self.color,
            name_font=name_font,
            team_code=self.team_code,
            facing=self.facing,
            elapsed_ms=pygame.time.get_ticks(),
            moving=self.is_moving,
        )

    def collides_with_orb(self, orb):
        distance_sq = (self.x - orb.x) ** 2 + (self.y - orb.y) ** 2
        radius_sum = self.radius + orb.radius
        return distance_sq <= radius_sum ** 2
