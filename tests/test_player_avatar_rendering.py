import importlib
import os
import unittest
from unittest.mock import patch

import pygame


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


arena_module = importlib.import_module("game.arena")
draw_player_avatar = arena_module.draw_player_avatar
pg_init = getattr(pygame, "init")
pg_srcalpha = getattr(pygame, "SRCALPHA")


class PlayerAvatarRenderingTests(unittest.TestCase):
    def setUp(self):
        pg_init()
        if not pygame.font.get_init():
            pygame.font.init()
        self.surface = pygame.Surface((320, 240), pg_srcalpha)
        self.font = pygame.font.SysFont("Segoe UI", 18)
        self.sprite = pygame.Surface((96, 96), pg_srcalpha)

    def test_uses_walk_animation_while_moving(self):
        with patch(
            "game.arena.load_sprite_animation_frame",
            return_value=self.sprite,
        ) as load_frame:
            draw_player_avatar(
                self.surface,
                name="Test",
                x=120,
                y=120,
                radius=24,
                accent_color=(255, 255, 255),
                name_font=self.font,
                sprite_id="skeleton_fighter_ember",
                facing=1,
                elapsed_ms=240.0,
                moving=True,
            )

        self.assertEqual(load_frame.call_count, 1)
        self.assertEqual(load_frame.call_args.args[1], "walk")

    def test_uses_idle_animation_when_still(self):
        with patch(
            "game.arena.load_sprite_animation_frame",
            return_value=self.sprite,
        ) as load_frame:
            draw_player_avatar(
                self.surface,
                name="Test",
                x=120,
                y=120,
                radius=24,
                accent_color=(255, 255, 255),
                name_font=self.font,
                sprite_id="skeleton_fighter_ember",
                facing=-1,
                elapsed_ms=240.0,
                moving=False,
            )

        self.assertEqual(load_frame.call_count, 1)
        self.assertEqual(load_frame.call_args.args[1], "idle")

    def test_accepts_combo_badge_arguments(self):
        with patch(
            "game.arena.load_sprite_animation_frame",
            return_value=self.sprite,
        ):
            draw_player_avatar(
                self.surface,
                name="Test",
                x=120,
                y=120,
                radius=24,
                accent_color=(255, 255, 255),
                name_font=self.font,
                sprite_id="skeleton_fighter_ember",
                facing=1,
                elapsed_ms=240.0,
                moving=True,
                combo_count=3,
                combo_remaining_ms=1200,
            )

        self.assertGreater(self.surface.get_bounding_rect(min_alpha=1).width, 0)


if __name__ == "__main__":
    unittest.main()
