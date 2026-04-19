import mariadb
import time

from db.demo_store import is_demo_storage_enabled, should_force_demo_storage
from runtime_utils import load_runtime_config


DB_FAILURE_COOLDOWN_SECONDS = 5.0
_LAST_CONNECTION_FAILURE_AT = 0.0
_LAST_CONNECTION_FAILURE_KEY = None


def _connection_cache_key(cfg: dict) -> tuple:
    return (
        str(cfg.get("db_host") or ""),
        int(cfg.get("db_port") or 0),
        str(cfg.get("db_user") or ""),
        str(cfg.get("db_name") or ""),
    )


def get_connection():
    global _LAST_CONNECTION_FAILURE_AT
    global _LAST_CONNECTION_FAILURE_KEY

    if should_force_demo_storage():
        return None

    cfg = load_runtime_config()
    cache_key = _connection_cache_key(cfg)
    now = time.monotonic()

    if (
        _LAST_CONNECTION_FAILURE_KEY == cache_key
        and now - _LAST_CONNECTION_FAILURE_AT < DB_FAILURE_COOLDOWN_SECONDS
    ):
        return None

    try:
        conn = mariadb.connect(
            host=cfg["db_host"],
            port=cfg["db_port"],
            user=cfg["db_user"],
            password=cfg["db_password"],
            database=cfg["db_name"],
            connect_timeout=cfg.get("db_connect_timeout", 3),
        )
        _LAST_CONNECTION_FAILURE_AT = 0.0
        _LAST_CONNECTION_FAILURE_KEY = None
        return conn
    except mariadb.Error:
        _LAST_CONNECTION_FAILURE_AT = now
        _LAST_CONNECTION_FAILURE_KEY = cache_key
        return None


def test_connection():
    return probe_connection() or is_demo_storage_enabled()


def probe_connection() -> bool:
    conn = get_connection()
    if not conn:
        return False

    try:
        conn.close()
        return True
    except mariadb.Error:
        return False
