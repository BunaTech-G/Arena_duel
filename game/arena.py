from __future__ import annotations

import math

import pygame

from game.asset_pipeline import (
    load_background_asset,
    load_orb_token_asset,
    load_sprite_animation_frame,
)
from game.arena_layout import (
    DEFAULT_MAP_ID,
    ArenaLayout,
    get_team_spawn_positions,
    load_arena_layout,
)
from game.settings import (
    ORB_COMBO_WINDOW_MS,
    ORB_COLLECTION_EFFECT_MS,
    ORB_RARE_SCORE_VALUE,
    ORB_SPAWN_ANIMATION_MS,
    TEAM_A_COLORS,
    TEAM_B_COLORS,
)


BACKGROUND_TOP = (18, 25, 35)
BACKGROUND_BOTTOM = (10, 13, 19)
BACKGROUND_GLOW_A = (70, 112, 98, 38)
BACKGROUND_GLOW_B = (145, 88, 58, 32)

ARENA_BASE = (49, 44, 38)
ARENA_TILE_DARK = (40, 35, 31)
ARENA_TILE_LIGHT = (56, 50, 44)
ARENA_EDGE = (151, 145, 132)
ARENA_EDGE_SHADOW = (31, 27, 24)
RUNE_COLOR = (111, 196, 196)
RUNE_SECONDARY = (220, 192, 124)

OBSTACLE_FILL = (88, 82, 76)
OBSTACLE_SHADE = (56, 50, 44)
OBSTACLE_EDGE = (176, 167, 150)
GRAVE_ACCENT = (101, 174, 170)
TRAP_CORE = (74, 40, 36)
TRAP_EDGE = (214, 146, 112)
TRAP_SPIKE = (206, 194, 174)
TRAP_GLOW = (250, 128, 84)
EMBER_TRAP_CORE = (105, 56, 38)
EMBER_TRAP_EDGE = (231, 151, 92)
EMBER_TRAP_GLOW = (255, 171, 88)
RUNE_TRAP_CORE = (34, 54, 58)
RUNE_TRAP_EDGE = (122, 201, 194)
RUNE_TRAP_GLOW = (171, 240, 228)

BONE_BASE = (236, 228, 210)
BONE_SHADE = (194, 183, 164)
BONE_OUTLINE = (79, 72, 64)
NAME_PANEL = (16, 19, 28, 210)
NAME_TEXT = (247, 241, 226)
WINDOW_BACKGROUND_ASSET = "arena_darkstone"
ARENA_FLOOR_ASSET = "forgotten_sanctum_floor"


_BACKGROUND_CACHE: dict[tuple[int, int], pygame.Surface] = {}
_FLOOR_CACHE: dict[tuple[str, int, int], pygame.Surface] = {}
_ORB_EFFECT_FONT_CACHE: dict[int, pygame.font.Font] = {}
PG_SRCALPHA = getattr(pygame, "SRCALPHA")


def get_map_layout(map_id: str = DEFAULT_MAP_ID) -> ArenaLayout:
    return load_arena_layout(map_id)


def get_arena_rect(layout: ArenaLayout | None = None) -> pygame.Rect:
    active_layout = layout or get_map_layout()
    return pygame.Rect(*active_layout.playable_rect)


def get_obstacles(layout: ArenaLayout | None = None) -> list[pygame.Rect]:
    active_layout = layout or get_map_layout()
    return [
        pygame.Rect(*element.rect)
        for element in active_layout.obstacles
        if element.collision
    ]


def get_team_spawn_positions_for_layout(
    layout: ArenaLayout, team_code: str, count: int
) -> list[tuple[int, int]]:
    return get_team_spawn_positions(layout, team_code, count)


def get_team_color(team_code: str, slot_index: int = 0) -> tuple[int, int, int]:
    palette = TEAM_A_COLORS if team_code == "A" else TEAM_B_COLORS
    return palette[slot_index % len(palette)]


def _get_orb_effect_font(size: int) -> pygame.font.Font:
    cached_font = _ORB_EFFECT_FONT_CACHE.get(size)
    if cached_font is not None:
        return cached_font

    if not pygame.font.get_init():
        pygame.font.init()

    font = pygame.font.SysFont("Segoe UI", size, bold=True)
    _ORB_EFFECT_FONT_CACHE[size] = font
    return font


