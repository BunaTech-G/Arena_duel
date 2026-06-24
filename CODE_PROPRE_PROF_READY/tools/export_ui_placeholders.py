"""
tools/export_ui_placeholders.py

Génère les PNG de placeholder HUD pour Arena Duel dans assets/ui/.
Chaque image est créée en code avec Pillow — aucune dépendance SVG.
Tailles : 64, 96, 128 px (carré pour les icônes), plus grand pour le portrait.

Exécution :
    python tools/export_ui_placeholders.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_UI = Path(__file__).parent.parent / "assets" / "ui"
ASSETS_UI.mkdir(parents=True, exist_ok=True)

# Palette (reprend ui/theme.py)
BG       = (15,  23,  36,  255)
SURFACE  = (23,  32,  51,  255)
PRIMARY  = (123, 92, 255,  255)
ACCENT   = (255, 184, 107, 255)
GOLD     = (255, 209, 102, 255)
TEXT     = (246, 247, 251, 255)
OUTLINE  = (38,  54,  69,  255)
MUTED    = (154, 164, 178, 255)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    radius: int,
    fill: tuple,
    outline: tuple,
    width: int = 3,
) -> None:
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)


def make_ability_ring(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy, r = size // 2, size // 2, size // 2 - 4

    # Anneau extérieur
    d.ellipse(
        (cx - r, cy - r, cx + r, cy + r),
        fill=SURFACE, outline=GOLD, width=4,
    )
    # Arc de cooldown (75 % rempli)
    arc_r = r - 5
    d.arc(
        (cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r),
        start=-90, end=180, fill=PRIMARY, width=4,
    )
    # Icône centrale — rune simple
    inner = size // 4
    d.ellipse(
        (cx - inner, cy - inner, cx + inner, cy + inner),
        fill=(*PRIMARY[:3], 200),
    )
    # Croix
    d.line((cx, cy - inner + 4, cx, cy + inner - 4), fill=TEXT, width=2)
    d.line((cx - inner + 4, cy, cx + inner - 4, cy), fill=TEXT, width=2)
    return img


def make_icon_timer(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r_outer = size // 2 - 3
    r_inner = r_outer - 7

    # Fond cercle
    d.ellipse(
        (cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer),
        fill=SURFACE, outline=ACCENT, width=4,
    )
    # Graduations
    for i in range(12):
        angle = math.radians(i * 30 - 90)
        xa = int(cx + math.cos(angle) * (r_inner - 2))
        ya = int(cy + math.sin(angle) * (r_inner - 2))
        xb = int(cx + math.cos(angle) * r_inner)
        yb = int(cy + math.sin(angle) * r_inner)
        d.line((xa, ya, xb, yb), fill=MUTED, width=2)

    # Aiguille des minutes
    angle_m = math.radians(-90 + 120)  # 4h
    d.line(
        (cx, cy,
         int(cx + math.cos(angle_m) * (r_inner - 6)),
         int(cy + math.sin(angle_m) * (r_inner - 6))),
        fill=GOLD, width=3,
    )
    # Aiguille des heures
    angle_h = math.radians(-90 + 220)
    d.line(
        (cx, cy,
         int(cx + math.cos(angle_h) * (r_inner - 12)),
         int(cy + math.sin(angle_h) * (r_inner - 12))),
        fill=TEXT, width=2,
    )
    d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=ACCENT)
    return img


def make_icon_score(w: int = 153, h: int = 36) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_rounded_rect(d, (0, 0, w - 1, h - 1), 10, SURFACE, OUTLINE, 2)

    # Orbe d'équipe
    orb_r = h // 2 - 4
    orb_cx = orb_r + 8
    d.ellipse(
        (orb_cx - orb_r, 4, orb_cx + orb_r, h - 4),
        fill=(*PRIMARY[:3], 220), outline=GOLD, width=2,
    )
    # Texte score
    font = _font(max(14, h - 14))
    d.text((orb_cx * 2 + 4, h // 2), "0", fill=TEXT, font=font, anchor="lm")
    return img


def make_portrait(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Cadre
    _draw_rounded_rect(d, (0, 0, size - 1, size - 1), 14, SURFACE, ACCENT, 3)

    # Silhouette squelette simplifié (grosse tête)
    head_r = size // 4
    hcx, hcy = size // 2, size // 3
    d.ellipse(
        (hcx - head_r, hcy - head_r, hcx + head_r, hcy + head_r),
        fill=(*PRIMARY[:3], 230), outline=GOLD, width=2,
    )
    # Yeux
    ey = hcy - head_r // 4
    for ex in (hcx - head_r // 3, hcx + head_r // 3):
        d.ellipse((ex - 3, ey - 3, ex + 3, ey + 3), fill=GOLD)

    # Corps
    body_top = hcy + head_r + 2
    body_bot = size - 8
    body_w = size // 5
    d.rounded_rectangle(
        (hcx - body_w, body_top, hcx + body_w, body_bot),
        radius=6, fill=(*PRIMARY[:3], 180),
    )

    # Barre HP en bas
    bar_h = 6
    bar_y = size - bar_h - 3
    d.rounded_rectangle((4, bar_y, size - 4, bar_y + bar_h), radius=3, fill=OUTLINE)
    d.rounded_rectangle((4, bar_y, int((size - 4) * 0.75), bar_y + bar_h),
                        radius=3, fill=(106, 232, 155, 255))
    return img


def make_minimap(size: int = 140) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    _draw_rounded_rect(
        d, (0, 0, size - 1, size - 1), 10, (10, 16, 25, 230), OUTLINE, 2
    )
    cx, cy = size // 2, size // 2

    # Sol arène (ellipse)
    ar = size // 2 - 14
    d.ellipse((cx - ar, cy - ar, cx + ar, cy + ar),
              fill=(49, 44, 38, 200), outline=(100, 90, 78, 255), width=2)

    # Obstacles simplifiés
    for ox, oy, ow, oh in [
        (cx - 20, cy - 8, 14, 14),
        (cx + 8, cy - 8, 14, 14),
        (cx - 8, cy - 24, 14, 10),
        (cx - 8, cy + 14, 14, 10),
    ]:
        d.rectangle((ox, oy, ox + ow, oy + oh), fill=(88, 82, 76, 255))

    # Joueurs
    d.ellipse((cx - ar + 14, cy - 10, cx - ar + 22, cy + 2),
              fill=(224, 105, 92, 255))   # Équipe A
    d.ellipse((cx + ar - 22, cy - 10, cx + ar - 14, cy + 2),
              fill=(100, 186, 255, 255))  # Équipe B

    # Label
    font = _font(10)
    d.text((cx, size - 10), "MAP", fill=MUTED, font=font, anchor="mm")
    return img


EXPORTS: list[tuple[str, tuple[int, ...]]] = [
    ("ability_ring", (56,)),
    ("ability_ring", (64,)),
    ("ability_ring", (96,)),
    ("ability_ring", (128,)),
    ("icon_timer",   (56,)),
    ("icon_timer",   (64,)),
    ("icon_timer",   (96,)),
    ("portrait_placeholder", (64,)),
    ("portrait_placeholder", (96,)),
    ("portrait_placeholder", (128,)),
    ("minimap_placeholder",  (140,)),
]


def export_all() -> None:
    generators = {
        "ability_ring":        lambda s: make_ability_ring(s),
        "icon_timer":          lambda s: make_icon_timer(s),
        "portrait_placeholder": lambda s: make_portrait(s),
        "minimap_placeholder": lambda s: make_minimap(s),
    }

    # icon_score est rectangulaire — on l'exporte une fois
    score_img = make_icon_score(153, 36)
    score_path = ASSETS_UI / "icon_score.png"
    score_img.save(score_path)
    print(f"  wrote {score_path}")

    for name, size_args in EXPORTS:
        size = size_args[0]
        gen = generators.get(name)
        if gen is None:
            print(f"  skip {name} (no generator)")
            continue

        img = gen(size)
        # Resize si besoin (toutes les fonctions acceptent déjà size)
        path = ASSETS_UI / f"{name}_{size}.png"
        # Aussi écrire le nom sans taille si c'est la taille "par défaut"
        img.save(path)
        print(f"  wrote {path}")

        # Alias sans suffixe pour la taille principale
        DEFAULTS = {
            "ability_ring": 56,
            "icon_timer": 56,
            "portrait_placeholder": 64,
            "minimap_placeholder": 140,
        }
        if size == DEFAULTS.get(name):
            alias = ASSETS_UI / f"{name}.png"
            img.save(alias)
            print(f"  wrote {alias}  [default alias]")

    print("\nDone — all UI placeholder PNGs exported.")


if __name__ == "__main__":
    export_all()
