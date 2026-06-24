from datetime import datetime
from pathlib import Path

import pygame

from hardware.service import create_match_hardware_service
from runtime_utils import get_app_icon_png_path
from game.asset_pipeline import load_font
from game.computer_opponent import BotController
from game.control_models import AI_CONTROL_MODE, HUMAN_CONTROL_MODE
from game.hud_panels import (
    choose_text_candidate,
    compute_end_overlay_layout,
    draw_end_team_card,
    draw_match_event_banner,
    draw_match_hud,
    get_shared_player_score_slot_width,
)
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
from game.settings import (
    FPS,
    PLAYER_SLOT_CONTROLS,
    TEAM_A_COLORS,
    TEAM_B_COLORS,
    ORB_SPAWN_COUNT,
    MATCH_DURATION_SECONDS,
    coerce_match_duration,
)
from game.player import Player
from game.orb import Orb
from game.arena import (
    draw_background,
    draw_arena,
    draw_orb_collection_effect,
    get_arena_rect,
    get_map_layout,
    get_obstacles,
    get_team_spawn_positions_for_layout,
)
from game.traps import (
    build_match_traps,
    snapshot_match_traps,
    update_match_traps,
)
from game.audio import init_audio, play_bonus_spawn, play_draw, play_trap
from game.audio import play_win, stop_music
from game.audio import play_lose, play_pickup


PG_KEYDOWN = getattr(pygame, "KEYDOWN")
PG_K_ESCAPE = getattr(pygame, "K_ESCAPE")
PG_K_RETURN = getattr(pygame, "K_RETURN")
PG_K_R = getattr(pygame, "K_r")
PG_QUIT = getattr(pygame, "QUIT")
PG_RESIZABLE = getattr(pygame, "RESIZABLE")
PG_SRCALPHA = getattr(pygame, "SRCALPHA")
pg_init = getattr(pygame, "init")
pg_quit = getattr(pygame, "quit")


MATCH_EVENT_BANNER_DURATION_MS = 1650


def _tick_frame(clock, target_fps):
    tick_method = getattr(clock, "tick_busy_loop", None) or clock.tick
    return tick_method(target_fps)


