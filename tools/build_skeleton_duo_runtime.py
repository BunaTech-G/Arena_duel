#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
EXTRACTION_DIR = (
    WORKSPACE_ROOT
    / "assets"
    / "sprites"
    / "skeleton_duo_fighters"
    / "extracted"
    / "perso_auto"
)
CLASSIFICATION_MANIFEST = EXTRACTION_DIR / "classification_manifest.json"
SPRITES_ROOT = WORKSPACE_ROOT / "assets" / "sprites"
PORTRAITS_ROOT = WORKSPACE_ROOT / "assets" / "portraits"


PACK_METADATA = {
    "skeleton_fighter_ember": {
        "style": "fantasy skeleton duelist with warm ember accents",
        "role": "agile duelist",
        "accent_hex": "#f3c96b",
        "secondary_hex": "#c8884a",
        "silhouette_rules": [
            "front-weighted readable silhouette",
            "short curved blade readable at gameplay distance",
            "narrower stance than aether",
            "no black background or matte halo",
        ],
    },
    "skeleton_fighter_aether": {
        "style": "fantasy skeleton guardian with cool cyan accents",
        "role": "sturdy guardian",
        "accent_hex": "#64d7ff",
        "secondary_hex": "#2d758e",
        "silhouette_rules": [
            "front-weighted readable silhouette",
            "compact hammer readable at gameplay distance",
            "broader grounded torso than ember",
            "no black background or matte halo",
        ],
    },
}


def _load_manifest() -> dict:
    with open(CLASSIFICATION_MANIFEST, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _trim_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return rgba.copy()
    return rgba.crop(bbox)


def _fit_to_canvas(
    image: Image.Image, size: tuple[int, int], bottom_padding: int
) -> Image.Image:
    trimmed = _trim_alpha(image)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))

    max_width = max(1, size[0] - 12)
    max_height = max(1, size[1] - bottom_padding - 8)
    scale = min(max_width / trimmed.width, max_height / trimmed.height)
    resized = trimmed.resize(
        (
            max(1, int(round(trimmed.width * scale))),
            max(1, int(round(trimmed.height * scale))),
        ),
        Image.Resampling.LANCZOS,
    )

    paste_x = (size[0] - resized.width) // 2
    paste_y = size[1] - bottom_padding - resized.height
    canvas.alpha_composite(resized, (paste_x, paste_y))
    return canvas


def _build_portrait(
    image: Image.Image, size: tuple[int, int] = (256, 256)
) -> Image.Image:
    trimmed = _trim_alpha(image)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))

    max_width = max(1, size[0] - 44)
    max_height = max(1, size[1] - 38)
    scale = min(max_width / trimmed.width, max_height / trimmed.height)
    resized = trimmed.resize(
        (
            max(1, int(round(trimmed.width * scale))),
            max(1, int(round(trimmed.height * scale))),
        ),
        Image.Resampling.LANCZOS,
    )

    paste_x = (size[0] - resized.width) // 2
    paste_y = max(10, (size[1] - resized.height) // 2 - 8)
    canvas.alpha_composite(resized, (paste_x, paste_y))
    return canvas


def _copy_classified_sources(manifest: dict) -> dict[str, dict[str, Path]]:
    pose_index: dict[str, dict[str, Path]] = {}
    for frame in manifest.get("frames", []):
        character = frame["character"]
        source_path = EXTRACTION_DIR / frame["source"]
        target_path = EXTRACTION_DIR / frame["target"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.open(source_path).convert("RGBA")
        image.save(target_path)
        pose_index.setdefault(character, {})[frame["pose"]] = target_path
    return pose_index


def _write_runtime_pack(
    sprite_id: str,
    config: dict,
    pose_index: dict[str, dict[str, Path]],
) -> dict:
    metadata = PACK_METADATA[sprite_id]
    character = config["character"]
    frame_size = tuple(config.get("base_frame_size", [96, 96]))
    output_dir = SPRITES_ROOT / sprite_id
    output_dir.mkdir(parents=True, exist_ok=True)

    animations_manifest: dict[str, list[str]] = {}
    for animation_name, pose_names in config.get("animations", {}).items():
        frame_names: list[str] = []
        for index, pose_name in enumerate(pose_names):
            source_path = pose_index[character][pose_name]
            frame_name = f"{animation_name}_{index}.png"
            frame_path = output_dir / frame_name
            frame_image = Image.open(source_path).convert("RGBA")
            fitted_frame = _fit_to_canvas(
                frame_image,
                frame_size,
                bottom_padding=4,
            )
            fitted_frame.save(frame_path)
            frame_names.append(frame_name)
        animations_manifest[animation_name] = frame_names

    portrait_name = config["portrait"]
    portrait_pose = config["portrait_pose"]
    portrait_path = PORTRAITS_ROOT / portrait_name
    portrait_path.parent.mkdir(parents=True, exist_ok=True)
    portrait_source_path = pose_index[character][portrait_pose]
    portrait_image = Image.open(portrait_source_path).convert("RGBA")
    _build_portrait(portrait_image).save(portrait_path)

    manifest_data = {
        "id": sprite_id,
        "label": config["label"],
        "style": metadata["style"],
        "base_frame_size": list(frame_size),
        "anchor": "center_bottom",
        "render_mode": "semi_top_down_front_weighted",
        "source_character": character,
        "source_sheet": ("../skeleton_duo_fighters/skeleton_duo_master_sheet.png"),
        "source_classification": (
            "../skeleton_duo_fighters/extracted/perso_auto/classification_manifest.json"
        ),
        "runtime_note": (
            "Front-biased 4-frame cycle derived from visually "
            "validated extracted poses because the imported sheet "
            "is not directional runtime-ready."
        ),
        "animations": animations_manifest,
        "portrait": f"../../portraits/{portrait_name}",
        "accent_hex": metadata["accent_hex"],
        "secondary_hex": metadata["secondary_hex"],
        "silhouette_rules": metadata["silhouette_rules"],
    }

    with open(
        output_dir / "manifest.json",
        "w",
        encoding="utf-8",
    ) as file_handle:
        json.dump(manifest_data, file_handle, indent=2)
        file_handle.write("\n")

    return {
        "id": sprite_id,
        "manifest": str(
            (output_dir / "manifest.json").relative_to(WORKSPACE_ROOT)
        ).replace("\\", "/"),
        "portrait": str(portrait_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
    }


def main() -> int:
    manifest = _load_manifest()
    pose_index = _copy_classified_sources(manifest)

    generated = []
    for sprite_id, config in manifest.get("runtime_packs", {}).items():
        generated.append(_write_runtime_pack(sprite_id, config, pose_index))

    summary = {
        "classification_manifest": str(
            CLASSIFICATION_MANIFEST.relative_to(WORKSPACE_ROOT)
        ).replace("\\", "/"),
        "generated": generated,
    }
    with open(
        EXTRACTION_DIR / "runtime_build_manifest.json", "w", encoding="utf-8"
    ) as file_handle:
        json.dump(summary, file_handle, indent=2)
        file_handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
