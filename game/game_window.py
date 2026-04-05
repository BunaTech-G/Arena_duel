import pygame

from game.settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    FPS,
    PLAYER_SLOT_CONTROLS,
    TEAM_A_COLORS,
    TEAM_B_COLORS,
    ORB_SPAWN_COUNT,
    MATCH_DURATION_SECONDS,
    HUD_TEXT_COLOR,
    HUD_ACCENT_COLOR,
    HUD_PANEL_COLOR,
    HUD_BORDER_COLOR,
)
from game.player import Player
from game.orb import Orb
from game.arena import draw_background, draw_arena, get_arena_rect, get_obstacles
from game.audio import init_audio, play_pickup, play_win, play_draw

def build_runtime_players(players_config, arena_rect):
    team_a = [p for p in players_config if p["team"] == "A"]
    team_b = [p for p in players_config if p["team"] == "B"]

    players = []

    def spawn_positions(team_players, side):
        count = len(team_players)
        if count == 1:
            y_positions = [arena_rect.centery]
        elif count == 2:
            y_positions = [arena_rect.centery - 80, arena_rect.centery + 80]
        else:
            y_positions = [arena_rect.centery - 120, arena_rect.centery, arena_rect.centery + 120]

        if side == "left":
            x = arena_rect.left + 100
        else:
            x = arena_rect.right - 100

        return [(x, y) for y in y_positions]

    team_a_positions = spawn_positions(team_a, "left")
    team_b_positions = spawn_positions(team_b, "right")

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
                team_code="A"
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
                team_code="B"
            )
        )

    return players


def get_team_scores(players):
    team_a_score = sum(p.score for p in players if p.team_code == "A")
    team_b_score = sum(p.score for p in players if p.team_code == "B")
    return team_a_score, team_b_score


def draw_hud(surface, big_font, medium_font, small_font, players, remaining_time):
    team_a_score, team_b_score = get_team_scores(players)

    title = big_font.render("ARENA DUEL", True, HUD_ACCENT_COLOR)

    team_a_panel = pygame.Rect(320, 12, 280, 58)
    team_b_panel = pygame.Rect(620, 12, 280, 58)
    time_panel = pygame.Rect(1020, 12, 180, 58)

    for panel in (team_a_panel, team_b_panel, time_panel):
        pygame.draw.rect(surface, HUD_PANEL_COLOR, panel, border_radius=10)
        pygame.draw.rect(surface, HUD_BORDER_COLOR, panel, width=2, border_radius=10)

    team_a_text = medium_font.render(f"Équipe A : {team_a_score}", True, HUD_TEXT_COLOR)
    team_b_text = medium_font.render(f"Équipe B : {team_b_score}", True, HUD_TEXT_COLOR)
    timer_text = medium_font.render(f"{remaining_time}s", True, HUD_TEXT_COLOR)

    surface.blit(title, (24, 18))
    surface.blit(team_a_text, (340, 26))
    surface.blit(team_b_text, (640, 26))
    surface.blit(timer_text, (1068, 26))

    # petits scores individuels en bas du HUD
    team_a_players = [p for p in players if p.team_code == "A"]
    team_b_players = [p for p in players if p.team_code == "B"]

    y_a = 82
    for idx, p in enumerate(team_a_players):
        txt = small_font.render(f"A - {p.name} : {p.score}", True, HUD_TEXT_COLOR)
        surface.blit(txt, (28, y_a + idx * 22))

    y_b = 82
    for idx, p in enumerate(team_b_players):
        txt = small_font.render(f"B - {p.name} : {p.score}", True, HUD_TEXT_COLOR)
        surface.blit(txt, (1020, y_b + idx * 22))


