import os
import unittest

import pygame

from game.hud_panels import choose_text_candidate, fit_text_to_width


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


if __name__ == "__main__":
    unittest.main()
