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
from game.match_text import format_winner_text, get_team_label, get_winner_team
from game.orb import Orb
from game.settings import (
    FPS,
    MATCH_DURATION_SECONDS,
    ORB_SPAWN_COUNT,
    coerce_match_duration,
)
from game.arena import get_arena_rect, get_map_layout, get_obstacles
from game.traps import build_match_traps, update_match_traps


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


def _load_player_texture(
    sprite_id: str,
    direction_name: str,
) -> arcade.Texture | None:
    texture_path, mirrored = _resolve_sprite_frame_path(
        sprite_id,
        direction_name,
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
            alpha = 70 if not trap_state.active else 180
            color = (*base_color[:3], alpha)
            self._draw_top_rect(
                trap_x,
                trap_y,
                trap_w,
                trap_h,
                color,
                outline_color=base_color,
                outline_width=2,
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
                    2,
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

            arcade.draw_line(
                player.x,
                center_y + player.radius * 0.25,
                player.x + direction_dx,
                center_y + player.radius * 0.25 + direction_dy,
                TEXT_PRIMARY,
                3,
            )
            self._draw_top_text(
                f"{player.name} ({player.score})",
                player.x,
                player.y - player.radius - 18,
                TEXT_PRIMARY,
                12,
                anchor_x="center",
                bold=True,
            )
            if player.combo_count > 1:
                combo_color = (
                    TEAM_A_ACCENT if player.team_code == "A" else TEAM_B_ACCENT
                )
                self._draw_top_text(
                    f"x{player.combo_count}",
                    player.x,
                    player.y + player.radius + 8,
                    combo_color,
                    12,
                    anchor_x="center",
                    bold=True,
                )

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
        team_a_score, team_b_score = get_team_scores(self.players)

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
            f"Sablier : {self.remaining_time}s",
            self.width / 2,
            32,
            TEXT_PRIMARY,
            28,
            anchor_x="center",
            bold=True,
        )
        self._draw_top_text(
            "Backend local : Arcade",
            self.width / 2,
            68,
            TEXT_MUTED,
            14,
            anchor_x="center",
        )

        team_a_rows = [player for player in self.players if player.team_code == "A"]
        team_b_rows = [player for player in self.players if player.team_code == "B"]
        for index, player in enumerate(team_a_rows):
            self._draw_top_text(
                f"{player.name}  {player.score}",
                190,
                34 + index * 24,
                TEXT_MUTED,
                13,
            )
        for index, player in enumerate(team_b_rows):
            self._draw_top_text(
                f"{player.score}  {player.name}",
                self.width - 190,
                34 + index * 24,
                TEXT_MUTED,
                13,
                anchor_x="right",
            )

    def _draw_end_overlay(self) -> None:
        self._draw_top_rect(0, 0, self.width, self.height, OVERLAY_FILL)
        panel_width = min(760, self.width - 120)
        panel_height = 260
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
            (
                f"{get_team_label('A')} : {team_a_score}  |  "
                f"{get_team_label('B')} : {team_b_score}"
            ),
            self.width / 2,
            panel_y + 92,
            TEXT_MUTED,
            22,
            anchor_x="center",
        )
        self._draw_top_text(
            "Entree : revenir au bastion",
            self.width / 2,
            panel_y + 154,
            TEXT_PRIMARY,
            18,
            anchor_x="center",
        )
        self._draw_top_text(
            "R : relancer la joute   |   Echap : quitter l'arene",
            self.width / 2,
            panel_y + 188,
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
        arcade.start_render()
        self._draw_vertical_gradient()
        self._draw_arena(self.match_elapsed_ms)
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
                    player.register_orb_pickup(elapsed_ms, orb.value)
                    play_pickup()
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
