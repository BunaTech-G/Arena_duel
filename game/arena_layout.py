from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from runtime_utils import resource_path


DEFAULT_MAP_ID = "forgotten_sanctum"
MAX_RANDOM_ATTEMPTS = 256

RectTuple = tuple[int, int, int, int]
PointTuple = tuple[int, int]


@dataclass(frozen=True)
class ArenaElement:
    element_id: str
    kind: str
    rect: RectTuple
    collision: bool = False


@dataclass(frozen=True)
class ArenaLayout:
    map_id: str
    label: str
    window_size: tuple[int, int]
    hud_height: int
    margin: int
    playable_rect: RectTuple
    spawn_groups: dict[str, tuple[PointTuple, ...]]
    obstacles: tuple[ArenaElement, ...]
    traps: tuple[ArenaElement, ...]
    decor: tuple[ArenaElement, ...]

    @property
    def width(self) -> int:
        return self.window_size[0]

    @property
    def height(self) -> int:
        return self.window_size[1]

    @property
    def left(self) -> int:
        return self.playable_rect[0]

    @property
    def top(self) -> int:
        return self.playable_rect[1]

    @property
    def right(self) -> int:
        return self.left + self.playable_rect[2]

    @property
    def bottom(self) -> int:
        return self.top + self.playable_rect[3]

    def collision_rects(self) -> tuple[RectTuple, ...]:
        return tuple(element.rect for element in self.obstacles if element.collision)

    def trap_rects(self) -> tuple[RectTuple, ...]:
        return tuple(element.rect for element in self.traps)

    def spawn_positions(self, team_code: str) -> tuple[PointTuple, ...]:
        return self.spawn_groups.get(team_code, ())


_LAYOUT_CACHE: dict[str, ArenaLayout] = {}


def _map_layout_path(map_id: str) -> Path:
    return Path(resource_path("assets", "maps", map_id, "layout.json"))


