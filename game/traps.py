from __future__ import annotations

import random
from dataclasses import dataclass

from game.arena_layout import ArenaLayout, RectTuple


TRAP_TRANSITION_MS = 220.0

_TRAP_PROFILES = {
    "spike_trap": {
        "active_range_ms": (900, 1500),
        "idle_range_ms": (1300, 2400),
        "slow_duration_ms": 900,
        "slow_multiplier": 0.5,
    },
    "ember_trap": {
        "active_range_ms": (1000, 1650),
        "idle_range_ms": (1500, 2600),
        "slow_duration_ms": 1350,
        "slow_multiplier": 0.64,
    },
    "rune_trap": {
        "active_range_ms": (1200, 1900),
        "idle_range_ms": (1100, 2150),
        "slow_duration_ms": 1100,
        "slow_multiplier": 0.74,
    },
}


@dataclass
class TrapRuntime:
    element_id: str
    kind: str
    rect: RectTuple
    active: bool
    last_toggle_ms: float
    next_toggle_ms: float
    slow_duration_ms: int
    slow_multiplier: float
    active_range_ms: tuple[int, int]
    idle_range_ms: tuple[int, int]
    rng: random.Random


def _seed_for_trap(map_id: str, trap_id: str, kind: str) -> int:
    source = f"{map_id}:{trap_id}:{kind}"
    return sum((index + 1) * ord(character) for index, character in enumerate(source))


def _get_trap_profile(kind: str) -> dict:
    return dict(_TRAP_PROFILES.get(kind, _TRAP_PROFILES["spike_trap"]))


def _pick_duration_ms(rng: random.Random, bounds: tuple[int, int]) -> int:
    lower, upper = bounds
    return rng.randint(int(lower), int(upper))


def build_match_traps(layout: ArenaLayout, start_ms: float = 0.0) -> list[TrapRuntime]:
    trap_states = []
    for trap in layout.traps:
        profile = _get_trap_profile(trap.kind)
        rng = random.Random(_seed_for_trap(layout.map_id, trap.element_id, trap.kind))
        active = rng.random() >= 0.45
        initial_bounds = (
            profile["active_range_ms"] if active else profile["idle_range_ms"]
        )
        trap_states.append(
            TrapRuntime(
                element_id=trap.element_id,
                kind=trap.kind,
                rect=trap.rect,
                active=active,
                last_toggle_ms=float(start_ms),
                next_toggle_ms=float(start_ms + _pick_duration_ms(rng, initial_bounds)),
                slow_duration_ms=int(profile["slow_duration_ms"]),
                slow_multiplier=float(profile["slow_multiplier"]),
                active_range_ms=tuple(profile["active_range_ms"]),
                idle_range_ms=tuple(profile["idle_range_ms"]),
                rng=rng,
            )
        )
    return trap_states


def update_match_traps(trap_states: list[TrapRuntime], elapsed_ms: float) -> None:
    for trap in trap_states:
        while elapsed_ms >= trap.next_toggle_ms:
            trap.active = not trap.active
            trap.last_toggle_ms = trap.next_toggle_ms
            next_bounds = trap.active_range_ms if trap.active else trap.idle_range_ms
            trap.next_toggle_ms += _pick_duration_ms(trap.rng, next_bounds)


def snapshot_match_traps(
    trap_states: list[TrapRuntime], elapsed_ms: float
) -> list[dict]:
    snapshots = []
    for trap in trap_states:
        transition_elapsed_ms = max(0.0, elapsed_ms - trap.last_toggle_ms)
        transition_progress = min(1.0, transition_elapsed_ms / TRAP_TRANSITION_MS)
        presence = (
            transition_progress if trap.active else max(0.0, 1.0 - transition_progress)
        )
        snapshots.append(
            {
                "trap_id": trap.element_id,
                "kind": trap.kind,
                "rect": list(trap.rect),
                "active": trap.active,
                "presence": round(presence, 3),
            }
        )
    return snapshots
