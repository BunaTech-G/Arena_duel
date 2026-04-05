import pygame
from game.settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    BACKGROUND_COLOR,
    ARENA_BG_COLOR,
    WALL_COLOR,
    GRID_COLOR,
    ARENA_MARGIN,
    OBSTACLE_COLOR,
    OBSTACLE_BORDER_COLOR,
)

HUD_HEIGHT = 80


def get_arena_rect():
    return pygame.Rect(
        ARENA_MARGIN,
        HUD_HEIGHT,
        WINDOW_WIDTH - (ARENA_MARGIN * 2),
        WINDOW_HEIGHT - HUD_HEIGHT - ARENA_MARGIN
    )


def get_obstacles(arena_rect):
    cx = arena_rect.centerx
    cy = arena_rect.centery

    obstacles = [
        pygame.Rect(cx - 70, arena_rect.top + 80, 140, 36),
        pygame.Rect(cx - 70, arena_rect.bottom - 116, 140, 36),
        pygame.Rect(arena_rect.left + 140, cy - 20, 120, 40),
        pygame.Rect(arena_rect.right - 260, cy - 20, 120, 40),
    ]
    return obstacles


def draw_background(surface):
    surface.fill(BACKGROUND_COLOR)


def draw_arena(surface, arena_rect, obstacles):
    # Fond d’arène
    pygame.draw.rect(surface, ARENA_BG_COLOR, arena_rect, border_radius=8)

    # Quadrillage
    grid_step = 40
    for x in range(arena_rect.left, arena_rect.right, grid_step):
        pygame.draw.line(surface, GRID_COLOR, (x, arena_rect.top), (x, arena_rect.bottom), 1)

    for y in range(arena_rect.top, arena_rect.bottom, grid_step):
        pygame.draw.line(surface, GRID_COLOR, (arena_rect.left, y), (arena_rect.right, y), 1)

    # Bordure
    pygame.draw.rect(surface, WALL_COLOR, arena_rect, width=4, border_radius=8)

    # Obstacles
    for rect in obstacles:
        pygame.draw.rect(surface, OBSTACLE_COLOR, rect, border_radius=6)
        pygame.draw.rect(surface, OBSTACLE_BORDER_COLOR, rect, width=2, border_radius=6)