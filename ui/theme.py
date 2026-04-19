from collections import deque
import customtkinter as ctk
from pathlib import Path
from tkinter import PhotoImage, TclError
from typing import cast

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from runtime_utils import get_app_icon_ico_path, get_app_icon_png_path, resource_path


PALETTE = {
    "bg": "#0f131a",
    "bg_alt": "#131924",
    "bg_glow": "#182233",
    "launcher_blend": "#152949",
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


RESAMPLING_LANCZOS = getattr(
    getattr(Image, "Resampling", Image),
    "LANCZOS",
)


TYPOGRAPHY = {
    "display": ("Palatino Linotype", 44, "bold"),
    "title": ("Palatino Linotype", 34, "bold"),
    "section": ("Palatino Linotype", 26, "bold"),
    "subtitle": ("Segoe UI Semibold", 18),
    "body": ("Segoe UI", 16),
    "body_bold": ("Segoe UI Semibold", 16),
    "small": ("Segoe UI", 14),
    "small_bold": ("Segoe UI Semibold", 14),
    "button": ("Segoe UI Semibold", 16),
    "button_small": ("Segoe UI Semibold", 14),
    "stat": ("Palatino Linotype", 24, "bold"),
}


WINDOW_ICON_PNG_SIZES = (256, 64, 32, 16)
LAUNCHER_BACKGROUND_WORKING_MAX_SIZE = (960, 540)

RESPONSIVE_BASELINE_SIZE = (1440, 900)
RESPONSIVE_MIN_SCALE = 0.84
_RESPONSIVE_STATE = {"last_scale": 1.0}
_CTK_IMAGE_CACHE = {}
_APP_ICON_IMAGE_CACHE = {}
_LAUNCHER_BACKGROUND_IMAGE_CACHE = {}


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


def apply_responsive_scaling(screen_width: int, screen_height: int) -> float:
    base_width, base_height = RESPONSIVE_BASELINE_SIZE
    width_ratio = screen_width / max(1, base_width)
    height_ratio = screen_height / max(1, base_height)

    if width_ratio >= 1.0 and height_ratio >= 1.0:
        target_scale = 1.0
    else:
        target_scale = max(
            RESPONSIVE_MIN_SCALE,
            min(1.0, min(width_ratio, height_ratio) * 0.98),
        )

    last_scale = float(_RESPONSIVE_STATE["last_scale"])
    if abs(target_scale - last_scale) < 0.01:
        return last_scale

    ctk.set_widget_scaling(target_scale)
    ctk.set_window_scaling(target_scale)
    _RESPONSIVE_STATE["last_scale"] = target_scale
    return target_scale


def _resolve_theme_color(color_value):
    if isinstance(color_value, (list, tuple)):
        for candidate in reversed(tuple(color_value)):
            resolved_color = _resolve_theme_color(candidate)
            if resolved_color is not None:
                return resolved_color
        return None

    if color_value is None:
        return None

    color_text = str(color_value).strip()
    if not color_text or color_text.lower() == "transparent":
        return None
    return color_text


def resolve_widget_bg_color(widget, fallback: str | None = None) -> str:
    current_widget = widget
    fallback_color = fallback or PALETTE["bg"]

    while current_widget is not None:
        for attribute_name in ("fg_color", "bg_color"):
            try:
                attribute_value = current_widget.cget(attribute_name)
            except (AttributeError, TclError):
                continue

            resolved_color = _resolve_theme_color(attribute_value)
            if resolved_color is not None:
                return resolved_color

        current_widget = getattr(current_widget, "master", None)

    return fallback_color


def style_window(window):
    window.configure(fg_color=PALETTE["bg"])


def _apply_window_icon_once(window, *, default: bool = False):
    icon_path = Path(get_app_icon_ico_path())
    if icon_path.exists():
        try:
            window.iconbitmap(str(icon_path))
        except (OSError, TclError):
            pass

    icon_images = []
    seen_paths = set()
    for preferred_size in WINDOW_ICON_PNG_SIZES:
        png_path = Path(get_app_icon_png_path(preferred_size))
        if not png_path.exists():
            continue

        normalized_path = str(png_path.resolve())
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)

        try:
            icon_images.append(PhotoImage(master=window, file=str(png_path)))
        except TclError:
            pass

    if not icon_images:
        return

    try:
        window.iconphoto(default, *icon_images)
        window._arena_window_icon_images = icon_images
    except TclError:
        pass


