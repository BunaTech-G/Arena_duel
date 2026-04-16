from pathlib import Path

import pygame

from game.asset_pipeline import load_font
from game.hud_panels import (
    choose_text_candidate,
    draw_end_team_card,
    draw_match_hud,
    get_shared_player_score_slot_width,
)
from game.arena import (
    draw_arena,
    draw_background,
    draw_orb_collection_effect,
    draw_orb_visual,
    draw_player_avatar,
    get_arena_rect,
    get_map_layout,
    get_obstacles,
    get_team_color,
)
from game.arena_layout import DEFAULT_MAP_ID
from game.match_text import (
    END_SCREEN_PLAYER_VALUE_LABEL,
    END_SCREEN_SUMMARY_LABEL,
    build_scoreline_candidates,
    format_winner_text,
    get_team_label,
    get_winner_team,
)
from game.settings import PLAYER_RADIUS, ORB_RADIUS
from network.messages import STATE, END, ERROR, DISCONNECTED
from game.audio import (
    init_audio,
    play_bonus_spawn,
    play_draw,
    play_lose,
    play_pickup,
    play_trap,
    play_win,
    stop_music,
)
from runtime_utils import get_app_icon_png_path


PG_QUIT = getattr(pygame, "QUIT")
PG_K_Z = getattr(pygame, "K_z")
PG_K_W = getattr(pygame, "K_w")
PG_K_UP = getattr(pygame, "K_UP")
PG_K_S = getattr(pygame, "K_s")
PG_K_DOWN = getattr(pygame, "K_DOWN")
PG_K_Q = getattr(pygame, "K_q")
PG_K_A = getattr(pygame, "K_a")
PG_K_LEFT = getattr(pygame, "K_LEFT")
PG_K_D = getattr(pygame, "K_d")
PG_K_RIGHT = getattr(pygame, "K_RIGHT")
PG_SRCALPHA = getattr(pygame, "SRCALPHA")
pg_init = getattr(pygame, "init")


def _tick_frame(clock, target_fps):
    tick_method = getattr(clock, "tick_busy_loop", None) or clock.tick
    return tick_method(target_fps)


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


def _default_sprite_id_for_team(team_code: str) -> str:
    if str(team_code or "A").strip().upper() == "B":
        return "skeleton_fighter_aether"
    return "skeleton_fighter_ember"


def _resolve_sprite_id(player_state: dict) -> str:
    sprite_id = str(player_state.get("sprite_id") or "").strip()
    if sprite_id:
        return sprite_id
    return _default_sprite_id_for_team(player_state.get("team", "A"))


def _normalize_direction_name(player_state: dict) -> str | None:
    direction_name = str(player_state.get("direction") or "").strip().lower()
    if direction_name in {"up", "down", "left", "right"}:
        return direction_name
    return None


