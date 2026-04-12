from __future__ import annotations

from importlib.util import find_spec

from runtime_utils import load_runtime_config


BACKEND_PYGAME = "pygame"
BACKEND_ARCADE = "arcade"
SUPPORTED_GAMEPLAY_BACKENDS = {
    BACKEND_PYGAME,
    BACKEND_ARCADE,
}
BACKEND_LABELS = {
    BACKEND_PYGAME: "Pygame",
    BACKEND_ARCADE: "Arcade",
}


def normalize_gameplay_backend(raw_value) -> str:
    normalized = str(raw_value or BACKEND_PYGAME).strip().lower()
    if normalized not in SUPPORTED_GAMEPLAY_BACKENDS:
        return BACKEND_PYGAME
    return normalized


def resolve_local_game_backend(config: dict | None = None) -> str:
    runtime_config = config if config is not None else load_runtime_config()
    return normalize_gameplay_backend(runtime_config.get("gameplay_backend"))


def is_arcade_available() -> bool:
    return find_spec("arcade") is not None


def get_local_game_backend_status(
    config: dict | None = None,
) -> dict[str, str | None]:
    requested_backend = resolve_local_game_backend(config)
    effective_backend = requested_backend
    fallback_reason = None

    if requested_backend == BACKEND_ARCADE and not is_arcade_available():
        effective_backend = BACKEND_PYGAME
        fallback_reason = "arcade_unavailable"

    return {
        "requested": requested_backend,
        "effective": effective_backend,
        "requested_label": BACKEND_LABELS[requested_backend],
        "effective_label": BACKEND_LABELS[effective_backend],
        "fallback_reason": fallback_reason,
    }


def run_local_game(players_config, match_duration_seconds):
    backend_status = get_local_game_backend_status()

    if backend_status["effective"] == BACKEND_ARCADE:
        from game.arcade_window import run_game as run_arcade_game

        return run_arcade_game(
            players_config,
            match_duration_seconds=match_duration_seconds,
        )

    from game.game_window import run_game as run_pygame_game

    return run_pygame_game(
        players_config,
        match_duration_seconds=match_duration_seconds,
    )
