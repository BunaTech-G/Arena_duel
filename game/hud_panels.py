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

from game.asset_pipeline import load_orb_token_asset, load_sprite_portrait
from game.score_formatter import format_score_value

PG_SRCALPHA = getattr(pygame, "SRCALPHA")

# ── Palette HUD ──────────────────────────────────────────────────────────────
_BG = (10, 14, 22, 220)  # fond panneau principal
_BG_ROW = (14, 20, 32, 210)  # fond rangée joueur
_BG_BADGE = (18, 26, 42, 230)  # fond badge score
_BORDER = (52, 68, 98, 255)  # bordure neutre
_TEXT = (240, 240, 240, 255)  # texte principal
_TEXT_MUTED = (165, 182, 208, 255)  # texte secondaire / labels
_TRACK = (26, 36, 52, 255)  # fond barre de progression
_TIMER_OK = (100, 210, 255, 255)  # timer normal  (bleu ciel)
_TIMER_WARN = (255, 185, 55, 255)  # timer < 30 s  (or chaud)
_TIMER_URG = (255, 65, 65, 255)  # timer < 10 s  (rouge urgence)

# ── Constantes de mise en page ──────────────────────────────────────────────
_RADIUS = 14  # arrondi principal des panneaux
_RADIUS_ROW = 10  # arrondi rangée joueur
_RADIUS_BAR = 4  # arrondi barre de progression
_ACCENT_W = 5  # largeur barre accent équipe
_PAD = 7  # padding interne de base
_ROW_H_MIN = 30
_ROW_H_MAX = 42
_SCORE_H_MIN = 60
_SCORE_H_MAX = 78
_ROSTER_HEADER_H = 18
_PANEL_SECTION_GAP = 6
_PANEL_INSET = 8
_PLAYER_SCORE_MIN_W = 52
_PLAYER_SCORE_MAX_RATIO = 0.34
_TIMER_BAR_BOTTOM_MARGIN = 3
_TIMER_SCORE_GAP = 12
_TEAM_SCORE_SCALE_UP = 1.18
_END_CARD_MIN_ROW_H = 40
_END_CARD_MAX_ROW_H = 48


# ── Helpers texte ────────────────────────────────────────────────────────────


def trim_player_name(name: str, max_chars: int = 14) -> str:
    clean = str(name or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3] + "..."


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


def choose_text_candidate(font, candidates: list[str], max_width: int) -> str:
    for candidate in candidates:
        clean = str(candidate or "").strip()
        if clean and font.size(clean)[0] <= max_width:
            return clean

    if not candidates:
        return ""
    return fit_text_to_width(font, str(candidates[-1]), max_width)


def _render_fitted_text(
    font,
    text: str,
    color,
    max_width: int,
    max_height: int,
    max_scale: float = 1.0,
):
    rendered = font.render(text, True, color[:3])
    if (
        rendered.get_width() <= max_width
        and rendered.get_height() <= max_height
        and max_scale <= 1.0
    ):
        return rendered

    width_ratio = max_width / max(1, rendered.get_width())
    height_ratio = max_height / max(1, rendered.get_height())
    scale_ratio = max(0.45, min(width_ratio, height_ratio, max_scale))
    if abs(scale_ratio - 1.0) < 0.01:
        return rendered

    scaled_size = (
        max(1, int(round(rendered.get_width() * scale_ratio))),
        max(1, int(round(rendered.get_height() * scale_ratio))),
    )
    return pygame.transform.smoothscale(rendered, scaled_size)


def _resolve_player_score(row: dict) -> int:
    return int(row.get("player_score", row.get("score", 0)))


def _should_show_player_score(
    team_score: int,
    player_score: int,
    team_size: int,
) -> bool:
    if team_size <= 0:
        return False
    return not (team_size == 1 and int(player_score) == int(team_score))


def should_show_player_score(
    team_score: int,
    player_score: int,
    team_size: int,
) -> bool:
    return _should_show_player_score(team_score, player_score, team_size)


def get_shared_player_score_slot_width(
    font,
    panel_width: int,
    left_rows: list[dict],
    right_rows: list[dict],
    left_team_score: int,
    right_team_score: int,
    score_format_mode: str = "grouped",
) -> int:
    return max(
        _get_player_score_slot_width(
            font,
            [
                format_score_value(
                    _resolve_player_score(row),
                    score_format_mode,
                )
                for row in left_rows
                if _should_show_player_score(
                    left_team_score,
                    _resolve_player_score(row),
                    len(left_rows),
                )
            ],
            panel_width,
        ),
        _get_player_score_slot_width(
            font,
            [
                format_score_value(
                    _resolve_player_score(row),
                    score_format_mode,
                )
                for row in right_rows
                if _should_show_player_score(
                    right_team_score,
                    _resolve_player_score(row),
                    len(right_rows),
                )
            ],
            panel_width,
        ),
    )


