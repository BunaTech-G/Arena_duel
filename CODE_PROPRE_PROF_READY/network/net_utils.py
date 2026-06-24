import errno
import ipaddress
import logging
import socket
from dataclasses import dataclass

from runtime_utils import load_runtime_config, runtime_user_file_path


LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}
DEFAULT_LAN_BIND_HOST = "0.0.0.0"
DEFAULT_LAN_PORT = 5000
DEFAULT_CONNECT_TIMEOUT_SECONDS = 4.0


@dataclass(frozen=True)
class LanRuntimeConfig:
    bind_host: str
    port: int
    connect_timeout_seconds: float
    client_state_path: str


@dataclass(frozen=True)
class LanAddressInfo:
    primary_ip: str | None
    candidate_ips: tuple[str, ...]
    warning: str | None = None

    @property
    def has_lan_ip(self) -> bool:
        return bool(self.primary_ip)


def load_lan_runtime_config() -> LanRuntimeConfig:
    raw_config = load_runtime_config()
    return LanRuntimeConfig(
        bind_host=str(
            raw_config.get("lan_bind_host") or DEFAULT_LAN_BIND_HOST
        ).strip() or DEFAULT_LAN_BIND_HOST,
        port=_coerce_port(raw_config.get("tcp_port"), DEFAULT_LAN_PORT),
        connect_timeout_seconds=_coerce_positive_float(
            raw_config.get(
                "lan_connect_timeout_seconds",
                DEFAULT_CONNECT_TIMEOUT_SECONDS,
            ),
            DEFAULT_CONNECT_TIMEOUT_SECONDS,
        ),
        client_state_path=runtime_user_file_path("client_lan_config.json"),
    )