def _draw_orb_sparkle(
    surface: pygame.Surface,
    *,
    x: int,
    y: int,
    radius: int,
    alpha: int,
) -> None:
    sparkle_size = radius * 4 + 4
    sparkle_surface = pygame.Surface(
        (sparkle_size, sparkle_size),
        PG_SRCALPHA,
    )
    center = sparkle_size // 2
    color = (255, 248, 226, alpha)
    pygame.draw.line(
        sparkle_surface,
        color,
        (center, center - radius),
        (center, center + radius),
        max(1, radius // 2),
    )
    pygame.draw.line(
        sparkle_surface,
        color,
        (center - radius, center),
        (center + radius, center),
        max(1, radius // 2),
    )
    pygame.draw.circle(
        sparkle_surface,
        (255, 252, 243, min(255, alpha + 35)),
        (center, center),
        max(1, radius // 2),
    )
    surface.blit(
        sparkle_surface,
        (x - center, y - center),
    )


def _mix_color(
    start: tuple[int, int, int], end: tuple[int, int, int], blend: float
) -> tuple[int, int, int]:
    return tuple(int(a + (b - a) * blend) for a, b in zip(start, end))


def _build_background_surface(size: tuple[int, int]) -> pygame.Surface:
    width, height = size
    background_asset = load_background_asset(
        WINDOW_BACKGROUND_ASSET, size=size, allow_placeholder=False
    )
    surface = (
        background_asset.copy()
        if background_asset is not None
        else pygame.Surface(size)
    )

    if background_asset is None:
        band_height = 6
        for y in range(0, height, band_height):
            blend = y / max(1, height - 1)
            color = _mix_color(BACKGROUND_TOP, BACKGROUND_BOTTOM, blend)
            pygame.draw.rect(surface, color, (0, y, width, band_height))

    glow_surface = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.ellipse(
        glow_surface, BACKGROUND_GLOW_A, (-120, 80, width // 2, height // 2)
    )
    pygame.draw.ellipse(
        glow_surface, BACKGROUND_GLOW_B, (width // 2, -40, width // 2, height // 3)
    )
    pygame.draw.ellipse(
        glow_surface,
        (20, 24, 34, 120),
        (-100, height // 2, width + 200, height // 2 + 120),
    )
    surface.blit(glow_surface, (0, 0))
    return surface


def _get_background_surface(size: tuple[int, int]) -> pygame.Surface:
    if size not in _BACKGROUND_CACHE:
        _BACKGROUND_CACHE[size] = _build_background_surface(size)
    return _BACKGROUND_CACHE[size]


def _build_floor_surface(layout: ArenaLayout) -> pygame.Surface:
    arena_rect = get_arena_rect(layout)
    width, height = arena_rect.size
    floor_asset = load_background_asset(
        ARENA_FLOOR_ASSET, size=(width, height), allow_placeholder=False
    )
    floor = (
        floor_asset.copy()
        if floor_asset is not None
        else pygame.Surface((width, height), pygame.SRCALPHA)
    )

    if floor_asset is None:
        floor.fill(ARENA_BASE)

        tile_size = 58
        for row in range(0, height, tile_size):
            for col in range(0, width, tile_size):
                tile_color = (
                    ARENA_TILE_LIGHT
                    if ((row // tile_size) + (col // tile_size)) % 2 == 0
                    else ARENA_TILE_DARK
                )
                tile_rect = pygame.Rect(col, row, tile_size - 2, tile_size - 2)
                pygame.draw.rect(floor, tile_color, tile_rect, border_radius=8)

        crack_color = (77, 70, 62)
        crack_lines = [
            (
                (width * 0.18, height * 0.06),
                (width * 0.31, height * 0.22),
                (width * 0.28, height * 0.34),
            ),
            (
                (width * 0.74, height * 0.14),
                (width * 0.66, height * 0.27),
                (width * 0.72, height * 0.39),
            ),
            (
                (width * 0.21, height * 0.63),
                (width * 0.33, height * 0.75),
                (width * 0.27, height * 0.86),
            ),
            (
                (width * 0.82, height * 0.58),
                (width * 0.7, height * 0.66),
                (width * 0.76, height * 0.8),
            ),
        ]
        for path in crack_lines:
            pygame.draw.lines(floor, crack_color, False, path, width=3)

    edge_shadow = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(
        edge_shadow, (*ARENA_EDGE_SHADOW, 120), edge_shadow.get_rect(), border_radius=18
    )
    pygame.draw.rect(
        edge_shadow,
        (*ARENA_EDGE, 205),
        edge_shadow.get_rect(),
        width=4,
        border_radius=18,
    )
    floor.blit(edge_shadow, (0, 0))
    return floor


def _get_floor_surface(layout: ArenaLayout) -> pygame.Surface:
    arena_rect = get_arena_rect(layout)
    cache_key = (layout.map_id, arena_rect.width, arena_rect.height)
    if cache_key not in _FLOOR_CACHE:
        _FLOOR_CACHE[cache_key] = _build_floor_surface(layout)
    return _FLOOR_CACHE[cache_key]


def _draw_rune_circle(
    surface: pygame.Surface, rect: pygame.Rect, elapsed_ms: float
) -> None:
    pulse = 0.55 + 0.45 * math.sin(elapsed_ms / 480.0)
    rune_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
    center = (rect.width // 2, rect.height // 2)

    for shrink, alpha in ((0, 54), (24, 78), (52, 110)):
        outline_rect = pygame.Rect(
            shrink, shrink, rect.width - shrink * 2, rect.height - shrink * 2
        )
        if outline_rect.width > 0 and outline_rect.height > 0:
            pygame.draw.ellipse(
                rune_surface, (*RUNE_COLOR, alpha), outline_rect, width=2
            )

    ring_radius = min(rect.width, rect.height) * 0.36
    for index in range(12):
        angle = (math.tau / 12.0) * index + (elapsed_ms / 1600.0)
        x = int(center[0] + math.cos(angle) * ring_radius)
        y = int(center[1] + math.sin(angle) * ring_radius)
        glow_alpha = int(80 + 60 * pulse)
        pygame.draw.circle(rune_surface, (*RUNE_SECONDARY, glow_alpha), (x, y), 5)

    surface.blit(rune_surface, rect.topleft)


def _draw_banner_shadow(surface: pygame.Surface, rect: pygame.Rect) -> None:
    banner_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(
        banner_surface, (8, 11, 17, 65), banner_surface.get_rect(), border_radius=18
    )
    pygame.draw.rect(
        banner_surface,
        (171, 135, 76, 34),
        banner_surface.get_rect(),
        width=2,
        border_radius=18,
    )
    surface.blit(banner_surface, rect.topleft)


def _draw_spike_trap(
    surface: pygame.Surface,
    rect: pygame.Rect,
    elapsed_ms: float,
    active_presence: float,
) -> None:
    pulse = 0.52 + 0.48 * math.sin(elapsed_ms / 220.0 + rect.centerx * 0.013)
    aura_margin = 12
    aura_size = (rect.width + aura_margin * 2, rect.height + aura_margin * 2)
    aura_surface = pygame.Surface(aura_size, pygame.SRCALPHA)
    aura_center = (aura_surface.get_width() // 2, aura_surface.get_height() // 2)
    aura_radius = max(rect.width, rect.height) // 2 - 2
    if active_presence > 0.04:
        pygame.draw.circle(
            aura_surface,
            (*TRAP_GLOW, int((18 + 32 * pulse) * active_presence)),
            aura_center,
            aura_radius + 5,
        )
        pygame.draw.circle(
            aura_surface,
            (42, 18, 14, int((118 + 28 * pulse) * active_presence)),
            aura_center,
            aura_radius,
        )
        surface.blit(
            aura_surface,
            (rect.left - aura_margin, rect.top - aura_margin),
        )

    plate_rect = rect.inflate(-12, -12)
    pygame.draw.ellipse(surface, (32, 21, 18), plate_rect)
    pygame.draw.ellipse(surface, TRAP_CORE, plate_rect, width=0)
    pygame.draw.ellipse(surface, TRAP_EDGE, plate_rect, width=2)

    center_x = plate_rect.centerx
    center_y = plate_rect.centery
    inner_radius = max(7, min(plate_rect.width, plate_rect.height) // 5)
    outer_radius = max(12, min(plate_rect.width, plate_rect.height) // 2 - 5)
    tip_radius = outer_radius + int((4 + 4 * pulse) * active_presence)
    if active_presence > 0.02:
        for index in range(6):
            angle = (math.tau / 6.0) * index - math.pi / 2.0
            left_angle = angle - 0.28
            right_angle = angle + 0.28
            spike_points = [
                (
                    int(center_x + math.cos(angle) * tip_radius),
                    int(center_y + math.sin(angle) * tip_radius),
                ),
                (
                    int(center_x + math.cos(left_angle) * inner_radius),
                    int(center_y + math.sin(left_angle) * inner_radius),
                ),
                (
                    int(center_x + math.cos(right_angle) * inner_radius),
                    int(center_y + math.sin(right_angle) * inner_radius),
                ),
            ]
            pygame.draw.polygon(surface, TRAP_SPIKE, spike_points)
            pygame.draw.polygon(surface, (87, 66, 58), spike_points, width=1)

    core_radius = max(8, inner_radius - 2)
    pygame.draw.circle(surface, (120, 58, 42), (center_x, center_y), core_radius)
    pygame.draw.circle(
        surface,
        (*TRAP_GLOW, int((38 + 86 * pulse) * (0.25 + active_presence * 0.75))),
        (center_x, center_y),
        max(4, core_radius - 3),
    )


def _draw_ember_trap(
    surface: pygame.Surface,
    rect: pygame.Rect,
    elapsed_ms: float,
    active_presence: float,
) -> None:
    pulse = 0.5 + 0.5 * math.sin(elapsed_ms / 170.0 + rect.centery * 0.015)
    base_rect = rect.inflate(-12, -12)
    pygame.draw.ellipse(surface, (30, 20, 18), base_rect)
    pygame.draw.ellipse(surface, EMBER_TRAP_CORE, base_rect, width=0)
    pygame.draw.ellipse(surface, EMBER_TRAP_EDGE, base_rect, width=2)

    grille_rect = base_rect.inflate(-10, -10)
    pygame.draw.ellipse(surface, (52, 30, 24), grille_rect)
    for offset in (-6, 0, 6):
        pygame.draw.line(
            surface,
            (92, 66, 48),
            (grille_rect.left + 6, grille_rect.centery + offset),
            (grille_rect.right - 6, grille_rect.centery + offset),
            2,
        )

    if active_presence <= 0.02:
        return

    glow_radius = max(14, rect.width // 2)
    glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(
        glow_surface,
        (*EMBER_TRAP_GLOW, int((34 + 54 * pulse) * active_presence)),
        (glow_radius, glow_radius),
        glow_radius,
    )
    surface.blit(
        glow_surface,
        (rect.centerx - glow_radius, rect.centery - glow_radius),
    )

    flame_height = int((8 + 8 * pulse) * active_presence)
    for offset_x in (-8, 0, 8):
        flame_points = [
            (rect.centerx + offset_x, rect.centery - flame_height - 5),
            (rect.centerx + offset_x - 5, rect.centery + 5),
            (rect.centerx + offset_x + 5, rect.centery + 5),
        ]
        pygame.draw.polygon(surface, (255, 214, 130), flame_points)
        inner_points = [
            (rect.centerx + offset_x, rect.centery - max(4, flame_height - 2)),
            (rect.centerx + offset_x - 3, rect.centery + 2),
            (rect.centerx + offset_x + 3, rect.centery + 2),
        ]
        pygame.draw.polygon(surface, (255, 128, 76), inner_points)


def _draw_rune_trap(
    surface: pygame.Surface,
    rect: pygame.Rect,
    elapsed_ms: float,
    active_presence: float,
) -> None:
    pulse = 0.5 + 0.5 * math.sin(elapsed_ms / 260.0 + rect.centerx * 0.012)
    base_rect = rect.inflate(-14, -14)
    pygame.draw.rect(surface, (18, 26, 30), base_rect, border_radius=10)
    pygame.draw.rect(surface, RUNE_TRAP_CORE, base_rect, border_radius=10)
    pygame.draw.rect(surface, RUNE_TRAP_EDGE, base_rect, width=2, border_radius=10)

    diamond = [
        (base_rect.centerx, base_rect.top + 2),
        (base_rect.right - 2, base_rect.centery),
        (base_rect.centerx, base_rect.bottom - 2),
        (base_rect.left + 2, base_rect.centery),
    ]
    pygame.draw.polygon(surface, (60, 98, 102), diamond, width=1)

    if active_presence <= 0.02:
        pygame.draw.circle(surface, (94, 128, 132), base_rect.center, 4)
        return

    rune_alpha = int((52 + 110 * pulse) * active_presence)
    rune_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    center = (rect.width // 2, rect.height // 2)
    pygame.draw.circle(
        rune_surface,
        (*RUNE_TRAP_GLOW, rune_alpha),
        center,
        max(12, rect.width // 3),
        width=2,
    )
    pygame.draw.line(
        rune_surface,
        (*RUNE_TRAP_GLOW, rune_alpha),
        (center[0], center[1] - 10),
        (center[0], center[1] + 10),
        2,
    )
    pygame.draw.line(
        rune_surface,
        (*RUNE_TRAP_GLOW, rune_alpha),
        (center[0] - 9, center[1]),
        (center[0] + 9, center[1]),
        2,
    )
    orbit_angle = elapsed_ms / 320.0
    orbit_x = int(center[0] + math.cos(orbit_angle) * 12)
    orbit_y = int(center[1] + math.sin(orbit_angle) * 12)
    pygame.draw.circle(
        rune_surface,
        (*RUNE_TRAP_GLOW, min(255, rune_alpha + 20)),
        (orbit_x, orbit_y),
        3,
    )
    surface.blit(rune_surface, rect.topleft)


def _draw_ruin_wall(surface: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, OBSTACLE_FILL, rect, border_radius=12)
    pygame.draw.rect(surface, OBSTACLE_EDGE, rect, width=3, border_radius=12)
    pygame.draw.rect(
        surface,
        OBSTACLE_SHADE,
        (rect.left + 8, rect.top + 8, rect.width - 16, rect.height // 2),
        border_radius=10,
    )

    brick_height = max(10, rect.height // 3)
    for y in range(rect.top + brick_height, rect.bottom, brick_height):
        pygame.draw.line(
            surface, OBSTACLE_EDGE, (rect.left + 10, y), (rect.right - 10, y), 2
        )


def _draw_pillar_cluster(surface: pygame.Surface, rect: pygame.Rect) -> None:
    base_rect = rect.inflate(10, 12)
    pygame.draw.rect(surface, OBSTACLE_SHADE, base_rect, border_radius=14)
    pygame.draw.rect(surface, OBSTACLE_EDGE, base_rect, width=2, border_radius=14)

    column_width = max(18, rect.width // 4)
    gap = max(6, (rect.width - column_width * 3) // 4)
    for index in range(3):
        column_rect = pygame.Rect(
            rect.left + gap + index * (column_width + gap),
            rect.top,
            column_width,
            rect.height,
        )
        pygame.draw.rect(surface, OBSTACLE_FILL, column_rect, border_radius=10)
        pygame.draw.rect(surface, OBSTACLE_EDGE, column_rect, width=2, border_radius=10)
        cap_rect = pygame.Rect(
            column_rect.left - 4, column_rect.top - 8, column_rect.width + 8, 16
        )
        pygame.draw.rect(surface, OBSTACLE_EDGE, cap_rect, border_radius=8)


def _draw_grave_marker(
    surface: pygame.Surface, rect: pygame.Rect, elapsed_ms: float
) -> None:
    headstone_rect = pygame.Rect(
        rect.left + 8, rect.top + 6, rect.width - 16, rect.height - 12
    )
    pygame.draw.rect(surface, OBSTACLE_FILL, headstone_rect, border_radius=22)
    pygame.draw.rect(surface, OBSTACLE_EDGE, headstone_rect, width=3, border_radius=22)
    pygame.draw.line(
        surface,
        BONE_SHADE,
        (headstone_rect.centerx, headstone_rect.top + 14),
        (headstone_rect.centerx, headstone_rect.bottom - 14),
        3,
    )
    pulse = 0.5 + 0.5 * math.sin(elapsed_ms / 340.0 + rect.centerx * 0.02)
    rune_rect = pygame.Rect(
        headstone_rect.centerx - 14, headstone_rect.centery - 18, 28, 36
    )
    rune_surface = pygame.Surface(rune_rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(
        rune_surface,
        (*GRAVE_ACCENT, int(80 + 70 * pulse)),
        rune_surface.get_rect(),
        width=2,
    )
    pygame.draw.line(
        rune_surface, (*GRAVE_ACCENT, int(110 + 80 * pulse)), (14, 6), (14, 30), 2
    )
    pygame.draw.line(
        rune_surface, (*GRAVE_ACCENT, int(110 + 80 * pulse)), (7, 18), (21, 18), 2
    )
    surface.blit(rune_surface, rune_rect.topleft)


def _draw_obstacle(
    surface: pygame.Surface, rect: pygame.Rect, kind: str, elapsed_ms: float
) -> None:
    if kind == "pillar_cluster":
        _draw_pillar_cluster(surface, rect)
        return
    if kind == "grave_marker":
        _draw_grave_marker(surface, rect, elapsed_ms)
        return
    _draw_ruin_wall(surface, rect)


def draw_background(surface: pygame.Surface, layout: ArenaLayout | None = None) -> None:
    del layout
    surface.blit(_get_background_surface(surface.get_size()), (0, 0))


def draw_arena(
    surface: pygame.Surface,
    arena_rect: pygame.Rect,
    obstacles: list[pygame.Rect],
    layout: ArenaLayout | None = None,
    trap_states: list[dict] | None = None,
    elapsed_ms: float = 0.0,
) -> None:
    active_layout = layout or get_map_layout()
    surface.blit(_get_floor_surface(active_layout), arena_rect.topleft)

    for decor in active_layout.decor:
        decor_rect = pygame.Rect(*decor.rect)
        if decor.kind == "rune_circle":
            _draw_rune_circle(surface, decor_rect, elapsed_ms)
        elif decor.kind == "banner_shadow":
            _draw_banner_shadow(surface, decor_rect)

    active_trap_states = trap_states or [
        {
            "kind": trap.kind,
            "rect": list(trap.rect),
            "presence": 1.0,
            "active": True,
        }
        for trap in active_layout.traps
    ]
    for trap_state in active_trap_states:
        trap_rect = pygame.Rect(*trap_state.get("rect", [0, 0, 0, 0]))
        trap_kind = str(trap_state.get("kind", "spike_trap"))
        active_presence = float(trap_state.get("presence", 1.0))
        if trap_kind == "ember_trap":
            _draw_ember_trap(surface, trap_rect, elapsed_ms, active_presence)
        elif trap_kind == "rune_trap":
            _draw_rune_trap(surface, trap_rect, elapsed_ms, active_presence)
        else:
            _draw_spike_trap(surface, trap_rect, elapsed_ms, active_presence)

    obstacle_kinds = [
        element.kind for element in active_layout.obstacles if element.collision
    ]
    for index, rect in enumerate(obstacles):
        obstacle_kind = (
            obstacle_kinds[index] if index < len(obstacle_kinds) else "ruin_wall"
        )
        _draw_obstacle(surface, rect, obstacle_kind, elapsed_ms)

    pygame.draw.rect(
        surface, ARENA_EDGE_SHADOW, arena_rect.inflate(8, 10), width=6, border_radius=18
    )
    pygame.draw.rect(surface, ARENA_EDGE, arena_rect, width=4, border_radius=16)


def draw_orb_visual(
    surface: pygame.Surface,
    x: float,
    y: float,
    radius: int,
    elapsed_ms: float = 0.0,
    value: int = 1,
    variant: str = "common",
    spawned_at_ms: float | None = None,
) -> None:
    is_rare = variant == "rare" or value >= ORB_RARE_SCORE_VALUE
    hover_amplitude = 3.2 if is_rare else 2.4
    hover_offset = math.sin((elapsed_ms / 280.0) + x * 0.022 + y * 0.017)
    center_x = int(x)
    center_y = int(y + hover_offset * hover_amplitude)
    floor_y = int(y + radius * 1.1)

    spawn_age = ORB_SPAWN_ANIMATION_MS
    if spawned_at_ms is not None:
        spawn_age = max(0.0, elapsed_ms - spawned_at_ms)
    spawn_progress = min(1.0, spawn_age / ORB_SPAWN_ANIMATION_MS)

    pulse = 1.0 + 0.05 * math.sin((elapsed_ms / 180.0) + x * 0.03)
    variant_scale = 1.15 if is_rare else 1.0
    pop_scale = 0.78 + (0.22 * spawn_progress)
    token_size = radius * 3.0 * pulse * variant_scale * pop_scale
    token_size = max(radius * 3, int(round(token_size / 2.0)) * 2)

    shadow_width = max(radius + 2, int(token_size * 0.34))
    shadow_height = max(6, int(radius * 0.44))
    shadow_alpha = 56 if is_rare else 42
    shadow_alpha = int(shadow_alpha * (0.78 + (0.22 * spawn_progress)))
    shadow_surface = pygame.Surface(
        (shadow_width * 2, shadow_height * 2),
        PG_SRCALPHA,
    )
    pygame.draw.ellipse(
        shadow_surface,
        (0, 0, 0, shadow_alpha),
        shadow_surface.get_rect(),
    )
    surface.blit(
        shadow_surface,
        (center_x - shadow_width, floor_y - shadow_height),
    )

    aura_radius = max(
        radius + 8,
        int(token_size * (0.42 if is_rare else 0.36)),
    )
    aura_color = (255, 162, 76) if is_rare else (247, 208, 106)
    aura_surface = pygame.Surface(
        (aura_radius * 2, aura_radius * 2),
        PG_SRCALPHA,
    )
    for factor, alpha in ((1.0, 18), (0.74, 30), (0.48, 52)):
        boost = 22 if is_rare else 0
        pygame.draw.circle(
            aura_surface,
            (*aura_color, alpha + boost),
            (aura_radius, aura_radius),
            int(aura_radius * factor),
        )
    surface.blit(
        aura_surface,
        (center_x - aura_radius, center_y - aura_radius),
    )

    if spawn_progress < 1.0:
        ring_radius = max(
            radius + 10,
            int(radius * (2.1 - (0.55 * spawn_progress))),
        )
        ring_alpha = int(140 * (1.0 - spawn_progress))
        ring_surface = pygame.Surface(
            (ring_radius * 2 + 6, ring_radius * 2 + 6),
            PG_SRCALPHA,
        )
        pygame.draw.circle(
            ring_surface,
            (*aura_color, ring_alpha),
            (ring_radius + 3, ring_radius + 3),
            ring_radius,
            width=max(2, radius // 4),
        )
        surface.blit(
            ring_surface,
            (center_x - ring_radius - 3, center_y - ring_radius - 3),
        )

    token = load_orb_token_asset(
        size=(token_size, token_size),
        allow_placeholder=True,
    )
    if token is None:
        return

    if spawn_progress < 1.0:
        token = token.copy()
        token.set_alpha(int(110 + (145 * spawn_progress)))

    token_rect = token.get_rect(center=(center_x, center_y))
    surface.blit(token, token_rect)

    if is_rare:
        sparkle_angle = (elapsed_ms / 320.0) + (x * 0.01)
        sparkle_radius = max(radius + 8, int(radius * 1.45))
        sparkle_alpha = int(150 + 60 * (0.5 + 0.5 * math.sin(elapsed_ms / 120.0)))
        sparkle_positions = [
            (
                int(center_x + math.cos(sparkle_angle) * sparkle_radius),
                int(center_y - radius * 0.3 + math.sin(sparkle_angle) * radius * 0.75),
            ),
            (
                int(
                    center_x
                    + math.cos(sparkle_angle + math.pi) * (sparkle_radius * 0.82)
                ),
                int(
                    center_y
                    - radius * 0.1
                    + math.sin(sparkle_angle + math.pi) * radius * 0.62
                ),
            ),
        ]
        for sparkle_x, sparkle_y in sparkle_positions:
            _draw_orb_sparkle(
                surface,
                x=sparkle_x,
                y=sparkle_y,
                radius=max(2, radius // 3),
                alpha=sparkle_alpha,
            )

    if is_rare:
        badge_radius = max(10, radius - 1)
        badge_size = badge_radius * 2 + 6
        badge_surface = pygame.Surface((badge_size, badge_size), PG_SRCALPHA)
        pygame.draw.circle(
            badge_surface,
            (120, 49, 12, 236),
            (badge_size // 2, badge_size // 2),
            badge_radius,
        )
        pygame.draw.circle(
            badge_surface,
            (255, 232, 184, 255),
            (badge_size // 2, badge_size // 2),
            badge_radius,
            width=2,
        )
        badge_font = _get_orb_effect_font(max(14, radius + 2))
        badge_text = badge_font.render(str(value), True, (255, 248, 223))
        badge_rect = badge_text.get_rect(
            center=(badge_size // 2, badge_size // 2),
        )
        badge_surface.blit(badge_text, badge_rect)
        surface.blit(
            badge_surface,
            (token_rect.right - badge_radius, token_rect.top - 2),
        )


def draw_orb_collection_effect(
    surface: pygame.Surface,
    *,
    x: float,
    y: float,
    value: int,
    elapsed_ms: float,
    started_at_ms: float,
    combo_count: int = 0,
    combo_bonus: int = 0,
) -> bool:
    age = max(0.0, elapsed_ms - started_at_ms)
    if age >= ORB_COLLECTION_EFFECT_MS:
        return False

    progress = age / ORB_COLLECTION_EFFECT_MS
    fade = 1.0 - progress
    is_rare = value >= ORB_RARE_SCORE_VALUE
    accent_color = (255, 166, 86) if is_rare else (247, 208, 106)
    text_color = (255, 245, 214) if is_rare else (255, 238, 196)

    effect_radius = int(12 + (24 * progress))
    effect_surface = pygame.Surface(
        (effect_radius * 2 + 20, effect_radius * 2 + 20),
        PG_SRCALPHA,
    )
    effect_center = (effect_radius + 10, effect_radius + 10)
    pygame.draw.circle(
        effect_surface,
        (*accent_color, int(136 * fade)),
        effect_center,
        effect_radius,
        width=max(2, int(3 - progress)),
    )

    particle_distance = 8 + ((18 if is_rare else 14) * progress)
    particle_radius = max(2, int((4 if is_rare else 3) * fade))
    particle_alpha = int(188 * fade)
    particle_count = 8 if is_rare else 6
    for index in range(particle_count):
        angle = ((math.tau / particle_count) * index) + (progress * 1.8)
        particle_x = int(effect_center[0] + math.cos(angle) * particle_distance)
        particle_y = int(effect_center[1] + math.sin(angle) * particle_distance)
        pygame.draw.circle(
            effect_surface,
            (*accent_color, particle_alpha),
            (particle_x, particle_y),
            particle_radius,
        )

    surface.blit(
        effect_surface,
        (int(x) - effect_center[0], int(y) - effect_center[1]),
    )

    text_font = _get_orb_effect_font(24 if is_rare else 20)
    text_surface = text_font.render(f"+{value}", True, text_color)
    text_surface = text_surface.copy()
    text_surface.set_alpha(int(255 * fade))
    text_rect = text_surface.get_rect(
        center=(int(x), int(y - 12 - (26 * progress))),
    )
    surface.blit(text_surface, text_rect)

    if combo_count >= 2:
        combo_font = _get_orb_effect_font(16 if combo_count < 4 else 18)
        combo_label = f"COMBO x{combo_count}"
        if combo_bonus > 0:
            combo_label += f"  +{combo_bonus}"
        combo_surface = combo_font.render(combo_label, True, text_color)
        combo_surface = combo_surface.copy()
        combo_surface.set_alpha(int(232 * fade))
        combo_rect = combo_surface.get_rect(
            center=(int(x), int(y + 12 - (14 * progress))),
        )
        surface.blit(combo_surface, combo_rect)

    return True


def _draw_combo_badge(
    surface: pygame.Surface,
    *,
    center_x: int,
    center_y: int,
    combo_count: int,
    combo_remaining_ms: int,
    accent_bright: tuple[int, int, int],
    font: pygame.font.Font,
) -> None:
    if combo_count < 2 or combo_remaining_ms <= 0:
        return

    label = f"x{combo_count}"
    text_surface = font.render(label, True, (250, 244, 230))
    text_rect = text_surface.get_rect(center=(center_x, center_y))
    badge_rect = text_rect.inflate(16, 8)
    badge_surface = pygame.Surface(badge_rect.size, PG_SRCALPHA)
    pygame.draw.rect(
        badge_surface,
        (34, 22, 16, 196),
        badge_surface.get_rect(),
        border_radius=11,
    )
    pygame.draw.rect(
        badge_surface,
        (*accent_bright, 220),
        badge_surface.get_rect(),
        width=2,
        border_radius=11,
    )

    progress_rect = pygame.Rect(
        6,
        badge_rect.height - 5,
        max(8, badge_rect.width - 12),
        2,
    )
    pygame.draw.rect(
        badge_surface,
        (72, 56, 48, 220),
        progress_rect,
        border_radius=3,
    )
    fill_width = max(
        6,
        int(progress_rect.width * min(1.0, combo_remaining_ms / ORB_COMBO_WINDOW_MS)),
    )
    pygame.draw.rect(
        badge_surface,
        (*accent_bright, 240),
        pygame.Rect(progress_rect.x, progress_rect.y, fill_width, progress_rect.height),
        border_radius=3,
    )

    badge_surface.blit(
        text_surface,
        text_surface.get_rect(
            center=(badge_rect.width // 2, badge_rect.height // 2 - 2)
        ),
    )
    surface.blit(badge_surface, badge_rect.topleft)


def _draw_nameplate(
    surface: pygame.Surface,
    *,
    center_x: int,
    center_y: int,
    name: str,
    name_font: pygame.font.Font,
    accent_bright: tuple[int, int, int],
) -> None:
    name_surface = name_font.render(name, True, NAME_TEXT)
    name_rect = name_surface.get_rect(center=(center_x, center_y))
    label_rect = name_rect.inflate(18, 10)
    label_surface = pygame.Surface(label_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(
        label_surface, NAME_PANEL, label_surface.get_rect(), border_radius=12
    )
    pygame.draw.rect(
        label_surface,
        (*accent_bright, 205),
        label_surface.get_rect(),
        width=2,
        border_radius=12,
    )
    surface.blit(label_surface, label_rect.topleft)
    surface.blit(name_surface, name_rect)


def _draw_procedural_player_avatar(
    surface: pygame.Surface,
    *,
    name: str,
    x: float,
    y: float,
    radius: int,
    accent_color: tuple[int, int, int],
    name_font: pygame.font.Font,
    highlight: bool = False,
    team_code: str = "A",
    facing: int = 1,
    elapsed_ms: float = 0.0,
    combo_count: int = 0,
    combo_remaining_ms: int = 0,
) -> None:
    center_x = int(x)
    center_y = int(y + math.sin((elapsed_ms / 210.0) + x * 0.02) * 2.0)
    direction = 1 if facing >= 0 else -1
    sway = math.sin((elapsed_ms / 260.0) + y * 0.02) * 3.0

    shadow_rect = pygame.Rect(
        center_x - radius, center_y + radius - 4, radius * 2, max(10, radius // 2 + 4)
    )
    shadow_surface = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surface, (0, 0, 0, 92), shadow_surface.get_rect())
    surface.blit(shadow_surface, shadow_rect.topleft)

    accent_dark = tuple(max(0, int(channel * 0.48)) for channel in accent_color)
    accent_bright = tuple(
        min(255, int(channel * 0.88 + 32)) for channel in accent_color
    )

    cape_points = [
        (center_x - int(radius * 0.5), center_y - int(radius * 0.45)),
        (center_x + int(radius * 0.54), center_y - int(radius * 0.45)),
        (
            center_x + int(radius * 0.95 * direction + sway),
            center_y + int(radius * 1.38),
        ),
        (
            center_x - int(radius * 0.9 * direction - sway),
            center_y + int(radius * 1.18),
        ),
    ]
    pygame.draw.polygon(surface, accent_dark, cape_points)
    pygame.draw.polygon(surface, accent_bright, cape_points, width=2)

    head_rect = pygame.Rect(
        center_x - int(radius * 0.72),
        center_y - int(radius * 1.7),
        int(radius * 1.44),
        int(radius * 1.26),
    )
    pygame.draw.ellipse(surface, BONE_BASE, head_rect)
    pygame.draw.ellipse(surface, BONE_OUTLINE, head_rect, width=2)

    jaw_rect = pygame.Rect(
        head_rect.left + int(radius * 0.16),
        head_rect.bottom - int(radius * 0.34),
        int(radius * 1.12),
        int(radius * 0.38),
    )
    pygame.draw.rect(surface, BONE_SHADE, jaw_rect, border_radius=6)
    pygame.draw.rect(surface, BONE_OUTLINE, jaw_rect, width=2, border_radius=6)

    eye_offset_x = int(radius * 0.28)
    eye_y = head_rect.centery - 2
    pygame.draw.circle(
        surface, (37, 43, 55), (center_x - eye_offset_x, eye_y), max(3, radius // 5)
    )
    pygame.draw.circle(
        surface, (37, 43, 55), (center_x + eye_offset_x, eye_y), max(3, radius // 5)
    )
    pygame.draw.polygon(
        surface,
        BONE_OUTLINE,
        [(center_x, eye_y + 2), (center_x - 4, eye_y + 10), (center_x + 4, eye_y + 10)],
    )

    neck_top = (center_x, head_rect.bottom - 2)
    spine_mid = (center_x, center_y - int(radius * 0.25))
    pelvis = (center_x, center_y + int(radius * 0.78))
    pygame.draw.line(surface, BONE_SHADE, neck_top, spine_mid, max(4, radius // 4))
    pygame.draw.line(surface, BONE_SHADE, spine_mid, pelvis, max(4, radius // 4))

    rib_rect = pygame.Rect(
        center_x - int(radius * 0.56),
        center_y - int(radius * 0.7),
        int(radius * 1.12),
        int(radius * 1.0),
    )
    pygame.draw.ellipse(surface, BONE_BASE, rib_rect)
    pygame.draw.ellipse(surface, BONE_OUTLINE, rib_rect, width=2)
    for offset in (-0.28, 0.0, 0.28):
        start_y = center_y - int(radius * 0.5) + int(offset * radius)
        pygame.draw.line(
            surface,
            BONE_SHADE,
            (center_x - int(radius * 0.44), start_y),
            (center_x + int(radius * 0.44), start_y),
            2,
        )

    arm_y = center_y - int(radius * 0.32)
    left_hand = (center_x - int(radius * 0.9), center_y + int(radius * 0.32))
    right_hand = (center_x + int(radius * 0.9), center_y + int(radius * 0.32))
    pygame.draw.line(
        surface,
        BONE_SHADE,
        (center_x - int(radius * 0.36), arm_y),
        left_hand,
        max(4, radius // 4),
    )
    pygame.draw.line(
        surface,
        BONE_SHADE,
        (center_x + int(radius * 0.36), arm_y),
        right_hand,
        max(4, radius // 4),
    )
    pygame.draw.circle(surface, BONE_BASE, left_hand, max(4, radius // 5))
    pygame.draw.circle(surface, BONE_BASE, right_hand, max(4, radius // 5))

    left_foot = (center_x - int(radius * 0.48), center_y + int(radius * 1.72))
    right_foot = (center_x + int(radius * 0.48), center_y + int(radius * 1.72))
    pygame.draw.line(surface, BONE_SHADE, pelvis, left_foot, max(4, radius // 4))
    pygame.draw.line(surface, BONE_SHADE, pelvis, right_foot, max(4, radius // 4))
    pygame.draw.line(
        surface,
        accent_bright,
        (center_x - int(radius * 0.3), center_y - int(radius * 0.2)),
        (center_x + int(radius * 0.42), center_y + int(radius * 0.38)),
        3,
    )

    if highlight:
        pygame.draw.circle(
            surface,
            (244, 241, 223),
            (center_x, center_y - int(radius * 0.1)),
            int(radius * 1.55),
            width=2,
        )

    _draw_nameplate(
        surface,
        center_x=center_x,
        center_y=center_y - int(radius * 2.15),
        name=name,
        name_font=name_font,
        accent_bright=accent_bright,
    )
    _draw_combo_badge(
        surface,
        center_x=center_x + int(radius * 0.92),
        center_y=center_y - int(radius * 1.55),
        combo_count=combo_count,
        combo_remaining_ms=combo_remaining_ms,
        accent_bright=accent_bright,
        font=name_font,
    )

    if team_code == "A":
        torch_pos = (center_x - int(radius * 0.76), center_y + int(radius * 0.3))
    else:
        torch_pos = (center_x + int(radius * 0.76), center_y + int(radius * 0.3))
    pygame.draw.circle(surface, (*accent_bright, 215), torch_pos, max(3, radius // 6))


def draw_player_avatar(
    surface: pygame.Surface,
    *,
    name: str,
    x: float,
    y: float,
    radius: int,
    accent_color: tuple[int, int, int],
    name_font: pygame.font.Font,
    sprite_id: str = "skeleton_mascot",
    highlight: bool = False,
    team_code: str = "A",
    facing: int = 1,
    direction_name: str | None = None,
    elapsed_ms: float = 0.0,
    moving: bool = False,
    combo_count: int = 0,
    combo_remaining_ms: int = 0,
) -> None:
    center_x = int(x)
    center_y = int(y)
    resolved_direction = direction_name or ("right" if facing >= 0 else "left")
    direction = 1 if facing >= 0 else -1
    accent_bright = tuple(
        min(255, int(channel * 0.88 + 32)) for channel in accent_color
    )

    shadow_rect = pygame.Rect(
        center_x - radius, center_y + radius - 4, radius * 2, max(10, radius // 2 + 4)
    )
    shadow_surface = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surface, (0, 0, 0, 92), shadow_surface.get_rect())
    surface.blit(shadow_surface, shadow_rect.topleft)

    animation_name = "walk" if moving else "idle"
    frame_index = int(elapsed_ms / (120 if moving else 180))
    sprite_size = (max(52, int(radius * 2.7)), max(52, int(radius * 2.7)))
    sprite = load_sprite_animation_frame(
        sprite_id,
        animation_name,
        frame_index,
        size=sprite_size,
        facing=direction,
        allow_placeholder=False,
    )
    if sprite is None and moving:
        sprite = load_sprite_animation_frame(
            sprite_id,
            "idle",
            frame_index,
            size=sprite_size,
            facing=direction,
            allow_placeholder=False,
        )

    if sprite is not None:
        aura_radius = int(radius * (1.85 if highlight else 1.45))
        aura_surface = pygame.Surface(
            (aura_radius * 2, aura_radius * 2), pygame.SRCALPHA
        )
        pygame.draw.circle(
            aura_surface,
            (*accent_bright, 38 if highlight else 24),
            (aura_radius, aura_radius),
            aura_radius,
        )
        surface.blit(
            aura_surface, (center_x - aura_radius, center_y - aura_radius - radius // 2)
        )

        sprite_rect = sprite.get_rect(
            midbottom=(center_x, center_y + int(radius * 1.7))
        )
        surface.blit(sprite, sprite_rect)

        if highlight:
            pygame.draw.circle(
                surface,
                (244, 241, 223),
                (center_x, center_y - int(radius * 0.08)),
                int(radius * 1.55),
                width=2,
            )

        _draw_nameplate(
            surface,
            center_x=center_x,
            center_y=center_y - int(radius * 2.0),
            name=name,
            name_font=name_font,
            accent_bright=accent_bright,
        )
        _draw_combo_badge(
            surface,
            center_x=center_x + int(radius * 0.98),
            center_y=center_y - int(radius * 1.5),
            combo_count=combo_count,
            combo_remaining_ms=combo_remaining_ms,
            accent_bright=accent_bright,
            font=name_font,
        )

        focus_offsets = {
            "left": (-int(radius * 0.8), int(radius * 0.18)),
            "right": (int(radius * 0.8), int(radius * 0.18)),
            "up": (0, -int(radius * 0.32)),
            "down": (0, int(radius * 0.18)),
        }
        offset_x, offset_y = focus_offsets.get(
            resolved_direction,
            (int(radius * 0.8), int(radius * 0.18)),
        )
        focus_pos = (center_x + offset_x, center_y + offset_y)
        pygame.draw.circle(
            surface, (*accent_bright, 215), focus_pos, max(3, radius // 6)
        )
        return

    _draw_procedural_player_avatar(
        surface,
        name=name,
        x=x,
        y=y,
        radius=radius,
        accent_color=accent_color,
        name_font=name_font,
        highlight=highlight,
        team_code=team_code,
        facing=facing,
        elapsed_ms=elapsed_ms,
        combo_count=combo_count,
        combo_remaining_ms=combo_remaining_ms,
    )
