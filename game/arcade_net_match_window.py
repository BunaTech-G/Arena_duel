from __future__ import annotations

import arcade
import pygame

from game.arcade_window import (
    ARENA_EDGE,
    ARENA_FILL,
    ARENA_FLOOR_ASSET,
    BACKGROUND_BOTTOM,
    BACKGROUND_TOP,
    OBSTACLE_EDGE,
    OBSTACLE_FILL,
    ORB_COMMON,
    ORB_RARE,
    OVERLAY_BORDER,
    OVERLAY_FILL,
    OVERLAY_PANEL,
    TEAM_A_ACCENT,
    TEAM_B_ACCENT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXTURE_WHITE,
    TRAP_COLORS,
    WINDOW_BACKGROUND_ASSET,
    _coerce_arcade_color,
    _load_background_texture,
    _load_orb_texture,
    _load_player_texture,
)
from game.arena import (
    get_arena_rect,
    get_map_layout,
    get_obstacles,
    get_team_color,
)
from game.arena_layout import DEFAULT_MAP_ID
from game.audio import (
    init_audio,
    play_draw,
    play_lose,
    play_pickup,
    play_win,
    start_match_music,
    stop_music,
)
from game.match_text import (
    format_scoreline,
    format_winner_text,
    get_team_label,
    get_winner_team,
)
from game.settings import FPS, ORB_COMBO_WINDOW_MS
from network.messages import DISCONNECTED, END, ERROR, STATE
from network.net_utils import get_network_logger


pg_init = getattr(pygame, "init", lambda: None)
pg_quit = getattr(pygame, "quit", lambda: None)
LOGGER = get_network_logger()
LAN_ARCADE_RUNTIME_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    OSError,
    AttributeError,
)
LAN_ARCADE_LAUNCH_ERRORS = (
    RuntimeError,
    OSError,
    AttributeError,
)

WINDOW_TITLE = "Arena Duel - Joute partagee Arcade"
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
VALID_DIRECTION_NAMES = {"up", "down", "left", "right"}
NETWORK_UP_KEYS = {
    getattr(arcade.key, "Z"),
    getattr(arcade.key, "W"),
    getattr(arcade.key, "UP"),
}
NETWORK_DOWN_KEYS = {
    getattr(arcade.key, "S"),
    getattr(arcade.key, "DOWN"),
}
NETWORK_LEFT_KEYS = {
    getattr(arcade.key, "Q"),
    getattr(arcade.key, "A"),
    getattr(arcade.key, "LEFT"),
}
NETWORK_RIGHT_KEYS = {
    getattr(arcade.key, "D"),
    getattr(arcade.key, "RIGHT"),
}


def _build_input_state(
    pressed_keys: set[int],
) -> tuple[bool, bool, bool, bool]:
    up = any(key in pressed_keys for key in NETWORK_UP_KEYS)
    down = any(key in pressed_keys for key in NETWORK_DOWN_KEYS)
    left = any(key in pressed_keys for key in NETWORK_LEFT_KEYS)
    right = any(key in pressed_keys for key in NETWORK_RIGHT_KEYS)
    return up, down, left, right


def _trim_display_name(name: str, max_chars: int = 14) -> str:
    clean_name = str(name or "").strip()
    if len(clean_name) <= max_chars:
        return clean_name
    return clean_name[: max_chars - 3] + "..."


def _resolve_timer_color(remaining_seconds: int):
    if remaining_seconds <= 10:
        return TIMER_URG
    if remaining_seconds <= 30:
        return TIMER_WARN
    return TIMER_OK


def _resolve_combo_ratio(combo_remaining_ms: int) -> float:
    return max(
        0.0,
        min(1.0, float(combo_remaining_ms) / max(1, ORB_COMBO_WINDOW_MS)),
    )


def _resolve_direction_from_delta(
    delta_x: float,
    delta_y: float,
    fallback: str,
) -> str:
    if abs(delta_x) <= 0.5 and abs(delta_y) <= 0.5:
        return fallback
    if abs(delta_x) >= abs(delta_y):
        return "right" if delta_x > 0 else "left"
    return "down" if delta_y > 0 else "up"


