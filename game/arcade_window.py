from __future__ import annotations

from pathlib import Path

import arcade
import pygame
from arcade.types.color import Color as ArcadeColor

from game.asset_pipeline import (
    asset_path,
    load_background_manifest,
    load_sprite_manifest,
)
from hardware.service import create_match_hardware_service
from game.audio import init_audio, play_draw, play_lose, play_pickup, play_win
from game.audio import start_match_music, stop_music
from game.control_models import (
    AI_CONTROL_MODE,
    HUMAN_CONTROL_MODE,
    MovementIntent,
)
from game.game_window import (
    build_result,
    build_runtime_players,
    get_local_focus_team,
    get_team_scores,
)
from game.match_text import (
    format_scoreline,
    format_winner_text,
    get_team_label,
    get_winner_team,
)
from game.orb import Orb
from game.settings import (
    FPS,
    MATCH_DURATION_SECONDS,
    ORB_COMBO_WINDOW_MS,
    ORB_SPAWN_COUNT,
    coerce_match_duration,
)
from game.arena import get_arena_rect, get_map_layout, get_obstacles
from game.traps import (
    TRAP_TRANSITION_MS,
    build_match_traps,
    update_match_traps,
)


pg_init = getattr(pygame, "init", lambda: None)
pg_quit = getattr(pygame, "quit", lambda: None)


WINDOW_TITLE = "Arena Duel - Joute locale Arcade"
WINDOW_BACKGROUND_ASSET = "arena_darkstone"
ARENA_FLOOR_ASSET = "forgotten_sanctum_floor"
BACKGROUND_TOP = (18, 25, 35)
BACKGROUND_BOTTOM = (10, 13, 19)
ARENA_FILL = (44, 40, 35)
ARENA_EDGE = (148, 138, 122)
OBSTACLE_FILL = (88, 82, 76)
OBSTACLE_EDGE = (176, 167, 150)
HUD_PANEL = (18, 21, 30, 220)
HUD_BORDER = (90, 108, 136)
OVERLAY_FILL = (10, 12, 18, 220)
OVERLAY_PANEL = (32, 36, 44, 240)
OVERLAY_BORDER = (106, 122, 160)
TEXT_PRIMARY = (245, 243, 236, 255)
TEXT_MUTED = (198, 206, 219, 255)
TEAM_A_ACCENT = (243, 201, 107, 255)
TEAM_B_ACCENT = (100, 215, 255, 255)
ORB_COMMON = (241, 196, 15, 255)
ORB_RARE = (151, 104, 255, 255)
TEXTURE_WHITE = (255, 255, 255, 255)
TRAP_COLORS = {
    "spike_trap": (214, 146, 112, 235),
    "ember_trap": (231, 151, 92, 235),
    "rune_trap": (122, 201, 194, 235),
}
HUD_PANEL_DEEP = (10, 14, 22, 220)
HUD_PANEL_SOFT = (8, 12, 20, 200)
HUD_ROW_FILL = (14, 20, 32, 210)
HUD_BADGE_FILL = (18, 26, 42, 230)
HUD_TRACK = (26, 36, 52, 255)
NAME_PANEL_FILL = (16, 19, 28, 210)
NAME_PANEL_BORDER = (52, 68, 98, 255)
TIMER_OK = (100, 210, 255, 255)
TIMER_WARN = (255, 185, 55, 255)
TIMER_URG = (255, 65, 65, 255)
SCORE_PANEL_HEIGHT = 78
ROSTER_ROW_HEIGHT = 44
SPRITE_ANIMATION_FRAME_MS = 140
CONTROL_NAME_BY_KEY = {
    "z": ("Z",),
    "q": ("Q",),
    "s": ("S",),
    "d": ("D",),
    "w": ("W",),
    "a": ("A",),
    "x": ("X",),
    "c": ("C",),
    "t": ("T",),
    "f": ("F",),
    "g": ("G",),
    "h": ("H",),
    "i": ("I",),
    "j": ("J",),
    "k": ("K",),
    "l": ("L",),
    "up": ("UP",),
    "down": ("DOWN",),
    "left": ("LEFT",),
    "right": ("RIGHT",),
    "kp8": ("NUM_8", "NUMPAD8", "KEY_8"),
    "kp5": ("NUM_5", "NUMPAD5", "KEY_5"),
    "kp4": ("NUM_4", "NUMPAD4", "KEY_4"),
    "kp6": ("NUM_6", "NUMPAD6", "KEY_6"),
}
_TEXTURE_CACHE: dict[tuple[str, bool], arcade.Texture] = {}
_BACKGROUND_TEXTURE_PATH_CACHE: dict[str, Path | None] = {}
_SPRITE_FRAME_SPEC_CACHE: dict[tuple[str, str], tuple[Path | None, bool]] = {}
_SPRITE_ANIMATION_SPEC_CACHE: dict[tuple[str, str], tuple[Path, ...]] = {}


def _coerce_arcade_color(color_value) -> ArcadeColor:
    if isinstance(color_value, ArcadeColor):
        return color_value
    return ArcadeColor(*color_value)


