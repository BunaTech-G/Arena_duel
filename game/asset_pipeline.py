from __future__ import annotations

import json
from pathlib import Path

import pygame

from runtime_utils import resource_path


ASSETS_ROOT = Path(resource_path("assets"))
MANIFEST_PATH = ASSETS_ROOT / "asset_manifest.json"
BACKGROUND_MANIFEST_PATH = ASSETS_ROOT / "backgrounds" / "manifest.json"


_IMAGE_CACHE: dict[tuple[str, tuple[int, int] | None, bool], pygame.Surface] = {}


def asset_path(*parts: str) -> Path:
    return ASSETS_ROOT.joinpath(*parts)


def load_asset_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}

    with open(MANIFEST_PATH, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def load_json_asset(*parts: str) -> dict:
    path = asset_path(*parts)
    with open(path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def load_background_manifest() -> dict:
    if not BACKGROUND_MANIFEST_PATH.exists():
        return {}

    with open(BACKGROUND_MANIFEST_PATH, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def load_map_definition(map_id: str = "forgotten_sanctum") -> dict:
    return load_json_asset("maps", map_id, "layout.json")


def load_sprite_manifest(sprite_id: str = "skeleton_mascot") -> dict:
    return load_json_asset("sprites", sprite_id, "manifest.json")


def list_sprite_frames(sprite_id: str, animation_name: str) -> list[Path]:
    manifest = load_sprite_manifest(sprite_id)
    animations = manifest.get("animations", {})
    frame_names = animations.get(animation_name, [])
    return [asset_path("sprites", sprite_id, frame_name) for frame_name in frame_names]


def load_font(filename: str, size: int, fallback_name: str = "Segoe UI", bold: bool = False) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()

    font_file = asset_path("fonts", filename)
    if font_file.exists():
        return pygame.font.Font(str(font_file), size)

    return pygame.font.SysFont(fallback_name, size, bold=bold)


def make_placeholder_surface(
    size: tuple[int, int],
    label: str = "placeholder",
    fill_color: tuple[int, int, int] = (29, 37, 53),
    border_color: tuple[int, int, int] = (96, 125, 170),
    accent_color: tuple[int, int, int] = (244, 200, 96),
) -> pygame.Surface:
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)

    surface.fill(fill_color)
    pygame.draw.rect(surface, border_color, surface.get_rect(), width=3, border_radius=12)
    pygame.draw.line(surface, accent_color, (12, 12), (width - 12, height - 12), width=2)
    pygame.draw.line(surface, accent_color, (width - 12, 12), (12, height - 12), width=2)

    if not pygame.font.get_init():
        pygame.font.init()

    font = pygame.font.SysFont("Segoe UI", max(14, min(width, height) // 6), bold=True)
    text_surface = font.render(label[:14], True, (243, 239, 223))
    text_rect = text_surface.get_rect(center=(width // 2, height // 2))
    surface.blit(text_surface, text_rect)
    return surface


def _load_image_from_path(
    path: Path,
    size: tuple[int, int] | None = None,
    fallback_label: str | None = None,
    use_alpha: bool = True,
    allow_placeholder: bool = True,
) -> pygame.Surface | None:
    cache_key = (str(path), size, use_alpha)

    if path.exists():
        if cache_key in _IMAGE_CACHE:
            return _IMAGE_CACHE[cache_key]

        image = pygame.image.load(str(path))
        try:
            image = image.convert_alpha() if use_alpha else image.convert()
        except pygame.error:
            pass

        if size is not None:
            image = pygame.transform.smoothscale(image, size)

        _IMAGE_CACHE[cache_key] = image
        return image

    if not allow_placeholder:
        return None

    placeholder_size = size or (96, 96)
    placeholder_text = fallback_label or path.stem or "missing"
    return make_placeholder_surface(placeholder_size, label=placeholder_text)


def load_image(
    *parts: str,
    size: tuple[int, int] | None = None,
    fallback_label: str | None = None,
    use_alpha: bool = True,
    allow_placeholder: bool = True,
) -> pygame.Surface | None:
    path = asset_path(*parts)
    return _load_image_from_path(
        path,
        size=size,
        fallback_label=fallback_label,
        use_alpha=use_alpha,
        allow_placeholder=allow_placeholder,
    )


def load_background_asset(
    background_id: str,
    size: tuple[int, int] | None = None,
    fallback_label: str | None = None,
    allow_placeholder: bool = True,
) -> pygame.Surface | None:
    manifest = load_background_manifest()
    asset_entry = manifest.get("assets", {}).get(background_id, {})
    file_name = asset_entry.get("file") or background_id
    label = fallback_label or asset_entry.get("label") or background_id
    return load_image(
        "backgrounds",
        file_name,
        size=size,
        fallback_label=label,
        allow_placeholder=allow_placeholder,
    )


def load_sprite_animation_frame(
    sprite_id: str,
    animation_name: str,
    frame_index: int,
    size: tuple[int, int] | None = None,
    facing: int = 1,
    allow_placeholder: bool = False,
) -> pygame.Surface | None:
    frame_paths = list_sprite_frames(sprite_id, animation_name)
    if not frame_paths:
        if not allow_placeholder:
            return None
        return make_placeholder_surface(size or (96, 96), label=f"{sprite_id}:{animation_name}")

    frame_path = frame_paths[frame_index % len(frame_paths)]
    image = _load_image_from_path(
        frame_path,
        size=size,
        fallback_label=f"{sprite_id}:{animation_name}",
        allow_placeholder=allow_placeholder,
    )
    if image is None:
        return None
    if facing < 0:
        return pygame.transform.flip(image, True, False)
    return image


def load_sprite_portrait(
    sprite_id: str = "skeleton_mascot",
    size: tuple[int, int] | None = None,
    fallback_label: str | None = None,
    allow_placeholder: bool = True,
) -> pygame.Surface | None:
    manifest = load_sprite_manifest(sprite_id)
    portrait_ref = manifest.get("portrait")
    if not portrait_ref:
        if not allow_placeholder:
            return None
        return make_placeholder_surface(size or (96, 96), label=fallback_label or sprite_id)

    portrait_path = asset_path("sprites", sprite_id, portrait_ref)
    return _load_image_from_path(
        portrait_path,
        size=size,
        fallback_label=fallback_label or sprite_id,
        allow_placeholder=allow_placeholder,
    )


def describe_asset_tree() -> dict:
    manifest = load_asset_manifest()
    return {
        "root": str(ASSETS_ROOT),
        "manifest_version": manifest.get("version"),
        "directories": manifest.get("directories", {}),
        "maps": [entry.get("id") for entry in manifest.get("maps", [])],
        "sprites": [entry.get("id") for entry in manifest.get("sprites", [])],
    }