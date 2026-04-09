#!/usr/bin/env python3
"""
gen_icon.py – Génère la nouvelle icône Arena Duel
Concept : bouclier héraldique bleu nuit + épées croisées en or + étoile centrale
Palette : bleu nuit profond (#0a1223) + or chaud (#c8a030) + reflets pâles
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

# ── Palette ──────────────────────────────────────────────────────────────────
TRANSPARENT  = (0,   0,   0,   0)
NAVY_BG      = (10,  18,  35, 255)
SHIELD_FILL  = (16,  34,  66, 255)
SHIELD_RIM   = (178, 140, 48, 255)
SHIELD_RIM2  = (140, 108, 35, 180)
GOLD_BRIGHT  = (235, 198, 78, 255)
GOLD_MID     = (200, 160, 52, 255)
GOLD_DARK    = (138, 106, 26, 255)
GOLD_PALE    = (252, 232, 150, 210)
GRIP_DARK    = (165, 125,  34, 255)   # ambre visible sur fond marine
GRIP_MID     = (195, 158,  48, 255)
STAR_CORE    = (232, 178, 52, 255)   # ambre soutenu, pas blanc


# ── Helpers géométriques ─────────────────────────────────────────────────────

def _scale_pts(pts, f: float):
    return [(x * f, y * f) for x, y in pts]


def shield_polygon(size: int):
    """Polygone bouclier héraldique (base 512)."""
    f = size / 512
    raw = [
        ( 82,  52),  # coin haut-gauche
        (430,  52),  # coin haut-droit
        (478, 264),  # milieu droit
        (256, 476),  # pointe basse
        ( 34, 264),  # milieu gauche
    ]
    return _scale_pts(raw, f)


def rotated_rect_pts(cx: float, cy: float, w: float, h: float, angle_deg: float):
    """4 sommets d'un rectangle centré (cx,cy), pivoté de angle_deg degrés."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    hw, hh = w / 2, h / 2
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in corners]


def octagram_pts(cx: float, cy: float, r_outer: float, r_inner: float, n: int = 8):
    """Étoile à n branches."""
    pts = []
    for i in range(n * 2):
        angle = math.pi / n * i - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    return pts


# ── Dessin d'épée ─────────────────────────────────────────────────────────────

