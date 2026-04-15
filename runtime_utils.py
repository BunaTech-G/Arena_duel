import json
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
USER_RUNTIME_OVERRIDE_FILENAME = "app_runtime.user.json"

# override runtime temporaire (en mémoire)
_RUNTIME_OVERRIDES = {}


def resource_path(*parts) -> str:
    """
    Retourne le chemin d'un asset :
    - en source
    - ou dans le build PyInstaller
    """
    if getattr(sys, "frozen", False):
        base_path = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(sys.executable).resolve().parent,
            )
        )
    else:
        base_path = PROJECT_DIR

    return str(base_path.joinpath(*parts))


def runtime_file_path(filename: str) -> str:
    """
    Retourne le chemin d'un fichier runtime externe (ex: app_runtime.json)
    placé à côté de l'exe ou à la racine du projet source.
    """
    if getattr(sys, "frozen", False):
        external_path = Path(sys.executable).resolve().parent / filename
        if external_path.exists():
            return str(external_path)

        bundled_path = Path(resource_path(filename))
        if bundled_path.exists():
            return str(bundled_path)

        return str(external_path)
    return str(PROJECT_DIR / filename)


def runtime_user_dir() -> Path:
    """
    Retourne un dossier utilisateur inscriptible pour l'etat runtime.
    Ce dossier reste stable meme quand l'application est installee ailleurs.
    """
    if sys.platform.startswith("win"):
        base_dir = Path(
            os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        )
    else:
        base_dir = Path(
            os.environ.get("XDG_STATE_HOME")
            or os.environ.get("XDG_CONFIG_HOME")
            or (Path.home() / ".config")
        )

    target_dir = base_dir / "ArenaDuel"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir
    except OSError:
        fallback_dir = Path.home() / ".arena_duel"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir


def runtime_user_file_path(filename: str) -> str:
    return str(runtime_user_dir() / filename)


def runtime_user_config_path() -> str:
    return runtime_user_file_path(USER_RUNTIME_OVERRIDE_FILENAME)


def is_runtime_flag_enabled(
    flag_name: str,
    default: bool = False,
) -> bool:
    raw_value = load_runtime_config().get(flag_name, default)
    if isinstance(raw_value, bool):
        return raw_value

    normalized_value = str(raw_value).strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def set_runtime_override(key: str, value):
    _RUNTIME_OVERRIDES[key] = value


def clear_runtime_override(key: str = None):
    if key is None:
        _RUNTIME_OVERRIDES.clear()
    else:
        _RUNTIME_OVERRIDES.pop(key, None)


def get_runtime_overrides() -> dict:
    return dict(_RUNTIME_OVERRIDES)


def load_runtime_user_overrides() -> dict:
    return _load_runtime_json_file(Path(runtime_user_config_path()))


def load_persisted_runtime_config() -> dict:
    return load_runtime_config(include_session_overrides=False)


def save_runtime_user_overrides(overrides: dict) -> str:
    path = Path(runtime_user_config_path())
    path.parent.mkdir(parents=True, exist_ok=True)

    serializable_overrides = dict(overrides or {})
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(
            serializable_overrides,
            file_handle,
            ensure_ascii=False,
            indent=2,
        )

    return str(path)


def clear_runtime_user_overrides() -> str:
    path = Path(runtime_user_config_path())
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    return str(path)


def load_runtime_config(include_session_overrides: bool = True) -> dict:
    default_config = {
        "db_host": "localhost",
        "db_port": 3306,
        "db_user": "root",
        "db_password": "",
        "db_name": "arena_duel_v2_db",
        "db_connect_timeout": 3,
        "lan_bind_host": "0.0.0.0",
        "tcp_port": 5000,
        "lan_connect_timeout_seconds": 4,
        "hardware_bridge_enabled": False,
        "hardware_bridge_backend": "arduino",
        "hardware_serial_port": "",
        "hardware_serial_auto_detect": True,
        "hardware_serial_baudrate": 115200,
        "hardware_serial_timeout_seconds": 0.2,
        "hardware_serial_write_timeout_seconds": 0.2,
        "debug_console_logs": False,
        "demo_local_storage_enabled": False,
        "demo_local_storage_force": False,
        "demo_seed_players": [],
    }

    default_config.update(
        _load_runtime_json_file(Path(runtime_file_path("app_runtime.json")))
    )
    default_config.update(load_runtime_user_overrides())

    if include_session_overrides:
        # appliquer les overrides runtime en dernier
        default_config.update(_RUNTIME_OVERRIDES)

    return default_config


def _load_runtime_json_file(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            raw_data = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(raw_data, dict):
        return raw_data
    return {}