def _load_texture_from_path(
    path: Path,
    *,
    mirrored: bool = False,
) -> arcade.Texture | None:
    resolved_path = path.resolve()
    if not resolved_path.exists():
        return None

    cache_key = (str(resolved_path), mirrored)
    cached_texture = _TEXTURE_CACHE.get(cache_key)
    if cached_texture is not None:
        return cached_texture

    texture = arcade.load_texture(resolved_path)
    if mirrored:
        texture = texture.flip_left_right()

    _TEXTURE_CACHE[cache_key] = texture
    return texture


def _resolve_background_texture_path(background_id: str) -> Path | None:
    if background_id in _BACKGROUND_TEXTURE_PATH_CACHE:
        return _BACKGROUND_TEXTURE_PATH_CACHE[background_id]

    background_manifest = load_background_manifest()
    background_entry = background_manifest.get("assets", {}).get(
        background_id,
        {},
    )
    file_name = background_entry.get("file")
    if not file_name:
        _BACKGROUND_TEXTURE_PATH_CACHE[background_id] = None
        return None

    resolved_path = asset_path("backgrounds", file_name)
    _BACKGROUND_TEXTURE_PATH_CACHE[background_id] = resolved_path
    return resolved_path


def _load_background_texture(background_id: str) -> arcade.Texture | None:
    background_path = _resolve_background_texture_path(background_id)
    if background_path is None:
        return None
    return _load_texture_from_path(background_path)


def _resolve_sprite_frame_path(
    sprite_id: str,
    direction_name: str,
) -> tuple[Path | None, bool]:
    cache_key = (sprite_id, direction_name)
    cached_spec = _SPRITE_FRAME_SPEC_CACHE.get(cache_key)
    if cached_spec is not None:
        return cached_spec

    sprite_manifest = load_sprite_manifest(sprite_id)
    directional_frames = sprite_manifest.get("directional_frames", {})
    frame_ref = directional_frames.get(direction_name)
    mirrored = False

    if frame_ref is None and direction_name == "left":
        frame_ref = directional_frames.get("right")
        mirrored = frame_ref is not None
    elif frame_ref is None and direction_name == "right":
        frame_ref = directional_frames.get("left")
        mirrored = frame_ref is not None

    if frame_ref is None:
        animation_frames = (
            sprite_manifest.get("animations", {}).get("idle")
            or sprite_manifest.get("animations", {}).get("walk")
            or []
        )
        if not animation_frames:
            _SPRITE_FRAME_SPEC_CACHE[cache_key] = (None, False)
            return None, False
        frame_ref = animation_frames[0]
        mirrored = direction_name == "left"

    resolved_spec = (asset_path("sprites", sprite_id, frame_ref), mirrored)
    _SPRITE_FRAME_SPEC_CACHE[cache_key] = resolved_spec
    return resolved_spec


def _resolve_sprite_animation_frame_paths(
    sprite_id: str,
    animation_name: str,
) -> tuple[Path, ...]:
    cache_key = (sprite_id, animation_name)
    cached_paths = _SPRITE_ANIMATION_SPEC_CACHE.get(cache_key)
    if cached_paths is not None:
        return cached_paths

    sprite_manifest = load_sprite_manifest(sprite_id)
    frame_names = tuple(sprite_manifest.get("animations", {}).get(animation_name, []))
    resolved_paths = tuple(
        asset_path("sprites", sprite_id, frame_name) for frame_name in frame_names
    )
    _SPRITE_ANIMATION_SPEC_CACHE[cache_key] = resolved_paths
    return resolved_paths


