import math
import importlib
import os
import unittest
from unittest.mock import patch

import pygame

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


asset_pipeline = importlib.import_module("game.asset_pipeline")
arena_module = importlib.import_module("game.arena")
hud_module = importlib.import_module("game.hud_panels")
orb_module = importlib.import_module("game.orb")
settings_module = importlib.import_module("game.settings")
load_orb_token_asset = asset_pipeline.load_orb_token_asset
draw_orb_collection_effect = arena_module.draw_orb_collection_effect
draw_orb_visual = arena_module.draw_orb_visual
draw_background = arena_module.draw_background
draw_arena = arena_module.draw_arena
get_arena_rect = arena_module.get_arena_rect
get_map_layout = arena_module.get_map_layout
get_obstacles = arena_module.get_obstacles
draw_rune_trap = getattr(arena_module, "_draw_rune_trap")
draw_match_hud = hud_module.draw_match_hud
draw_player_summary_row = hud_module.draw_player_summary_row
get_shared_player_score_slot_width = hud_module.get_shared_player_score_slot_width
should_show_player_score = hud_module.should_show_player_score
Orb = orb_module.Orb
ORB_RARE_SCORE_VALUE = settings_module.ORB_RARE_SCORE_VALUE
pg_init = getattr(pygame, "init")
pg_srcalpha = getattr(pygame, "SRCALPHA")


