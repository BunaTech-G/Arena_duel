from pathlib import Path

import pygame

from runtime_utils import resource_path
from game.asset_pipeline import load_font
from game.computer_opponent import BotController
from game.control_models import AI_CONTROL_MODE, HUMAN_CONTROL_MODE
from game.hud_panels import (
    draw_match_hud,
    draw_player_summary_row,
)
from game.match_text import (
    format_scoreline,
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
    get_arena_rect,
    get_map_layout,
    get_obstacles,
    get_team_spawn_positions_for_layout,
)
from game.audio import init_audio, play_draw, play_win, stop_music
from game.audio import play_lose


PG_KEYDOWN = getattr(pygame, "KEYDOWN")
PG_K_ESCAPE = getattr(pygame, "K_ESCAPE")
PG_K_RETURN = getattr(pygame, "K_RETURN")
PG_K_R = getattr(pygame, "K_r")
PG_QUIT = getattr(pygame, "QUIT")
PG_SRCALPHA = getattr(pygame, "SRCALPHA")
pg_init = getattr(pygame, "init")
pg_quit = getattr(pygame, "quit")


def get_local_focus_team(players):
    human_teams = {
        player.team_code
        for player in players
        if player.control_mode == HUMAN_CONTROL_MODE
    }
    ai_teams = {
        player.team_code
        for player in players
        if player.control_mode == AI_CONTROL_MODE
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
        control_mode = str(
            player_data.get("control_mode", HUMAN_CONTROL_MODE)
        ).lower()
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
        control_mode = str(
            player_data.get("control_mode", HUMAN_CONTROL_MODE)
        ).lower()
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
            {"name": p.name, "score": p.score, "accent_color": p.color}
            for p in team_a_players
        ],
        team_b_rows=[
            {"name": p.name, "score": p.score, "accent_color": p.color}
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

    overlay = pygame.Surface(surface.get_size(), PG_SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surface.blit(overlay, (0, 0))

    sw, sh = surface.get_size()
    panel_width = 820
    panel_height = 340
    panel_x = (sw - panel_width) // 2
    panel_y = (sh - panel_height) // 2

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

    score_label = format_scoreline(team_a_score, team_b_score)
    score_text = medium_font.render(
        score_label,
        True,
        (190, 210, 255),
    )
    score_rect = score_text.get_rect(center=(sw // 2, panel_y + 88))
    surface.blit(score_text, score_rect)

    team_a_players = [p for p in players if p.team_code == "A"]
    team_b_players = [p for p in players if p.team_code == "B"]

    team_a_title = medium_font.render(
        get_team_label("A"),
        True,
        (255, 255, 255),
    )
    team_b_title = medium_font.render(
        get_team_label("B"),
        True,
        (255, 255, 255),
    )

    surface.blit(team_a_title, (panel_x + 80, panel_y + 130))
    surface.blit(team_b_title, (panel_x + 460, panel_y + 130))

    for idx, p in enumerate(team_a_players):
        draw_player_summary_row(
            surface,
            small_font,
            panel_x + 80,
            panel_y + 166 + idx * 64,
            name=p.name,
            score=p.score,
            accent_color=p.color,
            portrait_size=48,
        )

    for idx, p in enumerate(team_b_players):
        draw_player_summary_row(
            surface,
            small_font,
            panel_x + 460,
            panel_y + 166 + idx * 64,
            name=p.name,
            score=p.score,
            accent_color=p.color,
            portrait_size=48,
        )

    instructions = [
        "Entrée · revenir au bastion",
        "R · relancer la joute",
        "Échap · quitter l'arène",
    ]

    for idx, line in enumerate(instructions):
        txt = small_font.render(line, True, (220, 220, 220))
        surface.blit(txt, (panel_x + 80, panel_y + 255 + idx * 24))


def build_result(
    players,
    winner_text,
    match_duration_seconds,
    *,
    players_config=None,
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
        "winner_team": winner_team,
        "winner_text": winner_text,
        "duration_seconds": match_duration_seconds,
        "source_code": "LOCAL",
        "mode_code": "LOCAL_AI" if has_ai else "LOCAL_HUMAN",
        "arena_code": current_layout.map_id,
    }


def run_game(players_config, match_duration_seconds=MATCH_DURATION_SECONDS):
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pg_init()
    init_audio()
    stop_music(fade_ms=0)
    active_match_duration = coerce_match_duration(match_duration_seconds)
    layout = get_map_layout()
    _icon_path = resource_path("assets", "icons", "app.png")
    if Path(_icon_path).exists():
        try:
            pygame.display.set_icon(pygame.image.load(_icon_path))
        except OSError:
            pass
    screen = pygame.display.set_mode(
        layout.window_size, getattr(pygame, "RESIZABLE")
    )
    pygame.display.set_caption("Arena Duel - Joute locale")
    clock = pygame.time.Clock()

    big_font = load_font(
        "Cinzel-Bold.ttf",
        34,
        fallback_name="Georgia",
        bold=True,
    )
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
    name_font = load_font(
        "CrimsonText-SemiBold.ttf",
        16,
        fallback_name="Georgia",
        bold=True,
    )

    arena_rect = get_arena_rect(layout)
    obstacles = get_obstacles(layout)
    game_w, game_h = layout.window_size
    game_surface = pygame.Surface((game_w, game_h))

    while True:
        players, ai_controllers = build_runtime_players(players_config, layout)
        orbs = [
            Orb(arena_rect, obstacles, layout=layout)
            for _ in range(ORB_SPAWN_COUNT)
        ]

        running = True
        game_over = False
        start_ticks = pygame.time.get_ticks()
        winner_text = ""
        final_sound_played = False

        while running:
            clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == PG_QUIT:
                    stop_music(fade_ms=120)
                    pg_quit()
                    return None

                if event.type == PG_KEYDOWN:
                    if event.key == PG_K_ESCAPE and not game_over:
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
                            )

                        elif event.key == PG_K_R:
                            stop_music(fade_ms=120)
                            return run_game(
                                players_config,
                                match_duration_seconds=active_match_duration,
                            )

                        elif event.key == PG_K_ESCAPE:
                            stop_music(fade_ms=120)
                            pg_quit()
                            return None

            elapsed_seconds = (pygame.time.get_ticks() - start_ticks) // 1000
            remaining_time = max(0, active_match_duration - elapsed_seconds)

            if remaining_time <= 0 and not game_over:
                game_over = True
                stop_music(fade_ms=280)
                team_a_score, team_b_score = get_team_scores(players)

                winner_team = get_winner_team(team_a_score, team_b_score)
                winner_text = format_winner_text(winner_team)

            keys = pygame.key.get_pressed()
            elapsed_ms = pygame.time.get_ticks()

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
                        )
                    else:
                        player.update(keys, arena_rect, obstacles)

                for orb in orbs:
                    for player in players:
                        if player.collides_with_orb(orb):
                            player.score += orb.value
                            orb.respawn(arena_rect, obstacles)
                            break

            if game_over and not final_sound_played:
                team_a_score, team_b_score = get_team_scores(players)
                winner_team = get_winner_team(team_a_score, team_b_score)
                local_focus_team = get_local_focus_team(players)

                if winner_team is None:
                    play_draw()
                elif local_focus_team is not None:
                    if winner_team == local_focus_team:
                        play_win()
                    else:
                        play_lose()
                else:
                    play_win()

                final_sound_played = True

            draw_background(game_surface, layout)
            draw_arena(
                game_surface,
                arena_rect,
                obstacles,
                layout=layout,
                elapsed_ms=elapsed_ms,
            )

            for orb in orbs:
                orb.draw(game_surface)

            for player in players:
                player.draw(game_surface, name_font)

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

            # Centre la scène de jeu dans la fenêtre (supporte resize/maximisé)
            sw, sh = screen.get_size()
            screen.fill((10, 13, 19))
            blit_x = max(0, (sw - game_w) // 2)
            blit_y = max(0, (sh - game_h) // 2)
            screen.blit(game_surface, (blit_x, blit_y))
            pygame.display.flip()
