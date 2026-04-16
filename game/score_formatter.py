"""Helpers de formatage pour les scores du HUD Arena Duel."""


def format_grouped_score(value: int) -> str:
    safe_value = int(value)
    sign = "-" if safe_value < 0 else ""
    digits = abs(safe_value)
    return f"{sign}{digits:,}".replace(",", " ")


def format_compact_score(value: int) -> str:
    safe_value = int(value)
    sign = "-" if safe_value < 0 else ""
    digits = abs(safe_value)

    if digits < 1_000:
        return f"{sign}{digits}"

    suffixes = (
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "k"),
    )
    for divisor, suffix in suffixes:
        if digits < divisor:
            continue

        reduced = digits / divisor
        if reduced >= 100 or reduced.is_integer():
            formatted = f"{reduced:.0f}"
        else:
            formatted = f"{reduced:.1f}".rstrip("0").rstrip(".")
        return f"{sign}{formatted}{suffix}"

    return f"{sign}{digits}"


def format_score_value(value: int, mode: str = "grouped") -> str:
    normalized_mode = str(mode or "grouped").strip().lower()
    if normalized_mode in {"short", "compact", "abbr", "abbreviated"}:
        return format_compact_score(value)
    return format_grouped_score(value)
