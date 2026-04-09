import json
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

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
        return str(Path(sys.executable).resolve().parent / filename)
    return str(PROJECT_DIR / filename)


def runtime_user_dir() -> Path:
    """
    Retourne un dossier utilisateur inscriptible pour l'etat runtime.
    Ce dossier reste stable meme quand l'application est installee ailleurs.
    """
    if sys.platform.startswith("win"):
        base_dir = Path(
            os.environ.get("APPDATA")
            or (Path.home() / "AppData" / "Roaming")
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


def set_runtime_override(key: str, value):
    _RUNTIME_OVERRIDES[key] = value


def clear_runtime_override(key: str = None):
    if key is None:
        _RUNTIME_OVERRIDES.clear()
    else:
        _RUNTIME_OVERRIDES.pop(key, None)


def get_runtime_overrides() -> dict:
    return dict(_RUNTIME_OVERRIDES)


def load_runtime_config() -> dict:
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
    }

    path = Path(runtime_file_path("app_runtime.json"))
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            default_config.update(data)
        except (OSError, json.JSONDecodeError):
            pass

    # appliquer les overrides runtime en dernier
    default_config.update(_RUNTIME_OVERRIDES)

    return default_config