class OrbTokenRenderingTests(unittest.TestCase):
    def setUp(self):
        pg_init()
        if not pygame.font.get_init():
            pygame.font.init()
        self.surface = pygame.Surface((180, 180), pg_srcalpha)

    def test_draw_orb_collection_effect_rebuilds_font_after_font_quit(self):
        getattr(arena_module, "_ORB_EFFECT_FONT_CACHE").clear()

        self.assertTrue(
            draw_orb_collection_effect(
                self.surface,
                x=90,
                y=90,
                value=3,
                elapsed_ms=100.0,
                started_at_ms=0.0,
            )
        )

        pygame.font.quit()
        pygame.font.init()

        self.assertTrue(
            draw_orb_collection_effect(
                self.surface,
                x=90,
                y=90,
                value=5,
                elapsed_ms=120.0,
                started_at_ms=0.0,
                combo_count=2,
                combo_bonus=1,
            )
        )

    def test_loads_scaled_orb_token_asset(self):
        token = load_orb_token_asset(size=(40, 40), allow_placeholder=False)

        self.assertIsNotNone(token)
        self.assertEqual(token.get_size(), (40, 40))

    def test_draw_orb_visual_uses_token_asset(self):
        token = pygame.Surface((36, 36), pg_srcalpha)
        token.fill((255, 200, 60, 255))

        with patch(
            "game.arena.load_orb_token_asset",
            return_value=token,
        ) as load_token:
            draw_orb_visual(
                self.surface,
                90,
                90,
                12,
                elapsed_ms=240.0,
                value=ORB_RARE_SCORE_VALUE,
                variant="rare",
                spawned_at_ms=120.0,
            )

        self.assertEqual(load_token.call_count, 1)
        self.assertGreaterEqual(load_token.call_args.kwargs["size"][0], 36)
        self.assertGreater(
            self.surface.get_bounding_rect(min_alpha=1).width,
            0,
        )

    def test_draw_player_summary_row_uses_token_badge_asset(self):
        token = pygame.Surface((28, 28), pg_srcalpha)
        token.fill((255, 200, 60, 255))
        font = pygame.font.SysFont("Segoe UI", 18)

        with patch(
            "game.hud_panels.load_orb_token_asset",
            return_value=token,
        ) as load_token:
            with patch(
                "game.hud_panels.load_sprite_portrait",
                return_value=None,
            ):
                draw_player_summary_row(
                    self.surface,
                    font,
                    12,
                    12,
                    name="Aether",
                    score=7,
                    accent_color=(100, 186, 255),
                    panel_width=220,
                    portrait_size=26,
                )

        self.assertEqual(load_token.call_count, 1)
        self.assertGreater(
            self.surface.get_bounding_rect(min_alpha=1).width,
            0,
        )

    def test_draw_match_hud_uses_token_asset_in_score_panels(self):
        token = pygame.Surface((32, 32), pg_srcalpha)
        token.fill((255, 200, 60, 255))
        font = pygame.font.SysFont("Segoe UI", 20)

        class DummyLayout:
            margin = 48
            top = 220
            hud_height = 220

        with patch(
            "game.hud_panels.load_orb_token_asset",
            return_value=token,
        ) as load_token:
            with patch(
                "game.hud_panels.load_sprite_portrait",
                return_value=None,
            ):
                draw_match_hud(
                    self.surface,
                    font,
                    font,
                    DummyLayout(),
                    team_a_title="Embrasés",
                    team_b_title="Aéthers",
                    team_a_score=9,
                    team_b_score=12,
                    remaining_time=42,
                    team_a_rows=[
                        {
                            "name": "A1",
                            "score": 4,
                            "accent_color": (243, 201, 107),
                            "sprite_id": "skeleton_mascot",
                        }
                    ],
                    team_b_rows=[
                        {
                            "name": "B1",
                            "score": 6,
                            "accent_color": (100, 186, 255),
                            "sprite_id": "skeleton_mascot",
                        }
                    ],
                    match_duration=60,
                )

        self.assertGreaterEqual(load_token.call_count, 2)
        self.assertGreater(
            self.surface.get_bounding_rect(min_alpha=1).width,
            0,
        )

    def test_arena_background_stays_visibly_lit(self):
        layout = get_map_layout()
        arena_rect = get_arena_rect(layout)
        obstacles = get_obstacles(layout)
        surface = pygame.Surface(layout.window_size)

        draw_background(surface, layout)
        draw_arena(
            surface,
            arena_rect,
            obstacles,
            layout=layout,
            elapsed_ms=0.0,
        )

        luma_samples = []
        for x in range(0, layout.window_size[0], 80):
            for y in range(0, layout.window_size[1], 80):
                red, green, blue, _ = surface.get_at((x, y))
                luma_samples.append((0.2126 * red) + (0.7152 * green) + (0.0722 * blue))

        average_luma = sum(luma_samples) / len(luma_samples)
        bright_samples = sum(value > 35.0 for value in luma_samples)

        self.assertGreater(average_luma, 40.0)
        self.assertGreater(bright_samples, 120)

    def test_rune_trap_handles_low_presence_alpha_transition(self):
        rect = pygame.Rect(52, 52, 52, 52)
        elapsed_ms = (
            (-math.pi / 2.0) - (rect.centerx * 0.012) + (2.0 * math.pi)
        ) * 260.0

        draw_rune_trap(
            self.surface,
            rect,
            elapsed_ms=elapsed_ms,
            active_presence=0.03,
        )

        self.assertGreater(
            self.surface.get_bounding_rect(min_alpha=1).width,
            0,
        )

    def test_single_player_team_hides_duplicate_row_score(self):
        self.assertFalse(should_show_player_score(30, 30, 1))
        self.assertTrue(should_show_player_score(293, 120, 2))

    def test_shared_score_slot_width_handles_both_sides(self):
        font = pygame.font.SysFont("Segoe UI", 18)
        width = get_shared_player_score_slot_width(
            font,
            260,
            [{"player_score": 30}],
            [{"player_score": 9999999}],
            30,
            12000000,
        )

        self.assertGreaterEqual(width, 52)

    def test_draw_orb_collection_effect_is_active_during_fade(self):
        is_active = draw_orb_collection_effect(
            self.surface,
            x=90,
            y=90,
            value=ORB_RARE_SCORE_VALUE,
            elapsed_ms=160.0,
            started_at_ms=0.0,
        )

        self.assertTrue(is_active)
        self.assertGreater(
            self.surface.get_bounding_rect(min_alpha=1).width,
            0,
        )

    def test_orb_can_roll_rare_variant(self):
        with patch("game.orb.random.random", return_value=0.0):
            with patch("game.orb.random.randint", side_effect=[80, 90]):
                orb = Orb(pygame.Rect(0, 0, 200, 200), [])

        self.assertEqual(orb.variant, "rare")
        self.assertEqual(orb.value, ORB_RARE_SCORE_VALUE)


if __name__ == "__main__":
    unittest.main()