def _load_raw_layout(map_id: str) -> dict:
    layout_path = _map_layout_path(map_id)
    with open(layout_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _coerce_rect(raw_rect: list[int] | tuple[int, int, int, int]) -> RectTuple:
    return tuple(int(value) for value in raw_rect)  # type: ignore[return-value]


def _build_element(raw_data: dict) -> ArenaElement:
    return ArenaElement(
        element_id=str(raw_data.get("id", "element")),
        kind=str(raw_data.get("kind", "generic")),
        rect=_coerce_rect(raw_data.get("rect", [0, 0, 0, 0])),
        collision=bool(raw_data.get("collision", False)),
    )


def load_arena_layout(map_id: str = DEFAULT_MAP_ID) -> ArenaLayout:
    if map_id in _LAYOUT_CACHE:
        return _LAYOUT_CACHE[map_id]

    raw_data = _load_raw_layout(map_id)
    arena_data = raw_data.get("arena", {})
    spawn_groups = {
        str(team_code): tuple((int(x), int(y)) for x, y in positions)
        for team_code, positions in raw_data.get("spawn_groups", {}).items()
    }

    layout = ArenaLayout(
        map_id=str(raw_data.get("id", map_id)),
        label=str(raw_data.get("label", map_id.replace("_", " ").title())),
        window_size=tuple(
            int(value) for value in arena_data.get("window_size", [1280, 720])
        ),
        hud_height=int(arena_data.get("hud_height", 80)),
        margin=int(arena_data.get("margin", 60)),
        playable_rect=_coerce_rect(
            arena_data.get("playable_rect", [60, 80, 1160, 580])
        ),
        spawn_groups=spawn_groups,
        obstacles=tuple(_build_element(item) for item in raw_data.get("obstacles", [])),
        traps=tuple(_build_element(item) for item in raw_data.get("traps", [])),
        decor=tuple(_build_element(item) for item in raw_data.get("decor", [])),
    )
    _LAYOUT_CACHE[map_id] = layout
    return layout


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def clamp_position_to_arena(
    layout: ArenaLayout, x: float, y: float, radius: float
) -> tuple[float, float]:
    clamped_x = clamp(x, layout.left + radius, layout.right - radius)
    clamped_y = clamp(y, layout.top + radius, layout.bottom - radius)
    return clamped_x, clamped_y


def circle_collides_with_rect(
    x: float, y: float, radius: float, rect: RectTuple
) -> bool:
    rect_x, rect_y, rect_w, rect_h = rect
    nearest_x = clamp(x, rect_x, rect_x + rect_w)
    nearest_y = clamp(y, rect_y, rect_y + rect_h)
    dx = x - nearest_x
    dy = y - nearest_y
    return (dx * dx) + (dy * dy) <= radius * radius


def collides_with_obstacles(
    x: float,
    y: float,
    radius: float,
    obstacle_rects: tuple[RectTuple, ...] | list[RectTuple],
) -> bool:
    return any(circle_collides_with_rect(x, y, radius, rect) for rect in obstacle_rects)


def resolve_movement(
    layout: ArenaLayout,
    x: float,
    y: float,
    dx: float,
    dy: float,
    radius: float,
    obstacle_rects: tuple[RectTuple, ...] | list[RectTuple] | None = None,
) -> tuple[float, float]:
    blocked_rects = tuple(obstacle_rects or layout.collision_rects())
    current_x = x
    current_y = y

    next_x, _ = clamp_position_to_arena(layout, x + dx, y, radius)
    if not collides_with_obstacles(next_x, current_y, radius, blocked_rects):
        current_x = next_x

    _, next_y = clamp_position_to_arena(layout, current_x, y + dy, radius)
    if not collides_with_obstacles(current_x, next_y, radius, blocked_rects):
        current_y = next_y

    return current_x, current_y


def pick_spawn_position(layout: ArenaLayout, team_code: str, index: int) -> PointTuple:
    spawn_list = layout.spawn_positions(team_code)
    if not spawn_list:
        return (
            layout.left + layout.playable_rect[2] // 2,
            layout.top + layout.playable_rect[3] // 2,
        )

    clamped_index = max(0, min(index, len(spawn_list) - 1))
    return spawn_list[clamped_index]


def get_team_spawn_positions(
    layout: ArenaLayout, team_code: str, count: int
) -> list[PointTuple]:
    spawn_list = list(layout.spawn_positions(team_code))
    if count <= 0:
        return []

    if not spawn_list:
        fallback = pick_spawn_position(layout, team_code, 0)
        return [fallback for _ in range(count)]

    if len(spawn_list) >= count:
        if count == 1 and len(spawn_list) >= 3:
            return [spawn_list[len(spawn_list) // 2]]
        if count == 2 and len(spawn_list) >= 3:
            return [spawn_list[0], spawn_list[-1]]
        return spawn_list[:count]

    missing_count = count - len(spawn_list)
    return spawn_list + [spawn_list[-1] for _ in range(missing_count)]


def random_free_point(
    layout: ArenaLayout,
    radius: int,
    obstacle_rects: tuple[RectTuple, ...] | list[RectTuple] | None = None,
    padding: int = 0,
) -> PointTuple:
    blocked_rects = tuple(obstacle_rects or layout.collision_rects())
    blocked_rects += layout.trap_rects()
    min_x = layout.left + radius + padding
    max_x = layout.right - radius - padding
    min_y = layout.top + radius + padding
    max_y = layout.bottom - radius - padding

    for _ in range(MAX_RANDOM_ATTEMPTS):
        x = random.randint(min_x, max_x)
        y = random.randint(min_y, max_y)
        if not collides_with_obstacles(x, y, radius, blocked_rects):
            return x, y

    fallback_points = [
        (
            layout.left + layout.playable_rect[2] // 2,
            layout.top + layout.playable_rect[3] // 2,
        ),
        *layout.spawn_positions("A"),
        *layout.spawn_positions("B"),
    ]
    for x, y in fallback_points:
        clamped_x, clamped_y = clamp_position_to_arena(layout, x, y, radius)
        if not collides_with_obstacles(clamped_x, clamped_y, radius, blocked_rects):
            return int(clamped_x), int(clamped_y)

    return int(min_x), int(min_y)
