from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from runtime_utils import load_runtime_config, runtime_user_file_path


DEFAULT_HARDWARE_BACKEND = "arduino"
DEFAULT_HARDWARE_BAUDRATE = 115200
DEFAULT_HARDWARE_TIMEOUT_SECONDS = 0.2
DEFAULT_HARDWARE_WRITE_TIMEOUT_SECONDS = 0.2


@dataclass(frozen=True)
class HardwareRuntimeConfig:
    enabled: bool
    backend: str
    serial_port: str
    auto_detect: bool
    baudrate: int
    timeout_seconds: float
    write_timeout_seconds: float


class HardwareBridge(ABC):
    @abstractmethod
    def send_reset(self):
        raise NotImplementedError

    @abstractmethod
    def send_state(self, state_code: str):
        raise NotImplementedError

    @abstractmethod
    def send_score(self, team_a_score: int, team_b_score: int):
        raise NotImplementedError

    @abstractmethod
    def send_winner(self, winner_code: str):
        raise NotImplementedError

    @abstractmethod
    def close(self):
        raise NotImplementedError


class NullHardwareBridge(HardwareBridge):
    def send_reset(self):
        return None

    def send_state(self, state_code: str):
        return None

    def send_score(self, team_a_score: int, team_b_score: int):
        return None

    def send_winner(self, winner_code: str):
        return None

    def close(self):
        return None


def get_hardware_logger() -> logging.Logger:
    logger = logging.getLogger("arena_duel.hardware")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        handler = logging.FileHandler(
            runtime_user_file_path("arena_duel_hardware.log"),
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            )
        )
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    return logger


def load_hardware_runtime_config() -> HardwareRuntimeConfig:
    raw_config = load_runtime_config()
    return HardwareRuntimeConfig(
        enabled=_coerce_bool(
            raw_config.get("hardware_bridge_enabled"),
            False,
        ),
        backend=(
            str(
                raw_config.get("hardware_bridge_backend")
                or DEFAULT_HARDWARE_BACKEND
            )
            .strip()
            .lower()
            or DEFAULT_HARDWARE_BACKEND
        ),
        serial_port=str(raw_config.get("hardware_serial_port") or "")
        .strip(),
        auto_detect=_coerce_bool(
            raw_config.get("hardware_serial_auto_detect"),
            True,
        ),
        baudrate=_coerce_int(
            raw_config.get("hardware_serial_baudrate"),
            DEFAULT_HARDWARE_BAUDRATE,
            minimum=1200,
        ),
        timeout_seconds=_coerce_positive_float(
            raw_config.get("hardware_serial_timeout_seconds"),
            DEFAULT_HARDWARE_TIMEOUT_SECONDS,
        ),
        write_timeout_seconds=_coerce_positive_float(
            raw_config.get("hardware_serial_write_timeout_seconds"),
            DEFAULT_HARDWARE_WRITE_TIMEOUT_SECONDS,
        ),
    )


def _coerce_bool(value, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value

    normalized_value = str(value or "").strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    return bool(fallback)


def _coerce_int(value, fallback: int, minimum: int) -> int:
    try:
        coerced_value = int(value)
    except (TypeError, ValueError):
        return fallback

    if coerced_value >= minimum:
        return coerced_value
    return fallback


def _coerce_positive_float(value, fallback: float) -> float:
    try:
        coerced_value = float(value)
    except (TypeError, ValueError):
        return fallback

    if coerced_value > 0:
        return coerced_value
    return fallback