def _resolve_player_frame_spec(
    sprite_id: str,
    direction_name: str,
    *,
    elapsed_ms: float | None = None,
    is_moving: bool = False,
) -> tuple[Path | None, bool]:
    if elapsed_ms is None:
        return _resolve_sprite_frame_path(sprite_id, direction_name)

    animation_name = "walk" if is_moving else "idle"
    animation_paths = _resolve_sprite_animation_frame_paths(
        sprite_id,
        animation_name,
    )
    if animation_paths:
        frame_index = int(max(0.0, float(elapsed_ms)) // SPRITE_ANIMATION_FRAME_MS)
        mirrored = direction_name == "left"
        return animation_paths[frame_index % len(animation_paths)], mirrored

    return _resolve_sprite_frame_path(sprite_id, direction_name)


def _load_player_texture(
    sprite_id: str,
    direction_name: str,
    *,
    elapsed_ms: float | None = None,
    is_moving: bool = False,
) -> arcade.Texture | None:
    texture_path, mirrored = _resolve_player_frame_spec(
        sprite_id,
        direction_name,
        elapsed_ms=elapsed_ms,
        is_moving=is_moving,
    )
    if texture_path is None:
        return None
    return _load_texture_from_path(texture_path, mirrored=mirrored)


def _load_orb_texture() -> arcade.Texture | None:
    for candidate_path in (
        asset_path("collectibles", "jetons.png"),
        asset_path("ui", "jetons.png"),
        asset_path("images", "jetons.png"),
    ):
        texture = _load_texture_from_path(candidate_path)
        if texture is not None:
            return texture
    return None


def _resolve_arcade_key(control_name: str) -> int | None:
    fallback_names = CONTROL_NAME_BY_KEY.get(
        control_name,
        (control_name.upper(),),
    )
    for constant_name in fallback_names:
        constant_value = getattr(arcade.key, constant_name, None)
        if constant_value is not None:
            return int(constant_value)
    return None


def _trim_display_name(name: str, max_chars: int = 14) -> str:
    clean_name = str(name or "").strip()
    if len(clean_name) <= max_chars:
        return clean_name
    return clean_name[: max_chars - 3] + "..."


def _format_timer_value(remaining_seconds: int) -> str:
    safe_seconds = max(0, int(remaining_seconds))
    minutes, seconds = divmod(safe_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _resolve_timer_color(remaining_seconds: int):
    if remaining_seconds <= 10:
        return TIMER_URG
    if remaining_seconds <= 30:
        return TIMER_WARN
    return TIMER_OK


def _resolve_local_team_rows(players, team_code: str) -> list[dict]:
    rows = []
    for player in players:
        if getattr(player, "team_code", None) != team_code:
            continue

        sprite_id = getattr(player, "sprite_id", None)
        if not sprite_id:
            sprite_id = (
                "skeleton_fighter_ember"
                if team_code == "A"
                else "skeleton_fighter_aether"
            )

        rows.append(
            {
                "name": getattr(player, "name", "Combattant"),
                "score": int(getattr(player, "score", 0)),
                "accent_color": getattr(player, "color", TEAM_A_ACCENT),
                "sprite_id": sprite_id,
            }
        )
    return rows


def _resolve_combo_ratio(combo_remaining_ms: int) -> float:
    return max(
        0.0,
        min(1.0, float(combo_remaining_ms) / max(1, ORB_COMBO_WINDOW_MS)),
    )


def _resolve_trap_presence(trap_state, elapsed_ms: float) -> float:
    transition_elapsed_ms = max(
        0.0,
        float(elapsed_ms) - float(getattr(trap_state, "last_toggle_ms", 0.0)),
    )
    transition_progress = min(
        1.0,
        transition_elapsed_ms / max(1.0, TRAP_TRANSITION_MS),
    )
    if getattr(trap_state, "active", False):
        return transition_progress
    return max(0.0, 1.0 - transition_progress)


class ArcadeMatchWindow(arcade.Window):
    def __init__(
        self,
        players_config,
        match_duration_seconds=MATCH_DURATION_SECONDS,
    ):
        self.layout = get_map_layout()
        width, height = self.layout.window_size
        super().__init__(
            width=width,
            height=height,
            title=WINDOW_TITLE,
            resizable=False,
            update_rate=1 / FPS,
        )

        self.players_config = list(players_config)
        self.active_match_duration = coerce_match_duration(match_duration_seconds)
        self.arena_rect = get_arena_rect(self.layout)
        self.obstacles = get_obstacles(self.layout)
        self.hardware_service = create_match_hardware_service()
        self.pressed_keys: set[int] = set()
        self.control_bindings = self._build_control_bindings()
        self.players = []
        self.ai_controllers = {}
        self.orbs = []
        self.trap_states = []
        self.match_elapsed_ms = 0.0
        self.remaining_time = self.active_match_duration
        self.game_over = False
        self.winner_text = ""
        self.final_sound_played = False
        self.orb_effects = []
        self.result = None
        self._shutdown_complete = False
        self._should_reset_hardware = True
        self.window_background_texture = _load_background_texture(
            WINDOW_BACKGROUND_ASSET
        )
        self.floor_texture = _load_background_texture(ARENA_FLOOR_ASSET)
        self.orb_texture = _load_orb_texture()

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pg_init()
        init_audio()
        stop_music(fade_ms=0)
        self._start_new_match()

    def _build_control_bindings(self) -> dict[str, dict[str, int]]:
        from game.settings import PLAYER_SLOT_CONTROLS

        bindings: dict[str, dict[str, int]] = {}
        for player_data in self.players_config:
            control_mode = str(
                player_data.get("control_mode", HUMAN_CONTROL_MODE)
            ).lower()
            if control_mode != HUMAN_CONTROL_MODE:
                continue

            slot_index = max(0, int(player_data.get("slot", 1)) - 1)
            if slot_index >= len(PLAYER_SLOT_CONTROLS):
                continue

            slot_controls = PLAYER_SLOT_CONTROLS[slot_index]
            player_bindings: dict[str, int] = {}
            for direction, control_name in slot_controls.items():
                arcade_key = _resolve_arcade_key(str(control_name))
                if arcade_key is not None:
                    player_bindings[direction] = arcade_key
            player_name = str(player_data.get("name", "")).strip()
            bindings[player_name] = player_bindings
        return bindings

    def _start_new_match(self) -> None:
        self.players, self.ai_controllers = build_runtime_players(
            self.players_config,
            self.layout,
        )
        self.orbs = [
            Orb(
                self.arena_rect,
                self.obstacles,
                layout=self.layout,
                elapsed_ms=0.0,
            )
            for _ in range(ORB_SPAWN_COUNT)
        ]
        self.trap_states = build_match_traps(self.layout)
        self.match_elapsed_ms = 0.0
        self.remaining_time = self.active_match_duration
        self.game_over = False
        self.winner_text = ""
        self.final_sound_played = False
        self.orb_effects = []
        self.pressed_keys.clear()
        self.hardware_service.reset()
        self.hardware_service.emit_state("COMBAT")
        self.hardware_service.emit_score(0, 0)
        start_match_music(restart=True)

    def _top_to_bottom(self, y: float, height: float = 0.0) -> float:
        return float(self.height) - float(y) - float(height)

    def _draw_top_text(
        self,
        text: str,
        x: float,
        y: float,
        color,
        size: int,
        *,
        anchor_x: str = "left",
        bold: bool = False,
    ) -> None:
        arcade.draw_text(
            text,
            x,
            float(self.height) - float(y),
            color,
            size,
            font_name=("Segoe UI", "Arial"),
            anchor_x=anchor_x,
            anchor_y="top",
            bold=bold,
        )

    def _draw_top_rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        color,
        *,
        outline_color=None,
        outline_width: int = 0,
    ) -> None:
        bottom = self._top_to_bottom(y, height)
        rect = arcade.LBWH(x, bottom, width, height)
        arcade.draw_rect_filled(rect, color)
        if outline_color is not None and outline_width > 0:
            arcade.draw_rect_outline(rect, outline_color, outline_width)

    def _draw_texture(
        self,
        texture: arcade.Texture | None,
        *,
        left: float,
        top: float,
        width: float,
        height: float,
        color=TEXTURE_WHITE,
    ) -> bool:
        if texture is None:
            return False

        rect = arcade.LBWH(
            left,
            self._top_to_bottom(top, height),
            width,
            height,
        )
        arcade.draw_texture_rect(
            texture,
            rect,
            color=_coerce_arcade_color(color),
        )
        return True

    def _draw_progress_bar(
        self,
        left: float,
        top: float,
        width: float,
        height: float,
        *,
        ratio: float,
        color,
    ) -> None:
        clamped_ratio = max(0.0, min(1.0, float(ratio)))
        self._draw_top_rect(left, top, width, height, HUD_TRACK)
        if clamped_ratio <= 0.0:
            return

        filled_width = max(height * 2, int(width * clamped_ratio))
        self._draw_top_rect(left, top, filled_width, height, color)

    def _draw_team_score_block(
        self,
        left: float,
        top: float,
        width: float,
        height: float,
        *,
        title: str,
        score: int,
        accent_color,
        align: str,
    ) -> None:
        self._draw_top_rect(
            left,
            top,
            width,
            height,
            HUD_PANEL_DEEP,
            outline_color=accent_color,
            outline_width=2,
        )
        stripe_left = left + 2 if align == "left" else left + width - 7
        self._draw_top_rect(
            stripe_left,
            top + 10,
            5,
            height - 20,
            accent_color,
        )

        title_x = left + 18 if align == "left" else left + width - 18
        self._draw_top_text(
            title,
            title_x,
            top + 8,
            TEXT_MUTED,
            13,
            anchor_x="left" if align == "left" else "right",
            bold=True,
        )
        self._draw_top_text(
            str(score),
            left + width / 2,
            top + 26,
            TEXT_PRIMARY,
            30,
            anchor_x="center",
            bold=True,
        )

    def _draw_team_summary_row(
        self,
        left: float,
        top: float,
        width: float,
        *,
        row: dict,
        align: str,
    ) -> None:
        accent_color = row.get("accent_color", TEAM_A_ACCENT)
        self._draw_top_rect(
            left,
            top,
            width,
            ROSTER_ROW_HEIGHT,
            HUD_ROW_FILL,
            outline_color=accent_color,
            outline_width=1,
        )

        stripe_left = left + 2 if align == "left" else left + width - 5
        self._draw_top_rect(
            stripe_left,
            top + 8,
            3,
            ROSTER_ROW_HEIGHT - 16,
            accent_color,
        )

        portrait_size = 30
        badge_width = 38
        badge_height = ROSTER_ROW_HEIGHT - 12
        portrait_direction = "right" if align == "left" else "left"
        portrait_texture = _load_player_texture(
            row.get("sprite_id", "skeleton_fighter_ember"),
            portrait_direction,
        )

        if align == "left":
            portrait_left = left + 9
            badge_left = left + width - badge_width - 9
            name_x = portrait_left + portrait_size + 12
            anchor_x = "left"
        else:
            badge_left = left + 9
            portrait_left = left + width - portrait_size - 9
            name_x = portrait_left - 12
            anchor_x = "right"

        badge_top = top + 6
        portrait_top = top + (ROSTER_ROW_HEIGHT - portrait_size) / 2
        available_name_width = max(
            48,
            int(width - portrait_size - badge_width - 42),
        )
        max_name_chars = max(8, min(18, available_name_width // 8))
        display_name = _trim_display_name(
            row.get("name", "Combattant"),
            max_chars=max_name_chars,
        )
        self._draw_top_rect(
            badge_left,
            badge_top,
            badge_width,
            badge_height,
            HUD_BADGE_FILL,
            outline_color=accent_color,
            outline_width=1,
        )
        self._draw_top_text(
            str(int(row.get("score", 0))),
            badge_left + badge_width / 2,
            badge_top + 8,
            TEXT_PRIMARY,
            12,
            anchor_x="center",
            bold=True,
        )

        if not self._draw_texture(
            portrait_texture,
            left=portrait_left,
            top=portrait_top,
            width=portrait_size,
            height=portrait_size,
        ):
            arcade.draw_circle_filled(
                portrait_left + portrait_size / 2,
                self.height - portrait_top - portrait_size / 2,
                portrait_size / 2,
                accent_color,
            )

        self._draw_top_text(
            display_name,
            name_x,
            top + 13,
            TEXT_PRIMARY,
            12,
            anchor_x=anchor_x,
            bold=True,
        )

    def _draw_team_summary_panel(
        self,
        left: float,
        top: float,
        *,
        title: str,
        rows: list[dict],
        accent_color,
        align: str,
        panel_width: float,
    ) -> None:
        header_height = 26
        row_count = max(1, len(rows))
        panel_height = header_height + row_count * ROSTER_ROW_HEIGHT + 8
        self._draw_top_rect(
            left,
            top,
            panel_width,
            panel_height,
            HUD_PANEL_SOFT,
            outline_color=accent_color,
            outline_width=1,
        )

        title_x = left + 12 if align == "left" else left + panel_width - 12
        self._draw_top_text(
            title,
            title_x,
            top + 6,
            TEXT_MUTED,
            12,
            anchor_x="left" if align == "left" else "right",
            bold=True,
        )

        if not rows:
            self._draw_top_text(
                "Aucun combattant",
                left + panel_width / 2,
                top + 44,
                TEXT_MUTED,
                12,
                anchor_x="center",
            )
            return

        for index, row in enumerate(rows):
            row_top = top + header_height + index * ROSTER_ROW_HEIGHT
            self._draw_team_summary_row(
                left + 6,
                row_top,
                panel_width - 12,
                row=row,
                align=align,
            )

    def _record_orb_effect(
        self,
        x: float,
        y: float,
        value: int,
        combo_bonus: int,
    ) -> None:
        if int(value) <= 0:
            return

        self.orb_effects.append(
            {
                "x": float(x),
                "y": float(y),
                "value": int(value),
                "combo_bonus": int(combo_bonus),
                "started_at_ms": self.match_elapsed_ms,
            }
        )

    def _draw_orb_effects(self) -> None:
        active_effects = []
        for effect in self.orb_effects:
            age_ms = self.match_elapsed_ms - float(effect["started_at_ms"])
            if age_ms >= 520:
                continue

            drift = age_ms / 18.0
            alpha = max(0, int(255 - age_ms / 2.2))
            effect_text = f"+{int(effect['value'])}"
            combo_bonus = int(effect.get("combo_bonus", 0))
            if combo_bonus > 0:
                effect_text += f"  combo +{combo_bonus}"
            self._draw_top_text(
                effect_text,
                float(effect["x"]),
                float(effect["y"]) - 20 - drift,
                (243, 201, 107, alpha),
                14,
                anchor_x="center",
                bold=True,
            )
            active_effects.append(effect)

        self.orb_effects = active_effects

    def _draw_vertical_gradient(self) -> None:
        if self._draw_texture(
            self.window_background_texture,
            left=0,
            top=0,
            width=self.width,
            height=self.height,
        ):
            self._draw_top_rect(
                0,
                0,
                self.width,
                self.height,
                (10, 14, 20, 96),
            )
            return

        band_height = 8
        for top in range(0, int(self.height), band_height):
            blend = top / max(1, int(self.height) - 1)
            color = tuple(
                int(start + (end - start) * blend)
                for start, end in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM)
            )
            self._draw_top_rect(0, top, self.width, band_height + 1, color)

    def _draw_arena(self, elapsed_ms: float) -> None:
        arena_left = self.arena_rect.left
        arena_top = self.arena_rect.top
        arena_width = self.arena_rect.width
        arena_height = self.arena_rect.height
        floor_drawn = self._draw_texture(
            self.floor_texture,
            left=arena_left,
            top=arena_top,
            width=arena_width,
            height=arena_height,
        )
        if not floor_drawn:
            self._draw_top_rect(
                arena_left,
                arena_top,
                arena_width,
                arena_height,
                ARENA_FILL,
            )
        self._draw_top_rect(
            arena_left,
            arena_top,
            arena_width,
            arena_height,
            (24, 20, 16, 28),
            outline_color=ARENA_EDGE,
            outline_width=3,
        )

        for obstacle in self.obstacles:
            self._draw_top_rect(
                obstacle.x,
                obstacle.y,
                obstacle.width,
                obstacle.height,
                OBSTACLE_FILL,
                outline_color=OBSTACLE_EDGE,
                outline_width=2,
            )

        for trap_state in self.trap_states:
            trap_x, trap_y, trap_w, trap_h = trap_state.rect
            base_color = TRAP_COLORS.get(
                trap_state.kind,
                TRAP_COLORS["spike_trap"],
            )
            presence = _resolve_trap_presence(trap_state, elapsed_ms)
            alpha = max(32, min(200, int(40 + presence * 160)))
            color = (*base_color[:3], alpha)
            self._draw_top_rect(
                trap_x,
                trap_y,
                trap_w,
                trap_h,
                color,
                outline_color=base_color,
                outline_width=3 if trap_state.active else 2,
            )
            inner_inset = max(4.0, min(trap_w, trap_h) * 0.18)
            inner_width = max(0.0, trap_w - inner_inset * 2)
            inner_height = max(0.0, trap_h - inner_inset * 2)
            if inner_width > 0 and inner_height > 0 and presence > 0.08:
                self._draw_top_rect(
                    trap_x + inner_inset,
                    trap_y + inner_inset,
                    inner_width,
                    inner_height,
                    (*base_color[:3], max(18, int(48 + presence * 72))),
                )

        pulse = 2.0 + (elapsed_ms % 900.0) / 900.0
        for orb in self.orbs:
            orb_color = ORB_RARE if orb.variant == "rare" else ORB_COMMON
            orb_y = self.height - orb.y
            orb_size = float(orb.radius * 2 + 12 + pulse * 2)
            orb_drawn = self._draw_texture(
                self.orb_texture,
                left=orb.x - orb_size / 2,
                top=(self.height - orb_y) - orb_size / 2,
                width=orb_size,
                height=orb_size,
                color=orb_color,
            )
            if not orb_drawn:
                arcade.draw_circle_filled(
                    orb.x,
                    orb_y,
                    orb.radius + pulse,
                    (*orb_color[:3], 48),
                )
                arcade.draw_circle_filled(orb.x, orb_y, orb.radius, orb_color)
            arcade.draw_circle_outline(
                orb.x,
                orb_y,
                orb.radius + 2,
                TEXT_PRIMARY,
                2,
            )

        for player in self.players:
            center_y = self.height - player.y
            moving = bool(player.is_moving)
            combo_remaining_ms = player.get_combo_remaining_ms(elapsed_ms)
            slowed = (
                elapsed_ms < float(player.trap_slowed_until_ms)
                and float(player.trap_slow_multiplier) < 1.0
            )
            arcade.draw_ellipse_filled(
                player.x,
                center_y - 2,
                player.radius * 2.1,
                player.radius * 1.2,
                (10, 14, 20, 120),
            )

            sprite_texture = _load_player_texture(
                player.sprite_id,
                player.direction_name,
                elapsed_ms=elapsed_ms,
                is_moving=moving,
            )
            sprite_size = max(88.0, player.radius * 4.8)
            sprite_top = player.y - sprite_size * 0.62
            sprite_drawn = self._draw_texture(
                sprite_texture,
                left=player.x - sprite_size / 2,
                top=sprite_top,
                width=sprite_size,
                height=sprite_size,
            )
            if not sprite_drawn:
                arcade.draw_circle_filled(
                    player.x,
                    center_y,
                    player.radius,
                    (*player.color, 255),
                )
                arcade.draw_circle_outline(
                    player.x,
                    center_y,
                    player.radius + 2,
                    TEXT_PRIMARY,
                    2,
                )
            else:
                arcade.draw_circle_outline(
                    player.x,
                    center_y + player.radius * 0.2,
                    player.radius + 3,
                    (*player.color, 210),
                    3 if moving else 2,
                )

            direction_dx, direction_dy = 0.0, 0.0
            if player.direction_name == "up":
                direction_dy = 16.0
            elif player.direction_name == "down":
                direction_dy = -16.0
            elif player.direction_name == "left":
                direction_dx = -16.0
            else:
                direction_dx = 16.0

            if moving:
                arcade.draw_ellipse_filled(
                    player.x - direction_dx * 0.35,
                    center_y - 6 - direction_dy * 0.35,
                    player.radius * 1.8,
                    player.radius * 0.9,
                    (10, 14, 20, 90),
                )

            arcade.draw_line(
                player.x,
                center_y + player.radius * 0.25,
                player.x + direction_dx,
                center_y + player.radius * 0.25 + direction_dy,
                TEXT_PRIMARY if moving else TEXT_MUTED,
                3 if moving else 2,
            )
            if slowed:
                arcade.draw_circle_outline(
                    player.x,
                    center_y + player.radius * 0.2,
                    player.radius + 8,
                    (122, 201, 194, 180),
                    2,
                )
            display_name = _trim_display_name(player.name, 16)
            score_text = f"Score {int(player.score)}"
            label_width = max(112, min(184, len(display_name) * 8 + 28))
            label_height = 38 if combo_remaining_ms > 0 else 34
            label_left = player.x - label_width / 2
            label_top = player.y - player.radius - 48
            self._draw_top_rect(
                label_left,
                label_top,
                label_width,
                label_height,
                NAME_PANEL_FILL,
                outline_color=NAME_PANEL_BORDER,
                outline_width=1,
            )
            self._draw_top_text(
                display_name,
                player.x,
                label_top + 5,
                TEXT_PRIMARY,
                12,
                anchor_x="center",
                bold=(player.control_mode == HUMAN_CONTROL_MODE),
            )
            self._draw_top_text(
                score_text,
                player.x,
                label_top + 20,
                TEXT_MUTED,
                10,
                anchor_x="center",
            )
            if player.combo_count > 1:
                combo_color = (
                    TEAM_A_ACCENT if player.team_code == "A" else TEAM_B_ACCENT
                )
                self._draw_top_rect(
                    player.x - 18,
                    player.y + player.radius + 6,
                    36,
                    18,
                    (*combo_color[:3], 148),
                    outline_color=combo_color,
                    outline_width=1,
                )
                self._draw_top_text(
                    f"x{player.combo_count}",
                    player.x,
                    player.y + player.radius + 8,
                    TEXT_PRIMARY,
                    11,
                    anchor_x="center",
                    bold=True,
                )
                self._draw_progress_bar(
                    label_left + 8,
                    label_top + label_height - 6,
                    label_width - 16,
                    3,
                    ratio=_resolve_combo_ratio(combo_remaining_ms),
                    color=combo_color,
                )

    def _draw_hud(self) -> None:
        team_a_score, team_b_score = get_team_scores(self.players)
        team_a_rows = _resolve_local_team_rows(self.players, "A")
        team_b_rows = _resolve_local_team_rows(self.players, "B")
        timer_color = _resolve_timer_color(self.remaining_time)
        team_a_accent = team_a_rows[0]["accent_color"] if team_a_rows else TEAM_A_ACCENT
        team_b_accent = team_b_rows[0]["accent_color"] if team_b_rows else TEAM_B_ACCENT
        margin = 18
        timer_width = min(208, max(164, self.width // 8))
        panel_width = min(
            286,
            max(236, int((self.width - margin * 2 - timer_width - 18) / 2)),
        )
        timer_left = (self.width - timer_width) / 2
        left_panel_x = margin
        right_panel_x = self.width - margin - panel_width
        top_y = 18
        roster_y = top_y + SCORE_PANEL_HEIGHT + 8

        self._draw_team_score_block(
            left_panel_x,
            top_y,
            panel_width,
            SCORE_PANEL_HEIGHT,
            title=get_team_label("A"),
            score=team_a_score,
            accent_color=team_a_accent,
            align="left",
        )
        self._draw_team_score_block(
            right_panel_x,
            top_y,
            panel_width,
            SCORE_PANEL_HEIGHT,
            title=get_team_label("B"),
            score=team_b_score,
            accent_color=team_b_accent,
            align="right",
        )
        self._draw_top_rect(
            timer_left,
            top_y,
            timer_width,
            SCORE_PANEL_HEIGHT,
            HUD_PANEL_DEEP,
            outline_color=timer_color,
            outline_width=2,
        )
        self._draw_top_text(
            "TEMPS",
            timer_left + timer_width / 2,
            top_y + 8,
            TEXT_MUTED,
            12,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            _format_timer_value(self.remaining_time),
            timer_left + timer_width / 2,
            top_y + 28,
            timer_color,
            28,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            "Backend local : Arcade",
            timer_left + timer_width / 2,
            top_y + 58,
            TEXT_MUTED,
            11,
            anchor_x="center",
        )
        self._draw_progress_bar(
            timer_left + 14,
            top_y + SCORE_PANEL_HEIGHT - 12,
            timer_width - 28,
            5,
            ratio=self.remaining_time / max(1, self.active_match_duration),
            color=timer_color,
        )
        self._draw_team_summary_panel(
            left_panel_x,
            roster_y,
            title=get_team_label("A"),
            rows=team_a_rows,
            accent_color=team_a_accent,
            align="left",
            panel_width=panel_width,
        )
        self._draw_team_summary_panel(
            right_panel_x,
            roster_y,
            title=get_team_label("B"),
            rows=team_b_rows,
            accent_color=team_b_accent,
            align="right",
            panel_width=panel_width,
        )

    def _draw_end_overlay(self) -> None:
        self._draw_top_rect(0, 0, self.width, self.height, OVERLAY_FILL)
        panel_width = min(860, self.width - 120)
        panel_height = 360
        panel_x = (self.width - panel_width) / 2
        panel_y = (self.height - panel_height) / 2
        self._draw_top_rect(
            panel_x,
            panel_y,
            panel_width,
            panel_height,
            OVERLAY_PANEL,
            outline_color=OVERLAY_BORDER,
            outline_width=3,
        )

        team_a_score, team_b_score = get_team_scores(self.players)
        team_a_rows = _resolve_local_team_rows(self.players, "A")
        team_b_rows = _resolve_local_team_rows(self.players, "B")
        team_a_accent = team_a_rows[0]["accent_color"] if team_a_rows else TEAM_A_ACCENT
        team_b_accent = team_b_rows[0]["accent_color"] if team_b_rows else TEAM_B_ACCENT
        summary_panel_width = min(248, max(204, int((panel_width - 140) / 2)))
        left_summary_x = panel_x + 54
        right_summary_x = panel_x + panel_width - 54 - summary_panel_width
        self._draw_top_text(
            self.winner_text,
            self.width / 2,
            panel_y + 40,
            TEXT_PRIMARY,
            34,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            format_scoreline(team_a_score, team_b_score),
            self.width / 2,
            panel_y + 92,
            TEXT_MUTED,
            22,
            anchor_x="center",
        )
        self._draw_team_summary_panel(
            left_summary_x,
            panel_y + 128,
            title=get_team_label("A"),
            rows=team_a_rows,
            accent_color=team_a_accent,
            align="left",
            panel_width=summary_panel_width,
        )
        self._draw_team_summary_panel(
            right_summary_x,
            panel_y + 128,
            title=get_team_label("B"),
            rows=team_b_rows,
            accent_color=team_b_accent,
            align="right",
            panel_width=summary_panel_width,
        )
        self._draw_top_text(
            "Entree : revenir au bastion",
            self.width / 2,
            panel_y + 316,
            TEXT_PRIMARY,
            18,
            anchor_x="center",
        )
        self._draw_top_text(
            "R : relancer la joute   |   Echap : quitter l'arene",
            self.width / 2,
            panel_y + 336,
            TEXT_MUTED,
            16,
            anchor_x="center",
        )

    def _build_intent_for_player(self, player) -> MovementIntent:
        bindings = self.control_bindings.get(player.name, {})
        return MovementIntent(
            up=bindings.get("up") in self.pressed_keys,
            down=bindings.get("down") in self.pressed_keys,
            left=bindings.get("left") in self.pressed_keys,
            right=bindings.get("right") in self.pressed_keys,
        )

    def _finish_match(self) -> None:
        self.game_over = True
        stop_music(fade_ms=280)
        team_a_score, team_b_score = get_team_scores(self.players)
        winner_team = get_winner_team(team_a_score, team_b_score)
        self.winner_text = format_winner_text(winner_team)

    def _play_final_sound_once(self) -> None:
        if not self.game_over or self.final_sound_played:
            return

        team_a_score, team_b_score = get_team_scores(self.players)
        winner_team = get_winner_team(team_a_score, team_b_score)
        local_focus_team = get_local_focus_team(self.players)
        if winner_team is None:
            play_draw()
        elif local_focus_team is not None:
            if winner_team == local_focus_team:
                play_win()
            else:
                play_lose()
        else:
            play_win()

        self.hardware_service.emit_state("RESULT")
        self.hardware_service.emit_winner(winner_team)
        self.final_sound_played = True

    def _request_close(self, result=None, *, reset_hardware: bool) -> None:
        self.result = result
        self._should_reset_hardware = reset_hardware
        self.close()
        exit_func = getattr(arcade, "exit", None)
        if callable(exit_func):
            exit_func()

    def on_draw(self) -> None:
        self.clear()
        self._draw_vertical_gradient()
        self._draw_arena(self.match_elapsed_ms)
        self._draw_orb_effects()
        self._draw_hud()
        if self.game_over:
            self._draw_end_overlay()

    def on_update(self, delta_time: float) -> None:
        if self.game_over:
            self._play_final_sound_once()
            return

        self.match_elapsed_ms += float(delta_time) * 1000.0
        elapsed_ms = self.match_elapsed_ms
        self.remaining_time = max(
            0,
            self.active_match_duration - int(elapsed_ms // 1000),
        )
        update_match_traps(self.trap_states, elapsed_ms)

        for player in self.players:
            if player.control_mode == AI_CONTROL_MODE:
                intent = self.ai_controllers[player].get_movement_intent(
                    player=player,
                    players=self.players,
                    orbs=self.orbs,
                    obstacles=self.obstacles,
                    elapsed_ms=int(elapsed_ms),
                )
            else:
                intent = self._build_intent_for_player(player)

            player.update_from_intent(
                intent,
                self.arena_rect,
                self.obstacles,
                elapsed_ms=elapsed_ms,
            )

        for player in self.players:
            for trap_state in self.trap_states:
                if not trap_state.active:
                    continue
                if player.collides_with_trap(trap_state.rect):
                    player.trigger_trap(
                        elapsed_ms,
                        slow_duration_ms=trap_state.slow_duration_ms,
                        slow_multiplier=trap_state.slow_multiplier,
                    )
                    break

        for orb in self.orbs:
            for player in self.players:
                if player.collides_with_orb(orb):
                    awarded_value, combo_bonus = player.register_orb_pickup(
                        elapsed_ms,
                        orb.value,
                    )
                    play_pickup()
                    self._record_orb_effect(
                        orb.x,
                        orb.y,
                        awarded_value,
                        combo_bonus,
                    )
                    orb.respawn(
                        self.arena_rect,
                        self.obstacles,
                        elapsed_ms=elapsed_ms,
                    )
                    break

        team_a_score, team_b_score = get_team_scores(self.players)
        self.hardware_service.emit_score(team_a_score, team_b_score)

        if self.remaining_time <= 0:
            self._finish_match()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        del modifiers
        self.pressed_keys.add(symbol)

        if not self.game_over:
            if symbol == arcade.key.ESCAPE:
                self._request_close(None, reset_hardware=True)
            return

        if symbol == arcade.key.ENTER:
            self._request_close(
                build_result(
                    self.players,
                    self.winner_text,
                    self.active_match_duration,
                    players_config=self.players_config,
                ),
                reset_hardware=False,
            )
        elif symbol == arcade.key.R:
            stop_music(fade_ms=120)
            self._start_new_match()
        elif symbol == arcade.key.ESCAPE:
            self._request_close(None, reset_hardware=True)

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        del modifiers
        self.pressed_keys.discard(symbol)

    def on_close(self) -> None:
        if not self._shutdown_complete:
            if self._should_reset_hardware:
                self.hardware_service.reset()
            stop_music(fade_ms=120)
            self.hardware_service.shutdown()
            pg_quit()
            self._shutdown_complete = True
        super().on_close()


def run_game(players_config, match_duration_seconds=MATCH_DURATION_SECONDS):
    window = ArcadeMatchWindow(
        players_config,
        match_duration_seconds=match_duration_seconds,
    )
    arcade.run()
    return window.result
