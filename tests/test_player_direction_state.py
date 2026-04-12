import importlib
import os
import unittest

import pygame


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


player_module = importlib.import_module("game.player")
control_models = importlib.import_module("game.control_models")
Player = player_module.Player
MovementIntent = control_models.MovementIntent


class PlayerDirectionStateTests(unittest.TestCase):
    def setUp(self):
        self.arena_rect = pygame.Rect(0, 0, 640, 480)

    def _build_player(self) -> Player:
        return Player(
            name="Test",
            x=160,
            y=160,
            color=(255, 255, 255),
            controls=None,
            team_code="A",
            sprite_id="skeleton_fighter_ember",
        )

    def test_keeps_last_direction_when_idle(self):
        player = self._build_player()

        player.update_from_intent(
            MovementIntent(right=True),
            self.arena_rect,
            [],
        )
        self.assertEqual(player.direction_name, "right")

        player.update_from_intent(MovementIntent(), self.arena_rect, [])

        self.assertFalse(player.is_moving)
        self.assertEqual(player.direction_name, "right")

    def test_changes_sprite_direction_only_when_input_direction_changes(self):
        player = self._build_player()

        player.update_from_intent(MovementIntent(down=True), self.arena_rect, [])
        self.assertEqual(player.direction_name, "down")

        player.update_from_intent(MovementIntent(down=True), self.arena_rect, [])
        self.assertEqual(player.direction_name, "down")

        player.update_from_intent(MovementIntent(left=True), self.arena_rect, [])
        self.assertEqual(player.direction_name, "left")

    def test_diagonal_keeps_current_direction_if_still_pressed(self):
        player = self._build_player()
        player.direction_name = "up"

        player.update_from_intent(
            MovementIntent(up=True, right=True),
            self.arena_rect,
            [],
        )

        self.assertEqual(player.direction_name, "up")


if __name__ == "__main__":
    unittest.main()
