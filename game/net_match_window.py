from pathlib import Path

import pygame

from game.asset_pipeline import load_font
from game.hud_panels import draw_match_hud, draw_team_summary_panel
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
    format_scoreline,
    format_winner_text,
    get_team_label,
    get_winner_team,
)
from game.settings import PLAYER_RADIUS, ORB_RADIUS
from network.messages import STATE, END, ERROR, DISCONNECTED
from game.audio import (
    init_audio,
    play_draw,
    play_lose,
    play_pickup,
    play_win,
    start_match_music,
    stop_music,
)
from runtime_utils import resource_path


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


def run_network_match(client, my_slot, my_name, my_team):
    pg_init()
    init_audio()
    stop_music(fade_ms=0)
    start_match_music(restart=True)
    active_layout = get_map_layout(DEFAULT_MAP_ID)
    icon_path = resource_path("assets", "icons", "app.png")
    if Path(icon_path).exists():
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except OSError:
            pass
    screen = pygame.display.set_mode(active_layout.window_size)
    pygame.display.set_caption(f"Arena Duel - Joute partagee \u00b7 {my_name}")
    clock = pygame.time.Clock()

    font = load_font("CrimsonText-Regular.ttf", 20, fallback_name="Georgia")
    medium_font = load_font(
        "Cinzel-Regular.ttf",
        24,
        fallback_name="Georgia",
        bold=True,
    )
    small_font = load_font(
        "CrimsonText-Regular.ttf",
        18,
        fallback_name="Georgia",
    )
    big_font = load_font(
        "Cinzel-Bold.ttf",
        36,
        fallback_name="Georgia",
        bold=True,
    )

    latest_state = None
    end_message = None
    end_timer = 0
    deferred_messages = []
    disconnect_message = None
    last_error_message = None

    previous_positions = {}
    previous_scores = {}
    previous_pickup_serials = {}
    previous_orbs = {}
    orb_effects = []
    orb_spawn_times = {}
    latest_movement = {}
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
                current_ticks = pygame.time.get_ticks()
                for player_state in msg.get("players", []):
                    slot = player_state["slot"]
                    score = int(player_state.get("score", 0))
                    pickup_serial = int(player_state.get("last_pickup_serial", 0))
                    previous_pos = previous_positions.get(player_state["slot"])
                    latest_movement[slot] = previous_pos is not None and (
                        abs(player_state["x"] - previous_pos[0]) > 0.5
                        or abs(player_state["y"] - previous_pos[1]) > 0.5
                    )
                    current_scores[slot] = score
                    next_pickup_serials[slot] = pickup_serial
                    if score > previous_scores.get(slot, score):
                        score_changed = True
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

                    orb_state["_local_spawned_at_ms"] = spawned_at_ms
                    next_spawn_times[orb_id] = spawned_at_ms
                    next_previous_orbs[orb_id] = dict(orb_state)

                previous_orbs = next_previous_orbs
                orb_spawn_times = next_spawn_times
                latest_state = msg
                active_layout = get_map_layout(msg.get("map_id", DEFAULT_MAP_ID))

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

        draw_background(screen, active_layout)

        if latest_state:
            draw_state(
                screen,
                latest_state,
                my_slot,
                font,
                big_font,
                medium_font,
                small_font,
                active_layout,
                latest_movement,
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
                screen,
                end_message,
                big_font,
                medium_font,
                small_font,
            )
            end_timer -= dt
            if end_timer <= 0:
                running = False

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
    orb_effects=None,
):
    movement_flags = movement_flags or {}
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
        if p["team"] == "A":
            sprite_id = "skeleton_fighter_ember"
        else:
            sprite_id = "skeleton_fighter_aether"
        row = {
            "name": p["name"],
            "score": p["score"],
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
        if p["team"] == "A":
            sprite_id = "skeleton_fighter_ember"
        else:
            sprite_id = "skeleton_fighter_aether"
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
            facing=1 if p["team"] == "A" else -1,
            elapsed_ms=elapsed_ms,
            moving=movement_flags.get(p["slot"], False),
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
    score_text = format_scoreline(
        end_message.get("team_a_score", 0),
        end_message.get("team_b_score", 0),
    )
    players = sorted(
        end_message.get("players", []),
        key=lambda item: item.get("slot", 0),
    )

    panel_width = 860
    panel_height = 360
    panel_x = (width - panel_width) // 2
    panel_y = (height - panel_height) // 2

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
    txt2 = medium_font.render(score_text, True, (190, 210, 255))

    screen.blit(txt1, (width // 2 - txt1.get_width() // 2, panel_y + 30))
    screen.blit(txt2, (width // 2 - txt2.get_width() // 2, panel_y + 84))

    team_a_rows = []
    team_b_rows = []
    for player in players:
        sprite_id = (
            "skeleton_fighter_ember"
            if player.get("team") == "A"
            else "skeleton_fighter_aether"
        )
        row = {
            "name": player.get("name", "Combattant"),
            "score": player.get("score", 0),
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

    draw_team_summary_panel(
        screen,
        small_font,
        panel_x + 54,
        panel_y + 128,
        get_team_label("A"),
        team_a_rows,
        align="left",
    )
    draw_team_summary_panel(
        screen,
        small_font,
        panel_x + 558,
        panel_y + 128,
        get_team_label("B"),
        team_b_rows,
        align="right",
    )

    if end_message.get("history_saved", False):
        match_id = end_message.get("match_id")
        if match_id is not None:
            history_text = f"Chronique du hall scellee · joute #{match_id}"
        else:
            history_text = "Chronique du hall scellee"
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
        (width // 2 - status_text.get_width() // 2, panel_y + 316),
    )
    screen.blit(
        return_text,
        (width // 2 - return_text.get_width() // 2, panel_y + 336),
    )
