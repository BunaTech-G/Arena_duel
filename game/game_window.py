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
    draw_end_team_card,
    draw_match_hud,
    get_shared_player_score_slot_width,
)
from game.match_text import (
    END_SCREEN_PLAYER_VALUE_LABEL,
    END_SCREEN_SUMMARY_LABEL,
    build_scoreline_candidates,
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
    team_a_score, team_b_score = get_team_scores(players)

    team_a_players = [p for p in players if p.team_code == "A"]
    team_b_players = [p for p in players if p.team_code == "B"]

    draw_match_hud(
        surface,
        big_font,
        small_font,
        layout,
        team_a_title=get_team_label("A"),
        team_b_title=get_team_label("B"),
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        remaining_time=remaining_time,
        team_a_rows=[
            {
                "name": p.name,
                "player_score": p.score,
                "accent_color": p.color,
                "sprite_id": p.sprite_id,
            }
            for p in team_a_players
        ],
        team_b_rows=[
            {
                "name": p.name,
                "player_score": p.score,
                "accent_color": p.color,
                "sprite_id": p.sprite_id,
            }
            for p in team_b_players
        ],
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
    team_a_score, team_b_score = get_team_scores(players)
    team_a_players = [p for p in players if p.team_code == "A"]
    team_b_players = [p for p in players if p.team_code == "B"]
    team_a_rows = [
        {
            "name": p.name,
            "player_score": p.score,
            "accent_color": p.color,
            "sprite_id": p.sprite_id,
        }
        for p in team_a_players
    ]
    team_b_rows = [
        {
            "name": p.name,
            "player_score": p.score,
            "accent_color": p.color,
            "sprite_id": p.sprite_id,
        }
        for p in team_b_players
    ]
    max_team_size = max(1, len(team_a_players), len(team_b_players))

    overlay = pygame.Surface(surface.get_size(), PG_SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surface.blit(overlay, (0, 0))

    sw, sh = surface.get_size()
    panel_width = min(920, sw - 48)
    column_gap = max(20, min(32, panel_width // 28))
    side_padding = max(24, min(36, panel_width // 24))
    header_height = 126
    footer_height = 82
    row_gap = 8
    available_rows_height = max(160, sh - header_height - footer_height - 96)
    row_height = max(
        40,
        min(
            48,
            int(
                (available_rows_height - 76 - row_gap * (max_team_size - 1))
                / max_team_size
            ),
        ),
    )
    portrait_size = max(30, min(36, row_height - 10))
    roster_height = 62 + max_team_size * row_height
    roster_height += max(0, max_team_size - 1) * row_gap
    roster_height += 16
    panel_height = min(
        sh - 40,
        max(392, header_height + roster_height + footer_height + 16),
    )
    panel_x = (sw - panel_width) // 2
    panel_y = (sh - panel_height) // 2
    column_width = (panel_width - side_padding * 2 - column_gap) // 2

    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    pygame.draw.rect(surface, (36, 40, 48), panel_rect, border_radius=18)
    pygame.draw.rect(
        surface,
        (110, 130, 180),
        panel_rect,
        width=3,
        border_radius=18,
    )

    title = big_font.render(winner_text, True, (255, 255, 255))
    title_rect = title.get_rect(center=(sw // 2, panel_y + 42))
    surface.blit(title, title_rect)

    summary_label = small_font.render(
        END_SCREEN_SUMMARY_LABEL,
        True,
        (175, 192, 220),
    )
    summary_label_rect = summary_label.get_rect(center=(sw // 2, panel_y + 78))
    surface.blit(summary_label, summary_label_rect)

    score_label = choose_text_candidate(
        medium_font,
        build_scoreline_candidates(team_a_score, team_b_score),
        panel_width - 80,
    )
    score_text = medium_font.render(score_label, True, (190, 210, 255))
    score_rect = score_text.get_rect(center=(sw // 2, panel_y + 102))
    surface.blit(score_text, score_rect)

    roster_top = panel_y + header_height
    team_a_rect = pygame.Rect(
        panel_x + side_padding,
        roster_top,
        column_width,
        roster_height,
    )
    team_b_rect = pygame.Rect(
        team_a_rect.right + column_gap,
        roster_top,
        column_width,
        roster_height,
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
        surface,
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
        row_value_label=END_SCREEN_PLAYER_VALUE_LABEL,
        score_format_mode="grouped",
        score_slot_width=shared_score_slot_width,
    )
    draw_end_team_card(
        surface,
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
        row_value_label=END_SCREEN_PLAYER_VALUE_LABEL,
        score_format_mode="grouped",
        score_slot_width=shared_score_slot_width,
    )

    footer_rect = pygame.Rect(
        panel_x + 24,
        panel_rect.bottom - footer_height + 12,
        panel_width - 48,
        footer_height - 24,
    )
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
                                trap_triggered = player.trigger_trap(
                                    elapsed_ms,
                                    slow_duration_ms=(trap_state.slow_duration_ms),
                                    slow_multiplier=trap_state.slow_multiplier,
                                )
                                if trap_triggered:
                                    play_trap()
                                break

                    for orb in orbs:
                        for player in players:
                            if player.collides_with_orb(orb):
                                awarded_value, combo_bonus = player.register_orb_pickup(
                                    elapsed_ms,
                                    orb.value,
                                )
                                orb_effects.append(
                                    {
                                        "x": orb.x,
                                        "y": orb.y,
                                        "value": awarded_value,
                                        "combo_count": player.combo_count,
                                        "combo_bonus": combo_bonus,
                                        "started_at_ms": elapsed_ms,
                                    }
                                )
                                play_pickup()
                                orb.respawn(arena_rect, obstacles)
                                if orb.variant == "rare":
                                    play_bonus_spawn()
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
