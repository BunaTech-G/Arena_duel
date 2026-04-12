from collections import deque
import customtkinter as ctk
from pathlib import Path
from tkinter import TclError
from typing import cast

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from runtime_utils import resource_path


PALETTE = {
    "bg": "#0f131a",
    "bg_alt": "#131924",
    "bg_glow": "#182233",
    "panel": "#1a2130",
    "panel_alt": "#212a3b",
    "panel_deep": "#141b27",
    "panel_highlight": "#2a3549",
    "panel_soft": "#161d29",
    "surface": "#273246",
    "surface_alt": "#33445f",
    "sidebar": "#101723",
    "sidebar_active": "#263247",
    "border": "#32435e",
    "border_strong": "#4a6387",
    "divider": "#243246",
    "text": "#f5efdf",
    "text_muted": "#d1dbed",
    "text_soft": "#a3aec4",
    "text_faint": "#8391ab",
    "gold": "#f3c96b",
    "gold_hover": "#ffda88",
    "gold_dim": "#9d7c37",
    "ember": "#c8884a",
    "cyan": "#64d7ff",
    "cyan_hover": "#91e3ff",
    "cyan_dim": "#2d758e",
    "steel": "#89a2c7",
    "success": "#79d59c",
    "success_dim": "#1f5d3b",
    "danger": "#e06b78",
    "danger_hover": "#f08490",
    "danger_dim": "#6f2430",
    "warning": "#efbf62",
    "warning_dim": "#735621",
    "neutral": "#66738d",
    "neutral_dim": "#2e3747",
}


TYPOGRAPHY = {
    "display": ("Palatino Linotype", 42, "bold"),
    "title": ("Palatino Linotype", 32, "bold"),
    "section": ("Palatino Linotype", 24, "bold"),
    "subtitle": ("Segoe UI Semibold", 17),
    "body": ("Segoe UI", 16),
    "body_bold": ("Segoe UI Semibold", 16),
    "small": ("Segoe UI", 14),
    "small_bold": ("Segoe UI Semibold", 14),
    "button": ("Segoe UI Semibold", 16),
    "button_small": ("Segoe UI Semibold", 14),
    "stat": ("Palatino Linotype", 22, "bold"),
}


BUTTON_VARIANTS = {
    "primary": {
        "fg_color": PALETTE["gold"],
        "hover_color": PALETTE["gold_hover"],
        "text_color": "#1c1711",
        "border_color": PALETTE["gold"],
        "border_width": 0,
    },
    "secondary": {
        "fg_color": PALETTE["panel_alt"],
        "hover_color": PALETTE["surface"],
        "text_color": PALETTE["text"],
        "border_color": PALETTE["border_strong"],
        "border_width": 1,
    },
    "accent": {
        "fg_color": PALETTE["cyan_dim"],
        "hover_color": PALETTE["cyan"],
        "text_color": PALETTE["text"],
        "border_color": PALETTE["cyan"],
        "border_width": 1,
    },
    "success": {
        "fg_color": PALETTE["success_dim"],
        "hover_color": PALETTE["success"],
        "text_color": PALETTE["text"],
        "border_color": PALETTE["success"],
        "border_width": 1,
    },
    "danger": {
        "fg_color": PALETTE["danger_dim"],
        "hover_color": PALETTE["danger_hover"],
        "text_color": PALETTE["text"],
        "border_color": PALETTE["danger"],
        "border_width": 1,
    },
    "ghost": {
        "fg_color": PALETTE["panel_soft"],
        "hover_color": PALETTE["panel_alt"],
        "text_color": PALETTE["text_muted"],
        "border_color": PALETTE["border"],
        "border_width": 1,
    },
    "nav": {
        "fg_color": PALETTE["sidebar"],
        "hover_color": PALETTE["sidebar_active"],
        "text_color": PALETTE["text_muted"],
        "border_color": PALETTE["sidebar"],
        "border_width": 1,
    },
    "nav_active": {
        "fg_color": PALETTE["sidebar_active"],
        "hover_color": PALETTE["surface_alt"],
        "text_color": PALETTE["text"],
        "border_color": PALETTE["gold_dim"],
        "border_width": 1,
    },
    "subtle": {
        "fg_color": PALETTE["panel"],
        "hover_color": PALETTE["panel_highlight"],
        "text_color": PALETTE["text_muted"],
        "border_color": PALETTE["divider"],
        "border_width": 1,
    },
}