def apply_window_icon(window, *, default: bool = False, retry_after_ms: int = 0):
    _apply_window_icon_once(window, default=default)

    if retry_after_ms <= 0:
        return

    def _retry():
        try:
            if not window.winfo_exists():
                return
        except TclError:
            return

        _apply_window_icon_once(window, default=default)

    try:
        window.after(retry_after_ms, _retry)
    except TclError:
        pass


def style_frame(frame, tone="panel", border_color=None, border_width=0):
    frame.configure(
        bg_color=resolve_widget_bg_color(getattr(frame, "master", None)),
        fg_color=PALETTE.get(tone, PALETTE["panel"]),
        border_width=border_width,
        border_color=border_color or PALETTE["border"],
    )


def style_textbox(textbox, tone="panel_soft"):
    textbox.configure(
        bg_color=resolve_widget_bg_color(getattr(textbox, "master", None)),
        fg_color=PALETTE.get(tone, PALETTE["panel_soft"]),
        border_width=1,
        border_color=PALETTE["divider"],
        text_color=PALETTE["text"],
        font=TYPOGRAPHY["body"],
    )


def style_entry(entry, tone="panel_soft"):
    entry.configure(
        bg_color=resolve_widget_bg_color(getattr(entry, "master", None)),
        fg_color=PALETTE.get(tone, PALETTE["panel_soft"]),
        border_color=PALETTE["border"],
        text_color=PALETTE["text"],
        font=TYPOGRAPHY["body"],
    )


def style_combobox(combo, tone="panel_soft"):
    combo.configure(
        bg_color=resolve_widget_bg_color(getattr(combo, "master", None)),
        fg_color=PALETTE.get(tone, PALETTE["panel_soft"]),
        border_color=PALETTE["border"],
        button_color=PALETTE["surface"],
        button_hover_color=PALETTE["border_strong"],
        text_color=PALETTE["text"],
    )


def style_checkbox(checkbox):
    checkbox.configure(
        bg_color=resolve_widget_bg_color(getattr(checkbox, "master", None)),
        text_color=PALETTE["text"],
    )


def style_scrollable_frame(
    scrollable_frame,
    *,
    tone="panel_soft",
    border_color=None,
    border_width=0,
):
    scrollable_frame.configure(
        bg_color=resolve_widget_bg_color(getattr(scrollable_frame, "master", None)),
        fg_color=PALETTE.get(tone, PALETTE["panel_soft"]),
        border_color=border_color or PALETTE["divider"],
        border_width=border_width,
        scrollbar_button_color=PALETTE["surface"],
        scrollbar_button_hover_color=PALETTE["border_strong"],
    )


def style_tabview(tabview, tone="panel_soft", border_color=None):
    tabview.configure(
        bg_color=resolve_widget_bg_color(getattr(tabview, "master", None)),
        fg_color=PALETTE.get(tone, PALETTE["panel_soft"]),
        border_color=border_color or PALETTE["divider"],
        segmented_button_fg_color=PALETTE["panel_deep"],
        segmented_button_selected_color=PALETTE["gold_dim"],
        segmented_button_selected_hover_color=PALETTE["gold"],
        segmented_button_unselected_color=PALETTE["panel"],
        segmented_button_unselected_hover_color=PALETTE["panel_highlight"],
        text_color=PALETTE["text"],
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
    bg_color = kwargs.pop("bg_color", None)
    if _resolve_theme_color(bg_color) is None:
        bg_color = resolve_widget_bg_color(master)

    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=14,
        font=font or TYPOGRAPHY["button"],
        bg_color=bg_color,
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
    bg_color = kwargs.pop("bg_color", None)
    if _resolve_theme_color(bg_color) is None:
        bg_color = resolve_widget_bg_color(master)

    return ctk.CTkOptionMenu(
        master,
        values=values,
        command=command,
        variable=variable,
        width=width,
        height=height,
        corner_radius=14,
        bg_color=bg_color,
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
        bg_color=resolve_widget_bg_color(master),
        fg_color=fg_color,
        text_color=text_color,
        font=TYPOGRAPHY["small_bold"],
        padx=12,
        pady=6,
    )


def style_image_label(label):
    label.configure(
        fg_color="transparent",
        bg_color=resolve_widget_bg_color(getattr(label, "master", None)),
    )


def update_badge(badge, text, tone="neutral"):
    fg_color, _, text_color = BADGE_VARIANTS[tone]
    badge.configure(text=text, fg_color=fg_color, text_color=text_color)


def present_window(window, *, clear_topmost_after_ms: int = 180):
    def _restore_zoom_state():
        if not bool(getattr(window, "_arena_should_zoom", False)):
            return

        try:
            window.state("zoomed")
        except TclError:
            try:
                window.attributes("-zoomed", True)
            except TclError:
                pass

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

        _restore_zoom_state()

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
    responsive_scale = apply_responsive_scaling(screen_width, screen_height)
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
        and responsive_scale >= 0.98
        and preferred_width is not None
        and preferred_height is not None
        and screen_width >= preferred_width + 120
        and screen_height >= preferred_height + 120
    )

    if not should_zoom:
        try:
            window._arena_should_zoom = False
        except AttributeError:
            pass
        return

    try:
        window._arena_should_zoom = True
    except AttributeError:
        pass

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
    cache_key = (
        str(image_path),
        tuple(size),
        fallback_label,
        float(brightness),
        float(blur_radius),
        bool(remove_edge_dark_regions),
        bool(crop_to_visible_bounds),
    )
    cached_image = _CTK_IMAGE_CACHE.get(cache_key)
    if cached_image is not None:
        return cached_image

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

    ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
    _CTK_IMAGE_CACHE[cache_key] = ctk_image
    return ctk_image


