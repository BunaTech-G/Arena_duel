from __future__ import annotations


BACKEND_PYGAME = "pygame"
SUPPORTED_GAMEPLAY_BACKENDS = {
    BACKEND_PYGAME,
}
BACKEND_LABELS = {
    BACKEND_PYGAME: "Pygame",
}


def normalize_gameplay_backend(raw_value) -> str:
    return BACKEND_PYGAME


def resolve_local_game_backend(config: dict | None = None) -> str:
    return BACKEND_PYGAME


def get_local_game_backend_status(
    config: dict | None = None,
) -> dict[str, str | None]:
    requested_backend = resolve_local_game_backend(config)
    effective_backend = BACKEND_PYGAME

    return {
        "requested": requested_backend,
        "effective": effective_backend,
        "requested_label": BACKEND_LABELS[requested_backend],
        "effective_label": BACKEND_LABELS[effective_backend],
        "fallback_reason": None,
    }


def run_local_game(players_config, match_duration_seconds):
    from game.game_window import run_game as run_pygame_game

    return run_pygame_game(
        players_config,
        match_duration_seconds=match_duration_seconds,
    )
