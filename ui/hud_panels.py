"""Helpers de layout HUD pour Arena Duel.

Fournit des helpers non dépendants d'un framework graphique pour
calculer les positions des éléments HUD (timer, scores, portrait,
barre de compétences, mini-map, notifications) selon la taille
de la fenêtre.
"""

from typing import Dict, Tuple

from .theme import UI

Rect = Tuple[int, int, int, int]


def _int_rect(x: float, y: float, w: float, h: float) -> Rect:
    return (int(round(x)), int(round(y)), int(round(w)), int(round(h)))


def get_hud_layout(screen_w: int, screen_h: int) -> Dict[str, object]:
    """Retourne un dictionnaire de positions et tailles pour le HUD.

    Clés retournées : `timer`, `score_left`, `score_right`, `abilities`,
    `portrait`, `minimap`, `notification`, et `meta`.
    Chaque valeur rect est (x,y,w,h) en pixels.
    """
    gutter = UI.get("gutter", 12)
    icon_size = UI.get("hud_icon_size", 56)
    portrait_size = UI.get("portrait_size", 64)

    # Timer (centre haut)
    timer_w = max(icon_size, int(screen_w * 0.06))
    timer_h = timer_w
    timer_x = (screen_w - timer_w) / 2
    timer_y = gutter * 1.5

    # Scores (coins supérieurs)
    score_w = max(120, int(screen_w * 0.12))
    score_h = max(36, int(icon_size * 0.6))
    score_left_x = gutter
    score_left_y = gutter
    score_right_x = screen_w - gutter - score_w
    score_right_y = gutter

    # Abilities (bas-centre) — 5 emplacements par défaut
    ability_count = 5
    total_width = ability_count * icon_size + (ability_count - 1) * gutter
    abilities_x = (screen_w - total_width) / 2
    abilities_y = screen_h - gutter - icon_size

    # Portrait (bas-gauche)
    portrait_x = gutter
    portrait_y = screen_h - gutter - portrait_size
    portrait_w = portrait_size
    portrait_h = portrait_size

    # Mini-map (bas-droite)
    minimap_size = min(140, int(screen_w * 0.18))
    minimap_x = screen_w - gutter - minimap_size
    minimap_y = screen_h - gutter - minimap_size

    # Notification banner (sous le timer)
    notif_w = min(int(screen_w * 0.8), 720)
    notif_h = 40
    notif_x = (screen_w - notif_w) / 2
    notif_y = timer_y + timer_h + (gutter / 2)

    layout = {
        "timer": _int_rect(timer_x, timer_y, timer_w, timer_h),
        "score_left": _int_rect(score_left_x, score_left_y, score_w, score_h),
        "score_right": _int_rect(
            score_right_x, score_right_y, score_w, score_h
        ),
        "abilities": {
            "origin": _int_rect(
                abilities_x, abilities_y, total_width, icon_size
            ),
            "icon_size": int(icon_size),
            "count": ability_count,
        },
        "portrait": _int_rect(portrait_x, portrait_y, portrait_w, portrait_h),
        "minimap": _int_rect(minimap_x, minimap_y, minimap_size, minimap_size),
        "notification": _int_rect(notif_x, notif_y, notif_w, notif_h),
        "meta": {"gutter": gutter, "screen": (screen_w, screen_h)},
    }

    return layout