def draw_sword(draw: ImageDraw.ImageDraw, cx: float, cy: float,
               length: float, angle_deg: float, scale: float):
    """
    Dessine une épée centrée en (cx, cy), de longueur `length`,
    orientée à `angle_deg` degrés.
    Pointe côté négatif de l'axe, pommeau côté positif.
    """
    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)   # vecteur axe
    px, py = -uy, ux                    # vecteur perpendiculaire

    # Positions clés le long de l'axe (depuis cx,cy)
    # Garde AU point de croisement (cx,cy) → X symétrique bien lisible
    tip_d   = -length * 0.470   # pointe (direction négative)
    guard_d =  0                # garde exactement au croisement
    grip_s  =  length * 0.038   # début du grip
    grip_e  =  grip_s + length * 0.270  # fin du grip
    pom_d   =  length * 0.470   # pommeau (symétrique)

    def pt(d, perp=0.0):
        return (cx + ux * d + px * perp, cy + uy * d + py * perp)

    # --- Ombre portée de la lame ---
    bw = 13 * scale   # demi-largeur maxi à la garde (lame bien visible)
    tw =  6 * scale   # demi-largeur à la pointe (épée large, pas un stylet)
    shadow_blade = [
        pt(tip_d + 2*scale, -tw + 1.5*scale), pt(tip_d + 2*scale,  tw + 1.5*scale),
        pt(guard_d + 1.5*scale,  bw + 1.5*scale),
        pt(guard_d + 1.5*scale, -bw + 1.5*scale),
    ]
    draw.polygon(shadow_blade, fill=(0, 0, 0, 80))

    # --- Lame (trapèze fantasy : épaisse, légèrement évasée vers la garde) ---
    blade_pts = [
        pt(tip_d, -tw), pt(tip_d,  tw),
        pt(guard_d,  bw), pt(guard_d, -bw),
    ]
    draw.polygon(blade_pts, fill=GOLD_BRIGHT)

    # Liseré pâle sur l'arête (brillance froide)
    shine_pts = [
        pt(tip_d,   -tw),
        pt(guard_d, -bw),
        pt(guard_d, -bw * 0.22),
        pt(tip_d,   -tw * 0.30),
    ]
    draw.polygon(shine_pts, fill=GOLD_PALE)

    # Nervure centrale (ombre chaude)
    spine_pts = [
        pt(tip_d + length * 0.01,  tw * 0.10),
        pt(guard_d - length * 0.01, bw * 0.18),
        pt(guard_d - length * 0.01, bw * 0.48),
        pt(tip_d + length * 0.01,  tw * 0.42),
    ]
    draw.polygon(spine_pts, fill=(190, 152, 40, 150))

    # --- Garde croisée (barre transversale) ---
    guard_w = length * 0.235
    guard_h = length * 0.048
    # ombre
    gshadow = rotated_rect_pts(
        cx + ux * (guard_d + length * 0.006),
        cy + uy * (guard_d + length * 0.006),
        guard_w, guard_h * 1.4, angle_deg + 90)
    draw.polygon(gshadow, fill=(0, 0, 0, 90))
    # Corps sombre
    gpts_dark = rotated_rect_pts(
        cx + ux * guard_d, cy + uy * guard_d,
        guard_w, guard_h * 1.2, angle_deg + 90)
    draw.polygon(gpts_dark, fill=GOLD_DARK)
    # Corps principal
    gpts = rotated_rect_pts(
        cx + ux * guard_d, cy + uy * guard_d,
        guard_w * 0.95, guard_h, angle_deg + 90)
    draw.polygon(gpts, fill=GOLD_MID)
    # Reflet dessus
    gpts_hi = rotated_rect_pts(
        cx + ux * (guard_d - guard_h * 0.15), cy + uy * (guard_d - guard_h * 0.15),
        guard_w * 0.88, guard_h * 0.35, angle_deg + 90)
    draw.polygon(gpts_hi, fill=GOLD_BRIGHT)
    # Contour
    draw.polygon(gpts, outline=(215, 178, 65, 255), width=max(1, round(1.5 * scale)))

    # --- Grip ---
    grip_mid_d = (grip_s + grip_e) / 2
    grip_len   = grip_e - grip_s
    gw = 5.5 * scale
    gpts2 = rotated_rect_pts(cx + ux * grip_mid_d, cy + uy * grip_mid_d,
                              gw, grip_len, angle_deg)
    draw.polygon(gpts2, fill=GRIP_DARK)
    # Bandage (3 raies)
    for i in range(4):
        t_wrap = grip_s + grip_len * (0.15 + i * 0.22)
        wrap = rotated_rect_pts(
            cx + ux * t_wrap, cy + uy * t_wrap,
            gw * 1.15, grip_len * 0.065, angle_deg)
        draw.polygon(wrap, fill=GRIP_MID)

    # --- Pommeau (grand cercle bien visible) ---
    pr = 13 * scale
    draw.ellipse([cx + ux * pom_d - pr, cy + uy * pom_d - pr,
                  cx + ux * pom_d + pr, cy + uy * pom_d + pr],
                 fill=GOLD_DARK, outline=GOLD_BRIGHT, width=max(1, round(1.5 * scale)))
    ir = pr * 0.60
    draw.ellipse([cx + ux * pom_d - ir, cy + uy * pom_d - ir,
                  cx + ux * pom_d + ir, cy + uy * pom_d + ir],
                 fill=GOLD_BRIGHT)


# ── Composition principale ─────────────────────────────────────────────────────

