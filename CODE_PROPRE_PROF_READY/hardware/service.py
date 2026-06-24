from __future__ import annotations

from dataclasses import dataclass

from hardware.arduino import (
    create_arduino_hardware_bridge,
    describe_arduino_runtime_status,
)
from hardware.bridge import (
    NullHardwareBridge,
    get_hardware_logger,
    load_hardware_runtime_config,
)


@dataclass(frozen=True)
class HardwareRuntimeStatus:
    badge_text: str
    tone: str
    detail_text: str


class MatchHardwareService:
    def __init__(self, bridge, logger=None):
        self.bridge = bridge
        self.logger = logger or get_hardware_logger()
        self._last_state = None
        self._last_score = None
        self._last_winner = None

    def reset(self):
        self._last_state = None
        self._last_score = None
        self._last_winner = None
        self.bridge.send_reset()

    def emit_state(self, state_code: str):
        normalized_state = _normalize_state_code(state_code)
        if not normalized_state or normalized_state == self._last_state:
            return

        self._last_state = normalized_state
        self.bridge.send_state(normalized_state)

    def emit_score(self, team_a_score: int, team_b_score: int):
        score = (int(team_a_score), int(team_b_score))
        if score == self._last_score:
            return

        self._last_score = score
        self.bridge.send_score(*score)

    def emit_winner(self, winner_code):
        normalized_winner = _normalize_winner_code(winner_code)
        if normalized_winner == self._last_winner:
            return

        self._last_winner = normalized_winner
        self.bridge.send_winner(normalized_winner)

    def shutdown(self):
        self.bridge.close()


def create_hardware_bridge(config=None):
    logger = get_hardware_logger()
    runtime_config = config or load_hardware_runtime_config()

    if not runtime_config.enabled:
        logger.info(
            "Support hardware desactive dans la configuration runtime."
        )
        return NullHardwareBridge()

    if runtime_config.backend != "arduino":
        logger.warning(
            "Backend hardware inconnu '%s' - pont desactive.",
            runtime_config.backend,
        )
        return NullHardwareBridge()

    return create_arduino_hardware_bridge(runtime_config, logger)


def create_match_hardware_service(config=None):
    logger = get_hardware_logger()
    bridge = create_hardware_bridge(config)
    return MatchHardwareService(bridge, logger=logger)


def describe_hardware_runtime_status(config=None) -> HardwareRuntimeStatus:
    runtime_config = config or load_hardware_runtime_config()

    if not runtime_config.enabled:
        return HardwareRuntimeStatus(
            badge_text="Bridge Arduino",
            tone="neutral",
            detail_text="Bonus materiel desactive dans la configuration.",
        )

    if runtime_config.backend != "arduino":
        return HardwareRuntimeStatus(
            badge_text="Bridge inconnu",
            tone="warning",
            detail_text=(
                f"Backend '{runtime_config.backend}' non gere. "
                "Le jeu reste autonome."
            ),
        )

    return HardwareRuntimeStatus(
        **describe_arduino_runtime_status(runtime_config)
    )


def _normalize_state_code(state_code: str) -> str:
    return str(state_code or "").strip().upper()


def _normalize_winner_code(winner_code) -> str:
    normalized_winner = str(winner_code or "DRAW").strip().upper()
    if normalized_winner in {"A", "B", "DRAW"}:
        return normalized_winner
    return "DRAW"
