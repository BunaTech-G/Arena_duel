import random
import pygame

from game.arena import draw_orb_visual
from game.arena_layout import random_free_point
from game.settings import (
    ORB_RADIUS,
    ORB_COLOR,
    ORB_RARE_SCORE_VALUE,
    ORB_RARE_SPAWN_CHANCE,
    ORB_SCORE_VALUE,
)


def _roll_orb_reward() -> tuple[str, int]:
    if random.random() < ORB_RARE_SPAWN_CHANCE:
        return "rare", ORB_RARE_SCORE_VALUE
    return "common", ORB_SCORE_VALUE


class Orb:
    def __init__(
        self,
        arena_rect,
        obstacles,
        layout=None,
        elapsed_ms: float | None = None,
    ):
        self.radius = ORB_RADIUS
        self.color = ORB_COLOR
        self.value = ORB_SCORE_VALUE
        self.variant = "common"
        self.spawned_at_ms = 0
        self.layout = layout
        self.respawn(arena_rect, obstacles, elapsed_ms=elapsed_ms)

    def _resolve_elapsed_ms(self, elapsed_ms: float | None = None) -> int:
        if elapsed_ms is None:
            return pygame.time.get_ticks()
        return int(elapsed_ms)

    def _is_inside_obstacle(self, x, y, obstacles):
        test_rect = pygame.Rect(
            x - self.radius, y - self.radius, self.radius * 2, self.radius * 2
        )
        for obstacle in obstacles:
            if test_rect.colliderect(obstacle):
                return True
        return False

    def respawn(self, arena_rect, obstacles, elapsed_ms: float | None = None):
        self.variant, self.value = _roll_orb_reward()
        active_elapsed_ms = self._resolve_elapsed_ms(elapsed_ms)

        if self.layout is not None:
            x, y = random_free_point(self.layout, self.radius, padding=20)
            self.x = x
            self.y = y
            self.spawned_at_ms = active_elapsed_ms
            return

        while True:
            x = random.randint(
                arena_rect.left + self.radius,
                arena_rect.right - self.radius,
            )
            y = random.randint(
                arena_rect.top + self.radius,
                arena_rect.bottom - self.radius,
            )

            if not self._is_inside_obstacle(x, y, obstacles):
                self.x = x
                self.y = y
                self.spawned_at_ms = active_elapsed_ms
                return

    def draw(self, surface):
        elapsed_ms = pygame.time.get_ticks()
        draw_orb_visual(
            surface,
            self.x,
            self.y,
            self.radius,
            elapsed_ms=elapsed_ms,
            value=self.value,
            variant=self.variant,
            spawned_at_ms=self.spawned_at_ms,
        )
