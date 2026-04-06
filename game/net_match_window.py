import pygame

from network.messages import STATE, END


TEAM_COLORS = {
    "A": (80, 170, 255),
    "B": (255, 110, 110),
}


def run_network_match(client, my_slot, my_name):
    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    pygame.display.set_caption(f"Arena Duel LAN - {my_name}")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Arial", 20)
    big_font = pygame.font.SysFont("Arial", 36, bold=True)

    latest_state = None
    end_message = None
    end_timer = 0

    running = True

    while running and client.running:
        dt = clock.tick(60) / 1000.0

        up = down = left = right = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        up = keys[pygame.K_z] or keys[pygame.K_w] or keys[pygame.K_UP]
        down = keys[pygame.K_s] or keys[pygame.K_DOWN]
        left = keys[pygame.K_q] or keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]

        client.send_input(up, down, left, right)

        for msg in client.poll_messages():
            msg_type = msg.get("type")

            if msg_type == STATE:
                latest_state = msg

            elif msg_type == END:
                end_message = msg
                end_timer = 3.0

        screen.fill((22, 26, 32))

        if latest_state:
            draw_state(screen, latest_state, my_slot, font, big_font)

        if end_message:
            draw_end_overlay(screen, end_message, big_font)
            end_timer -= dt
            if end_timer <= 0:
                running = False

        pygame.display.flip()

    pygame.quit()
    return

def draw_state(screen, state, my_slot, font, big_font):
    arena_w = state.get("arena_w", 1280)
    arena_h = state.get("arena_h", 720)

    # Bordure arène
    pygame.draw.rect(screen, (70, 80, 95), (20, 20, arena_w - 40, arena_h - 40), 3)

    # Scores
    team_a = state.get("team_a_score", 0)
    team_b = state.get("team_b_score", 0)
    remaining = state.get("remaining_time", 0)

    hud = f"Équipe A: {team_a}   |   Équipe B: {team_b}   |   Temps: {remaining}s"
    hud_surface = big_font.render(hud, True, (240, 240, 240))
    screen.blit(hud_surface, (30, 30))

    # Orbes
    for orb in state.get("orbs", []):
        pygame.draw.circle(screen, (255, 215, 80), (int(orb["x"]), int(orb["y"])), 10)

    # Joueurs
    for p in state.get("players", []):
        color = TEAM_COLORS.get(p["team"], (200, 200, 200))
        pos = (int(p["x"]), int(p["y"]))

        pygame.draw.circle(screen, color, pos, 18)

        if p["slot"] == my_slot:
            pygame.draw.circle(screen, (255, 255, 255), pos, 24, 2)

        name_text = f"{p['name']} (S{p['slot']}) - {p['score']}"
        text_surface = font.render(name_text, True, (240, 240, 240))
        screen.blit(text_surface, (pos[0] - 45, pos[1] - 38))


def draw_end_overlay(screen, end_message, big_font):
    overlay = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    winner = end_message.get("winner_text", "Fin de partie")
    score_text = (
        f"A: {end_message.get('team_a_score', 0)} | "
        f"B: {end_message.get('team_b_score', 0)}"
    )

    txt1 = big_font.render(winner, True, (255, 255, 255))
    txt2 = big_font.render(score_text, True, (255, 255, 255))

    screen.blit(txt1, (1280 // 2 - txt1.get_width() // 2, 300))
    screen.blit(txt2, (1280 // 2 - txt2.get_width() // 2, 360))
