import os
import unittest
from types import SimpleNamespace

import pygame

from game.hud_panels import (
    choose_text_candidate,
    compute_end_overlay_layout,
    compute_match_hud_layout,
    draw_match_event_banner,
    fit_text_to_width,
)


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


class HudPanelTextHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()
        cls.font = pygame.font.Font(None, 24)

    @classmethod
    def tearDownClass(cls):
        pygame.font.quit()

    def test_fit_text_to_width_truncates_long_names_with_ellipsis(self):
        max_width = 92
        text = "Pseudonyme_du_bastion_infiniment_long"

        fitted = fit_text_to_width(self.font, text, max_width)

        self.assertTrue(fitted.endswith("..."))
        self.assertLessEqual(self.font.size(fitted)[0], max_width)

    def test_choose_text_candidate_uses_shorter_variant_when_needed(self):
        long_text = "Bastion braise : 6 745   |   Bastion azur : 9 999 999"
        short_text = "Braise : 6.7k  |  Azur : 10M"
        max_width = self.font.size(short_text)[0]

        chosen = choose_text_candidate(
            self.font,
            [long_text, short_text],
            max_width,
        )

        self.assertEqual(chosen, short_text)

    def test_compute_match_hud_layout_returns_centered_timer_and_rows(self):
        layout = SimpleNamespace(margin=60, top=220, hud_height=220)

        hud_layout = compute_match_hud_layout(
            (1280, 720),
            layout,
            self.font,
            team_a_rows=[
                {"player_score": 3},
                {"player_score": 2},
            ],
            team_b_rows=[
                {"player_score": 1},
                {"player_score": 1},
            ],
            team_a_score=5,
            team_b_score=2,
        )

        self.assertEqual(hud_layout["timer_rect"].centerx, 640)
        self.assertLess(
            hud_layout["team_a_score_rect"].right,
            hud_layout["timer_rect"].left,
        )
        self.assertGreater(
            hud_layout["team_b_score_rect"].left,
            hud_layout["timer_rect"].right,
        )
        self.assertGreater(hud_layout["roster_y"], hud_layout["timer_rect"].bottom)
        self.assertGreater(hud_layout["shared_row_score_width"], 0)

    def test_compute_end_overlay_layout_returns_symmetric_team_cards(self):
        overlay_layout = compute_end_overlay_layout(
            (960, 540),
            2,
            footer_height=88,
            min_panel_height=380,
            min_available_rows_height=150,
        )

        self.assertEqual(overlay_layout["panel_rect"].centerx, 480)
        self.assertEqual(
            overlay_layout["team_a_rect"].width,
            overlay_layout["team_b_rect"].width,
        )
        self.assertEqual(
            overlay_layout["team_a_rect"].top,
            overlay_layout["team_b_rect"].top,
        )
        self.assertGreater(
            overlay_layout["team_b_rect"].left,
            overlay_layout["team_a_rect"].right,
        )
        self.assertGreaterEqual(overlay_layout["row_height"], 40)
        self.assertLessEqual(overlay_layout["row_height"], 48)

    def test_draw_match_event_banner_renders_center_panel(self):
        surface = pygame.Surface((960, 540), getattr(pygame, "SRCALPHA"))

        draw_match_event_banner(
            surface,
            self.font,
            "Braise · Aelys capte orbe rare +4 · combo x2 (+1)",
            accent_color=(242, 209, 118),
        )

        self.assertGreater(surface.get_bounding_rect(min_alpha=1).width, 0)


if __name__ == "__main__":
    unittest.main()