def make_icon_image(size: int = 512) -> Image.Image:
    img  = Image.new("RGBA", (size, size), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    f    = size / 512
    cx   = size * 0.50
    cy   = size * 0.48

    # ── 1. Halo de fond (cercle dégradé simulé) ──────────────────────────────
    half = size * 0.48
    for step in range(28, 0, -1):
        frac   = step / 28
        radius = int(half * frac)
        shade  = (int(8 + (1 - frac) * 18), int(12 + (1 - frac) * 30), int(28 + (1 - frac) * 55))
        alpha  = int(frac * 230)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(*shade, alpha)
        )

    # ── 2. Ombre du bouclier ───────────────────────────────────────────────────
    shadow_pts = [(x + 4 * f, y + 5 * f) for x, y in shield_polygon(size)]
    draw.polygon(shadow_pts, fill=(0, 0, 0, 90))

    # ── 3. Corps du bouclier ──────────────────────────────────────────────────
    sp = shield_polygon(size)
    draw.polygon(sp, fill=SHIELD_FILL)

    # ── 4. Bordure externe dorée ──────────────────────────────────────────────
    draw.polygon(sp, outline=SHIELD_RIM, width=round(7 * f))

    # ── 5. Bordure interne fine ───────────────────────────────────────────────
    mg = 13 * f
    inner_shield = [
        ( 82 * f + mg,        52 * f + mg),
        (430 * f - mg,        52 * f + mg),
        (478 * f - mg * 0.5, 264 * f),
        (256 * f,            476 * f - mg * 1.4),
        ( 34 * f + mg * 0.5, 264 * f),
    ]
    draw.polygon(inner_shield, outline=SHIELD_RIM2, width=round(2.5 * f))

    # ── 6. Lueur ambrée centrale (très subtile) ────────────────────────────────
    glow_layer = Image.new("RGBA", (size, size), TRANSPARENT)
    gd = ImageDraw.Draw(glow_layer)
    for radius, alpha in [(100 * f, 28), (64 * f, 18), (36 * f, 10)]:
        gd.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                   fill=(200, 155, 38, alpha))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(20 * f)))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # ── 7. Épées croisées ─────────────────────────────────────────────────────
    sword_len = size * 0.570
    # Épée arrière (pointe haut-gauche → pommeau bas-droit)
    draw_sword(draw, cx, cy, sword_len, 45, f)
    # Épée avant (pointe haut-droit → pommeau bas-gauche)
    draw_sword(draw, cx, cy, sword_len, 135, f)

    # ── 8. Étoile de croisement ───────────────────────────────────────────────
    star_outer = 14 * f
    star_inner =  5.5 * f
    star_pts   = octagram_pts(cx, cy, star_outer, star_inner, 8)
    # halo ambré discret
    for r2, al in [(star_outer * 2.6, 22), (star_outer * 1.8, 14)]:
        draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
                     fill=(220, 165, 40, al))
    draw.polygon(star_pts, fill=STAR_CORE)

    # ── 9. Contour final du bouclier (au premier plan) ────────────────────────
    draw.polygon(shield_polygon(size), outline=SHIELD_RIM, width=round(5 * f))

    return img


# ── Export multi-format ────────────────────────────────────────────────────────

ICO_SIZES   = [16, 24, 32, 48, 64, 128, 256]


def generate_all(icons_dir: Path, images_dir: Path):
    icons_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    print("[1/3] Génération de l'image source 512×512…")
    base = make_icon_image(512)

    # --- PNG pour Pygame (pygame.display.set_icon) ---
    png_path = icons_dir / "app.png"
    base.save(str(png_path), "PNG")
    print(f"      {png_path}")

    # Vignette de preview
    preview_path = icons_dir / "icon_preview_256.png"
    base.resize((256, 256), Image.LANCZOS).save(str(preview_path), "PNG")
    print(f"      {preview_path}")

    print("[2/3] Génération des .ico multi-tailles…")
    variants = [base.resize((s, s), Image.LANCZOS).convert("RGBA")
                for s in ICO_SIZES]

    # ICO pour Tkinter (assets/icons/app.ico)
    ico_tkinter = icons_dir / "app.ico"
    variants[0].save(
        str(ico_tkinter), format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=variants[1:],
    )
    print(f"      {ico_tkinter}")

    # ICO pour PyInstaller + installateur Inno (assets/images/arena_duel.ico)
    ico_build = images_dir / "arena_duel.ico"
    build_variants = [base.resize((s, s), Image.LANCZOS).convert("RGBA")
                      for s in ICO_SIZES]
    build_variants[0].save(
        str(ico_build), format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=build_variants[1:],
    )
    print(f"      {ico_build}")

    print("[3/3] Vérification des fichiers générés…")
    results = {
        "PNG (Pygame)":          png_path,
        "ICO (Tkinter/desktop)": ico_tkinter,
        "ICO (build/installer)": ico_build,
        "PNG preview 256":       preview_path,
    }
    all_ok = True
    for label, path in results.items():
        exists = path.exists()
        status = "OK" if exists else "MANQUANT"
        print(f"  [{status}] {label:26s} → {path}")
        all_ok = all_ok and exists

    return all_ok


if __name__ == "__main__":
    root       = Path(__file__).parent.parent
    icons_dir  = root / "assets" / "icons"
    images_dir = root / "assets" / "images"

    ok = generate_all(icons_dir, images_dir)
    print()
    if ok:
        print("Icône Arena Duel générée avec succès.")
    else:
        print("Erreur : certains fichiers n'ont pas été créés.")
        raise SystemExit(1)