BADGE_VARIANTS = {
    "neutral": (
        PALETTE["neutral_dim"],
        PALETTE["neutral"],
        PALETTE["text_muted"],
    ),
    "info": (PALETTE["cyan_dim"], PALETTE["cyan"], PALETTE["text"]),
    "success": (PALETTE["success_dim"], PALETTE["success"], PALETTE["text"]),
    "warning": (PALETTE["warning_dim"], PALETTE["warning"], PALETTE["text"]),
    "danger": (PALETTE["danger_dim"], PALETTE["danger"], PALETTE["text"]),
    "gold": (PALETTE["gold_dim"], PALETTE["gold"], "#1c1711"),
}


def apply_theme_settings():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def style_window(window):
    window.configure(fg_color=PALETTE["bg"])


def style_frame(frame, tone="panel", border_color=None):
    frame.configure(
        fg_color=PALETTE.get(tone, PALETTE["panel"]),
        border_width=1,
        border_color=border_color or PALETTE["border"],
    )


def style_textbox(textbox, tone="panel_soft"):
    textbox.configure(
        fg_color=PALETTE.get(tone, PALETTE["panel_soft"]),
        border_width=1,
        border_color=PALETTE["border"],
        text_color=PALETTE["text_muted"],
        font=TYPOGRAPHY["body"],
    )


def set_textbox_content(textbox, text):
    textbox.configure(state="normal")
    textbox.delete("0.0", "end")
    textbox.insert("0.0", text)
    textbox.configure(state="disabled")


def create_button(
    master,
    text,
    command,
    variant="primary",
    width=220,
    height=46,
    font=None,
    **kwargs,
):
    style = BUTTON_VARIANTS[variant]
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=14,
        font=font or TYPOGRAPHY["button"],
        fg_color=style["fg_color"],
        hover_color=style["hover_color"],
        text_color=style["text_color"],
        border_color=style["border_color"],
        border_width=style["border_width"],
        **kwargs,
    )


def create_option_menu(
    master,
    values,
    command=None,
    variable=None,
    width=220,
    height=42,
    font=None,
    dropdown_font=None,
    **kwargs,
):
    return ctk.CTkOptionMenu(
        master,
        values=values,
        command=command,
        variable=variable,
        width=width,
        height=height,
        corner_radius=14,
        fg_color=PALETTE["panel_soft"],
        button_color=PALETTE["surface"],
        button_hover_color=PALETTE["border_strong"],
        text_color=PALETTE["text"],
        dropdown_fg_color=PALETTE["panel"],
        dropdown_hover_color=PALETTE["surface"],
        dropdown_text_color=PALETTE["text"],
        font=font or TYPOGRAPHY["body_bold"],
        dropdown_font=dropdown_font or TYPOGRAPHY["body"],
        anchor="w",
        dynamic_resizing=False,
        **kwargs,
    )


def create_badge(master, text, tone="neutral"):
    badge_colors = BADGE_VARIANTS[tone]
    fg_color = badge_colors[0]
    text_color = badge_colors[2]
    return ctk.CTkLabel(
        master,
        text=text,
        corner_radius=999,
        fg_color=fg_color,
        text_color=text_color,
        font=TYPOGRAPHY["small_bold"],
        padx=12,
        pady=6,
    )


def update_badge(badge, text, tone="neutral"):
    fg_color, _, text_color = BADGE_VARIANTS[tone]
    badge.configure(text=text, fg_color=fg_color, text_color=text_color)


def present_window(window, *, clear_topmost_after_ms: int = 180):
    def _clear_topmost():
        try:
            window.attributes("-topmost", False)
        except TclError:
            pass

    def _present():
        try:
            window.deiconify()
        except TclError:
            pass

        try:
            window.update_idletasks()
        except TclError:
            pass

        try:
            window.lift()
            window.focus_force()
            window.attributes("-topmost", True)
        except TclError:
            _clear_topmost()
            return

        try:
            window.after(120, _repulse)
            window.after(clear_topmost_after_ms + 120, _clear_topmost)
        except TclError:
            _clear_topmost()

    def _repulse():
        try:
            window.lift()
            window.focus_force()
            window.attributes("-topmost", True)
        except TclError:
            _clear_topmost()

    try:
        window.after(0, _present)
    except TclError:
        _present()


def _parse_geometry_size(geometry: str) -> tuple[int | None, int | None]:
    try:
        size_token = geometry.split("+", 1)[0]
        width_text, height_text = size_token.split("x", 1)
        return int(width_text), int(height_text)
    except ValueError:
        return None, None


