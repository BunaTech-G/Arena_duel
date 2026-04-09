"""
game.hud_panels — HUD compétitif Arena Duel

Design :
  - TIMER (centre-haut) : gros, lisible, barre de progression urgence-colorée.
  - SCORE EQUIPE (gauche/droite) : panel flanquant, barre accent
    couleur équipe, gros chiffre dominant, points-joueurs en bas.
  - ROSTER (sous les scores) : portrait + nom + badge score, compact et rempli.

Hiérarchie visuelle : timer > score > roster.
Référence ergonomique : lisibilité Battlerite, ambiance fantasy RO.
"""

import pygame

from game.asset_pipeline import load_sprite_portrait
PG_SRCALPHA = getattr(pygame, "SRCALPHA")

# ── Palette HUD ──────────────────────────────────────────────────────────────
_BG = (10, 14, 22, 220)         # fond panneau principal
_BG_ROW = (14, 20, 32, 210)     # fond rangée joueur
_BG_BADGE = (18, 26, 42, 230)   # fond badge score
_BORDER = (52, 68, 98, 255)     # bordure neutre
_TEXT = (240, 240, 240, 255)    # texte principal
_TEXT_MUTED = (165, 182, 208, 255)  # texte secondaire / labels
_TRACK = (26, 36, 52, 255)      # fond barre de progression
_TIMER_OK = (100, 210, 255, 255)    # timer normal  (bleu ciel)
_TIMER_WARN = (255, 185, 55, 255)   # timer < 30 s  (or chaud)
_TIMER_URG = (255, 65, 65, 255)     # timer < 10 s  (rouge urgence)

# ── Constantes de mise en page ──────────────────────────────────────────────
_RADIUS = 14     # arrondi principal des panneaux
_RADIUS_ROW = 10  # arrondi rangée joueur
_RADIUS_BAR = 4   # arrondi barre de progression
_ACCENT_W = 5     # largeur barre accent équipe
_ROW_H = 40       # hauteur rangée joueur dans le roster
_PAD = 8          # padding interne de base
# hauteur fixe du bloc score/timer (indépendant de layout.hud_height)
_SCORE_H = 78


# ── Helpers texte ────────────────────────────────────────────────────────────

def trim_player_name(name: str, max_chars: int = 14) -> str:
    clean = str(name or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars - 3] + "..."


def fit_text_to_width(font, text: str, max_width: int) -> str:
    clean = str(text or "").strip()
    if max_width <= 0 or not clean:
        return ""
    if font.size(clean)[0] <= max_width:
        return clean
    suffix = "..."
    trimmed = clean
    while trimmed and font.size(trimmed + suffix)[0] > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + suffix) if trimmed else suffix


def format_timer_value(remaining_seconds: int) -> str:
    safe = max(0, int(remaining_seconds))
    m, s = divmod(safe, 60)
    return f"{m:02d}:{s:02d}"


def _timer_color(remaining: int) -> tuple:
    if remaining <= 10:
        return _TIMER_URG
    if remaining <= 30:
        return _TIMER_WARN
    return _TIMER_OK


# ── Primitives de dessin ────────────────────────────────────────────────

def _panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill: tuple = _BG,
    border: tuple = _BORDER,
    radius: int = _RADIUS,
    border_width: int = 2,
) -> None:
    """Dessine un panneau arrondi semi-transparent sur surface."""
    surf = pygame.Surface(rect.size, PG_SRCALPHA)
    pygame.draw.rect(surf, fill, surf.get_rect(), border_radius=radius)
    pygame.draw.rect(
        surf, border, surf.get_rect(),
        width=border_width, border_radius=radius,
    )
    surface.blit(surf, rect.topleft)


def _accent_stripe(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple,
    side: str = "left",
) -> None:
    """Barre verticale colorée (accent équipe) à gauche ou droite du rect."""
    inset = _RADIUS // 2
    bar_h = rect.height - inset * 2
    if bar_h <= 0:
        return
    bx = rect.x + 2 if side == "left" else rect.right - 2 - _ACCENT_W
    bar = pygame.Surface((_ACCENT_W, bar_h), PG_SRCALPHA)
    bar.fill((*color[:3], 235))
    surface.blit(bar, (bx, rect.y + inset))


def _progress_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    ratio: float,
    color: tuple,
) -> None:
    """Barre de progression: track gris + fill coloré."""
    pygame.draw.rect(surface, _TRACK, rect, border_radius=_RADIUS_BAR)
    if ratio > 0.002:
        fw = max(_RADIUS_BAR * 2, int(rect.width * min(ratio, 1.0)))
        pygame.draw.rect(
            surface, color[:3],
            pygame.Rect(rect.x, rect.y, fw, rect.height),
            border_radius=_RADIUS_BAR,
        )


