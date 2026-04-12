from __future__ import annotations

import arcade
import pygame

from game.arcade_window import (
    ARENA_EDGE,
    ARENA_FILL,
    ARENA_FLOOR_ASSET,
    BACKGROUND_BOTTOM,
    BACKGROUND_TOP,
    HUD_BORDER,
    HUD_PANEL,
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
from game.settings import FPS
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
                outline_width=2,
            )

    def _draw_players(self) -> None:
        for player_state in self.latest_state.get("players", []):
            x = float(player_state.get("x", 0.0))
            y = float(player_state.get("y", 0.0))
            radius = 20.0
            center_y = self.height - y
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

            direction_name = str(player_state.get("direction", "right") or "right")
            sprite_texture = _load_player_texture(
                _resolve_network_sprite_id(player_state),
                direction_name,
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
                2,
            )

            self._draw_top_text(
                (
                    f"{player_state.get('name', 'Combattant')} "
                    f"({int(player_state.get('score', 0))})"
                ),
                x,
                y - radius - 18,
                TEXT_PRIMARY,
                12,
                anchor_x="center",
                bold=(int(player_state.get("slot", -1)) == int(self.my_slot or -1)),
            )

    def _draw_orbs(self) -> None:
        for fallback_index, orb_state in enumerate(self.latest_state.get("orbs", [])):
            orb_id = int(orb_state.get("orb_id", fallback_index))
            spawned_at_ms = self.orb_spawn_times.get(
                orb_id,
                self.render_elapsed_ms,
            )
            pulse = 2.0 + ((self.render_elapsed_ms - spawned_at_ms) % 900.0) / 900.0
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
        panel_height = 104
        self._draw_top_rect(
            18,
            18,
            self.width - 36,
            panel_height,
            HUD_PANEL,
            outline_color=HUD_BORDER,
            outline_width=2,
        )

        team_a_score = int(self.latest_state.get("team_a_score", 0))
        team_b_score = int(self.latest_state.get("team_b_score", 0))
        remaining_time = int(self.latest_state.get("remaining_time", 0))

        self._draw_top_text(
            get_team_label("A"),
            42,
            34,
            TEAM_A_ACCENT,
            24,
            bold=True,
        )
        self._draw_top_text(
            str(team_a_score),
            46,
            64,
            TEXT_PRIMARY,
            28,
            bold=True,
        )
        self._draw_top_text(
            get_team_label("B"),
            self.width - 42,
            34,
            TEAM_B_ACCENT,
            24,
            anchor_x="right",
            bold=True,
        )
        self._draw_top_text(
            str(team_b_score),
            self.width - 46,
            64,
            TEXT_PRIMARY,
            28,
            anchor_x="right",
            bold=True,
        )
        self._draw_top_text(
            f"Sablier : {remaining_time}s",
            self.width / 2,
            32,
            TEXT_PRIMARY,
            28,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            "Backend match : Arcade",
            self.width / 2,
            68,
            TEXT_MUTED,
            14,
            anchor_x="center",
        )

        team_a_rows = _resolve_state_team_rows(self.latest_state, "A")
        team_b_rows = _resolve_state_team_rows(self.latest_state, "B")
        for index, row in enumerate(team_a_rows):
            self._draw_top_text(
                f"{row['name']}  {row['score']}",
                190,
                34 + index * 24,
                TEXT_MUTED,
                13,
            )
        for index, row in enumerate(team_b_rows):
            self._draw_top_text(
                f"{row['score']}  {row['name']}",
                self.width - 190,
                34 + index * 24,
                TEXT_MUTED,
                13,
                anchor_x="right",
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
        panel_height = 320
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
            panel_y + 170,
            history_color,
            16,
            anchor_x="center",
        )
        self._draw_top_text(
            "Entree ou Echap : retour au hall",
            self.width / 2,
            panel_y + 212,
            TEXT_PRIMARY,
            18,
            anchor_x="center",
        )
        self._draw_top_text(
            "Retour automatique imminent...",
            self.width / 2,
            panel_y + 246,
            TEXT_MUTED,
            15,
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
        score_changed = False
        current_scores = {}
        next_pickup_serials = {}
        current_ticks = int(self.render_elapsed_ms)

        for player_state in message.get("players", []):
            slot = int(player_state.get("slot", 0))
            score = int(player_state.get("score", 0))
            pickup_serial = int(player_state.get("last_pickup_serial", 0))
            previous_pos = self.previous_positions.get(slot)
            self.latest_movement[slot] = previous_pos is not None and (
                abs(float(player_state.get("x", 0.0)) - previous_pos[0]) > 0.5
                or abs(float(player_state.get("y", 0.0)) - previous_pos[1]) > 0.5
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
            arcade.start_render()
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