def run_network_match(client, my_slot, my_name, my_team):
    pg_init()
    init_audio()
    stop_music(fade_ms=0)
    active_layout = get_map_layout(DEFAULT_MAP_ID)
    icon_path = get_app_icon_png_path(64)
    if Path(icon_path).exists():
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except OSError:
            pass
    screen = pygame.display.set_mode(
        active_layout.window_size,
        getattr(pygame, "RESIZABLE"),
    )
    pygame.display.set_caption(f"Arena Duel - Joute partagée \u00b7 {my_name}")
    clock = pygame.time.Clock()

    font = load_font("CrimsonText-Regular.ttf", 20, fallback_name="Georgia")
    medium_font = load_font(
        "Cinzel-Regular.ttf",
        26,
        fallback_name="Georgia",
        bold=True,
    )
    small_font = load_font(
        "CrimsonText-Regular.ttf",
        20,
        fallback_name="Georgia",
    )
    big_font = load_font(
        "Cinzel-Bold.ttf",
        38,
        fallback_name="Georgia",
        bold=True,
    )

    frame_surface = pygame.Surface(active_layout.window_size)

    latest_state = None
    end_message = None
    end_timer = 0
    deferred_messages = []
    disconnect_message = None
    last_error_message = None

    previous_positions = {}
    previous_scores = {}
    previous_pickup_serials = {}
    previous_trap_serials = {}
    previous_orbs = {}
    orb_effects = []
    orb_spawn_times = {}
    latest_movement = {}
    latest_facing = {}
    end_sound_played = False

    running = True

    while running and client.running:
        dt = _tick_frame(clock, 50) / 1000.0

        up = down = left = right = False

        for event in pygame.event.get():
            if event.type == PG_QUIT:
                disconnect_message = "Match fermé par le joueur."
                stop_music(fade_ms=120)
                client.close()
                running = False

        keys = pygame.key.get_pressed()
        up = keys[PG_K_Z] or keys[PG_K_W] or keys[PG_K_UP]
        down = keys[PG_K_S] or keys[PG_K_DOWN]
        left = keys[PG_K_Q] or keys[PG_K_A] or keys[PG_K_LEFT]
        right = keys[PG_K_D] or keys[PG_K_RIGHT]

        client.send_input(up, down, left, right)

        for msg in client.poll_messages():
            msg_type = msg.get("type")

            if msg_type == STATE:
                latest_movement = {}
                score_changed = False
                current_scores = {}
                next_pickup_serials = {}
                next_trap_serials = {}
                bonus_spawned = False
                current_ticks = pygame.time.get_ticks()
                for player_state in msg.get("players", []):
                    slot = player_state["slot"]
                    score = int(player_state.get("score", 0))
                    pickup_serial = int(player_state.get("last_pickup_serial", 0))
                    trap_serial = int(player_state.get("last_trap_serial", 0))
                    previous_pos = previous_positions.get(player_state["slot"])
                    server_is_moving = player_state.get("is_moving")
                    if server_is_moving is None:
                        latest_movement[slot] = previous_pos is not None and (
                            abs(player_state["x"] - previous_pos[0]) > 0.5
                            or abs(player_state["y"] - previous_pos[1]) > 0.5
                        )
                    else:
                        latest_movement[slot] = bool(server_is_moving)

                    default_facing = 1 if player_state.get("team") == "A" else -1
                    latest_facing[slot] = latest_facing.get(
                        slot,
                        default_facing,
                    )
                    direction_name = _normalize_direction_name(player_state)
                    if direction_name == "left":
                        latest_facing[slot] = -1
                    elif direction_name == "right":
                        latest_facing[slot] = 1

                    current_scores[slot] = score
                    next_pickup_serials[slot] = pickup_serial
                    next_trap_serials[slot] = trap_serial
                    if score > previous_scores.get(slot, score):
                        score_changed = True
                    if slot == my_slot and trap_serial > previous_trap_serials.get(
                        slot, 0
                    ):
                        play_trap()
                    if pickup_serial > previous_pickup_serials.get(slot, 0):
                        pickup = player_state.get("last_pickup") or {}
                        if int(pickup.get("value", 0)) > 0:
                            orb_effects.append(
                                {
                                    "x": float(pickup.get("x", player_state["x"])),
                                    "y": float(pickup.get("y", player_state["y"])),
                                    "value": int(pickup.get("value", 0)),
                                    "combo_count": int(pickup.get("combo_count", 0)),
                                    "combo_bonus": int(pickup.get("combo_bonus", 0)),
                                    "started_at_ms": current_ticks,
                                }
                            )
                previous_positions = {
                    player_state["slot"]: (
                        player_state["x"],
                        player_state["y"],
                    )
                    for player_state in msg.get("players", [])
                }
                previous_scores = current_scores
                previous_pickup_serials = next_pickup_serials
                previous_trap_serials = next_trap_serials
                if score_changed:
                    play_pickup()

                next_spawn_times = {}
                next_previous_orbs = {}
                for fallback_index, orb_state in enumerate(msg.get("orbs", [])):
                    orb_id = int(orb_state.get("orb_id", fallback_index))
                    previous_orb = previous_orbs.get(orb_id)
                    spawned_at_ms = orb_spawn_times.get(orb_id, current_ticks)
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
                            if str(orb_state.get("variant") or "") == "rare":
                                bonus_spawned = True

                    orb_state["_local_spawned_at_ms"] = spawned_at_ms
                    next_spawn_times[orb_id] = spawned_at_ms
                    next_previous_orbs[orb_id] = dict(orb_state)

                previous_orbs = next_previous_orbs
                orb_spawn_times = next_spawn_times
                if bonus_spawned:
                    play_bonus_spawn()
                latest_state = msg
                active_layout = get_map_layout(msg.get("map_id", DEFAULT_MAP_ID))
                if frame_surface.get_size() != active_layout.window_size:
                    frame_surface = pygame.Surface(active_layout.window_size)

            elif msg_type == END:
                end_message = msg
                end_timer = 1.2
                stop_music(fade_ms=280)

            elif msg_type == ERROR:
                last_error_message = msg.get(
                    "message",
                    "Le hall a signale une alerte.",
                )

            elif msg_type == DISCONNECTED:
                disconnect_message = msg.get(
                    "message",
                    "Le lien au hall s'est rompu.",
                )
                stop_music(fade_ms=120)
                running = False

            else:
                deferred_messages.append(msg)

        draw_background(frame_surface, active_layout)

        if latest_state:
            draw_state(
                frame_surface,
                latest_state,
                my_slot,
                font,
                big_font,
                medium_font,
                small_font,
                active_layout,
                latest_movement,
                latest_facing,
                orb_effects,
            )

        if end_message:
            if not end_sound_played:
                winner_team = end_message.get("winner_team")
                local_team = _resolve_local_team(
                    my_team,
                    my_slot,
                    end_message,
                    latest_state,
                )
                if winner_team is None:
                    winner_team = get_winner_team(
                        end_message.get("team_a_score", 0),
                        end_message.get("team_b_score", 0),
                    )

                if winner_team is None:
                    play_draw()
                elif local_team and winner_team == local_team:
                    play_win()
                else:
                    play_lose()

                end_sound_played = True

            draw_end_overlay(
                frame_surface,
                end_message,
                big_font,
                medium_font,
                small_font,
            )
            end_timer -= dt
            if end_timer <= 0:
                running = False

        sw, sh = screen.get_size()
        screen.fill((10, 13, 19))
        base_w, base_h = frame_surface.get_size()
        scale = min(sw / base_w, sh / base_h)
        if scale <= 1.001:
            blit_x = max(0, (sw - base_w) // 2)
            blit_y = max(0, (sh - base_h) // 2)
            screen.blit(frame_surface, (blit_x, blit_y))
        else:
            target_size = (
                max(1, int(base_w * scale)),
                max(1, int(base_h * scale)),
            )
            scaled_surface = pygame.transform.smoothscale(
                frame_surface,
                target_size,
            )
            blit_x = max(0, (sw - target_size[0]) // 2)
            blit_y = max(0, (sh - target_size[1]) // 2)
            screen.blit(scaled_surface, (blit_x, blit_y))

        pygame.display.flip()

    pygame.display.quit()
    stop_music(fade_ms=120)
    if end_message is not None:
        return {
            "completed": True,
            "end_message": end_message,
            "deferred_messages": deferred_messages,
            "disconnect_message": None,
        }

    return {
        "completed": False,
        "end_message": None,
        "deferred_messages": deferred_messages,
        "disconnect_message": (
            disconnect_message or last_error_message or "Le lien au hall s'est rompu."
        ),
    }


def draw_state(
    screen,
    state,
    my_slot,
    font,
    big_font,
    _medium_font,
    small_font,
    layout,
    movement_flags=None,
    facing_by_slot=None,
    orb_effects=None,
):
    movement_flags = movement_flags or {}
    facing_by_slot = facing_by_slot or {}
    orb_effects = orb_effects or []
    elapsed_ms = pygame.time.get_ticks()
    arena_rect = get_arena_rect(layout)
    obstacles = get_obstacles(layout)
    draw_arena(
        screen,
        arena_rect,
        obstacles,
        layout=layout,
        trap_states=state.get("traps"),
        elapsed_ms=elapsed_ms,
    )

    team_a = state.get("team_a_score", 0)
    team_b = state.get("team_b_score", 0)
    remaining = state.get("remaining_time", 0)

    team_a_rows = []
    team_b_rows = []
    for p in sorted(
        state.get("players", []),
        key=lambda item: item.get("slot", 0),
    ):
        sprite_id = _resolve_sprite_id(p)
        row = {
            "name": p["name"],
            "player_score": p["score"],
            "accent_color": get_team_color(p["team"], max(0, p["slot"] - 1)),
            "sprite_id": sprite_id,
        }
        if p["team"] == "A":
            team_a_rows.append(row)
        else:
            team_b_rows.append(row)

    draw_match_hud(
        screen,
        big_font,
        small_font,
        layout,
        team_a_title=get_team_label("A"),
        team_b_title=get_team_label("B"),
        team_a_score=team_a,
        team_b_score=team_b,
        remaining_time=remaining,
        team_a_rows=team_a_rows,
        team_b_rows=team_b_rows,
    )

    for orb in state.get("orbs", []):
        draw_orb_visual(
            screen,
            orb["x"],
            orb["y"],
            ORB_RADIUS,
            elapsed_ms=elapsed_ms,
            value=int(orb.get("value", 1)),
            variant=str(orb.get("variant", "common")),
            spawned_at_ms=orb.get("_local_spawned_at_ms"),
        )

    for p in state.get("players", []):
        accent_color = get_team_color(p["team"], max(0, p["slot"] - 1))
        sprite_id = _resolve_sprite_id(p)
        default_facing = 1 if p["team"] == "A" else -1
        draw_player_avatar(
            screen,
            name=p["name"],
            x=p["x"],
            y=p["y"],
            radius=PLAYER_RADIUS,
            accent_color=accent_color,
            name_font=font,
            sprite_id=sprite_id,
            highlight=p["slot"] == my_slot,
            team_code=p["team"],
            facing=facing_by_slot.get(p["slot"], default_facing),
            direction_name=_normalize_direction_name(p),
            elapsed_ms=elapsed_ms,
            moving=movement_flags.get(
                p["slot"],
                bool(p.get("is_moving", False)),
            ),
            combo_count=int(p.get("combo_count", 0)),
            combo_remaining_ms=int(p.get("combo_remaining_ms", 0)),
        )

    active_orb_effects = []
    for effect in orb_effects:
        if draw_orb_collection_effect(
            screen,
            x=effect["x"],
            y=effect["y"],
            value=effect["value"],
            elapsed_ms=elapsed_ms,
            started_at_ms=effect["started_at_ms"],
            combo_count=effect.get("combo_count", 0),
            combo_bonus=effect.get("combo_bonus", 0),
        ):
            active_orb_effects.append(effect)
    orb_effects[:] = active_orb_effects


def draw_end_overlay(screen, end_message, big_font, medium_font, small_font):
    width, height = screen.get_size()

    overlay = pygame.Surface((width, height), PG_SRCALPHA)
    overlay.fill((0, 0, 0, 182))
    screen.blit(overlay, (0, 0))

    winner_team = end_message.get("winner_team")
    if winner_team is None:
        winner_team = get_winner_team(
            end_message.get("team_a_score", 0),
            end_message.get("team_b_score", 0),
        )

    winner = end_message.get("winner_text") or format_winner_text(winner_team)
    summary_metric_label = (
        end_message.get("summary_metric_label") or END_SCREEN_SUMMARY_LABEL
    )
    team_panel_value_label = (
        end_message.get("team_panel_value_label") or END_SCREEN_PLAYER_VALUE_LABEL
    )
    players = sorted(
        end_message.get("players", []),
        key=lambda item: item.get("slot", 0),
    )

    team_a_score = end_message.get("team_a_score", 0)
    team_b_score = end_message.get("team_b_score", 0)
    team_a_rows = []
    team_b_rows = []
    for player in players:
        sprite_id = _resolve_sprite_id(player)
        row = {
            "name": player.get("name", "Combattant"),
            "player_score": player.get("score", 0),
            "accent_color": get_team_color(
                player.get("team", "A"),
                max(0, player.get("slot", 1) - 1),
            ),
            "sprite_id": sprite_id,
        }
        if player.get("team") == "A":
            team_a_rows.append(row)
        else:
            team_b_rows.append(row)

    max_team_size = max(1, len(team_a_rows), len(team_b_rows))
    panel_width = min(920, width - 48)
    header_height = 126
    row_gap = 8
    available_rows_height = max(150, height - header_height - 124)
    row_height = max(
        40,
        min(
            48,
            int(
                (available_rows_height - 72 - row_gap * (max_team_size - 1))
                / max_team_size
            ),
        ),
    )
    portrait_size = max(30, min(36, row_height - 10))
    card_height = 62 + max_team_size * row_height
    card_height += max(0, max_team_size - 1) * row_gap
    card_height += 16
    panel_height = min(
        height - 40,
        max(380, header_height + card_height + 88),
    )
    panel_x = (width - panel_width) // 2
    panel_y = (height - panel_height) // 2
    side_padding = max(24, min(36, panel_width // 24))
    column_gap = max(20, min(32, panel_width // 28))
    column_width = (panel_width - side_padding * 2 - column_gap) // 2

    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    pygame.draw.rect(screen, (34, 38, 46), panel_rect, border_radius=18)
    pygame.draw.rect(
        screen,
        (108, 130, 178),
        panel_rect,
        width=3,
        border_radius=18,
    )

    txt1 = big_font.render(winner, True, (255, 255, 255))
    score_text = choose_text_candidate(
        medium_font,
        build_scoreline_candidates(team_a_score, team_b_score),
        panel_width - 80,
    )
    summary_surface = small_font.render(
        summary_metric_label,
        True,
        (175, 192, 220),
    )
    txt2 = medium_font.render(score_text, True, (190, 210, 255))

    screen.blit(txt1, (width // 2 - txt1.get_width() // 2, panel_y + 30))
    screen.blit(
        summary_surface,
        (
            width // 2 - summary_surface.get_width() // 2,
            panel_y + 72,
        ),
    )
    screen.blit(txt2, (width // 2 - txt2.get_width() // 2, panel_y + 96))

    team_a_rect = pygame.Rect(
        panel_x + side_padding,
        panel_y + header_height,
        column_width,
        card_height,
    )
    team_b_rect = pygame.Rect(
        team_a_rect.right + column_gap,
        panel_y + header_height,
        column_width,
        card_height,
    )

    shared_score_slot_width = get_shared_player_score_slot_width(
        small_font,
        team_a_rect.width - 20,
        team_a_rows,
        team_b_rows,
        team_a_score,
        team_b_score,
    )

    draw_end_team_card(
        screen,
        medium_font,
        small_font,
        team_a_rect,
        title=get_team_label("A"),
        rows=team_a_rows,
        align="left",
        border_color=(243, 201, 107),
        team_score=team_a_score,
        row_height=row_height,
        row_gap=row_gap,
        portrait_size=portrait_size,
        row_value_label=team_panel_value_label,
        score_format_mode="grouped",
        score_slot_width=shared_score_slot_width,
    )
    draw_end_team_card(
        screen,
        medium_font,
        small_font,
        team_b_rect,
        title=get_team_label("B"),
        rows=team_b_rows,
        align="right",
        border_color=(100, 215, 255),
        team_score=team_b_score,
        row_height=row_height,
        row_gap=row_gap,
        portrait_size=portrait_size,
        row_value_label=team_panel_value_label,
        score_format_mode="grouped",
        score_slot_width=shared_score_slot_width,
    )

    if end_message.get("history_saved", False):
        match_id = end_message.get("match_id")
        if match_id is not None:
            history_text = f"Chronique du hall scellée · joute #{match_id}"
        else:
            history_text = "Chronique du hall scellée"
        history_color = (206, 228, 194)
    else:
        history_error = end_message.get("history_error")
        if history_error:
            history_text = f"Chronique du hall indisponible · {history_error}"
        else:
            history_text = "Chronique du hall indisponible"
        history_color = (255, 188, 166)

    status_text = small_font.render(history_text, True, history_color)
    return_text = small_font.render(
        "Retour au hall dans un instant...",
        True,
        (220, 220, 220),
    )

    screen.blit(
        status_text,
        (
            width // 2 - status_text.get_width() // 2,
            panel_rect.bottom - 52,
        ),
    )
    screen.blit(
        return_text,
        (
            width // 2 - return_text.get_width() // 2,
            panel_rect.bottom - 30,
        ),
    )
