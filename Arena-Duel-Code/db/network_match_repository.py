from db.match_repository import save_match_result


def save_network_match_result(match_result: dict) -> int:
    payload = {
        **dict(match_result or {}),
        "source_code": str(match_result.get("source_code") or "LAN").upper(),
        "mode_code": str(match_result.get("mode_code") or "LAN").upper(),
    }
    return save_match_result(payload)
