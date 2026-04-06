import json
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
        base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
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
        "tcp_port": 5000,
    }

    path = Path(runtime_file_path("app_runtime.json"))
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            default_config.update(data)
        except Exception:
            pass

    # appliquer les overrides runtime en dernier
    default_config.update(_RUNTIME_OVERRIDES)

    return default_config