def _resolve_network_movement(
    player_state: dict,
    delta_x: float,
    delta_y: float,
) -> bool:
    if "is_moving" in player_state:
        return bool(player_state.get("is_moving"))
    return abs(delta_x) > 0.5 or abs(delta_y) > 0.5


def _resolve_network_direction(
    player_state: dict,
    delta_x: float,
    delta_y: float,
    fallback: str,
) -> str:
    explicit_direction = str(player_state.get("direction") or "").strip().lower()
    if explicit_direction in VALID_DIRECTION_NAMES:
        return explicit_direction
    return _resolve_direction_from_delta(delta_x, delta_y, fallback)


def _resolve_network_sprite_id(player_state: dict) -> str:
    explicit_sprite_id = str(player_state.get("sprite_id") or "").strip()
    if explicit_sprite_id:
        return explicit_sprite_id
    if str(player_state.get("team", "A")).upper() == "A":
        return "skeleton_fighter_ember"
    return "skeleton_fighter_aether"


def _resolve_state_team_rows(state: dict, team_code: str) -> list[dict]:
    rows = []
    for player_state in sorted(
        state.get("players", []),
        key=lambda item: item.get("slot", 0),
    ):
        if player_state.get("team") != team_code:
            continue
        rows.append(
            {
                "name": player_state.get("name", "Combattant"),
                "score": int(player_state.get("score", 0)),
                "accent_color": get_team_color(
                    team_code,
                    max(0, int(player_state.get("slot", 1)) - 1),
                ),
                "sprite_id": _resolve_network_sprite_id(player_state),
            }
        )
    return rows


def _resolve_local_team(my_team, my_slot, *payloads):
    if my_team:
        return my_team

    for payload in payloads:
        if not payload:
            continue

        for player_state in payload.get("players", []):
            if player_state.get("slot") == my_slot:
                return player_state.get("team")

    return None