def load_app_icon_image(
    size: tuple[int, int] | int,
    *,
    fallback_label: str = "arena duel",
) -> ctk.CTkImage:
    if isinstance(size, int):
        target_size = (size, size)
    else:
        target_size = size

    cache_key = (tuple(target_size), fallback_label)
    cached_image = _APP_ICON_IMAGE_CACHE.get(cache_key)
    if cached_image is not None:
        return cached_image

    requested_size = max(target_size)
    icon_path = Path(get_app_icon_png_path(requested_size))
    try:
        image = Image.open(icon_path).convert("RGBA")
    except (FileNotFoundError, OSError):
        return load_ctk_image(
            "assets",
            "icons",
            "icon_preview_256.png",
            size=target_size,
            fallback_label=fallback_label,
        )

    ctk_image = ctk.CTkImage(
        light_image=image,
        dark_image=image,
        size=target_size,
    )
    _APP_ICON_IMAGE_CACHE[cache_key] = ctk_image
    return ctk_image


def load_launcher_background_image(
    *parts: str,
    size: tuple[int, int],
    fallback_label: str | None = None,
) -> ctk.CTkImage:
    image_path = Path(resource_path(*parts))
    cache_key = (str(image_path), tuple(size), fallback_label)
    cached_image = _LAUNCHER_BACKGROUND_IMAGE_CACHE.get(cache_key)
    if cached_image is not None:
        return cached_image

    working_size = _get_launcher_background_working_size(size)

    image = _load_rgba_asset(
        image_path,
        size=working_size,
        fallback_label=fallback_label,
    )
    image = _fit_image_to_cover(image, working_size)
    image = _lift_dark_regions(
        image,
        threshold=64,
        strength=0.44,
        target_color=(30, 56, 102),
    )
    blur_scale = min(
        working_size[0] / max(size[0], 1),
        working_size[1] / max(size[1], 1),
    )
    image = image.filter(
        ImageFilter.GaussianBlur(radius=max(1, round(14 * blur_scale)))
    )
    image = Image.alpha_composite(
        image,
        Image.new("RGBA", image.size, (18, 34, 62, 88)),
    )
    image = ImageEnhance.Brightness(image).enhance(0.92)
    image = ImageEnhance.Color(image).enhance(0.82)

    if working_size != size:
        image = image.resize(size, RESAMPLING_LANCZOS)

    ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
    _LAUNCHER_BACKGROUND_IMAGE_CACHE[cache_key] = ctk_image
    return ctk_image


def _get_launcher_background_working_size(
    size: tuple[int, int],
) -> tuple[int, int]:
    width, height = size
    max_width, max_height = LAUNCHER_BACKGROUND_WORKING_MAX_SIZE

    if width <= max_width and height <= max_height:
        return size

    scale = min(max_width / width, max_height / height)
    return (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )


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
        method=RESAMPLING_LANCZOS,
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

            pixel_luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            if pixel_luminance >= threshold:
                continue

            blend_strength = (threshold - pixel_luminance) / threshold * strength
            pixels[x_pos, y_pos] = (
                round(red * (1 - blend_strength) + target_red * blend_strength),
                round(green * (1 - blend_strength) + target_green * blend_strength),
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