# ── Bloc Timer ───────────────────────────────────────────────────────────────

def _draw_timer_block(
    surface: pygame.Surface,
    big_font,
    small_font,
    rect: pygame.Rect,
    remaining: int,
    total: int,
) -> None:
    """
    Timer centré.
    Hier. : label muted (haut) > valeur MM:SS (large, colorée) > barre.
    Couleur urgence : bleu → or → rouge selon temps restant.
    """
    tc = _timer_color(remaining)
    _panel(surface, rect, fill=_BG, border=tc)

    # Label "SABLIER"
    label = small_font.render("TEMPS", True, _TEXT_MUTED[:3])
    surface.blit(label, (
        rect.centerx - label.get_width() // 2,
        rect.y + _PAD,
    ))

    # Valeur MM:SS — gros et centré dans la zone centrale
    val_surf = big_font.render(format_timer_value(remaining), True, tc[:3])
    inner_top = rect.y + _PAD + label.get_height() + 2
    inner_bot = rect.bottom - 18   # laisse place à la barre
    cy = (inner_top + inner_bot) // 2
    val_rect = val_surf.get_rect(center=(rect.centerx, cy))
    surface.blit(val_surf, val_rect)

    # Barre de progression (remaining / total)
    bar_margin = 14
    bar_h = 5
    bar_rect = pygame.Rect(
        rect.x + bar_margin,
        rect.bottom - bar_h - 7,
        rect.width - bar_margin * 2,
        bar_h,
    )
    ratio = remaining / max(1, total)
    _progress_bar(surface, bar_rect, ratio, tc)


# ── Bloc score équipe ─────────────────────────────────────────────────────

