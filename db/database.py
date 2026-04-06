import mariadb
from runtime_utils import load_runtime_config


def get_connection():
    cfg = load_runtime_config()

    return mariadb.connect(
        host=cfg["db_host"],
        port=cfg["db_port"],
        user=cfg["db_user"],
        password=cfg["db_password"],
        database=cfg["db_name"]
    )


def test_connection():
    try:
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False