def get_network_logger() -> logging.Logger:
    logger = logging.getLogger("arena_duel.network")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        handler = logging.FileHandler(
            runtime_user_file_path("arena_duel_network.log"),
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


def get_lan_address_info() -> LanAddressInfo:
    candidates = _collect_candidate_ipv4_addresses()
    if candidates:
        ordered = tuple(sorted(candidates, key=_ipv4_sort_key))
        return LanAddressInfo(primary_ip=ordered[0], candidate_ips=ordered)

    return LanAddressInfo(
        primary_ip=None,
        candidate_ips=tuple(),
        warning=(
            "Aucune IPv4 LAN exploitable n'a ete detectee sur ce poste. "
            "Verifie la connexion au reseau local avant d'inviter un autre PC."
        ),
    )


def get_local_lan_ip(fallback_to_loopback: bool = False) -> str:
    info = get_lan_address_info()
    if info.primary_ip:
        return info.primary_ip
    if fallback_to_loopback:
        return "127.0.0.1"
    return ""


def is_loopback_host(host: str) -> bool:
    normalized_host = str(host or "").strip().lower()
    if not normalized_host:
        return False
    if normalized_host in LOOPBACK_HOSTS:
        return True

    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def format_endpoint(host: str, port: int) -> str:
    return f"{host}:{int(port)}"


def parse_server_invitation(
    raw_value: str,
    default_port: int,
) -> tuple[str, int]:
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(
            "Saisis une invitation du type 192.168.1.25:5000 "
            "ou une IP LAN valide."
        )

    if "://" in value:
        value = value.split("://", 1)[1].strip()

    host = value
    port = _coerce_port(default_port, DEFAULT_LAN_PORT)

    if value.count(":") == 1:
        maybe_host, maybe_port = value.rsplit(":", 1)
        if maybe_port.isdigit():
            host = maybe_host.strip()
            port = _coerce_port(maybe_port, DEFAULT_LAN_PORT)

    host = host.strip().strip("[]")
    if not host:
        raise ValueError(
            "L'invitation LAN est incomplete. Utilise une IP "
            "du type 192.168.1.25."
        )

    normalized_host = host.lower()
    if normalized_host not in LOOPBACK_HOSTS:
        try:
            ipaddress.ip_address(host)
        except ValueError as error:
            raise ValueError(
                "L'invitation doit contenir une IPv4 exploitable, "
                "par exemple 192.168.1.25:5000."
            ) from error

    return host, port


def format_bind_error(host: str, port: int, error: OSError) -> str:
    endpoint = format_endpoint(host, port)
    winerror = getattr(error, "winerror", None)
    error_code = getattr(error, "errno", None)

    if (
        error_code == errno.EADDRINUSE
        or winerror in {10013, 10048}
    ):
        return (
            f"Impossible d'ouvrir le hall LAN sur {endpoint}: "
            "le port est deja occupe sur ce PC "
            "ou bloque par une autre application."
        )

    if error_code == errno.EADDRNOTAVAIL or winerror == 10049:
        return (
            f"Impossible d'ecouter sur {endpoint}: l'adresse "
            "de bind n'est pas disponible sur ce poste."
        )

    return f"Impossible d'ouvrir le hall LAN sur {endpoint}: {error}."


def format_connect_error(host: str, port: int, error: OSError) -> str:
    endpoint = format_endpoint(host, port)
    winerror = getattr(error, "winerror", None)
    error_code = getattr(error, "errno", None)

    if isinstance(error, socket.gaierror):
        return (
            f"Adresse invalide ou introuvable: {endpoint}. "
            "Utilise l'IP LAN affichee par l'hote."
        )

    if (
        isinstance(error, TimeoutError)
        or error_code == errno.ETIMEDOUT
        or winerror == 10060
    ):
        return (
            f"Aucun hall n'ecoute ou ne repond sur {endpoint}. "
            "Verifie que l'hote LAN est demarre et joignable."
        )

    if (
        isinstance(error, ConnectionRefusedError)
        or error_code == errno.ECONNREFUSED
        or winerror == 10061
    ):
        return (
            f"Aucun hall n'ecoute sur {endpoint}. Verifie que "
            "l'hote a bien demarre le hall LAN et que le port est correct."
        )

    if (
        error_code in {errno.EHOSTUNREACH, errno.ENETUNREACH}
        or winerror in {10051, 10065}
    ):
        return (
            f"Le reseau local n'est pas joignable vers {endpoint}. "
            "Verifie que les deux PC sont sur le meme reseau."
        )

    return f"Connexion impossible vers {endpoint}: {error}."


def _coerce_port(value, fallback: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return fallback

    if 1 <= port <= 65535:
        return port
    return fallback


def _coerce_positive_float(value, fallback: float) -> float:
    try:
        coerced_value = float(value)
    except (TypeError, ValueError):
        return fallback

    if coerced_value > 0:
        return coerced_value
    return fallback


def _collect_candidate_ipv4_addresses() -> list[str]:
    candidates: list[str] = []

    for target in (
        ("1.1.1.1", 80),
        ("8.8.8.8", 80),
        ("192.0.2.1", 80),
    ):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(target)
                _append_candidate(candidates, sock.getsockname()[0])
        except OSError:
            continue

    hostname = socket.gethostname()

    try:
        for _, _, _, _, sockaddr in socket.getaddrinfo(
            hostname,
            None,
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ):
            _append_candidate(candidates, sockaddr[0])
    except OSError:
        pass

    try:
        _, _, host_ips = socket.gethostbyname_ex(hostname)
        for host_ip in host_ips:
            _append_candidate(candidates, host_ip)
    except OSError:
        pass

    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _append_candidate(candidates: list[str], value: str):
    if not _is_usable_ipv4(value):
        return
    candidates.append(value)


def _is_usable_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return (
        isinstance(address, ipaddress.IPv4Address)
        and not address.is_loopback
        and not address.is_unspecified
        and not address.is_multicast
    )


def _ipv4_sort_key(value: str) -> tuple[int, str]:
    address = ipaddress.ip_address(value)
    if address.is_private:
        return (0, value)
    if address.is_link_local:
        return (1, value)
    return (2, value)