class ArcadeNetworkMatchWindow(arcade.Window):
    def __init__(self, client, my_slot, my_name, my_team):
        self.client = client
        self.my_slot = my_slot
        self.my_name = my_name
        self.my_team = my_team
        self.active_layout = get_map_layout(DEFAULT_MAP_ID)
        width, height = self.active_layout.window_size

        super().__init__(
            width=width,
            height=height,
            title=f"{WINDOW_TITLE} · {my_name}",
            resizable=False,
            update_rate=1 / FPS,
        )

        self.window_background_texture = _load_background_texture(
            WINDOW_BACKGROUND_ASSET
        )
        self.floor_texture = _load_background_texture(ARENA_FLOOR_ASSET)
        self.orb_texture = _load_orb_texture()
        self.pressed_keys: set[int] = set()
        self.render_elapsed_ms = 0.0
        self.latest_state = None
        self.end_message = None
        self.end_timer_seconds = 0.0
        self.deferred_messages = []
        self.disconnect_message = None
        self.last_error_message = None
        self.previous_positions = {}
        self.previous_scores = {}
        self.previous_pickup_serials = {}
        self.previous_orbs = {}
        self.orb_effects = []
        self.orb_spawn_times = {}
        self.latest_movement = {}
        self.latest_direction = {}
        self.end_sound_played = False
        self.result_summary = None
        self._shutdown_complete = False
        self._close_client_on_close = False
        self._first_state_logged = False

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pg_init()
        init_audio()
        stop_music(fade_ms=0)
        start_match_music(restart=True)
        LOGGER.info(
            "Ouverture match LAN Arcade (joueur=%s, slot=%s, team=%s)",
            my_name,
            my_slot,
            my_team,
        )

    def _abort_runtime(self, stage: str, error) -> None:
        if self.result_summary is not None:
            return

        LOGGER.exception(
            "Erreur dans la fenetre LAN Arcade pendant %s",
            stage,
        )
        self.last_error_message = (
            f"Le rendu Arcade du match LAN a echoue pendant {stage}: {error}"
        )
        stop_music(fade_ms=120)
        self._request_close(
            self.build_match_summary(completed=False),
            close_client=False,
        )

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
        rect = arcade.LBWH(
            x,
            self._top_to_bottom(y, height),
            width,
            height,
        )
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

    def _draw_background(self) -> None:
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

    def _draw_arena(self) -> None:
        arena_rect = get_arena_rect(self.active_layout)
        obstacles = get_obstacles(self.active_layout)
        floor_drawn = self._draw_texture(
            self.floor_texture,
            left=arena_rect.left,
            top=arena_rect.top,
            width=arena_rect.width,
            height=arena_rect.height,
        )
        if not floor_drawn:
            self._draw_top_rect(
                arena_rect.left,
                arena_rect.top,
                arena_rect.width,
                arena_rect.height,
                ARENA_FILL,
            )
        self._draw_top_rect(
            arena_rect.left,
            arena_rect.top,
            arena_rect.width,
            arena_rect.height,
            (24, 20, 16, 28),
            outline_color=ARENA_EDGE,
            outline_width=3,
        )

        for obstacle in obstacles:
            self._draw_top_rect(
                obstacle.x,
                obstacle.y,
                obstacle.width,
                obstacle.height,
                OBSTACLE_FILL,
                outline_color=OBSTACLE_EDGE,
                outline_width=2,
            )

        for trap_state in self.latest_state.get("traps", []):
            trap_x, trap_y, trap_w, trap_h = trap_state.get(
                "rect",
                [0, 0, 0, 0],
            )
            base_color = TRAP_COLORS.get(
                trap_state.get("kind"),
                TRAP_COLORS["spike_trap"],
            )
            presence = float(trap_state.get("presence", 0.0))
            alpha = max(32, min(200, int(40 + presence * 160)))
            self._draw_top_rect(
                trap_x,
                trap_y,
                trap_w,
                trap_h,
                (*base_color[:3], alpha),
                outline_color=base_color,
                outline_width=3 if presence > 0.55 else 2,
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
                    (*base_color[:3], max(18, int(44 + presence * 76))),
                )

    def _draw_players(self) -> None:
        for player_state in self.latest_state.get("players", []):
            x = float(player_state.get("x", 0.0))
            y = float(player_state.get("y", 0.0))
            radius = 20.0
            center_y = self.height - y
            slot = int(player_state.get("slot", 0))
            moving = bool(self.latest_movement.get(slot, False))
            combo_count = int(player_state.get("combo_count", 0))
            combo_remaining_ms = int(player_state.get("combo_remaining_ms", 0))
            accent_color = get_team_color(
                player_state.get("team", "A"),
                max(0, int(player_state.get("slot", 1)) - 1),
            )

            arcade.draw_ellipse_filled(
                x,
                center_y - 2,
                radius * 2.1,
                radius * 1.2,
                (10, 14, 20, 120),
            )

            direction_name = self.latest_direction.get(
                slot,
                "right" if player_state.get("team") == "A" else "left",
            )
            sprite_texture = _load_player_texture(
                _resolve_network_sprite_id(player_state),
                direction_name,
                elapsed_ms=self.render_elapsed_ms,
                is_moving=moving,
            )
            sprite_size = 96.0
            sprite_drawn = self._draw_texture(
                sprite_texture,
                left=x - sprite_size / 2,
                top=y - sprite_size * 0.62,
                width=sprite_size,
                height=sprite_size,
            )
            if not sprite_drawn:
                arcade.draw_circle_filled(
                    x,
                    center_y,
                    radius,
                    (*accent_color, 255),
                )

            highlight_color = (*accent_color, 220)
            if int(player_state.get("slot", -1)) == int(self.my_slot or -1):
                highlight_color = TEXT_PRIMARY
            arcade.draw_circle_outline(
                x,
                center_y + radius * 0.2,
                radius + 3,
                highlight_color,
                3 if moving else 2,
            )

            direction_dx, direction_dy = 0.0, 0.0
            if direction_name == "up":
                direction_dy = 16.0
            elif direction_name == "down":
                direction_dy = -16.0
            elif direction_name == "left":
                direction_dx = -16.0
            else:
                direction_dx = 16.0

            if moving:
                arcade.draw_ellipse_filled(
                    x - direction_dx * 0.35,
                    center_y - 6 - direction_dy * 0.35,
                    radius * 1.8,
                    radius * 0.9,
                    (10, 14, 20, 90),
                )

            arcade.draw_line(
                x,
                center_y + radius * 0.25,
                x + direction_dx,
                center_y + radius * 0.25 + direction_dy,
                TEXT_PRIMARY if moving else TEXT_MUTED,
                3 if moving else 2,
            )

            display_name = _trim_display_name(player_state.get("name", ""), 16)
            player_score = int(player_state.get("score", 0))
            score_text = f"Score {player_score}"
            label_width = max(112, min(184, len(display_name) * 8 + 28))
            label_height = 38 if combo_remaining_ms > 0 else 34
            label_left = x - label_width / 2
            label_top = y - radius - 48
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
                x,
                label_top + 5,
                TEXT_PRIMARY,
                12,
                anchor_x="center",
                bold=(int(player_state.get("slot", -1)) == int(self.my_slot or -1)),
            )
            self._draw_top_text(
                score_text,
                x,
                label_top + 20,
                TEXT_MUTED,
                10,
                anchor_x="center",
            )

            if combo_count > 1:
                combo_color = (
                    TEAM_A_ACCENT if player_state.get("team") == "A" else TEAM_B_ACCENT
                )
                self._draw_top_rect(
                    x - 18,
                    y + radius + 6,
                    36,
                    18,
                    (*combo_color[:3], 148),
                    outline_color=combo_color,
                    outline_width=1,
                )
                self._draw_top_text(
                    f"x{combo_count}",
                    x,
                    y + radius + 8,
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

    def _draw_orbs(self) -> None:
        for fallback_index, orb_state in enumerate(self.latest_state.get("orbs", [])):
            orb_id = int(orb_state.get("orb_id", fallback_index))
            spawned_at_ms = self.orb_spawn_times.get(
                orb_id,
                self.render_elapsed_ms,
            )
            orb_age_ms = max(0.0, self.render_elapsed_ms - spawned_at_ms)
            pulse = 2.0 + (orb_age_ms % 900.0) / 900.0
            orb_color = ORB_RARE if orb_state.get("variant") == "rare" else ORB_COMMON
            orb_x = float(orb_state.get("x", 0.0))
            orb_y = float(orb_state.get("y", 0.0))
            draw_y = self.height - orb_y
            orb_size = float(24 + pulse * 2)
            orb_drawn = self._draw_texture(
                self.orb_texture,
                left=orb_x - orb_size / 2,
                top=orb_y - orb_size / 2,
                width=orb_size,
                height=orb_size,
                color=orb_color,
            )
            if not orb_drawn:
                arcade.draw_circle_filled(
                    orb_x,
                    draw_y,
                    12 + pulse,
                    (*orb_color[:3], 48),
                )
                arcade.draw_circle_filled(orb_x, draw_y, 12, orb_color)
            if orb_age_ms <= 440.0:
                spawn_alpha = max(0, int(210 - orb_age_ms / 2.1))
                arcade.draw_circle_outline(
                    orb_x,
                    draw_y,
                    16 + orb_age_ms / 36.0,
                    (*orb_color[:3], spawn_alpha),
                    2,
                )
            arcade.draw_circle_outline(orb_x, draw_y, 14, TEXT_PRIMARY, 2)

    def _draw_orb_effects(self) -> None:
        active_effects = []
        for effect in self.orb_effects:
            age_ms = self.render_elapsed_ms - float(effect["started_at_ms"])
            if age_ms >= 520:
                continue

            drift = age_ms / 18.0
            alpha = max(0, int(255 - age_ms / 2.2))
            combo_bonus = int(effect.get("combo_bonus", 0))
            effect_text = f"+{int(effect['value'])}"
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

    def _draw_hud(self) -> None:
        team_a_score = int(self.latest_state.get("team_a_score", 0))
        team_b_score = int(self.latest_state.get("team_b_score", 0))
        remaining_time = int(self.latest_state.get("remaining_time", 0))
        total_duration = int(self.latest_state.get("duration_seconds", 60))
        team_a_rows = _resolve_state_team_rows(self.latest_state, "A")
        team_b_rows = _resolve_state_team_rows(self.latest_state, "B")
        timer_color = _resolve_timer_color(remaining_time)
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
        timer_text = f"{remaining_time // 60:02d}:{remaining_time % 60:02d}"

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
            timer_text,
            timer_left + timer_width / 2,
            top_y + 28,
            timer_color,
            28,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            "Backend match : Arcade",
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
            ratio=remaining_time / max(1, total_duration),
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

    def _draw_waiting_overlay(self) -> None:
        self._draw_top_text(
            "Synchronisation du hall en cours...",
            self.width / 2,
            self.height / 2 - 20,
            TEXT_PRIMARY,
            28,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            "Les bastions preparent la joute partagee.",
            self.width / 2,
            self.height / 2 + 24,
            TEXT_MUTED,
            16,
            anchor_x="center",
        )

    def _draw_end_overlay(self) -> None:
        if not self.end_message:
            return

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

        winner_team = self.end_message.get("winner_team")
        if winner_team is None:
            winner_team = get_winner_team(
                int(self.end_message.get("team_a_score", 0)),
                int(self.end_message.get("team_b_score", 0)),
            )

        end_rows_payload = {
            "players": self.end_message.get("players", []),
        }
        team_a_rows = _resolve_state_team_rows(end_rows_payload, "A")
        team_b_rows = _resolve_state_team_rows(end_rows_payload, "B")
        team_a_accent = team_a_rows[0]["accent_color"] if team_a_rows else TEAM_A_ACCENT
        team_b_accent = team_b_rows[0]["accent_color"] if team_b_rows else TEAM_B_ACCENT
        summary_panel_width = min(248, max(204, int((panel_width - 140) / 2)))
        left_summary_x = panel_x + 54
        right_summary_x = panel_x + panel_width - 54 - summary_panel_width

        winner_text = self.end_message.get("winner_text") or format_winner_text(
            winner_team
        )
        score_text = format_scoreline(
            int(self.end_message.get("team_a_score", 0)),
            int(self.end_message.get("team_b_score", 0)),
        )
        self._draw_top_text(
            winner_text,
            self.width / 2,
            panel_y + 40,
            TEXT_PRIMARY,
            34,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            score_text,
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

        if self.end_message.get("history_saved", False):
            match_id = self.end_message.get("match_id")
            if match_id is not None:
                history_text = f"Chronique du hall archivee · joute #{match_id}"
            else:
                history_text = "Chronique du hall archivee"
            history_color = (206, 228, 194, 255)
        else:
            history_error = self.end_message.get("history_error")
            if history_error:
                history_text = f"Chronique du hall indisponible · {history_error}"
            else:
                history_text = "Chronique du hall indisponible"
            history_color = (255, 188, 166, 255)

        self._draw_top_text(
            history_text,
            self.width / 2,
            panel_y + 316,
            history_color,
            16,
            anchor_x="center",
        )
        self._draw_top_text(
            "Entree ou Echap : retour au hall",
            self.width / 2,
            panel_y + 336,
            TEXT_PRIMARY,
            18,
            anchor_x="center",
        )

    def _record_orb_effect(self, pickup: dict, player_state: dict) -> None:
        if int(pickup.get("value", 0)) <= 0:
            return
        self.orb_effects.append(
            {
                "x": float(pickup.get("x", player_state.get("x", 0.0))),
                "y": float(pickup.get("y", player_state.get("y", 0.0))),
                "value": int(pickup.get("value", 0)),
                "combo_count": int(pickup.get("combo_count", 0)),
                "combo_bonus": int(pickup.get("combo_bonus", 0)),
                "started_at_ms": self.render_elapsed_ms,
            }
        )

    def _handle_state_message(self, message: dict) -> None:
        self.latest_movement = {}
        next_directions = {}
        score_changed = False
        current_scores = {}
        next_pickup_serials = {}
        current_ticks = int(self.render_elapsed_ms)

        for player_state in message.get("players", []):
            slot = int(player_state.get("slot", 0))
            score = int(player_state.get("score", 0))
            pickup_serial = int(player_state.get("last_pickup_serial", 0))
            previous_pos = self.previous_positions.get(slot)
            delta_x = 0.0
            delta_y = 0.0
            if previous_pos is not None:
                delta_x = float(player_state.get("x", 0.0)) - previous_pos[0]
                delta_y = float(player_state.get("y", 0.0)) - previous_pos[1]

            fallback_direction = self.latest_direction.get(
                slot,
                "right" if player_state.get("team") == "A" else "left",
            )
            self.latest_movement[slot] = _resolve_network_movement(
                player_state,
                delta_x,
                delta_y,
            )
            next_directions[slot] = _resolve_network_direction(
                player_state,
                delta_x,
                delta_y,
                fallback_direction,
            )
            current_scores[slot] = score
            next_pickup_serials[slot] = pickup_serial
            if score > self.previous_scores.get(slot, score):
                score_changed = True
            if pickup_serial > self.previous_pickup_serials.get(slot, 0):
                pickup = player_state.get("last_pickup") or {}
                self._record_orb_effect(pickup, player_state)

        self.previous_positions = {
            int(player_state.get("slot", 0)): (
                float(player_state.get("x", 0.0)),
                float(player_state.get("y", 0.0)),
            )
            for player_state in message.get("players", [])
        }
        self.previous_scores = current_scores
        self.previous_pickup_serials = next_pickup_serials
        self.latest_direction = next_directions
        if score_changed:
            play_pickup()

        next_spawn_times = {}
        next_previous_orbs = {}
        for fallback_index, orb_state in enumerate(message.get("orbs", [])):
            orb_id = int(orb_state.get("orb_id", fallback_index))
            previous_orb = self.previous_orbs.get(orb_id)
            spawned_at_ms = self.orb_spawn_times.get(orb_id, current_ticks)
            if previous_orb is None:
                spawned_at_ms = current_ticks
            else:
                previous_serial = int(
                    previous_orb.get(
                        "spawn_serial",
                        orb_state.get("spawn_serial", 0),
                    )
                )
                current_serial = int(orb_state.get("spawn_serial", 0))
                if current_serial != previous_serial:
                    spawned_at_ms = current_ticks

            next_spawn_times[orb_id] = spawned_at_ms
            next_previous_orbs[orb_id] = dict(orb_state)

        self.previous_orbs = next_previous_orbs
        self.orb_spawn_times = next_spawn_times
        self.latest_state = message
        self.active_layout = get_map_layout(message.get("map_id", DEFAULT_MAP_ID))
        if not self._first_state_logged:
            LOGGER.info(
                "Premier etat LAN Arcade recu (joueurs=%s, orbes=%s)",
                len(message.get("players", [])),
                len(message.get("orbs", [])),
            )
            self._first_state_logged = True

    def build_match_summary(self, *, completed: bool) -> dict:
        if completed:
            return {
                "completed": True,
                "end_message": self.end_message,
                "deferred_messages": self.deferred_messages,
                "disconnect_message": None,
            }

        return {
            "completed": False,
            "end_message": None,
            "deferred_messages": self.deferred_messages,
            "disconnect_message": (
                self.disconnect_message
                or self.last_error_message
                or "Le lien au hall s'est rompu."
            ),
        }

    def _request_close(
        self,
        summary: dict,
        *,
        close_client: bool = False,
    ) -> None:
        self.result_summary = summary
        self._close_client_on_close = close_client
        self.close()
        exit_func = getattr(arcade, "exit", None)
        if callable(exit_func):
            exit_func()

    def _process_messages(self) -> None:
        for message in self.client.poll_messages():
            message_type = message.get("type")

            if message_type == STATE:
                self._handle_state_message(message)
            elif message_type == END:
                self.end_message = message
                self.end_timer_seconds = 1.2
                stop_music(fade_ms=280)
            elif message_type == ERROR:
                self.last_error_message = message.get(
                    "message",
                    "Le hall a signale une alerte.",
                )
            elif message_type == DISCONNECTED:
                self.disconnect_message = message.get(
                    "message",
                    "Le lien au hall s'est rompu.",
                )
                stop_music(fade_ms=120)
                self._request_close(self.build_match_summary(completed=False))
                return
            else:
                self.deferred_messages.append(message)

    def _play_final_sound_once(self) -> None:
        if self.end_message is None or self.end_sound_played:
            return

        winner_team = self.end_message.get("winner_team")
        local_team = _resolve_local_team(
            self.my_team,
            self.my_slot,
            self.end_message,
            self.latest_state,
        )
        if winner_team is None:
            winner_team = get_winner_team(
                int(self.end_message.get("team_a_score", 0)),
                int(self.end_message.get("team_b_score", 0)),
            )

        if winner_team is None:
            play_draw()
        elif local_team and winner_team == local_team:
            play_win()
        else:
            play_lose()

        self.end_sound_played = True

    def on_draw(self) -> None:
        try:
            self.clear()
            self._draw_background()
            if self.latest_state is None:
                self._draw_waiting_overlay()
            else:
                self._draw_arena()
                self._draw_orbs()
                self._draw_players()
                self._draw_orb_effects()
                self._draw_hud()
            if self.end_message is not None:
                self._draw_end_overlay()
        except LAN_ARCADE_RUNTIME_ERRORS as error:
            self._abort_runtime("on_draw", error)

    def on_update(self, delta_time: float) -> None:
        try:
            if self.result_summary is not None:
                return

            self.render_elapsed_ms += float(delta_time) * 1000.0
            self._process_messages()
            if self.result_summary is not None:
                return

            if self.end_message is None and self.client.running:
                up, down, left, right = _build_input_state(self.pressed_keys)
                self.client.send_input(up, down, left, right)
            elif self.end_message is not None:
                self._play_final_sound_once()
                self.end_timer_seconds -= float(delta_time)
                if self.end_timer_seconds <= 0:
                    self._request_close(self.build_match_summary(completed=True))
        except LAN_ARCADE_RUNTIME_ERRORS as error:
            self._abort_runtime("on_update", error)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        del modifiers
        self.pressed_keys.add(symbol)

        if self.end_message is not None:
            if symbol in {arcade.key.ENTER, arcade.key.ESCAPE}:
                self._request_close(self.build_match_summary(completed=True))
            return

        if symbol == arcade.key.ESCAPE:
            self.disconnect_message = "Match ferme par le joueur."
            if self.client.running:
                self.client.close()
            stop_music(fade_ms=120)
            self._request_close(
                self.build_match_summary(completed=False),
                close_client=False,
            )

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        del modifiers
        self.pressed_keys.discard(symbol)

    def on_close(self) -> None:
        if not self._shutdown_complete:
            if self.result_summary is None:
                self.disconnect_message = (
                    self.disconnect_message or "Match ferme par le joueur."
                )
                if self.client.running:
                    self.client.close()
                self.result_summary = self.build_match_summary(completed=False)

            if self._close_client_on_close and self.client.running:
                self.client.close()

            stop_music(fade_ms=120)
            pg_quit()
            self._shutdown_complete = True

        super().on_close()


def run_network_match(client, my_slot, my_name, my_team):
    window = ArcadeNetworkMatchWindow(client, my_slot, my_name, my_team)
    try:
        window.set_visible(True)
        activate_window = getattr(window, "activate", None)
        if callable(activate_window):
            activate_window()
        arcade.run()
    except LAN_ARCADE_LAUNCH_ERRORS as error:
        LOGGER.exception("Crash pendant arcade.run() du match LAN")
        window.last_error_message = (
            f"Le moteur Arcade du match LAN a plante au lancement : {error}"
        )
        stop_music(fade_ms=120)
        try:
            window.close()
        except LAN_ARCADE_LAUNCH_ERRORS:
            pass
        return window.build_match_summary(completed=False)

    LOGGER.info(
        "Fermeture match LAN Arcade (complete=%s, client_running=%s)",
        bool(window.result_summary and window.result_summary.get("completed")),
        bool(client.running),
    )
    return window.result_summary or {
        "completed": False,
        "end_message": None,
        "deferred_messages": [],
        "disconnect_message": "Le lien au hall s'est rompu.",
    }
