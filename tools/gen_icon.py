#!/usr/bin/env python3
"""Genere le pack d'icones Arena Duel a partir du logo officiel fourni."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent.parent
MASTER_LOGO_PATH = ROOT_DIR / "logo principale.png"
REFERENCE_SHEET_PATH = ROOT_DIR / "ico du jeu.png"
ICONS_DIR = ROOT_DIR / "assets" / "icons"
IMAGES_DIR = ROOT_DIR / "assets" / "images"

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
WINDOW_ICON_SIZE = 64
MASTER_PREVIEW_SIZE = 256

RESAMPLING_NEAREST = getattr(
    getattr(Image, "Resampling", Image),
    "NEAREST",
)

# Recadrages en coordonnees du logo principal 1024x1024.
FULL_CROP = None
MEDIUM_CROP = (120, 210, 930, 980)
SMALL_CROP = (250, 250, 760, 760)

SIZE_TO_CROP = {
    256: FULL_CROP,
    128: FULL_CROP,
    64: MEDIUM_CROP,
    48: MEDIUM_CROP,
    32: SMALL_CROP,
    24: SMALL_CROP,
    16: SMALL_CROP,
}


def _load_master_logo() -> Image.Image:
    if not MASTER_LOGO_PATH.exists():
        raise FileNotFoundError(f"Logo principal introuvable : {MASTER_LOGO_PATH}")

    image = Image.open(MASTER_LOGO_PATH).convert("RGBA")
    visible_bounds = image.getbbox()
    if visible_bounds is None:
        raise ValueError("Le logo principal est vide ou entierement transparent.")
    return image.crop(visible_bounds)


def _make_square_canvas(image: Image.Image) -> Image.Image:
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    offset_x = (side - image.width) // 2
    offset_y = (side - image.height) // 2
    canvas.alpha_composite(image, (offset_x, offset_y))
    return canvas


def _crop_variant(master: Image.Image, crop_box) -> Image.Image:
    if crop_box is None:
        return _make_square_canvas(master)
    return _make_square_canvas(master.crop(crop_box))


def _render_variant(master: Image.Image, size: int) -> Image.Image:
    crop_box = SIZE_TO_CROP.get(size, FULL_CROP)
    square_variant = _crop_variant(master, crop_box)
    return square_variant.resize((size, size), RESAMPLING_NEAREST)


def _save_png_variants(variants: dict[int, Image.Image]) -> dict[str, Path]:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    generated_paths: dict[str, Path] = {}
    for size, image in variants.items():
        output_path = ICONS_DIR / f"app_{size}.png"
        image.save(output_path, "PNG")
        generated_paths[f"png_{size}"] = output_path

    runtime_icon_path = ICONS_DIR / "app.png"
    variants[WINDOW_ICON_SIZE].save(runtime_icon_path, "PNG")
    generated_paths["runtime_png"] = runtime_icon_path

    preview_path = ICONS_DIR / "icon_preview_256.png"
    variants[MASTER_PREVIEW_SIZE].save(preview_path, "PNG")
    generated_paths["preview_png"] = preview_path

    return generated_paths


def _save_multi_resolution_ico(
    variants: dict[int, Image.Image],
    output_path: Path,
) -> Path:
    ordered_sizes = tuple(sorted(variants))
    largest_size = max(ordered_sizes)
    base_image = variants[largest_size]
    append_images = [variants[size] for size in ordered_sizes if size != largest_size]
    base_image.save(
        output_path,
        format="ICO",
        sizes=[(size, size) for size in ordered_sizes],
        append_images=append_images,
    )
    return output_path


def generate_all() -> dict[str, Path]:
    master_logo = _load_master_logo()
    variants = {size: _render_variant(master_logo, size) for size in ICON_SIZES}

    generated_paths = _save_png_variants(variants)

    app_ico_path = ICONS_DIR / "app.ico"
    generated_paths["app_ico"] = _save_multi_resolution_ico(
        variants,
        app_ico_path,
    )

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    installer_ico_path = IMAGES_DIR / "arena_duel.ico"
    shutil.copyfile(app_ico_path, installer_ico_path)
    generated_paths["installer_ico"] = installer_ico_path

    return generated_paths


def _print_report(generated_paths: dict[str, Path]):
    print("[INFO] Generation des icones Arena Duel depuis le logo officiel")
    print(f"       source maitre : {MASTER_LOGO_PATH}")
    if REFERENCE_SHEET_PATH.exists():
        print(f"       planche fournie : {REFERENCE_SHEET_PATH}")
    else:
        print("       planche fournie : absente")

    print()
    for key in (
        "png_16",
        "png_24",
        "png_32",
        "png_48",
        "png_64",
        "png_128",
        "png_256",
        "runtime_png",
        "preview_png",
        "app_ico",
        "installer_ico",
    ):
        path = generated_paths[key]
        print(f"[OK] {key:13s} -> {path}")


if __name__ == "__main__":
    results = generate_all()
    _print_report(results)