def draw_end_overlay(surface, big_font, medium_font, small_font, winner_text, players):
    team_a_score, team_b_score = get_team_scores(players)

    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surface.blit(overlay, (0, 0))

    panel_width = 820
    panel_height = 340
    panel_x = (WINDOW_WIDTH - panel_width) // 2
    panel_y = (WINDOW_HEIGHT - panel_height) // 2

    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    pygame.draw.rect(surface, (36, 40, 48), panel_rect, border_radius=18)
    pygame.draw.rect(surface, (110, 130, 180), panel_rect, width=3, border_radius=18)

    title = big_font.render(winner_text, True, (255, 255, 255))
    title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 42))
    surface.blit(title, title_rect)

    score_text = medium_font.render(
        f"Équipe A : {team_a_score}   |   Équipe B : {team_b_score}",
        True,
        (190, 210, 255)
    )
    score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 88))
    surface.blit(score_text, score_rect)

    team_a_players = [p for p in players if p.team_code == "A"]
    team_b_players = [p for p in players if p.team_code == "B"]

    team_a_title = medium_font.render("Équipe A", True, (255, 255, 255))
    team_b_title = medium_font.render("Équipe B", True, (255, 255, 255))

    surface.blit(team_a_title, (panel_x + 80, panel_y + 130))
    surface.blit(team_b_title, (panel_x + 460, panel_y + 130))

    for idx, p in enumerate(team_a_players):
        txt = small_font.render(f"{p.name} : {p.score}", True, (255, 255, 255))
        surface.blit(txt, (panel_x + 80, panel_y + 170 + idx * 28))

    for idx, p in enumerate(team_b_players):
        txt = small_font.render(f"{p.name} : {p.score}", True, (255, 255, 255))
        surface.blit(txt, (panel_x + 460, panel_y + 170 + idx * 28))

    instructions = [
        "Entrée = retour au menu",
        "R = rejouer immédiatement",
        "Échap = quitter la partie"
    ]

    for idx, line in enumerate(instructions):
        txt = small_font.render(line, True, (220, 220, 220))
        surface.blit(txt, (panel_x + 80, panel_y + 255 + idx * 24))


def build_result(players, winner_text):
    team_a_score, team_b_score = get_team_scores(players)

    players_data = []
    for p in players:
        players_data.append({
            "name": p.name,
            "team": p.team_code,
            "individual_score": p.score,
        })

    winner_team = None
    if team_a_score > team_b_score:
        winner_team = "A"
    elif team_b_score > team_a_score:
        winner_team = "B"

    return {
        "players_data": players_data,
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "winner_team": winner_team,
        "winner_text": winner_text,
        "duration_seconds": MATCH_DURATION_SECONDS,
    }

def run_game(players_config):
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    init_audio()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Arena Duel - Game")
    clock = pygame.time.Clock()

    big_font = pygame.font.SysFont("Arial", 34, bold=True)
    medium_font = pygame.font.SysFont("Arial", 24, bold=True)
    small_font = pygame.font.SysFont("Arial", 18)
    name_font = pygame.font.SysFont("Arial", 16, bold=True)

    arena_rect = get_arena_rect()
    obstacles = get_obstacles(arena_rect)

    while True:
        players = build_runtime_players(players_config, arena_rect)
        orbs = [Orb(arena_rect, obstacles) for _ in range(ORB_SPAWN_COUNT)]

        running = True
        game_over = False
        start_ticks = pygame.time.get_ticks()
        winner_text = ""
        final_sound_played = False

        while running:
            clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE and not game_over:
                        pygame.quit()
                        return None

                    if game_over:
                        if event.key == pygame.K_RETURN:
                            pygame.quit()
                            return build_result(players, winner_text)

                        elif event.key == pygame.K_r:
                            return run_game(players_config)

                        elif event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            return None

            elapsed_seconds = (pygame.time.get_ticks() - start_ticks) // 1000
            remaining_time = max(0, MATCH_DURATION_SECONDS - elapsed_seconds)

            if remaining_time <= 0 and not game_over:
                game_over = True
                team_a_score, team_b_score = get_team_scores(players)

                if team_a_score > team_b_score:
                    winner_text = "Victoire Équipe A"
                elif team_b_score > team_a_score:
                    winner_text = "Victoire Équipe B"
                else:
                    winner_text = "Égalité"

            keys = pygame.key.get_pressed()

            if not game_over:
                for player in players:
                    player.update(keys, arena_rect, obstacles)

                for orb in orbs:
                    for player in players:
                        if player.collides_with_orb(orb):
                            player.score += orb.value
                            play_pickup()
                            orb.respawn(arena_rect, obstacles)
                            break

            if game_over and not final_sound_played:
                team_a_score, team_b_score = get_team_scores(players)

                if team_a_score == team_b_score:
                    play_draw()
                else:
                    play_win()

                final_sound_played = True

            draw_background(screen)
            draw_arena(screen, arena_rect, obstacles)

            for orb in orbs:
                orb.draw(screen)

            for player in players:
                player.draw(screen, name_font)

            draw_hud(screen, big_font, medium_font, small_font, players, remaining_time)

            if game_over:
                draw_end_overlay(screen, big_font, medium_font, small_font, winner_text, players)

            pygame.display.flip()
