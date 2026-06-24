from __future__ import annotations

import queue
import threading

from hardware.bridge import HardwareRuntimeConfig, NullHardwareBridge

try:
    import serial
    from serial import SerialException
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None
    SerialException = OSError


ARDUINO_PORT_KEYWORDS = (
    "arduino",
    "ch340",
    "wch",
    "usb serial",
    "cp210",
)


class ArduinoHardwareBridge:
    def __init__(self, serial_connection, logger):
        self.serial_connection = serial_connection
        self.logger = logger
        self.write_queue = queue.Queue()
        self.closed = False
        self.disabled = False
        self.writer_thread = threading.Thread(
            target=self._writer_loop,
            daemon=True,
        )
        self.writer_thread.start()

    def send_reset(self):
        self._enqueue_line("RESET")

    def send_state(self, state_code: str):
        self._enqueue_line(f"STATE:{state_code}")

    def send_score(self, team_a_score: int, team_b_score: int):
        self._enqueue_line(
            f"SCORE:{int(team_a_score)},{int(team_b_score)}"
        )

    def send_winner(self, winner_code: str):
        self._enqueue_line(f"WINNER:{winner_code}")

    def close(self):
        if self.closed:
            return

        self.closed = True
        self.write_queue.put(None)
        if self.writer_thread.is_alive():
            self.writer_thread.join(timeout=0.3)
        self._close_serial()

    def _enqueue_line(self, line: str):
        if self.closed or self.disabled:
            return
        self.write_queue.put(line)

    def _writer_loop(self):
        while True:
            payload = self.write_queue.get()
            if payload is None:
                break

            if self.disabled:
                continue

            try:
                self.serial_connection.write(
                    (payload + "\n").encode("ascii", errors="ignore")
                )
                self.serial_connection.flush()
            except (OSError, SerialException, ValueError) as error:
                self.disabled = True
                self.logger.warning(
                    "Pont Arduino desactive apres erreur serie: %s",
                    error,
                )
                break

        self._close_serial()

    def _close_serial(self):
        try:
            self.serial_connection.close()
        except (AttributeError, OSError, SerialException):
            pass


def create_arduino_hardware_bridge(config, logger):
    if serial is None or list_ports is None:
        logger.info(
            "Pont Arduino desactive: pyserial n'est pas installe."
        )
        return NullHardwareBridge()

    serial_port = _resolve_serial_port(config)
    if not serial_port:
        logger.info(
            "Pont Arduino desactive: aucun port serie compatible n'a "
            "ete detecte."
        )
        return NullHardwareBridge()

    try:
        serial_connection = serial.Serial(
            port=serial_port,
            baudrate=config.baudrate,
            timeout=config.timeout_seconds,
            write_timeout=config.write_timeout_seconds,
        )
    except (OSError, SerialException, ValueError) as error:
        logger.warning(
            "Pont Arduino indisponible sur %s: %s",
            serial_port,
            error,
        )
        return NullHardwareBridge()

    logger.info(
        "Pont Arduino actif sur %s (%s bauds).",
        serial_port,
        config.baudrate,
    )
    return ArduinoHardwareBridge(serial_connection, logger)


def describe_arduino_runtime_status(config):
    if serial is None or list_ports is None:
        return {
            "badge_text": "Bridge Arduino",
            "tone": "warning",
            "detail_text": (
                "pyserial manquant - le bonus materiel reste inactif."
            ),
        }

    available_ports = list(_list_available_ports())

    if config.serial_port:
        if config.serial_port in available_ports:
            return {
                "badge_text": "Arduino configure",
                "tone": "success",
                "detail_text": (
                    f"Port cible pret : {config.serial_port} · "
                    "LCD I2C + buzzer"
                ),
            }

        return {
            "badge_text": "Port serie introuvable",
            "tone": "warning",
            "detail_text": (
                f"{config.serial_port} n'est pas visible. "
                "Le jeu fonctionnera sans materiel."
            ),
        }

    if not config.auto_detect:
        return {
            "badge_text": "Bridge Arduino",
            "tone": "neutral",
            "detail_text": (
                "Auto-detection coupee. Renseigne un port serie pour "
                "l'activer."
            ),
        }

    detected_port = _resolve_serial_port(config)
    if detected_port:
        return {
            "badge_text": "Arduino detecte",
            "tone": "success",
            "detail_text": f"Port pressenti : {detected_port}",
        }

    return {
        "badge_text": "Arduino non detecte",
        "tone": "warning",
        "detail_text": (
            "Aucun port compatible visible. Le bonus materiel reste "
            "optionnel."
        ),
    }


def list_available_serial_ports() -> list[str]:
    return _list_available_ports()


def _resolve_serial_port(config: HardwareRuntimeConfig) -> str | None:
    if config.serial_port:
        return config.serial_port

    if not config.auto_detect or list_ports is None:
        return None

    available_ports = list(list_ports.comports())
    if not available_ports:
        return None

    for port_info in available_ports:
        searchable_text = " ".join(
            [
                str(port_info.device or ""),
                str(getattr(port_info, "description", "") or ""),
                str(getattr(port_info, "manufacturer", "") or ""),
                str(getattr(port_info, "hwid", "") or ""),
            ]
        ).lower()
        if any(
            keyword in searchable_text
            for keyword in ARDUINO_PORT_KEYWORDS
        ):
            return str(port_info.device)

    if len(available_ports) == 1:
        return str(available_ports[0].device)

    return None


def _list_available_ports() -> list[str]:
    if list_ports is None:
        return []
    return [str(port_info.device) for port_info in list_ports.comports()]
