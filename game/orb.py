import random
import pygame
from game.settings import ORB_RADIUS, ORB_COLOR, ORB_SCORE_VALUE


class Orb:
    def __init__(self, arena_rect, obstacles):
        self.radius = ORB_RADIUS
        self.color = ORB_COLOR
        self.value = ORB_SCORE_VALUE
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
        while True:
            x = random.randint(arena_rect.left + self.radius, arena_rect.right - self.radius)
            y = random.randint(arena_rect.top + self.radius, arena_rect.bottom - self.radius)

            if not self._is_inside_obstacle(x, y, obstacles):
                self.x = x
                self.y = y
                return

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 1)
