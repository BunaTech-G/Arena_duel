"""
tools/gen_arena_assets.py
Génère les assets PNG de l'arène (fond ambiant + sol) avec Pillow.
Usage : python tools/gen_arena_assets.py
"""
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("Pillow manquant – pip install Pillow")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
OUT = ROOT / "assets" / "backgrounds"
OUT.mkdir(parents=True, exist_ok=True)


# ─────────────────────────── FOND AMBIANT ───────────────────────────────────
def gen_ambient(path: Path, w: int = 1280, h: int = 980) -> None:
    """
    Fond derrière l'arène.
    Gradient violet-profond + halos d'équipe intenses + aurora centrale
    + silhouettes d'arches + vignette dramatique.
    """
    layer_base = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    draw = ImageDraw.Draw(layer_base)

    # Gradient vertical : violet-nuit en haut → noir-bleu en bas
    for y in range(0, h, 2):
        t = y / max(1, h - 1)
        r = int(14 - 14 * t)
        g = int(6 - 6 * t)
        b = int(28 - 18 * t)
        draw.rectangle(
            [0, y, w, y + 2],
            fill=(max(0, r), max(0, g), max(0, b)),
        )

    # ── Halo équipe A (gauche, rouge-cramoisi intense)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for step in range(0, 380, 10):
        alpha = int(110 * (1 - step / 380))
        margin = step
        x0a = -300 + margin
        y0a = h // 2 - 320 + margin
        x1a = 760 - margin
        y1a = h // 2 + 320 - margin
        if x1a > x0a and y1a > y0a:
            gd.ellipse([x0a, y0a, x1a, y1a], fill=(215, 30, 10, max(0, alpha)))
    glow_a = glow.filter(ImageFilter.GaussianBlur(radius=34))
    layer_base = Image.alpha_composite(layer_base, glow_a)

    # ── Halo équipe B (droite, bleu-saphir intense)
    glow2 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow2)
    for step in range(0, 380, 10):
        alpha = int(98 * (1 - step / 380))
        margin = step
        x0b = w - 760 + margin
        y0b = h // 2 - 320 + margin
        x1b = w + 300 - margin
        y1b = h // 2 + 320 - margin
        if x1b > x0b and y1b > y0b:
            gd2.ellipse(
                [x0b, y0b, x1b, y1b], fill=(12, 50, 220, max(0, alpha))
            )
    glow_b = glow2.filter(ImageFilter.GaussianBlur(radius=34))
    layer_base = Image.alpha_composite(layer_base, glow_b)

    # ── Bande aurora centrale (croisée teal+or au niveau de l'arène)
    aurora = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aurora)
    cy_a = int(h * 0.60)
    for band in range(0, 140, 3):
        a_teal = int(48 * (1 - band / 140))
        ad.rectangle(
            [0, cy_a - band, w, cy_a + band],
            fill=(45, 150, 190, max(0, a_teal // 3)),
        )
    for band in range(0, 70, 2):
        a_gold = int(32 * (1 - band / 70))
        ad.rectangle(
            [0, cy_a - band, w, cy_a + band],
            fill=(175, 130, 40, max(0, a_gold // 3)),
        )
    aurora_blur = aurora.filter(ImageFilter.GaussianBlur(radius=36))
    layer_base = Image.alpha_composite(layer_base, aurora_blur)

    # ── Silhouettes d'arches aux bords inférieurs
    arch_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ad2 = ImageDraw.Draw(arch_layer)
    arch_y = int(h * 0.90)
    # Arche gauche
    ad2.arc(
        [int(w * -0.06), arch_y - 180, int(w * 0.24), arch_y + 90],
        start=200, end=340, fill=(5, 3, 10, 210), width=32,
    )
    ad2.rectangle(
        [int(w * 0.012), arch_y - 160, int(w * 0.048), arch_y + 90],
        fill=(4, 2, 8, 195),
    )
    # Arche droite
    ad2.arc(
        [int(w * 0.76), arch_y - 180, int(w * 1.06), arch_y + 90],
        start=200, end=340, fill=(5, 3, 10, 210), width=32,
    )
    ad2.rectangle(
        [int(w * 0.952), arch_y - 160, int(w * 0.988), arch_y + 90],
        fill=(4, 2, 8, 195),
    )
    arch_blur = arch_layer.filter(ImageFilter.GaussianBlur(radius=5))
    layer_base = Image.alpha_composite(layer_base, arch_blur)

    # ── Vignette bords dramatique
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for inset in range(0, 90, 4):
        a = int(180 * (1 - inset / 90) ** 2)
        vd.rectangle(
            [inset, inset, w - inset, h - inset],
            outline=(0, 0, 0, a), width=4,
        )
    vig_blur = vignette.filter(ImageFilter.GaussianBlur(radius=14))
    layer_base = Image.alpha_composite(layer_base, vig_blur)

    layer_base.save(str(path))
    print(f"  Fond ambiant : {path.name} ({w}×{h})")


# ─────────────────────────── SOL DE L'ARÈNE ─────────────────────────────────
def gen_floor(path: Path, w: int = 1160, h: int = 700) -> None:
    """
    Sol de l'arène forgotten_sanctum.
    Pavés sombres avec variation de teinte, cercle magique teal au centre,
    marques ambre aux coins, vignette bords.
    """
    TILE = 56
    base = Image.new("RGBA", (w, h), (20, 16, 13, 255))
    draw = ImageDraw.Draw(base)

    # ── Pavés avec décalage par rang + variation couleur déterministe
    for ry in range(-1, h // TILE + 2):
        offset = TILE // 2 if (ry % 2) else 0
        for rx in range(-1, w // TILE + 2):
            x0 = rx * TILE + offset
            y0 = ry * TILE
            seed = (ry * 137 + rx * 47) % 28
            b = 28 + seed
            col = (b + 8, b + 5, b + 1)
            grout = max(10, b - 12)
            # Fond du pavé
            draw.rectangle(
                [x0, y0, x0 + TILE - 3, y0 + TILE - 3],
                fill=col
            )
            # Highlight haut-gauche
            draw.line(
                [(x0, y0), (x0 + TILE - 4, y0)],
                fill=(min(255, col[0] + 22), min(255, col[1] + 16),
                      min(255, col[2] + 12))
            )
            draw.line(
                [(x0, y0), (x0, y0 + TILE - 4)],
                fill=(min(255, col[0] + 14), min(255, col[1] + 10),
                      min(255, col[2] + 8))
            )
            # Ombre bas-droite
            draw.line(
                [(x0 + TILE - 3, y0), (x0 + TILE - 3, y0 + TILE - 3)],
                fill=(grout, max(0, grout - 5), max(0, grout - 8))
            )
            draw.line(
                [(x0, y0 + TILE - 3), (x0 + TILE - 3, y0 + TILE - 3)],
                fill=(grout, max(0, grout - 5), max(0, grout - 8))
            )

    # ── Lueur centrale (sous le cercle, plus chaude)
    cx, cy = w // 2, h // 2
    ambient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ad = ImageDraw.Draw(ambient)
    for r in range(220, 0, -6):
        alpha = int(50 * (1 - r / 220) ** 2)
        ad.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(35, 90, 85, alpha)
        )
    ambient_blur = ambient.filter(ImageFilter.GaussianBlur(radius=22))
    base = Image.alpha_composite(base, ambient_blur)
    draw = ImageDraw.Draw(base)

    # ── Cercle magique teal (couche vive au-dessus)
    glow_ring = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grd = ImageDraw.Draw(glow_ring)
    ring_specs = [
        (195, 2, (60, 190, 180, 50)),
        (170, 2, (70, 205, 195, 70)),
        (145, 3, (85, 220, 210, 100)),
        (112, 4, (95, 230, 220, 130)),
        (80,  2, (80, 215, 205, 90)),
        (50,  2, (70, 200, 190, 70)),
    ]
    for r, lw, color in ring_specs:
        grd.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=color, width=lw
        )

    # Nœuds runiques (12 points sur l'anneau principal r=112)
    for i in range(12):
        angle = (math.tau / 12) * i
        rx = int(cx + math.cos(angle) * 112)
        ry = int(cy + math.sin(angle) * 112)
        grd.ellipse(
            [rx - 5, ry - 5, rx + 5, ry + 5],
            fill=(160, 240, 230, 110)
        )

    # Lignes cardinales
    for angle in [0, math.pi / 2]:
        x0e = int(cx + math.cos(angle) * 190)
        y0e = int(cy + math.sin(angle) * 190)
        x1e = int(cx - math.cos(angle) * 190)
        y1e = int(cy - math.sin(angle) * 190)
        grd.line([(x0e, y0e), (x1e, y1e)], fill=(75, 185, 175, 35), width=1)

    # Lignes diagonales
    for angle in [math.pi / 4, 3 * math.pi / 4]:
        x0e = int(cx + math.cos(angle) * 145)
        y0e = int(cy + math.sin(angle) * 145)
        x1e = int(cx - math.cos(angle) * 145)
        y1e = int(cy - math.sin(angle) * 145)
        grd.line([(x0e, y0e), (x1e, y1e)], fill=(60, 170, 160, 25), width=1)

    ring_blur = glow_ring.filter(ImageFilter.GaussianBlur(radius=5))
    base = Image.alpha_composite(base, ring_blur)

    # ── Marques ambre aux coins
    corner_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(corner_layer)
    for ccx, ccy in [(80, 50), (w - 80, 50), (80, h - 50), (w - 80, h - 50)]:
        # Losange
        cdraw.polygon(
            [(ccx, ccy - 20), (ccx + 13, ccy),
             (ccx, ccy + 20), (ccx - 13, ccy)],
            outline=(185, 148, 55, 110), width=1
        )
        # Centre
        cdraw.ellipse(
            [ccx - 4, ccy - 4, ccx + 4, ccy + 4],
            fill=(205, 168, 70, 100)
        )
        # Ticks cardinaux
        for ang in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
            tx = int(ccx + math.cos(ang) * 25)
            ty = int(ccy + math.sin(ang) * 25)
            cdraw.ellipse([tx - 2, ty - 2, tx + 2, ty + 2],
                          fill=(180, 145, 55, 80))
    corners_blur = corner_layer.filter(ImageFilter.GaussianBlur(radius=1.5))
    base = Image.alpha_composite(base, corners_blur)

    # ── Fissures
    crack_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    crackd = ImageDraw.Draw(crack_layer)
    crack_paths = [
        [(int(w * .17), int(h * .08)), (int(w * .21), int(h * .22)),
         (int(w * .18), int(h * .37))],
        [(int(w * .78), int(h * .11)), (int(w * .74), int(h * .24)),
         (int(w * .76), int(h * .40))],
        [(int(w * .19), int(h * .64)), (int(w * .24), int(h * .76)),
         (int(w * .20), int(h * .91))],
        [(int(w * .83), int(h * .62)), (int(w * .79), int(h * .74)),
         (int(w * .81), int(h * .92))],
    ]
    for crack_p in crack_paths:
        crackd.line(crack_p, fill=(12, 10, 8, 90), width=3)
        crackd.line(crack_p, fill=(10, 8, 6, 45), width=5)
    base = Image.alpha_composite(base, crack_layer)

    # ── Vignette bords
    vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for i in range(0, 110, 2):
        alpha = int(200 * (1 - i / 110) ** 2)
        vd.rectangle([i, i, w - i, h - i],
                     outline=(0, 0, 0, alpha), width=1)
    base = Image.alpha_composite(
        base, vig.filter(ImageFilter.GaussianBlur(radius=10))
    )

    # ── Bordure lumineuse fine (edge de l'arène)
    edge_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge_layer)
    ed.rectangle([0, 0, w - 1, h - 1],
                 outline=(155, 148, 128, 180), width=3)
    ed.rectangle([3, 3, w - 4, h - 4],
                 outline=(90, 85, 72, 90), width=2)
    base = Image.alpha_composite(base, edge_layer)

    base.save(str(path), format="PNG")
    print(f"  Sol arène    : {path.name} ({w}×{h})")


if __name__ == "__main__":
    print("Génération des assets arène…")
    gen_ambient(OUT / "arena_darkstone_bg.png", w=1280, h=980)
    gen_floor(OUT / "arena_forgotten_sanctum_floor.png", w=1160, h=700)
    print("OK")
