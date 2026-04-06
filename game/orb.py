import random
import pygame
from game.arena import draw_orb_visual
from game.arena_layout import random_free_point
from game.settings import ORB_RADIUS, ORB_COLOR, ORB_SCORE_VALUE


class Orb:
    def __init__(self, arena_rect, obstacles, layout=None):
        self.radius = ORB_RADIUS
        self.color = ORB_COLOR
        self.value = ORB_SCORE_VALUE
        self.layout = layout
        self.respawn(arena_rect, obstacles)

    def _is_inside_obstacle(self, x, y, obstacles):
        test_rect = pygame.Rect(
            x - self.radius,
            y - self.radius,
            self.radius * 2,
            self.radius * 2
        )
        for obstacle in obstacles:
            if test_rect.colliderect(obstacle):
                return True
        return False

    def respawn(self, arena_rect, obstacles):
        if self.layout is not None:
            x, y = random_free_point(self.layout, self.radius, padding=20)
            self.x = x
            self.y = y
            return

        while True:
            x = random.randint(arena_rect.left + self.radius, arena_rect.right - self.radius)
            y = random.randint(arena_rect.top + self.radius, arena_rect.bottom - self.radius)

            if not self._is_inside_obstacle(x, y, obstacles):
                self.x = x
                self.y = y
                return

    def draw(self, surface):
        draw_orb_visual(surface, self.x, self.y, self.radius, elapsed_ms=pygame.time.get_ticks())
