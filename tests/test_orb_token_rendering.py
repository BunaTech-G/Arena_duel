import importlib
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame


asset_pipeline = importlib.import_module("game.asset_pipeline")
arena_module = importlib.import_module("game.arena")
orb_module = importlib.import_module("game.orb")
settings_module = importlib.import_module("game.settings")
load_orb_token_asset = asset_pipeline.load_orb_token_asset
draw_orb_collection_effect = arena_module.draw_orb_collection_effect
draw_orb_visual = arena_module.draw_orb_visual
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

    def test_loads_scaled_orb_token_asset(self):
        token = load_orb_token_asset(size=(40, 40), allow_placeholder=False)

        self.assertIsNotNone(token)
        self.assertEqual(token.get_size(), (40, 40))

    def test_draw_orb_visual_uses_token_asset(self):
        token = pygame.Surface((36, 36), pg_srcalpha)
        token.fill((255, 200, 60, 255))

        with patch("game.arena.load_orb_token_asset", return_value=token) as load_token:
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
        self.assertGreater(self.surface.get_bounding_rect(min_alpha=1).width, 0)

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
        self.assertGreater(self.surface.get_bounding_rect(min_alpha=1).width, 0)

    def test_orb_can_roll_rare_variant(self):
        with patch("game.orb.random.random", return_value=0.0):
            with patch("game.orb.random.randint", side_effect=[80, 90]):
                orb = Orb(pygame.Rect(0, 0, 200, 200), [])

        self.assertEqual(orb.variant, "rare")
        self.assertEqual(orb.value, ORB_RARE_SCORE_VALUE)


if __name__ == "__main__":
    unittest.main()