def _get_player_score_slot_width(
    font,
    score_texts: list[str],
    panel_width: int,
) -> int:
    if not score_texts:
        return 0

    widest_text = max(font.size(text)[0] for text in score_texts)
    preferred_width = widest_text + 24
    max_width = max(
        _PLAYER_SCORE_MIN_W,
        int(panel_width * _PLAYER_SCORE_MAX_RATIO),
    )
    return max(_PLAYER_SCORE_MIN_W, min(max_width, preferred_width))


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
        surf,
        border,
        surf.get_rect(),
        width=border_width,
        border_radius=radius,
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
            surface,
            color[:3],
            pygame.Rect(rect.x, rect.y, fw, rect.height),
            border_radius=_RADIUS_BAR,
        )


def _load_score_token(size: int) -> pygame.Surface | None:
    safe_size = max(12, int(size))
    return load_orb_token_asset(
        size=(safe_size, safe_size),
        allow_placeholder=True,
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
    surface.blit(
        label,
        (
            rect.centerx - label.get_width() // 2,
            rect.y + _PAD,
        ),
    )

    # Valeur MM:SS — gros et centré dans la zone centrale
    val_surf = big_font.render(format_timer_value(remaining), True, tc[:3])
    inner_top = rect.y + _PAD + label.get_height() + 2
    inner_bot = rect.bottom - (18 + _TIMER_SCORE_GAP)
    cy = (inner_top + inner_bot) // 2
    val_rect = val_surf.get_rect(center=(rect.centerx, cy))
    surface.blit(val_surf, val_rect)

    # Barre de progression (remaining / total)
    bar_margin = 14
    bar_h = 5
    bar_rect = pygame.Rect(
        rect.x + bar_margin,
        rect.bottom - bar_h - _TIMER_BAR_BOTTOM_MARGIN,
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
    score_format_mode: str = "grouped",
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
    title_width = max(32, rect.width - text_pad * 2)
    title_text = fit_text_to_width(small_font, title, title_width)
    label = small_font.render(title_text, True, _TEXT_MUTED[:3])
    lx = (
        rect.x + text_pad
        if align == "left"
        else rect.right - text_pad - label.get_width()
    )
    surface.blit(label, (lx, rect.y + _PAD))

    score_area = pygame.Rect(
        rect.x + 16,
        rect.y + _PAD + label.get_height() + 4,
        rect.width - 32,
        rect.height - label.get_height() - 20,
    )
    score_text = format_score_value(score, score_format_mode)
    score_shadow = _render_fitted_text(
        big_font,
        score_text,
        (20, 24, 30),
        score_area.width,
        score_area.height,
        max_scale=_TEAM_SCORE_SCALE_UP,
    )
    score_surf = _render_fitted_text(
        big_font,
        score_text,
        _TEXT,
        score_area.width,
        score_area.height,
        max_scale=_TEAM_SCORE_SCALE_UP,
    )
    shadow_rect = score_shadow.get_rect(
        center=(score_area.centerx + 1, score_area.centery + 1)
    )
    surface.blit(score_shadow, shadow_rect)
    score_rect = score_surf.get_rect(center=score_area.center)
    surface.blit(score_surf, score_rect)


# ── Rangée joueur (roster) ──────────────────────────────────────────────


def draw_player_summary_row(
    surface,
    small_font,
    x,
    y,
    *,
    name: str,
    score: int | None = None,
    player_score: int | None = None,
    accent_color,
    sprite_id: str = "skeleton_mascot",
    panel_width: int = 260,
    portrait_size: int = 26,
    row_height: int | None = None,
    show_score: bool = True,
    mirror: bool = False,
    score_format_mode: str = "grouped",
    score_slot_width: int | None = None,
    value_label: str | None = None,
):
    """
    Rangée joueur compacte : portrait encadré | nom tronqué | badge score.
    Tout le contenu remplit la hauteur — aucun vide.
    """
    row_h = max(portrait_size + 8, row_height or portrait_size + 8)
    row_rect = pygame.Rect(x, y, panel_width, row_h)
    _panel(
        surface,
        row_rect,
        fill=_BG_ROW,
        border=accent_color,
        radius=_RADIUS_ROW,
    )

    resolved_player_score = int(
        player_score if player_score is not None else score or 0
    )

    score_badge_w = max(_PLAYER_SCORE_MIN_W, int(score_slot_width or 0))
    score_badge_h = row_h - 8
    score_badge_rect = None
    if show_score:
        if mirror:
            badge_x = row_rect.x + 6
        else:
            badge_x = row_rect.right - score_badge_w - 6
        score_badge_rect = pygame.Rect(
            badge_x,
            y + 4,
            score_badge_w,
            score_badge_h,
        )
        _panel(
            surface,
            score_badge_rect,
            fill=_BG_BADGE,
            border=accent_color,
            radius=8,
        )

        token_size = max(16, min(score_badge_rect.height - 6, 20))
        token = _load_score_token(token_size)
        text_area_left = score_badge_rect.x + 6
        if token is not None:
            token_rect = token.get_rect(
                midleft=(score_badge_rect.x + 6, score_badge_rect.centery)
            )
            surface.blit(token, token_rect)
            text_area_left = token_rect.right + 4

        score_text = format_score_value(
            resolved_player_score,
            score_format_mode,
        )
        score_text_area = pygame.Rect(
            text_area_left,
            score_badge_rect.y + 2,
            score_badge_rect.right - text_area_left - 6,
            score_badge_rect.height - 4,
        )
        label_text = str(value_label or "").strip()
        if label_text:
            label_area = pygame.Rect(
                score_text_area.x,
                score_text_area.y,
                score_text_area.width,
                max(10, min(12, score_text_area.height // 3)),
            )
            fitted_label = fit_text_to_width(
                small_font,
                label_text,
                label_area.width,
            )
            label_surface = _render_fitted_text(
                small_font,
                fitted_label,
                _TEXT_MUTED,
                label_area.width,
                label_area.height,
                max_scale=0.8,
            )
            label_rect = label_surface.get_rect(
                midright=(label_area.right, label_area.centery)
            )
            surface.blit(label_surface, label_rect)
            score_text_area = pygame.Rect(
                score_text_area.x,
                label_area.bottom - 1,
                score_text_area.width,
                max(8, score_badge_rect.bottom - label_area.bottom - 2),
            )

        score_shadow = _render_fitted_text(
            small_font,
            score_text,
            (18, 20, 24),
            score_text_area.width,
            score_text_area.height,
        )
        shadow_rect = score_shadow.get_rect(
            midright=(score_text_area.right + 1, score_badge_rect.centery + 1)
        )
        surface.blit(score_shadow, shadow_rect)

        score_surface = _render_fitted_text(
            small_font,
            score_text,
            _TEXT,
            score_text_area.width,
            score_text_area.height,
        )
        score_rect = score_surface.get_rect(
            midright=(score_text_area.right, score_badge_rect.centery)
        )
        surface.blit(score_surface, score_rect)

    # Portrait avec cadre coloré équipe
    px = row_rect.right - _PAD - portrait_size if mirror else x + _PAD
    py = y + (row_h - portrait_size) // 2
    portrait_rect = pygame.Rect(px, py, portrait_size, portrait_size)
    frame = portrait_rect.inflate(4, 4)
    pygame.draw.rect(surface, (14, 20, 32), frame, border_radius=8)
    pygame.draw.rect(
        surface,
        accent_color[:3],
        frame,
        width=2,
        border_radius=8,
    )

    portrait = load_sprite_portrait(
        sprite_id=sprite_id,
        size=(portrait_size, portrait_size),
        allow_placeholder=True,
    )
    if portrait:
        surface.blit(portrait, portrait_rect)

    # Nom (entre portrait et badge)
    content_left = row_rect.x + _PAD
    content_right = row_rect.right - _PAD
    if mirror:
        content_right = portrait_rect.x - 10
        if score_badge_rect is not None:
            content_left = score_badge_rect.right + 8
    else:
        content_left = portrait_rect.right + 8
        if score_badge_rect is not None:
            content_right = score_badge_rect.x - 8

    name_max_w = max(24, content_right - content_left)
    trimmed = fit_text_to_width(small_font, trim_player_name(name), name_max_w)
    nm_surf = small_font.render(trimmed, True, _TEXT[:3])
    ny = row_rect.centery - nm_surf.get_height() // 2
    if mirror:
        name_x = content_right - nm_surf.get_width()
    else:
        name_x = content_left
    surface.blit(nm_surf, (name_x, ny))


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
    row_height: int = _ROW_H_MIN,
    header_height: int = _ROSTER_HEADER_H,
    portrait_size: int = 26,
    team_score: int | None = None,
    show_header: bool = True,
    score_format_mode: str = "grouped",
    score_slot_width: int | None = None,
):
    """
    Panneau roster : header titre + rangées joueurs.
    Fond légèrement plus sombre que les panneaux de score.
    """
    header_h = header_height if show_header else 0
    row_count = len(rows)
    panel_h = header_h + row_count * row_height
    panel_h += max(6, row_count * _PANEL_SECTION_GAP)
    panel_rect = pygame.Rect(x, y, panel_width, panel_h)
    _panel(surface, panel_rect, fill=(8, 12, 20, 200), radius=12)

    rows_score_width = score_slot_width
    if rows_score_width is None and team_score is not None:
        score_texts = [
            format_score_value(_resolve_player_score(row), score_format_mode)
            for row in rows
            if _should_show_player_score(
                team_score,
                _resolve_player_score(row),
                len(rows),
            )
        ]
        rows_score_width = _get_player_score_slot_width(
            small_font,
            score_texts,
            panel_width,
        )

    if show_header:
        title_width = max(24, panel_rect.width - 24)
        header_text = fit_text_to_width(small_font, title, title_width)
        hdr = small_font.render(header_text, True, _TEXT_MUTED[:3])
        hx = (
            panel_rect.x + 12
            if align == "left"
            else panel_rect.right - hdr.get_width() - 12
        )
        surface.blit(hdr, (hx, panel_rect.y + 4))

    for idx, row in enumerate(rows):
        ry = (
            panel_rect.y
            + header_h
            + _PANEL_SECTION_GAP
            + idx * (row_height + _PANEL_SECTION_GAP)
        )
        resolved_score = _resolve_player_score(row)
        draw_player_summary_row(
            surface,
            small_font,
            panel_rect.x + 6,
            ry,
            name=row["name"],
            player_score=resolved_score,
            accent_color=row["accent_color"],
            sprite_id=row.get("sprite_id", "skeleton_mascot"),
            panel_width=panel_width - 12,
            portrait_size=portrait_size,
            row_height=row_height,
            show_score=_should_show_player_score(
                team_score or 0,
                resolved_score,
                len(rows),
            ),
            mirror=(align == "right"),
            score_format_mode=score_format_mode,
            score_slot_width=rows_score_width,
        )


def draw_end_team_card(
    surface,
    medium_font,
    small_font,
    rect: pygame.Rect,
    *,
    title: str,
    rows,
    align: str = "left",
    border_color: tuple = _BORDER,
    team_score: int = 0,
    row_height: int = 44,
    row_gap: int = 8,
    portrait_size: int = 32,
    row_value_label: str = "",
    score_format_mode: str = "grouped",
    score_slot_width: int | None = None,
):
    _panel(
        surface,
        rect,
        fill=(12, 16, 24, 228),
        border=border_color,
        radius=14,
    )

    header_rect = pygame.Rect(
        rect.x + 16,
        rect.y + 12,
        rect.width - 32,
        32,
    )
    title_text = fit_text_to_width(medium_font, title, header_rect.width)
    title_surface = _render_fitted_text(
        medium_font,
        title_text,
        _TEXT,
        header_rect.width,
        header_rect.height,
    )
    title_x = header_rect.x
    if align == "right":
        title_x = header_rect.right - title_surface.get_width()
    surface.blit(title_surface, (title_x, header_rect.y))

    divider_y = header_rect.bottom + 8
    pygame.draw.line(
        surface,
        border_color[:3],
        (rect.x + 16, divider_y),
        (rect.right - 16, divider_y),
        2,
    )

    if not rows:
        empty_surface = small_font.render(
            "Aucun combattant",
            True,
            _TEXT_MUTED[:3],
        )
        empty_rect = empty_surface.get_rect(center=(rect.centerx, rect.centery + 8))
        surface.blit(empty_surface, empty_rect)
        return

    clamped_row_height = max(
        _END_CARD_MIN_ROW_H,
        min(_END_CARD_MAX_ROW_H, int(row_height)),
    )
    body_x = rect.x + 10
    row_y = divider_y + 10
    for row in rows:
        resolved_score = _resolve_player_score(row)
        show_score = _should_show_player_score(
            team_score,
            resolved_score,
            len(rows),
        )
        draw_player_summary_row(
            surface,
            small_font,
            body_x,
            row_y,
            name=row["name"],
            player_score=resolved_score,
            accent_color=row["accent_color"],
            sprite_id=row.get("sprite_id", "skeleton_mascot"),
            panel_width=rect.width - 20,
            portrait_size=portrait_size,
            row_height=clamped_row_height,
            show_score=show_score,
            mirror=(align == "right"),
            score_format_mode=score_format_mode,
            score_slot_width=score_slot_width,
            value_label=row_value_label if show_score else None,
        )
        row_y += clamped_row_height + row_gap


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
    team_score_format_mode: str = "grouped",
    player_score_format_mode: str = "grouped",
) -> None:
    """
    Orchestre le HUD complet dans la hauteur reservee par le layout.

    Le timer reste centré, les scores s'ancrent aux marges et les rosters
    tiennent sous les scores sans repousser la zone de jeu inutilement.
    """
    sw, _ = surface.get_size()
    top_y = 8
    margin = max(12, min(36, getattr(layout, "margin", 60) // 2))
    arena_top = int(getattr(layout, "top", 220))
    configured_hud_h = int(getattr(layout, "hud_height", arena_top))
    available_h = max(140, min(configured_hud_h, arena_top - top_y))
    max_rows = max(1, len(team_a_rows), len(team_b_rows))
    hud_h = max(_SCORE_H_MIN, min(_SCORE_H_MAX, int(available_h * 0.34)))
    roster_gap = 8
    available_roster_h = max(40, available_h - hud_h - roster_gap)
    row_h = max(
        _ROW_H_MIN,
        min(
            _ROW_H_MAX,
            int((available_roster_h - (max_rows * _PANEL_SECTION_GAP) - 6) / max_rows),
        ),
    )
    portrait_size = max(22, min(30, row_h - 8))

    # Dimensions des blocs
    timer_w = min(214, max(180, sw // 7))
    avail = sw - margin * 2 - timer_w - 18
    panel_w = min(320, max(236, avail // 2))

    # Positions horizontales — symétrie autour du centre
    timer_x = (sw - timer_w) // 2
    a_x = margin
    b_x = sw - margin - panel_w

    # Couleurs d'accent
    if team_a_rows:
        a_accent = team_a_rows[0]["accent_color"]
    else:
        a_accent = (224, 105, 92)

    if team_b_rows:
        b_accent = team_b_rows[0]["accent_color"]
    else:
        b_accent = (100, 186, 255)
    shared_row_score_width = get_shared_player_score_slot_width(
        small_font,
        panel_w,
        team_a_rows,
        team_b_rows,
        team_a_score,
        team_b_score,
        score_format_mode=player_score_format_mode,
    )

    # ── Bande supérieure ─────────────────────────────────────────────────────
    _draw_timer_block(
        surface,
        big_font,
        small_font,
        pygame.Rect(timer_x, top_y, timer_w, hud_h),
        remaining=remaining_time,
        total=match_duration,
    )
    _draw_team_score_block(
        surface,
        big_font,
        small_font,
        pygame.Rect(a_x, top_y, panel_w, hud_h),
        title=team_a_title,
        score=team_a_score,
        accent_color=a_accent,
        rows=team_a_rows,
        align="left",
        score_format_mode=team_score_format_mode,
    )
    _draw_team_score_block(
        surface,
        big_font,
        small_font,
        pygame.Rect(b_x, top_y, panel_w, hud_h),
        title=team_b_title,
        score=team_b_score,
        accent_color=b_accent,
        rows=team_b_rows,
        align="right",
        score_format_mode=team_score_format_mode,
    )

    # ── Rosters sous les blocs score ─────────────────────────────────────────
    roster_y = top_y + hud_h + roster_gap
    draw_team_summary_panel(
        surface,
        small_font,
        a_x,
        roster_y,
        team_a_title,
        team_a_rows,
        align="left",
        panel_width=panel_w,
        row_height=row_h,
        header_height=0,
        portrait_size=portrait_size,
        team_score=team_a_score,
        show_header=False,
        score_format_mode=player_score_format_mode,
        score_slot_width=shared_row_score_width,
    )
    draw_team_summary_panel(
        surface,
        small_font,
        b_x,
        roster_y,
        team_b_title,
        team_b_rows,
        align="right",
        panel_width=panel_w,
        row_height=row_h,
        header_height=0,
        portrait_size=portrait_size,
        team_score=team_b_score,
        show_header=False,
        score_format_mode=player_score_format_mode,
        score_slot_width=shared_row_score_width,
    )
