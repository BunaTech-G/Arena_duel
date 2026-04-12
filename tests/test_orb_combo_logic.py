import importlib
import os
import unittest

import pygame


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


player_module = importlib.import_module("game.player")
Player = player_module.Player
MovementIntent = importlib.import_module("game.control_models").MovementIntent
load_arena_layout = importlib.import_module("game.arena_layout").load_arena_layout
trap_module = importlib.import_module("game.traps")
build_match_traps = trap_module.build_match_traps
update_match_traps = trap_module.update_match_traps
TRAP_SLOW_DURATION_MS = importlib.import_module("game.settings").TRAP_SLOW_DURATION_MS
TRAP_SLOW_MULTIPLIER = importlib.import_module("game.settings").TRAP_SLOW_MULTIPLIER


class OrbComboLogicTests(unittest.TestCase):
    def test_local_player_combo_bonus_accumulates_within_window(self):
        player = Player(
            name="Alpha",
            x=100,
            y=100,
            color=(255, 255, 255),
            controls=None,
            team_code="A",
        )

        first_award, first_bonus = player.register_orb_pickup(1000.0, 1)
        second_award, second_bonus = player.register_orb_pickup(2200.0, 1)
        third_award, third_bonus = player.register_orb_pickup(3000.0, 1)

        self.assertEqual((first_award, first_bonus), (1, 0))
        self.assertEqual((second_award, second_bonus), (2, 1))
        self.assertEqual((third_award, third_bonus), (3, 2))
        self.assertEqual(player.score, 6)

    def test_local_player_combo_resets_after_window(self):
        player = Player(
            name="Beta",
            x=100,
            y=100,
            color=(255, 255, 255),
            controls=None,
            team_code="B",
        )

        player.register_orb_pickup(1000.0, 1)
        awarded_value, combo_bonus = player.register_orb_pickup(4000.0, 1)

        self.assertEqual((awarded_value, combo_bonus), (1, 0))
        self.assertEqual(player.combo_count, 1)

    def test_trap_resets_combo_and_applies_slow(self):
        player = Player(
            name="Gamma",
            x=100,
            y=100,
            color=(255, 255, 255),
            controls=None,
            team_code="A",
        )

        player.register_orb_pickup(1000.0, 1)
        player.register_orb_pickup(1800.0, 1)

        triggered = player.trigger_trap(2000.0)

        self.assertTrue(triggered)
        self.assertEqual(player.combo_count, 0)
        self.assertEqual(player.get_combo_remaining_ms(2000.0), 0)
        self.assertAlmostEqual(
            player.get_speed_multiplier(2200.0),
            TRAP_SLOW_MULTIPLIER,
        )
        self.assertEqual(
            player.get_speed_multiplier(2000.0 + TRAP_SLOW_DURATION_MS + 1),
            1.0,
        )

    def test_trap_reduces_movement_distance(self):
        arena_rect = pygame.Rect(0, 0, 400, 400)
        player = Player(
            name="Delta",
            x=100,
            y=100,
            color=(255, 255, 255),
            controls=None,
            team_code="B",
        )

        player.trigger_trap(1000.0)
        player.update_from_intent(
            MovementIntent(right=True),
            arena_rect,
            (),
            elapsed_ms=1100.0,
        )

        self.assertLess(player.x, 100 + player.speed)
        self.assertAlmostEqual(
            player.x,
            100 + player.speed * TRAP_SLOW_MULTIPLIER,
            places=2,
        )

    def test_match_traps_cycle_and_cover_multiple_types(self):
        layout = load_arena_layout()
        trap_states = build_match_traps(layout)

        update_match_traps(trap_states, 6000.0)

        self.assertGreaterEqual(len({trap.kind for trap in trap_states}), 3)
        self.assertTrue(any(trap.last_toggle_ms > 0.0 for trap in trap_states))


if __name__ == "__main__":
    unittest.main()