def enable_large_window(
    window,
    min_width: int,
    min_height: int,
    start_zoomed: bool = True,
):
    screen_width = max(1, int(window.winfo_screenwidth()))
    screen_height = max(1, int(window.winfo_screenheight()))
    preferred_width, preferred_height = _parse_geometry_size(window.geometry())

    usable_width = max(480, screen_width - 80)
    usable_height = max(520, screen_height - 96)
    target_width = min(preferred_width or usable_width, usable_width)
    target_height = min(preferred_height or usable_height, usable_height)
    target_x = max(16, (screen_width - target_width) // 2)
    target_y = max(16, (screen_height - target_height) // 2 - 20)

    window.geometry(f"{target_width}x{target_height}+{target_x}+{target_y}")
    window.minsize(
        min(min_width, usable_width),
        min(min_height, usable_height),
    )
    try:
        window.resizable(True, True)
    except TclError:
        pass

    should_zoom = (
        start_zoomed
        and preferred_width is not None
        and preferred_height is not None
        and screen_width >= preferred_width + 120
        and screen_height >= preferred_height + 120
    )

    if not should_zoom:
        return

    def _zoom():
        try:
            window.state("zoomed")
        except TclError:
            try:
                window.attributes("-zoomed", True)
            except TclError:
                pass

    try:
        window.after(40, _zoom)
    except TclError:
        pass


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def make_ui_placeholder_image(
    size: tuple[int, int],
    label: str = "asset",
) -> Image.Image:
    width, height = size
    image = Image.new(
        "RGBA",
        size,
        _hex_to_rgb(PALETTE["panel_soft"]) + (255,),
    )
    draw = ImageDraw.Draw(image)
    border = _hex_to_rgb(PALETTE["border_strong"]) + (255,)
    accent = _hex_to_rgb(PALETTE["gold"]) + (255,)
    draw.rounded_rectangle(
        (2, 2, width - 3, height - 3),
        radius=16,
        outline=border,
        width=3,
    )
    draw.line((14, 14, width - 14, height - 14), fill=accent, width=2)
    draw.line((width - 14, 14, 14, height - 14), fill=accent, width=2)
    draw.text(
        (16, max(12, height - 30)),
        label[:20],
        fill=_hex_to_rgb(PALETTE["text"]) + (255,),
    )
    return image


def load_ctk_image(
    *parts: str,
    size: tuple[int, int],
    fallback_label: str | None = None,
    brightness: float = 1.0,
    blur_radius: float = 0.0,
    remove_edge_dark_regions: bool = False,
    crop_to_visible_bounds: bool = False,
) -> ctk.CTkImage:
    image_path = Path(resource_path(*parts))
    try:
        image = Image.open(image_path).convert("RGBA")
    except (FileNotFoundError, OSError):
        image = make_ui_placeholder_image(
            size,
            fallback_label or image_path.stem or "asset",
        )

    if remove_edge_dark_regions:
        image = _remove_edge_connected_dark_regions(image)
    if crop_to_visible_bounds:
        image = _crop_to_visible_bounds(image)
    if brightness != 1.0:
        image = ImageEnhance.Brightness(image).enhance(brightness)
    if blur_radius > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    return ctk.CTkImage(light_image=image, dark_image=image, size=size)


def load_launcher_background_image(
    *parts: str,
    size: tuple[int, int],
    fallback_label: str | None = None,
) -> ctk.CTkImage:
    image_path = Path(resource_path(*parts))
    image = _load_rgba_asset(
        image_path,
        size=size,
        fallback_label=fallback_label,
    )
    image = _fit_image_to_cover(image, size)
    image = _add_launcher_side_glow(image)
    image = _lift_dark_regions(
        image,
        threshold=64,
        strength=0.62,
        target_color=(28, 58, 108),
    )
    image = ImageEnhance.Brightness(image).enhance(1.12)
    image = ImageEnhance.Color(image).enhance(1.12)
    image = image.filter(ImageFilter.GaussianBlur(radius=8))
    return ctk.CTkImage(light_image=image, dark_image=image, size=size)


def _load_rgba_asset(
    image_path: Path,
    *,
    size: tuple[int, int],
    fallback_label: str | None = None,
) -> Image.Image:
    try:
        return Image.open(image_path).convert("RGBA")
    except (FileNotFoundError, OSError):
        return make_ui_placeholder_image(
            size,
            fallback_label or image_path.stem or "asset",
        )


def _fit_image_to_cover(
    image: Image.Image,
    size: tuple[int, int],
) -> Image.Image:
    return ImageOps.fit(
        image,
        size,
        method=Image.LANCZOS,
        centering=(0.5, 0.5),
    )


def _add_launcher_side_glow(image: Image.Image) -> Image.Image:
    width, height = image.size
    ambient = Image.new("RGBA", image.size, (22, 48, 86, 48))
    draw = ImageDraw.Draw(ambient)
    draw.ellipse(
        (
            int(-0.10 * width),
            0,
            int(0.42 * width),
            int(1.05 * height),
        ),
        fill=(42, 96, 170, 90),
    )
    draw.ellipse(
        (
            int(0.58 * width),
            0,
            int(1.10 * width),
            int(1.05 * height),
        ),
        fill=(38, 92, 164, 82),
    )
    draw.ellipse(
        (
            int(0.18 * width),
            int(-0.15 * height),
            int(0.82 * width),
            int(0.55 * height),
        ),
        fill=(18, 54, 110, 40),
    )
    ambient = ambient.filter(ImageFilter.GaussianBlur(radius=110))
    return Image.alpha_composite(image, ambient)


def _lift_dark_regions(
    image: Image.Image,
    *,
    threshold: float,
    strength: float,
    target_color: tuple[int, int, int],
) -> Image.Image:
    processed_image = image.copy()
    pixels = processed_image.load()
    if pixels is None:
        return processed_image

    width, height = processed_image.size
    target_red, target_green, target_blue = target_color
    for x_pos in range(width):
        for y_pos in range(height):
            red, green, blue, alpha = cast(
                tuple[int, int, int, int],
                pixels[x_pos, y_pos],
            )
            if alpha <= 0:
                continue

            luminance = (
                0.2126 * red
                + 0.7152 * green
                + 0.0722 * blue
            )
            if luminance >= threshold:
                continue

            blend_strength = (threshold - luminance) / threshold * strength
            pixels[x_pos, y_pos] = (
                round(red * (1 - blend_strength) + target_red * blend_strength),
                round(
                    green * (1 - blend_strength)
                    + target_green * blend_strength
                ),
                round(blue * (1 - blend_strength) + target_blue * blend_strength),
                alpha,
            )

    return processed_image


def _remove_edge_connected_dark_regions(image: Image.Image) -> Image.Image:
    processed_image = image.copy()
    pixels = processed_image.load()
    if pixels is None:
        return processed_image
    width, height = processed_image.size
    pending_pixels: deque[tuple[int, int]] = deque()
    visited_pixels: set[tuple[int, int]] = set()

    for x_pos in range(width):
        pending_pixels.append((x_pos, 0))
        pending_pixels.append((x_pos, height - 1))
    for y_pos in range(1, height - 1):
        pending_pixels.append((0, y_pos))
        pending_pixels.append((width - 1, y_pos))

    while pending_pixels:
        x_pos, y_pos = pending_pixels.popleft()
        if (x_pos, y_pos) in visited_pixels:
            continue
        visited_pixels.add((x_pos, y_pos))

        pixel_value = cast(tuple[int, int, int, int], pixels[x_pos, y_pos])
        red, green, blue, alpha = pixel_value
        if not _is_edge_dark_pixel(red, green, blue, alpha):
            continue

        pixels[x_pos, y_pos] = (red, green, blue, 0)
        for x_offset in (-1, 0, 1):
            for y_offset in (-1, 0, 1):
                if x_offset == 0 and y_offset == 0:
                    continue
                next_x = x_pos + x_offset
                next_y = y_pos + y_offset
                if 0 <= next_x < width and 0 <= next_y < height:
                    pending_pixels.append((next_x, next_y))

    return processed_image


def _is_edge_dark_pixel(red: int, green: int, blue: int, alpha: int) -> bool:
    if alpha <= 0:
        return False
    return red <= 14 and green <= 20 and blue <= 42


def _crop_to_visible_bounds(image: Image.Image) -> Image.Image:
    visible_bounds = image.getbbox()
    if visible_bounds is None:
        return image
    return image.crop(visible_bounds)


# --- Tokens HUD / layout utilitaires (Pygame) ---

# Dimensions des composants HUD
UI = {
    "button_min_size": 44,
    "button_radius": 8,
    "hud_timer_size": 56,
    "hud_icon_size": 56,
    "portrait_size": 64,
    "gutter": 12,
}


def _srgb_channel_to_linear(c: float) -> float:
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    """Luminance relative WCAG (0..1) d'une couleur hex."""
    r, g, b = _hex_to_rgb(hex_color)
    rs, gs, bs = r / 255.0, g / 255.0, b / 255.0
    rl, gl, bl = (
        _srgb_channel_to_linear(rs),
        _srgb_channel_to_linear(gs),
        _srgb_channel_to_linear(bs),
    )
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Ratio de contraste WCAG entre deux couleurs."""
    la, lb = luminance(hex_a), luminance(hex_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(bg_hex: str) -> str:
    """Retourne la couleur de texte la plus lisible sur bg_hex."""
    white = PALETTE["text"]
    dark = PALETTE["bg"]
    if contrast_ratio(bg_hex, white) >= contrast_ratio(bg_hex, dark):
        return white
    return dark