def _present_game_surface(screen, game_surface, game_size):
    game_w, game_h = game_size
    sw, sh = screen.get_size()
    screen.fill((10, 13, 19))
    scale = min(sw / game_w, sh / game_h)
    if scale <= 1.001:
        blit_x = max(0, (sw - game_w) // 2)
        blit_y = max(0, (sh - game_h) // 2)
        screen.blit(game_surface, (blit_x, blit_y))
        return

    target_size = (
        max(1, int(game_w * scale)),
        max(1, int(game_h * scale)),
    )
    scaled_surface = pygame.transform.smoothscale(
        game_surface,
        target_size,
    )
    blit_x = max(0, (sw - target_size[0]) // 2)
    blit_y = max(0, (sh - target_size[1]) // 2)
    screen.blit(scaled_surface, (blit_x, blit_y))


def _draw_loading_frame(
    screen,
    game_surface,
    layout,
    arena_rect,
    obstacles,
    big_font,
    small_font,
):
    draw_background(game_surface, layout)
    draw_arena(
        game_surface,
        arena_rect,
        obstacles,
        layout=layout,
        elapsed_ms=0.0,
    )

    panel_rect = pygame.Rect(0, 0, 420, 112)
    panel_rect.center = (layout.window_size[0] // 2, 132)
    panel_surface = pygame.Surface(panel_rect.size, PG_SRCALPHA)
    pygame.draw.rect(
        panel_surface,
        (14, 18, 28, 214),
        panel_surface.get_rect(),
        border_radius=18,
    )
    pygame.draw.rect(
        panel_surface,
        (222, 194, 120, 228),
        panel_surface.get_rect(),
        width=2,
        border_radius=18,
    )
    game_surface.blit(panel_surface, panel_rect.topleft)

    title_surface = big_font.render(
        "Chargement du combat",
        True,
        (244, 236, 214),
    )
    subtitle_surface = small_font.render(
        "Preparation de l'arene et des combattants...",
        True,
        (187, 201, 224),
    )
    game_surface.blit(
        title_surface,
        title_surface.get_rect(center=(panel_rect.centerx, panel_rect.y + 38)),
    )
    game_surface.blit(
        subtitle_surface,
        subtitle_surface.get_rect(
            center=(panel_rect.centerx, panel_rect.y + 76),
        ),
    )

    _present_game_surface(screen, game_surface, layout.window_size)
    pygame.display.flip()
    pygame.event.pump()


def get_local_focus_team(players):
    human_teams = {
        player.team_code
        for player in players
        if player.control_mode == HUMAN_CONTROL_MODE
    }
    ai_teams = {
        player.team_code for player in players if player.control_mode == AI_CONTROL_MODE
    }

    if len(human_teams) == 1 and len(ai_teams) == 1:
        return next(iter(human_teams))

    return None


def build_runtime_players(players_config, layout):
    team_a = [p for p in players_config if p["team"] == "A"]
    team_b = [p for p in players_config if p["team"] == "B"]

    players = []
    ai_controllers = {}

    team_a_positions = get_team_spawn_positions_for_layout(
        layout,
        "A",
        len(team_a),
    )
    team_b_positions = get_team_spawn_positions_for_layout(
        layout,
        "B",
        len(team_b),
    )

    for idx, player_data in enumerate(team_a):
        slot_index = player_data["slot"] - 1
        control_mode = str(player_data.get("control_mode", HUMAN_CONTROL_MODE)).lower()
        controls = None
        if control_mode == HUMAN_CONTROL_MODE:
            controls = PLAYER_SLOT_CONTROLS[slot_index]
        color = TEAM_A_COLORS[idx % len(TEAM_A_COLORS)]
        x, y = team_a_positions[idx]

        player = Player(
            name=player_data["name"],
            x=x,
            y=y,
            color=color,
            controls=controls,
            team_code="A",
            control_mode=control_mode,
            sprite_id=player_data.get("sprite_id"),
        )
        players.append(player)
        if control_mode == AI_CONTROL_MODE:
            ai_controllers[player] = BotController(
                profile=str(player_data.get("ai_profile", "orb_hunter")),
                difficulty=str(player_data.get("ai_difficulty", "standard")),
                seed=(slot_index + 1) * 97,
            )

    for idx, player_data in enumerate(team_b):
        slot_index = player_data["slot"] - 1
        control_mode = str(player_data.get("control_mode", HUMAN_CONTROL_MODE)).lower()
        controls = None
        if control_mode == HUMAN_CONTROL_MODE:
            controls = PLAYER_SLOT_CONTROLS[slot_index]
        color = TEAM_B_COLORS[idx % len(TEAM_B_COLORS)]
        x, y = team_b_positions[idx]

        player = Player(
            name=player_data["name"],
            x=x,
            y=y,
            color=color,
            controls=controls,
            team_code="B",
            control_mode=control_mode,
            sprite_id=player_data.get("sprite_id"),
        )
        players.append(player)
        if control_mode == AI_CONTROL_MODE:
            ai_controllers[player] = BotController(
                profile=str(player_data.get("ai_profile", "orb_hunter")),
                difficulty=str(player_data.get("ai_difficulty", "standard")),
                seed=(slot_index + 1) * 197,
            )

    return players, ai_controllers


def get_team_scores(players):
    team_a_score = sum(p.score for p in players if p.team_code == "A")
    team_b_score = sum(p.score for p in players if p.team_code == "B")
    return team_a_score, team_b_score


def _build_local_player_row(player) -> dict:
    return {
        "name": player.name,
        "player_score": player.score,
        "accent_color": player.color,
        "sprite_id": player.sprite_id,
        "is_focus": player.control_mode == HUMAN_CONTROL_MODE,
    }


def _build_local_team_rows(players) -> tuple[list[dict], list[dict]]:
    team_a_rows = []
    team_b_rows = []

    for player in players:
        row = _build_local_player_row(player)
        if player.team_code == "A":
            team_a_rows.append(row)
        else:
            team_b_rows.append(row)

    return team_a_rows, team_b_rows


def _build_local_hud_payload(players) -> dict:
    team_a_score, team_b_score = get_team_scores(players)
    team_a_rows, team_b_rows = _build_local_team_rows(players)
    return {
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "team_a_rows": team_a_rows,
        "team_b_rows": team_b_rows,
    }


def _build_local_end_overlay_payload(players, winner_text: str) -> dict:
    payload = _build_local_hud_payload(players)
    payload.update(
        {
            "winner_text": winner_text,
            "summary_metric_label": END_SCREEN_SUMMARY_LABEL,
            "team_panel_value_label": END_SCREEN_PLAYER_VALUE_LABEL,
            "max_team_size": max(
                1,
                len(payload["team_a_rows"]),
                len(payload["team_b_rows"]),
            ),
        }
    )
    return payload


def _should_surface_local_feedback(player) -> bool:
    return (
        str(
            getattr(player, "control_mode", HUMAN_CONTROL_MODE) or HUMAN_CONTROL_MODE
        ).lower()
        == HUMAN_CONTROL_MODE
    )


def _build_local_pickup_feedback(
    player,
    awarded_value: int,
    combo_bonus: int,
    orb,
    elapsed_ms: int,
) -> dict | None:
    if not _should_surface_local_feedback(player):
        return None

    variant = getattr(orb, "variant", None)
    normalized_variant = str(variant or "").strip().lower()
    normalized_combo_bonus = max(0, int(combo_bonus or 0))
    priority = (
        4 if normalized_variant == "rare" else 3 if normalized_combo_bonus > 0 else 1
    )

    return {
        "message": format_pickup_event(
            player.name,
            player.team_code,
            awarded_value,
            combo_count=player.combo_count,
            combo_bonus=combo_bonus,
            variant=variant,
        ),
        "accent_color": tuple(player.color),
        "until_ms": elapsed_ms + MATCH_EVENT_BANNER_DURATION_MS,
        "priority": priority,
        "audio": {
            "combo_bonus": combo_bonus,
            "variant": variant,
        },
    }


def _build_local_trap_feedback(
    player,
    trap_state,
    elapsed_ms: int,
) -> dict | None:
    if not _should_surface_local_feedback(player):
        return None

    return {
        "message": format_trap_event(
            player.name,
            player.team_code,
            trap_kind=getattr(trap_state, "kind", None),
        ),
        "accent_color": tuple(player.color),
        "until_ms": elapsed_ms + MATCH_EVENT_BANNER_DURATION_MS,
        "priority": 2,
        "audio": {
            "trap_kind": getattr(trap_state, "kind", None),
        },
    }


def _event_banner_from_feedback(feedback: dict | None) -> dict | None:
    if feedback is None:
        return None

    return {
        "message": feedback["message"],
        "accent_color": feedback["accent_color"],
        "until_ms": feedback["until_ms"],
        "priority": int(feedback.get("priority", 0)),
    }


def _select_local_event_banner(
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


def _handle_local_orb_pickup(
    player,
    orb,
    arena_rect,
    obstacles,
    elapsed_ms: int,
    orb_effects: list[dict],
) -> dict | None:
    awarded_value, combo_bonus = player.register_orb_pickup(
        elapsed_ms,
        orb.value,
    )
    orb_effects.append(
        {
            "x": orb.x,
            "y": orb.y,
            "value": awarded_value,
            "variant": getattr(orb, "variant", None),
            "combo_count": player.combo_count,
            "combo_bonus": combo_bonus,
            "started_at_ms": elapsed_ms,
        }
    )

    feedback = _build_local_pickup_feedback(
        player,
        awarded_value,
        combo_bonus,
        orb,
        elapsed_ms,
    )
    if feedback is not None:
        play_pickup(**feedback["audio"])

    event_banner = _event_banner_from_feedback(feedback)
    orb.respawn(arena_rect, obstacles)
    if orb.variant == "rare":
        play_bonus_spawn()
    return event_banner


def _handle_local_trap_trigger(
    player,
    trap_state,
    elapsed_ms: int,
) -> dict | None:
    trap_triggered = player.trigger_trap(
        elapsed_ms,
        slow_duration_ms=(trap_state.slow_duration_ms),
        slow_multiplier=trap_state.slow_multiplier,
    )
    if not trap_triggered:
        return None

    feedback = _build_local_trap_feedback(
        player,
        trap_state,
        elapsed_ms,
    )
    if feedback is not None:
        play_trap(trap_kind=feedback["audio"]["trap_kind"])
    return _event_banner_from_feedback(feedback)


def draw_hud(
    surface,
    big_font,
    _medium_font,
    small_font,
    players,
    remaining_time,
    layout,
    match_duration: int = 60,
):
    payload = _build_local_hud_payload(players)

    draw_match_hud(
        surface,
        big_font,
        small_font,
        layout,
        team_a_title=get_team_label("A"),
        team_b_title=get_team_label("B"),
        team_a_score=payload["team_a_score"],
        team_b_score=payload["team_b_score"],
        remaining_time=remaining_time,
        team_a_rows=payload["team_a_rows"],
        team_b_rows=payload["team_b_rows"],
        match_duration=match_duration,
    )


def draw_end_overlay(
    surface,
    big_font,
    medium_font,
    small_font,
    winner_text,
    players,
):
    payload = _build_local_end_overlay_payload(players, winner_text)

    overlay = pygame.Surface(surface.get_size(), PG_SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surface.blit(overlay, (0, 0))

    overlay_layout = compute_end_overlay_layout(
        surface.get_size(),
        payload["max_team_size"],
        footer_height=82,
        min_panel_height=392,
        min_available_rows_height=160,
    )
    panel_rect = overlay_layout["panel_rect"]
    pygame.draw.rect(surface, (36, 40, 48), panel_rect, border_radius=18)
    pygame.draw.rect(
        surface,
        (110, 130, 180),
        panel_rect,
        width=3,
        border_radius=18,
    )

    title = big_font.render(payload["winner_text"], True, (255, 255, 255))
    title_rect = title.get_rect(center=(panel_rect.centerx, panel_rect.y + 42))
    surface.blit(title, title_rect)

    summary_label = small_font.render(
        payload["summary_metric_label"],
        True,
        (175, 192, 220),
    )
    summary_label_rect = summary_label.get_rect(
        center=(panel_rect.centerx, panel_rect.y + 78)
    )
    surface.blit(summary_label, summary_label_rect)

    score_label = choose_text_candidate(
        medium_font,
        build_scoreline_candidates(
            payload["team_a_score"],
            payload["team_b_score"],
        ),
        panel_rect.width - 80,
    )
    score_text = medium_font.render(score_label, True, (190, 210, 255))
    score_rect = score_text.get_rect(center=(panel_rect.centerx, panel_rect.y + 102))
    surface.blit(score_text, score_rect)

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
        surface,
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
        surface,
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

    footer_rect = overlay_layout["footer_rect"]
    pygame.draw.rect(surface, (24, 28, 36), footer_rect, border_radius=14)
    pygame.draw.rect(
        surface,
        (86, 102, 132),
        footer_rect,
        width=1,
        border_radius=14,
    )

    instruction_specs = [
        ("Entrée", "revenir au bastion"),
        ("R", "relancer la joute"),
        ("Échap", "quitter l'arène"),
    ]
    chips = []
    total_width = 0
    for key_text, label_text in instruction_specs:
        key_surface = small_font.render(key_text, True, (28, 28, 32))
        label_surface = small_font.render(label_text, True, (228, 230, 236))
        chip_width = 72 + key_surface.get_width() + label_surface.get_width()
        chips.append((key_surface, label_surface, chip_width))
        total_width += chip_width

    total_width += 18 * (len(chips) - 1)
    chip_x = footer_rect.centerx - total_width // 2
    chip_y = footer_rect.centery - 18

    for key_surface, label_surface, chip_width in chips:
        chip_rect = pygame.Rect(chip_x, chip_y, chip_width, 36)
        pygame.draw.rect(surface, (39, 47, 61), chip_rect, border_radius=18)
        pygame.draw.rect(
            surface,
            (82, 94, 117),
            chip_rect,
            width=1,
            border_radius=18,
        )

        key_badge = pygame.Rect(chip_rect.x + 8, chip_rect.y + 5, 62, 26)
        pygame.draw.rect(surface, (243, 201, 107), key_badge, border_radius=13)

        key_rect = key_surface.get_rect(center=key_badge.center)
        surface.blit(key_surface, key_rect)

        label_x = key_badge.right + 12
        label_y = chip_rect.centery - label_surface.get_height() // 2
        surface.blit(label_surface, (label_x, label_y))
        chip_x += chip_width + 18


def build_result(
    players,
    winner_text,
    match_duration_seconds,
    *,
    players_config=None,
    started_at=None,
    finished_at=None,
):
    team_a_score, team_b_score = get_team_scores(players)
    config_by_name = {
        str(player_config.get("name", "")).strip(): player_config
        for player_config in (players_config or [])
    }

    players_data = []
    for p in players:
        player_config = config_by_name.get(str(p.name).strip(), {})
        players_data.append(
            {
                "name": p.name,
                "team": p.team_code,
                "individual_score": p.score,
                "control_mode": p.control_mode,
                "is_ai": p.control_mode == AI_CONTROL_MODE,
                "slot_number": player_config.get("slot"),
                "ai_difficulty_code": player_config.get("ai_difficulty"),
                "ai_profile_code": player_config.get("ai_profile"),
            }
        )

    winner_team = get_winner_team(team_a_score, team_b_score)
    has_ai = any(player["is_ai"] for player in players_data)
    current_layout = get_map_layout()

    return {
        "players": players_data,
        "players_data": players_data,
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "summary_metric_key": "team_score",
        "summary_metric_label": END_SCREEN_SUMMARY_LABEL,
        "team_panel_value_key": "player_score",
        "team_panel_value_label": END_SCREEN_PLAYER_VALUE_LABEL,
        "winner_team": winner_team,
        "winner_text": winner_text,
        "duration_seconds": match_duration_seconds,
        "source_code": "LOCAL",
        "mode_code": "LOCAL_AI" if has_ai else "LOCAL_HUMAN",
        "arena_code": current_layout.map_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "played_at": finished_at or started_at,
    }


def run_game(players_config, match_duration_seconds=MATCH_DURATION_SECONDS):
    hardware_service = create_match_hardware_service()
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pg_init()
    init_audio()
    stop_music(fade_ms=0)
    active_match_duration = coerce_match_duration(match_duration_seconds)
    layout = get_map_layout()
    icon_path = get_app_icon_png_path(64)
    if Path(icon_path).exists():
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except OSError:
            pass
    screen = pygame.display.set_mode(layout.window_size, PG_RESIZABLE)
    pygame.display.set_caption("Arena Duel - Joute locale")
    clock = pygame.time.Clock()

    big_font = load_font(
        "Cinzel-Bold.ttf",
        38,
        fallback_name="Georgia",
        bold=True,
    )
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
    name_font = load_font(
        "CrimsonText-SemiBold.ttf",
        18,
        fallback_name="Georgia",
        bold=True,
    )

    arena_rect = get_arena_rect(layout)
    obstacles = get_obstacles(layout)
    game_w, game_h = layout.window_size
    game_surface = pygame.Surface((game_w, game_h))
    _draw_loading_frame(
        screen,
        game_surface,
        layout,
        arena_rect,
        obstacles,
        big_font,
        small_font,
    )

    last_focus_losing_team = None

    try:
        while True:
            players, ai_controllers = build_runtime_players(
                players_config,
                layout,
            )
            orbs = [
                Orb(arena_rect, obstacles, layout=layout)
                for _ in range(ORB_SPAWN_COUNT)
            ]
            trap_states = build_match_traps(layout)
            orb_effects = []
            event_banner = None
            stop_music(fade_ms=0)
            hardware_service.reset()
            hardware_service.emit_state("COMBAT")
            hardware_service.emit_score(0, 0)

            running = True
            game_over = False
            restart_requested = False
            match_started_at = datetime.now()
            match_finished_at = None
            start_ticks = pygame.time.get_ticks()
            winner_text = ""
            final_sound_played = False

            while running:
                _tick_frame(clock, FPS)

                for event in pygame.event.get():
                    if event.type == PG_QUIT:
                        hardware_service.reset()
                        stop_music(fade_ms=120)
                        pg_quit()
                        return None

                    if event.type == PG_KEYDOWN:
                        if event.key == PG_K_ESCAPE and not game_over:
                            hardware_service.reset()
                            stop_music(fade_ms=120)
                            pg_quit()
                            return None

                        if game_over:
                            if event.key == PG_K_RETURN:
                                stop_music(fade_ms=120)
                                pg_quit()
                                return build_result(
                                    players,
                                    winner_text,
                                    active_match_duration,
                                    players_config=players_config,
                                    started_at=match_started_at,
                                    finished_at=match_finished_at or datetime.now(),
                                )

                            elif event.key == PG_K_R:
                                hardware_service.reset()
                                stop_music(fade_ms=120)
                                restart_requested = True
                                running = False

                            elif event.key == PG_K_ESCAPE:
                                stop_music(fade_ms=120)
                                pg_quit()
                                return None

                elapsed_seconds = (pygame.time.get_ticks() - start_ticks) // 1000
                remaining_time = max(
                    0,
                    active_match_duration - elapsed_seconds,
                )

                if remaining_time <= 0 and not game_over:
                    game_over = True
                    match_finished_at = datetime.now()
                    stop_music(fade_ms=280)
                    team_a_score, team_b_score = get_team_scores(players)

                    winner_team = get_winner_team(
                        team_a_score,
                        team_b_score,
                    )
                    winner_text = format_winner_text(winner_team)

                keys = pygame.key.get_pressed()
                current_ticks = pygame.time.get_ticks()
                elapsed_ms = current_ticks
                match_elapsed_ms = current_ticks - start_ticks
                update_match_traps(trap_states, match_elapsed_ms)

                if not game_over:
                    for player in players:
                        if player.control_mode == AI_CONTROL_MODE:
                            intent = ai_controllers[player].get_movement_intent(
                                player=player,
                                players=players,
                                orbs=orbs,
                                obstacles=obstacles,
                                elapsed_ms=elapsed_ms,
                            )
                            player.update_from_intent(
                                intent,
                                arena_rect,
                                obstacles,
                                elapsed_ms=elapsed_ms,
                            )
                        else:
                            player.update(
                                keys,
                                arena_rect,
                                obstacles,
                                elapsed_ms=elapsed_ms,
                            )

                    for player in players:
                        for trap_state in trap_states:
                            if not trap_state.active:
                                continue
                            if player.collides_with_trap(trap_state.rect):
                                next_banner = _handle_local_trap_trigger(
                                    player,
                                    trap_state,
                                    elapsed_ms,
                                )
                                event_banner = _select_local_event_banner(
                                    event_banner,
                                    next_banner,
                                )
                                break

                    for orb in orbs:
                        for player in players:
                            if player.collides_with_orb(orb):
                                next_banner = _handle_local_orb_pickup(
                                    player,
                                    orb,
                                    arena_rect,
                                    obstacles,
                                    elapsed_ms,
                                    orb_effects,
                                )
                                event_banner = _select_local_event_banner(
                                    event_banner,
                                    next_banner,
                                )
                                break

                team_a_score, team_b_score = get_team_scores(players)
                hardware_service.emit_score(team_a_score, team_b_score)

                if game_over and not final_sound_played:
                    winner_team = get_winner_team(
                        team_a_score,
                        team_b_score,
                    )
                    local_focus_team = get_local_focus_team(players)

                    if winner_team is None:
                        play_draw()
                        last_focus_losing_team = None
                    elif local_focus_team is not None:
                        if winner_team == local_focus_team:
                            play_win()
                            last_focus_losing_team = None
                        else:
                            play_lose(
                                consecutive_rematch_loss=(
                                    last_focus_losing_team == local_focus_team
                                )
                            )
                            last_focus_losing_team = local_focus_team
                    else:
                        play_win()
                        last_focus_losing_team = None

                    hardware_service.emit_state("RESULT")
                    hardware_service.emit_winner(winner_team)
                    final_sound_played = True

                draw_background(game_surface, layout)
                draw_arena(
                    game_surface,
                    arena_rect,
                    obstacles,
                    layout=layout,
                    trap_states=snapshot_match_traps(
                        trap_states,
                        match_elapsed_ms,
                    ),
                    elapsed_ms=elapsed_ms,
                )

                for orb in orbs:
                    orb.draw(game_surface)

                for player in players:
                    player.draw(game_surface, name_font)

                active_orb_effects = []
                for effect in orb_effects:
                    if draw_orb_collection_effect(
                        game_surface,
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
                orb_effects = active_orb_effects

                draw_hud(
                    game_surface,
                    big_font,
                    medium_font,
                    small_font,
                    players,
                    remaining_time,
                    layout,
                    match_duration=active_match_duration,
                )

                if (
                    event_banner
                    and elapsed_ms <= event_banner["until_ms"]
                    and not game_over
                ):
                    draw_match_event_banner(
                        game_surface,
                        small_font,
                        event_banner["message"],
                        accent_color=event_banner["accent_color"],
                    )
                elif event_banner and elapsed_ms > event_banner["until_ms"]:
                    event_banner = None

                if game_over:
                    draw_end_overlay(
                        game_surface,
                        big_font,
                        medium_font,
                        small_font,
                        winner_text,
                        players,
                    )

                # Centre et agrandit la scene quand la fenetre est plus grande.
                _present_game_surface(screen, game_surface, layout.window_size)
                pygame.display.flip()

            if restart_requested:
                continue
    finally:
        hardware_service.shutdown()
