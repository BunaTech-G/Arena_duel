from pathlib import Path

import pygame

from game.asset_pipeline import load_font
from game.hud_panels import (
    choose_text_candidate,
    compute_end_overlay_layout,
    draw_end_team_card,
    draw_match_event_banner,
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
    format_pickup_event,
    format_trap_event,
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
PG_K_RETURN = getattr(pygame, "K_RETURN")
PG_K_SPACE = getattr(pygame, "K_SPACE")
PG_K_ESCAPE = getattr(pygame, "K_ESCAPE")
PG_KEYDOWN = getattr(pygame, "KEYDOWN")
PG_SRCALPHA = getattr(pygame, "SRCALPHA")
pg_init = getattr(pygame, "init")


END_OVERLAY_DURATION_SECONDS = 4.5
END_OVERLAY_SKIP_KEYS = {PG_K_RETURN, PG_K_SPACE, PG_K_ESCAPE}
MATCH_EVENT_BANNER_DURATION_MS = 1650


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


def _build_network_player_row(
    player_state: dict,
    *,
    my_slot: int | None = None,
) -> dict:
    slot = int(player_state.get("slot", 0) or 0)
    return {
        "name": player_state.get("name", "Combattant"),
        "player_score": int(player_state.get("score", 0)),
        "accent_color": get_team_color(
            player_state.get("team", "A"),
            max(0, slot - 1),
        ),
        "sprite_id": _resolve_sprite_id(player_state),
        "is_focus": my_slot is not None and slot == my_slot,
    }


def _build_network_team_rows(
    player_states,
    *,
    my_slot: int | None = None,
) -> tuple[list[dict], list[dict]]:
    team_a_rows = []
    team_b_rows = []

    for player_state in sorted(
        player_states,
        key=lambda item: item.get("slot", 0),
    ):
        row = _build_network_player_row(player_state, my_slot=my_slot)
        if player_state.get("team") == "A":
            team_a_rows.append(row)
        else:
            team_b_rows.append(row)

    return team_a_rows, team_b_rows


def _build_network_hud_payload(state: dict, my_slot: int) -> dict:
    team_a_rows, team_b_rows = _build_network_team_rows(
        state.get("players", []),
        my_slot=my_slot,
    )
    return {
        "team_a_score": state.get("team_a_score", 0),
        "team_b_score": state.get("team_b_score", 0),
        "remaining_time": state.get("remaining_time", 0),
        "team_a_rows": team_a_rows,
        "team_b_rows": team_b_rows,
    }


def _build_network_end_overlay_payload(
    end_message: dict,
    my_slot: int | None = None,
) -> dict:
    winner_team = end_message.get("winner_team")
    if winner_team is None:
        winner_team = get_winner_team(
            end_message.get("team_a_score", 0),
            end_message.get("team_b_score", 0),
        )

    team_a_rows, team_b_rows = _build_network_team_rows(
        end_message.get("players", []),
        my_slot=my_slot,
    )
    return {
        "winner_text": end_message.get("winner_text")
        or format_winner_text(winner_team),
        "summary_metric_label": end_message.get("summary_metric_label")
        or END_SCREEN_SUMMARY_LABEL,
        "team_panel_value_label": end_message.get("team_panel_value_label")
        or END_SCREEN_PLAYER_VALUE_LABEL,
        "team_a_score": end_message.get("team_a_score", 0),
        "team_b_score": end_message.get("team_b_score", 0),
        "team_a_rows": team_a_rows,
        "team_b_rows": team_b_rows,
        "max_team_size": max(1, len(team_a_rows), len(team_b_rows)),
    }


def _select_network_event_banner(
    current_banner: dict | None,
    next_banner: dict | None,
) -> dict | None:
    if next_banner is None:
        return current_banner
    if current_banner is None:
        return next_banner

    current_priority = int(current_banner.get("priority", 0))
    next_priority = int(next_banner.get("priority", 0))
    if next_priority > current_priority:
        return next_banner
    if next_priority < current_priority:
        return current_banner

    current_until = int(current_banner.get("until_ms", 0))
    next_until = int(next_banner.get("until_ms", 0))
    if next_until > current_until:
        return next_banner
    if next_until < current_until:
        return current_banner

    return next_banner


def _build_network_trap_banner(player_state: dict, elapsed_ms: int) -> dict:
    slot = int(player_state.get("slot", 0) or 0)
    return {
        "message": format_trap_event(
            player_state.get("name", "Combattant"),
            player_state.get("team"),
            trap_kind=player_state.get("last_trap_kind"),
        ),
        "accent_color": get_team_color(
            player_state.get("team", "A"),
            max(0, slot - 1),
        ),
        "until_ms": elapsed_ms + MATCH_EVENT_BANNER_DURATION_MS,
        "priority": 2,
    }


def _build_network_pickup_banner(
    player_state: dict,
    pickup: dict,
    elapsed_ms: int,
) -> dict | None:
    pickup_value = int(pickup.get("value", 0))
    if pickup_value <= 0:
        return None

    slot = int(player_state.get("slot", 0) or 0)
    variant = pickup.get("variant")
    combo_bonus = int(pickup.get("combo_bonus", 0))
    normalized_variant = str(variant or "").strip().lower()
    priority = 4 if normalized_variant == "rare" else 3 if combo_bonus > 0 else 1
    return {
        "message": format_pickup_event(
            player_state.get("name", "Combattant"),
            player_state.get("team"),
            pickup_value,
            combo_count=int(pickup.get("combo_count", 0)),
            combo_bonus=combo_bonus,
            variant=variant,
        ),
        "accent_color": get_team_color(
            player_state.get("team", "A"),
            max(0, slot - 1),
        ),
        "until_ms": elapsed_ms + MATCH_EVENT_BANNER_DURATION_MS,
        "priority": priority,
    }


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
    previous_pickup_serials = {}
    previous_trap_serials = {}
    previous_orbs = {}
    orb_effects = []
    orb_spawn_times = {}
    event_banner = None
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
            elif (
                end_message is not None
                and event.type == PG_KEYDOWN
                and getattr(event, "key", None) in END_OVERLAY_SKIP_KEYS
            ):
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
                next_pickup_serials = {}
                next_trap_serials = {}
                bonus_spawned = False
                current_ticks = pygame.time.get_ticks()
                if event_banner and current_ticks > int(
                    event_banner.get("until_ms", 0)
                ):
                    event_banner = None
                for player_state in msg.get("players", []):
                    slot = player_state["slot"]
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

                    next_pickup_serials[slot] = pickup_serial
                    next_trap_serials[slot] = trap_serial
                    if slot == my_slot and trap_serial > previous_trap_serials.get(
                        slot, 0
                    ):
                        play_trap(trap_kind=player_state.get("last_trap_kind"))
                        event_banner = _select_network_event_banner(
                            event_banner,
                            _build_network_trap_banner(player_state, current_ticks),
                        )
                    if pickup_serial > previous_pickup_serials.get(slot, 0):
                        pickup = player_state.get("last_pickup") or {}
                        if int(pickup.get("value", 0)) > 0:
                            orb_effects.append(
                                {
                                    "x": float(pickup.get("x", player_state["x"])),
                                    "y": float(pickup.get("y", player_state["y"])),
                                    "value": int(pickup.get("value", 0)),
                                    "variant": pickup.get("variant"),
                                    "combo_count": int(pickup.get("combo_count", 0)),
                                    "combo_bonus": int(pickup.get("combo_bonus", 0)),
                                    "started_at_ms": current_ticks,
                                }
                            )
                        if int(pickup.get("value", 0)) > 0 and slot == my_slot:
                            play_pickup(
                                combo_bonus=int(pickup.get("combo_bonus", 0)),
                                variant=pickup.get("variant"),
                            )
                            event_banner = _select_network_event_banner(
                                event_banner,
                                _build_network_pickup_banner(
                                    player_state,
                                    pickup,
                                    current_ticks,
                                ),
                            )
                previous_positions = {
                    player_state["slot"]: (
                        player_state["x"],
                        player_state["y"],
                    )
                    for player_state in msg.get("players", [])
                }
                previous_pickup_serials = next_pickup_serials
                previous_trap_serials = next_trap_serials

                next_spawn_times = {}
                next_previous_orbs = {}
                for fallback_index, orb_state in enumerate(msg.get("orbs", [])):
                    orb_id = int(orb_state.get("orb_id", fallback_index))
                    previous_orb = previous_orbs.get(orb_id)
                    spawned_at_ms = orb_spawn_times.get(orb_id, current_ticks)
                    if previous_orb is None:
                        spawned_at_ms = current_ticks
                        if (
                            latest_state is not None
                            and str(orb_state.get("variant") or "") == "rare"
                        ):
                            bonus_spawned = True
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
                end_timer = END_OVERLAY_DURATION_SECONDS
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
            if event_banner and pygame.time.get_ticks() > event_banner["until_ms"]:
                event_banner = None
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
                event_banner,
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
                my_slot=my_slot,
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
    event_banner=None,
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

    hud_payload = _build_network_hud_payload(state, my_slot)

    draw_match_hud(
        screen,
        big_font,
        small_font,
        layout,
        team_a_title=get_team_label("A"),
        team_b_title=get_team_label("B"),
        team_a_score=hud_payload["team_a_score"],
        team_b_score=hud_payload["team_b_score"],
        remaining_time=hud_payload["remaining_time"],
        team_a_rows=hud_payload["team_a_rows"],
        team_b_rows=hud_payload["team_b_rows"],
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
            variant=effect.get("variant"),
            elapsed_ms=elapsed_ms,
            started_at_ms=effect["started_at_ms"],
            combo_count=effect.get("combo_count", 0),
            combo_bonus=effect.get("combo_bonus", 0),
        ):
            active_orb_effects.append(effect)
    orb_effects[:] = active_orb_effects

    if event_banner:
        draw_match_event_banner(
            screen,
            small_font,
            event_banner.get("message", ""),
            accent_color=tuple(event_banner.get("accent_color", (242, 209, 118))),
        )


def draw_end_overlay(
    screen,
    end_message,
    big_font,
    medium_font,
    small_font,
    my_slot: int | None = None,
):
    width, height = screen.get_size()
    payload = _build_network_end_overlay_payload(end_message, my_slot=my_slot)

    overlay = pygame.Surface((width, height), PG_SRCALPHA)
    overlay.fill((0, 0, 0, 182))
    screen.blit(overlay, (0, 0))

    overlay_layout = compute_end_overlay_layout(
        (width, height),
        payload["max_team_size"],
        footer_height=88,
        min_panel_height=380,
        min_available_rows_height=150,
    )
    panel_rect = overlay_layout["panel_rect"]
    pygame.draw.rect(screen, (34, 38, 46), panel_rect, border_radius=18)
    pygame.draw.rect(
        screen,
        (108, 130, 178),
        panel_rect,
        width=3,
        border_radius=18,
    )

    txt1 = big_font.render(payload["winner_text"], True, (255, 255, 255))
    score_text = choose_text_candidate(
        medium_font,
        build_scoreline_candidates(
            payload["team_a_score"],
            payload["team_b_score"],
        ),
        panel_rect.width - 80,
    )
    summary_surface = small_font.render(
        payload["summary_metric_label"],
        True,
        (175, 192, 220),
    )
    txt2 = medium_font.render(score_text, True, (190, 210, 255))

    screen.blit(txt1, (width // 2 - txt1.get_width() // 2, panel_rect.y + 30))
    screen.blit(
        summary_surface,
        (
            width // 2 - summary_surface.get_width() // 2,
            panel_rect.y + 72,
        ),
    )
    screen.blit(txt2, (width // 2 - txt2.get_width() // 2, panel_rect.y + 96))

    team_a_rect = overlay_layout["team_a_rect"]
    team_b_rect = overlay_layout["team_b_rect"]

    shared_score_slot_width = get_shared_player_score_slot_width(
        small_font,
        team_a_rect.width - 20,
        payload["team_a_rows"],
        payload["team_b_rows"],
        payload["team_a_score"],
        payload["team_b_score"],
    )

    draw_end_team_card(
        screen,
        medium_font,
        small_font,
        team_a_rect,
        title=get_team_label("A"),
        rows=payload["team_a_rows"],
        align="left",
        border_color=(243, 201, 107),
        team_score=payload["team_a_score"],
        row_height=overlay_layout["row_height"],
        row_gap=overlay_layout["row_gap"],
        portrait_size=overlay_layout["portrait_size"],
        row_value_label=payload["team_panel_value_label"],
        score_format_mode="grouped",
        score_slot_width=shared_score_slot_width,
    )
    draw_end_team_card(
        screen,
        medium_font,
        small_font,
        team_b_rect,
        title=get_team_label("B"),
        rows=payload["team_b_rows"],
        align="right",
        border_color=(100, 215, 255),
        team_score=payload["team_b_score"],
        row_height=overlay_layout["row_height"],
        row_gap=overlay_layout["row_gap"],
        portrait_size=overlay_layout["portrait_size"],
        row_value_label=payload["team_panel_value_label"],
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
        "Entrée, Espace ou Échap pour revenir.",
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
