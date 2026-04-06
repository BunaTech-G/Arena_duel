import pygame

from game.asset_pipeline import load_sprite_portrait
from game.settings import HUD_BORDER_COLOR, HUD_TEXT_COLOR


def trim_player_name(name: str, max_chars: int = 10) -> str:
    clean_name = str(name or "").strip()
    if len(clean_name) <= max_chars:
        return clean_name
    return clean_name[: max_chars - 1] + "…"


def draw_player_summary_row(
    surface,
    small_font,
    x,
    y,
    *,
    name: str,
    score: int,
    accent_color,
    panel_width: int = 228,
    portrait_size: int = 30,
):
    row_rect = pygame.Rect(x, y, panel_width, portrait_size + 12)
    pygame.draw.rect(surface, (18, 22, 30), row_rect, border_radius=12)
    pygame.draw.rect(surface, accent_color, row_rect, width=2, border_radius=12)

    portrait = load_sprite_portrait(size=(portrait_size, portrait_size), allow_placeholder=True)
    portrait_rect = pygame.Rect(x + 8, y + 6, portrait_size, portrait_size)

    frame_rect = portrait_rect.inflate(6, 6)
    pygame.draw.rect(surface, (20, 24, 32), frame_rect, border_radius=10)
    pygame.draw.rect(surface, accent_color, frame_rect, width=2, border_radius=10)

    if portrait is not None:
        surface.blit(portrait, portrait_rect)

    label = f"{trim_player_name(name)} · {score}"
    txt = small_font.render(label, True, HUD_TEXT_COLOR)
    text_y = row_rect.centery - txt.get_height() // 2
    surface.blit(txt, (portrait_rect.right + 14, text_y))


def draw_team_summary_panel(surface, small_font, x, y, title: str, rows, align: str = "left"):
    panel_width = 248
    row_height = 42
    title_height = 24
    panel_height = title_height + max(1, len(rows)) * row_height + 16
    panel_rect = pygame.Rect(x, y, panel_width, panel_height)

    pygame.draw.rect(surface, (16, 20, 28), panel_rect, border_radius=16)
    pygame.draw.rect(surface, HUD_BORDER_COLOR, panel_rect, width=2, border_radius=16)

    title_text = small_font.render(title, True, HUD_TEXT_COLOR)
    title_x = panel_rect.x + 14 if align == "left" else panel_rect.right - title_text.get_width() - 14
    surface.blit(title_text, (title_x, panel_rect.y + 10))

    if not rows:
        return

    for idx, row in enumerate(rows):
        row_y = panel_rect.y + title_height + 6 + idx * row_height
        draw_player_summary_row(
            surface,
            small_font,
            panel_rect.x + 10,
            row_y,
            name=row["name"],
            score=row["score"],
            accent_color=row["accent_color"],
            panel_width=panel_width - 20,
            portrait_size=26,
        )