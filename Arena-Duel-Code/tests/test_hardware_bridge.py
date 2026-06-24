import os
import sys
import tempfile
import types
import unittest
import importlib
from unittest.mock import patch


TEST_APPDATA_DIR = tempfile.mkdtemp(prefix="arena_duel_hw_tests_")
os.environ.setdefault("APPDATA", TEST_APPDATA_DIR)

if "mariadb" not in sys.modules:
    sys.modules["mariadb"] = types.SimpleNamespace(
        Error=Exception,
        IntegrityError=Exception,
        connect=lambda **_kwargs: None,
    )


create_arduino_hardware_bridge = importlib.import_module(
    "hardware.arduino"
).create_arduino_hardware_bridge
list_available_serial_ports = importlib.import_module(
    "hardware.arduino"
).list_available_serial_ports
bridge_module = importlib.import_module("hardware.bridge")
service_module = importlib.import_module("hardware.service")
HardwareRuntimeConfig = bridge_module.HardwareRuntimeConfig
NullHardwareBridge = bridge_module.NullHardwareBridge
MatchHardwareService = service_module.MatchHardwareService
create_hardware_bridge = service_module.create_hardware_bridge


class RecordingBridge:
    def __init__(self):
        self.messages = []

    def send_reset(self):
        self.messages.append("RESET")

    def send_state(self, state_code: str):
        self.messages.append(f"STATE:{state_code}")

    def send_score(self, team_a_score: int, team_b_score: int):
        self.messages.append(f"SCORE:{team_a_score},{team_b_score}")

    def send_winner(self, winner_code: str):
        self.messages.append(f"WINNER:{winner_code}")

    def close(self):
        self.messages.append("CLOSE")


class HardwareBridgeTests(unittest.TestCase):
    def test_create_hardware_bridge_returns_null_when_disabled(self):
        config = HardwareRuntimeConfig(
            enabled=False,
            backend="arduino",
            serial_port="",
            auto_detect=True,
            baudrate=115200,
            timeout_seconds=0.2,
            write_timeout_seconds=0.2,
        )

        bridge = create_hardware_bridge(config)

        self.assertIsInstance(bridge, NullHardwareBridge)

    def test_arduino_bridge_falls_back_to_null_without_pyserial(self):
        config = HardwareRuntimeConfig(
            enabled=True,
            backend="arduino",
            serial_port="COM7",
            auto_detect=False,
            baudrate=115200,
            timeout_seconds=0.2,
            write_timeout_seconds=0.2,
        )

        with patch("hardware.arduino.serial", None), patch(
            "hardware.arduino.list_ports",
            None,
        ):
            bridge = create_arduino_hardware_bridge(
                config,
                logger=_NullLogger(),
            )

        self.assertIsInstance(bridge, NullHardwareBridge)

    def test_match_hardware_service_deduplicates_messages(self):
        bridge = RecordingBridge()
        service = MatchHardwareService(bridge)

        service.reset()
        service.emit_state("combat")
        service.emit_state("COMBAT")
        service.emit_score(1, 0)
        service.emit_score(1, 0)
        service.emit_score(2, 1)
        service.emit_winner("A")
        service.emit_winner("A")
        service.shutdown()

        self.assertEqual(
            bridge.messages,
            [
                "RESET",
                "STATE:COMBAT",
                "SCORE:1,0",
                "SCORE:2,1",
                "WINNER:A",
                "CLOSE",
            ],
        )

    def test_list_available_serial_ports_returns_devices(self):
        fake_port = types.SimpleNamespace(device="COM7")

        with patch("hardware.arduino.list_ports") as mocked_list_ports:
            mocked_list_ports.comports.return_value = [fake_port]

            ports = list_available_serial_ports()

        self.assertEqual(ports, ["COM7"])


class _NullLogger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None
