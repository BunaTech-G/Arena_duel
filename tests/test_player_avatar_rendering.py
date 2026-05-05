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

    def test_highlight_draws_marker_above_nameplate(self):
        normal_surface = pygame.Surface((320, 240), pg_srcalpha)

        with patch(
            "game.arena.load_sprite_animation_frame",
            return_value=self.sprite,
        ):
            draw_player_avatar(
                normal_surface,
                name="Test",
                x=120,
                y=120,
                radius=24,
                accent_color=(255, 255, 255),
                name_font=self.font,
                sprite_id="skeleton_fighter_ember",
                facing=1,
                elapsed_ms=240.0,
                moving=False,
                highlight=False,
            )
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
                moving=False,
                highlight=True,
            )

        normal_bounds = normal_surface.get_bounding_rect(min_alpha=1)
        highlight_bounds = self.surface.get_bounding_rect(min_alpha=1)

        self.assertLess(highlight_bounds.top, normal_bounds.top)

    def test_highlight_does_not_draw_outline_ring(self):
        radius = 24
        display_radius = max(radius, int(radius * 1.18))
        ring_center = (120, 120 - int(display_radius * 0.08))
        ring_radius = int(display_radius * 1.55)

        with (
            patch(
                "game.arena.load_sprite_animation_frame",
                return_value=self.sprite,
            ),
            patch.object(
                pygame.draw,
                "circle",
                wraps=pygame.draw.circle,
            ) as draw_circle,
        ):
            draw_player_avatar(
                self.surface,
                name="Test",
                x=120,
                y=120,
                radius=radius,
                accent_color=(255, 255, 255),
                name_font=self.font,
                sprite_id="skeleton_fighter_ember",
                facing=1,
                elapsed_ms=240.0,
                moving=False,
                highlight=True,
            )

        outline_calls = [
            call
            for call in draw_circle.call_args_list
            if call.args[0] is self.surface
            and call.args[2] == ring_center
            and call.args[3] == ring_radius
            and call.kwargs.get("width") == 2
        ]
        self.assertEqual(outline_calls, [])

    def test_control_marker_panel_stays_above_nameplate(self):
        radius = max(24, int(24 * 1.18))
        center_x = 120
        center_y = 120
        name_surface = self.font.render("Test", True, (255, 255, 255))
        name_rect = name_surface.get_rect(
            center=(center_x, center_y - int(radius * 2.0))
        )
        nameplate_rect = name_rect.inflate(18, 10)

        with patch.object(
            pygame.draw,
            "rect",
            wraps=pygame.draw.rect,
        ) as draw_rect:
            getattr(arena_module, "_draw_control_marker")(
                self.surface,
                center_x=center_x,
                center_y=center_y,
                radius=radius,
                accent_bright=(255, 255, 255),
                elapsed_ms=240.0,
            )

        panel_rect = draw_rect.call_args_list[1].args[2]
        self.assertLessEqual(panel_rect.bottom, nameplate_rect.top - 4)


if __name__ == "__main__":
    unittest.main()
