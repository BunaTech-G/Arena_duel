import customtkinter as ctk
from pathlib import Path

from PIL import Image, ImageDraw

from runtime_utils import resource_path


PALETTE = {
    "bg": "#0f131a",
    "bg_alt": "#131924",
    "panel": "#1a2130",
    "panel_alt": "#212a3b",
    "panel_soft": "#161d29",
    "surface": "#273246",
    "border": "#32435e",
    "border_strong": "#4a6387",
    "text": "#f5efdf",
    "text_muted": "#d1dbed",
    "text_soft": "#a3aec4",
    "gold": "#f3c96b",
    "gold_hover": "#ffda88",
    "gold_dim": "#9d7c37",
    "cyan": "#64d7ff",
    "cyan_hover": "#91e3ff",
    "cyan_dim": "#2d758e",
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
}


BADGE_VARIANTS = {
    "neutral": (PALETTE["neutral_dim"], PALETTE["neutral"], PALETTE["text_muted"]),
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


def create_button(master, text, command, variant="primary", width=220, height=46, font=None, **kwargs):
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


def create_badge(master, text, tone="neutral"):
    fg_color, border_color, text_color = BADGE_VARIANTS[tone]
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


def _parse_geometry_size(geometry: str) -> tuple[int | None, int | None]:
    try:
        size_token = geometry.split("+", 1)[0]
        width_text, height_text = size_token.split("x", 1)
        return int(width_text), int(height_text)
    except Exception:
        return None, None


def enable_large_window(window, min_width: int, min_height: int, start_zoomed: bool = True):
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
    window.minsize(min(min_width, usable_width), min(min_height, usable_height))
    try:
        window.resizable(True, True)
    except Exception:
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
        except Exception:
            try:
                window.attributes("-zoomed", True)
            except Exception:
                pass

    try:
        window.after(40, _zoom)
    except Exception:
        pass


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def make_ui_placeholder_image(size: tuple[int, int], label: str = "asset") -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, _hex_to_rgb(PALETTE["panel_soft"]) + (255,))
    draw = ImageDraw.Draw(image)
    border = _hex_to_rgb(PALETTE["border_strong"]) + (255,)
    accent = _hex_to_rgb(PALETTE["gold"]) + (255,)
    draw.rounded_rectangle((2, 2, width - 3, height - 3), radius=16, outline=border, width=3)
    draw.line((14, 14, width - 14, height - 14), fill=accent, width=2)
    draw.line((width - 14, 14, 14, height - 14), fill=accent, width=2)
    draw.text((16, max(12, height - 30)), label[:20], fill=_hex_to_rgb(PALETTE["text"]) + (255,))
    return image


def load_ctk_image(*parts: str, size: tuple[int, int], fallback_label: str | None = None) -> ctk.CTkImage:
    image_path = Path(resource_path(*parts))
    try:
        image = Image.open(image_path).convert("RGBA")
    except Exception:
        image = make_ui_placeholder_image(size, fallback_label or image_path.stem or "asset")
    return ctk.CTkImage(light_image=image, dark_image=image, size=size)