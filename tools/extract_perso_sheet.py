#!/usr/bin/env python3
"""
Extract sprite frames from a transparent sheet by connected alpha components.

This is tuned for generated character sheets like Perso.png where each frame
is visually separated by transparent gutters but the global grid may not be
perfectly regular.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class Component:
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    pixel_count: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x

    @property
    def height(self) -> int:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.min_x, self.min_y, self.max_x, self.max_y)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract frames from a transparent sprite sheet.",
    )
    parser.add_argument(
        "--input",
        default="Perso.png",
        help="Source sprite sheet path.",
    )
    parser.add_argument(
        "--output-dir",
        default="assets/sprites/skeleton_duo_fighters/extracted/perso_auto",
        help="Directory where extracted frames are written.",
    )
    parser.add_argument(
        "--min-pixels",
        type=int,
        default=200,
        help="Ignore smaller connected components.",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=12,
        help="Transparent padding around each extracted frame.",
    )
    return parser.parse_args()


def detect_components(image: Image.Image, min_pixels: int) -> list[Component]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    width, height = rgba.size
    visited = bytearray(width * height)
    components: list[Component] = []

    for y_pos in range(height):
        for x_pos in range(width):
            index = y_pos * width + x_pos
            if visited[index] or alpha.getpixel((x_pos, y_pos)) == 0:
                continue

            visited[index] = 1
            pending: deque[tuple[int, int]] = deque([(x_pos, y_pos)])
            min_x = max_x = x_pos
            min_y = max_y = y_pos
            pixel_count = 0

            while pending:
                current_x, current_y = pending.popleft()
                pixel_count += 1
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)

                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_index = next_y * width + next_x
                    if visited[next_index]:
                        continue
                    if alpha.getpixel((next_x, next_y)) == 0:
                        continue
                    visited[next_index] = 1
                    pending.append((next_x, next_y))

            if pixel_count >= min_pixels:
                components.append(
                    Component(
                        min_x=min_x,
                        min_y=min_y,
                        max_x=max_x + 1,
                        max_y=max_y + 1,
                        pixel_count=pixel_count,
                    )
                )

    return sorted(components, key=lambda component: (component.min_y, component.min_x))


def group_rows(components: list[Component]) -> list[list[Component]]:
    if not components:
        return []

    average_height = sum(component.height for component in components) / len(components)
    threshold = max(32.0, average_height * 0.45)

    rows: list[list[Component]] = []
    current_row: list[Component] = []
    current_anchor_y: float | None = None

    for component in components:
        if current_anchor_y is None:
            current_row = [component]
            current_anchor_y = component.center_y
            continue

        if abs(component.center_y - current_anchor_y) <= threshold:
            current_row.append(component)
            current_anchor_y = sum(item.center_y for item in current_row) / len(current_row)
            continue

        rows.append(sorted(current_row, key=lambda item: item.min_x))
        current_row = [component]
        current_anchor_y = component.center_y

    if current_row:
        rows.append(sorted(current_row, key=lambda item: item.min_x))

    return rows


def normalize_frame(
    source: Image.Image,
    component: Component,
    frame_size: tuple[int, int],
    padding: int,
) -> Image.Image:
    crop = source.crop(component.bbox)
    frame_width, frame_height = frame_size
    canvas = Image.new("RGBA", frame_size, (0, 0, 0, 0))

    paste_x = (frame_width - crop.width) // 2
    paste_y = frame_height - padding - crop.height
    canvas.alpha_composite(crop, (paste_x, paste_y))
    return canvas


def build_preview(
    frame_paths: list[Path],
    frame_size: tuple[int, int],
    columns: int,
) -> Image.Image:
    frame_width, frame_height = frame_size
    rows = (len(frame_paths) + columns - 1) // columns
    preview = Image.new(
        "RGBA",
        (columns * frame_width, rows * frame_height),
        (0, 0, 0, 0),
    )

    for index, frame_path in enumerate(frame_paths):
        frame = Image.open(frame_path).convert("RGBA")
        x_pos = (index % columns) * frame_width
        y_pos = (index // columns) * frame_height
        preview.alpha_composite(frame, (x_pos, y_pos))

    return preview


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source = Image.open(input_path).convert("RGBA")
    components = detect_components(source, min_pixels=args.min_pixels)
    rows = group_rows(components)
    max_columns = max((len(row) for row in rows), default=0)
    max_width = max((component.width for component in components), default=0)
    max_height = max((component.height for component in components), default=0)
    frame_size = (
        max_width + args.padding * 2,
        max_height + args.padding * 2,
    )

    metadata = {
        "source": str(input_path),
        "output_dir": str(output_dir),
        "source_size": list(source.size),
        "frame_size": list(frame_size),
        "row_count": len(rows),
        "max_columns": max_columns,
        "frames": [],
    }

    frame_paths: list[Path] = []
    for row_index, row in enumerate(rows, start=1):
        for column_index, component in enumerate(row, start=1):
            frame_name = f"row{row_index:02d}_col{column_index:02d}.png"
            frame_path = output_dir / frame_name
            frame_image = normalize_frame(
                source,
                component,
                frame_size=frame_size,
                padding=args.padding,
            )
            frame_image.save(frame_path)
            frame_paths.append(frame_path)

            metadata["frames"].append(
                {
                    "name": frame_name,
                    "row": row_index,
                    "column": column_index,
                    "bbox": list(component.bbox),
                    "pixel_count": component.pixel_count,
                }
            )

    preview_path = output_dir / "atlas_preview.png"
    build_preview(frame_paths, frame_size=frame_size, columns=max_columns).save(preview_path)
    metadata["preview"] = preview_path.name

    metadata_path = output_dir / "extraction_manifest.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "frames": len(frame_paths),
                "rows": len(rows),
                "max_columns": max_columns,
                "frame_size": frame_size,
                "output_dir": str(output_dir),
                "preview": str(preview_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