def _draw_team_score_block(
    surface: pygame.Surface,
    big_font,
    small_font,
    rect: pygame.Rect,
    *,
    title: str,
    score: int,
    accent_color: tuple,
    rows: list,
    align: str = "left",
) -> None:
    """
    Panneau score équipe.
    - Barre accent (5px) du côté de l'équipe pour identification immédiate.
    - Label équipe petit en haut (muted).
    - Score grand centré (dominant).
    - Points colorés par joueur en bas (identification rapide des combattants).
    """
    del rows  # conservé dans la signature pour compatibilité des appelants
    # Fond + bordure colorée par équipe
    _panel(surface, rect, fill=_BG, border=accent_color)
    _accent_stripe(surface, rect, accent_color, side=align)

    text_pad = _ACCENT_W + 10

    # Label équipe — petit, discret, décoré
    label = small_font.render(title, True, _TEXT_MUTED[:3])
    lx = (
        rect.x + text_pad
        if align == "left"
        else rect.right - text_pad - label.get_width()
    )
    surface.blit(label, (lx, rect.y + _PAD))

    # Score — grand et centré verticalement (element dominant)
    score_str = str(score)
    score_surf = big_font.render(score_str, True, _TEXT[:3])
    score_rect = score_surf.get_rect(
        center=(rect.centerx, rect.y + _PAD + label.get_height() + 4
                + score_surf.get_height() // 2)
    )
    surface.blit(score_surf, score_rect)


# ── Rangée joueur (roster) ──────────────────────────────────────────────

def draw_player_summary_row(
    surface,
    small_font,
    x,
    y,
    *,
    name: str,
    score: int,
    accent_color,
    panel_width: int = 260,
    portrait_size: int = 26,
):
    """
    Rangée joueur compacte : portrait encadré | nom tronqué | badge score.
    Tout le contenu remplit la hauteur — aucun vide.
    """
    row_h = portrait_size + 12
    row_rect = pygame.Rect(x, y, panel_width, row_h)
    _panel(
        surface, row_rect,
        fill=_BG_ROW, border=accent_color, radius=_RADIUS_ROW,
    )

    # Portrait avec cadre coloré équipe
    px = x + _PAD
    py = y + (row_h - portrait_size) // 2
    portrait_rect = pygame.Rect(px, py, portrait_size, portrait_size)
    frame = portrait_rect.inflate(4, 4)
    pygame.draw.rect(surface, (14, 20, 32), frame, border_radius=8)
    pygame.draw.rect(
        surface, accent_color[:3], frame, width=2, border_radius=8
    )

    portrait = load_sprite_portrait(
        size=(portrait_size, portrait_size),
        allow_placeholder=True,
    )
    if portrait:
        surface.blit(portrait, portrait_rect)

    # Badge score (droite)
    badge_w = 34
    badge_h = row_h - 10
    badge_rect = pygame.Rect(
        row_rect.right - badge_w - 6,
        y + 5,
        badge_w,
        badge_h,
    )
    _panel(
        surface, badge_rect,
        fill=_BG_BADGE, border=accent_color, radius=8,
    )
    sc_surf = small_font.render(str(score), True, _TEXT[:3])
    surface.blit(sc_surf, sc_surf.get_rect(center=badge_rect.center))

    # Nom (entre portrait et badge)
    name_max_w = badge_rect.x - portrait_rect.right - 16
    trimmed = fit_text_to_width(
        small_font, trim_player_name(name), name_max_w
    )
    nm_surf = small_font.render(trimmed, True, _TEXT[:3])
    ny = row_rect.centery - nm_surf.get_height() // 2
    surface.blit(nm_surf, (portrait_rect.right + 10, ny))


# ── Panneau roster équipe ─────────────────────────────────────────────────

def draw_team_summary_panel(
    surface,
    small_font,
    x,
    y,
    title: str,
    rows,
    align: str = "left",
    panel_width: int = 260,
):
    """
    Panneau roster : header titre + rangées joueurs.
    Fond légèrement plus sombre que les panneaux de score.
    """
    header_h = 26
    panel_h = header_h + len(rows) * _ROW_H + 8
    panel_rect = pygame.Rect(x, y, panel_width, panel_h)
    _panel(surface, panel_rect, fill=(8, 12, 20, 200), radius=12)

    hdr = small_font.render(title, True, _TEXT_MUTED[:3])
    hx = (
        panel_rect.x + 12
        if align == "left"
        else panel_rect.right - hdr.get_width() - 12
    )
    surface.blit(hdr, (hx, panel_rect.y + 5))

    for idx, row in enumerate(rows):
        ry = panel_rect.y + header_h + idx * _ROW_H
        draw_player_summary_row(
            surface, small_font,
            panel_rect.x + 6, ry,
            name=row["name"],
            score=row["score"],
            accent_color=row["accent_color"],
            panel_width=panel_width - 12,
            portrait_size=26,
        )


# ── Point d'entrée principal ──────────────────────────────────────────────

def draw_match_hud(
    surface: pygame.Surface,
    big_font,
    small_font,
    layout,
    *,
    team_a_title: str,
    team_b_title: str,
    team_a_score: int,
    team_b_score: int,
    remaining_time: int,
    team_a_rows,
    team_b_rows,
    match_duration: int = 60,
) -> None:
    """
    Orchestre le HUD complet.

    Composition (1280×810, hud_height=250) :
      - Bande top (y=8, h=_SCORE_H) : [score A] [timer centré] [score B]
      - Bande roster (y=8+_SCORE_H+8) : [roster A gauche] [roster B droite]

    Le timer est toujours centré ; les blocs score s'ancrent aux marges.
    Les rosters sont positionnés sous les blocs score, dans l'espace HUD.
    """
    sw, _ = surface.get_size()
    margin = max(16, getattr(layout, "margin", 60) // 2)
    hud_h = _SCORE_H   # hauteur fixe des blocs score/timer
    top_y = 8

    # Dimensions des blocs
    timer_w = min(200, max(170, sw // 7))
    avail = sw - margin * 2 - timer_w - 16
    panel_w = min(260, max(200, avail // 2))

    # Positions horizontales — symétrie autour du centre
    timer_x = (sw - timer_w) // 2
    a_x = margin
    b_x = sw - margin - panel_w

    # Couleurs d'accent
    a_accent = (
        team_a_rows[0]["accent_color"] if team_a_rows else (224, 105, 92)
    )
    b_accent = (
        team_b_rows[0]["accent_color"] if team_b_rows else (100, 186, 255)
    )

    # ── Bande supérieure ─────────────────────────────────────────────────────
    _draw_timer_block(
        surface, big_font, small_font,
        pygame.Rect(timer_x, top_y, timer_w, hud_h),
        remaining=remaining_time,
        total=match_duration,
    )
    _draw_team_score_block(
        surface, big_font, small_font,
        pygame.Rect(a_x, top_y, panel_w, hud_h),
        title=team_a_title,
        score=team_a_score,
        accent_color=a_accent,
        rows=team_a_rows,
        align="left",
    )
    _draw_team_score_block(
        surface, big_font, small_font,
        pygame.Rect(b_x, top_y, panel_w, hud_h),
        title=team_b_title,
        score=team_b_score,
        accent_color=b_accent,
        rows=team_b_rows,
        align="right",
    )

    # ── Rosters sous les blocs score ─────────────────────────────────────────
    roster_y = top_y + hud_h + 8
    draw_team_summary_panel(
        surface, small_font,
        a_x, roster_y,
        team_a_title, team_a_rows,
        align="left", panel_width=panel_w,
    )
    draw_team_summary_panel(
        surface, small_font,
        b_x, roster_y,
        team_b_title, team_b_rows,
        align="right", panel_width=panel_w,
    )
