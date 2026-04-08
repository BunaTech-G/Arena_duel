import pygame

from game.asset_pipeline import load_font
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
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
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


PG_KEYDOWN = getattr(pygame, "KEYDOWN")
PG_K_ESCAPE = getattr(pygame, "K_ESCAPE")
PG_K_RETURN = getattr(pygame, "K_RETURN")
PG_K_R = getattr(pygame, "K_r")
PG_QUIT = getattr(pygame, "QUIT")
PG_SRCALPHA = getattr(pygame, "SRCALPHA")
pg_init = getattr(pygame, "init")
pg_quit = getattr(pygame, "quit")


def build_runtime_players(players_config, layout):
    team_a = [p for p in players_config if p["team"] == "A"]
    team_b = [p for p in players_config if p["team"] == "B"]

    players = []

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
        controls = PLAYER_SLOT_CONTROLS[slot_index]
        color = TEAM_A_COLORS[idx % len(TEAM_A_COLORS)]
        x, y = team_a_positions[idx]

        players.append(
            Player(
                name=player_data["name"],
                x=x,
                y=y,
                color=color,
                controls=controls,
                team_code="A",
            )
        )

    for idx, player_data in enumerate(team_b):
        slot_index = player_data["slot"] - 1
        controls = PLAYER_SLOT_CONTROLS[slot_index]
        color = TEAM_B_COLORS[idx % len(TEAM_B_COLORS)]
        x, y = team_b_positions[idx]

        players.append(
            Player(
                name=player_data["name"],
                x=x,
                y=y,
                color=color,
                controls=controls,
                team_code="B",
            )
        )

    return players


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

    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), PG_SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surface.blit(overlay, (0, 0))

    panel_width = 820
    panel_height = 340
    panel_x = (WINDOW_WIDTH - panel_width) // 2
    panel_y = (WINDOW_HEIGHT - panel_height) // 2

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
    title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 42))
    surface.blit(title, title_rect)

    score_label = format_scoreline(team_a_score, team_b_score)
    score_text = medium_font.render(
        score_label,
        True,
        (190, 210, 255),
    )
    score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 88))
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


def build_result(players, winner_text, match_duration_seconds):
    team_a_score, team_b_score = get_team_scores(players)

    players_data = []
    for p in players:
        players_data.append(
            {
                "name": p.name,
                "team": p.team_code,
                "individual_score": p.score,
            }
        )

    winner_team = get_winner_team(team_a_score, team_b_score)

    return {
        "players_data": players_data,
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "winner_team": winner_team,
        "winner_text": winner_text,
        "duration_seconds": match_duration_seconds,
    }


def run_game(players_config, match_duration_seconds=MATCH_DURATION_SECONDS):
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pg_init()
    init_audio()
    stop_music(fade_ms=0)
    active_match_duration = coerce_match_duration(match_duration_seconds)
    layout = get_map_layout()
    screen = pygame.display.set_mode(layout.window_size)
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

    while True:
        players = build_runtime_players(players_config, layout)
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

            if not game_over:
                for player in players:
                    player.update(keys, arena_rect, obstacles)

                for orb in orbs:
                    for player in players:
                        if player.collides_with_orb(orb):
                            player.score += orb.value
                            orb.respawn(arena_rect, obstacles)
                            break

            if game_over and not final_sound_played:
                team_a_score, team_b_score = get_team_scores(players)

                if team_a_score == team_b_score:
                    play_draw()
                else:
                    play_win()

                final_sound_played = True

            elapsed_ms = pygame.time.get_ticks()
            draw_background(screen, layout)
            draw_arena(
                screen,
                arena_rect,
                obstacles,
                layout=layout,
                elapsed_ms=elapsed_ms,
            )

            for orb in orbs:
                orb.draw(screen)

            for player in players:
                player.draw(screen, name_font)

            draw_hud(
                screen,
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
                    screen,
                    big_font,
                    medium_font,
                    small_font,
                    winner_text,
                    players,
                )

            pygame.display.flip()
