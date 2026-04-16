import unittest

from game.match_text import build_scoreline_candidates, format_scoreline


class MatchTextTests(unittest.TestCase):
    def test_grouped_scoreline_uses_explicit_team_points(self):
        self.assertEqual(
            format_scoreline(
                6745,
                114,
                score_format_mode="grouped",
            ),
            "Bastion braise : 6 745   |   Bastion azur : 114",
        )

    def test_scoreline_candidates_fallback_from_full_to_compact(self):
        candidates = build_scoreline_candidates(6745, 9999999)

        self.assertEqual(
            candidates[0],
            "Bastion braise : 6 745   |   Bastion azur : 9 999 999",
        )
        self.assertEqual(
            candidates[-1],
            "Braise : 6.7k  |  Azur : 10M",
        )


if __name__ == "__main__":
    unittest.main()
