import unittest

from game.match_text import (
    build_scoreline_candidates,
    format_pickup_event,
    format_scoreline,
    format_trap_event,
)


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

    def test_format_pickup_event_mentions_rare_orb_and_combo(self):
        self.assertEqual(
            format_pickup_event(
                "Aelys",
                "A",
                4,
                combo_count=3,
                combo_bonus=2,
                variant="rare",
            ),
            "Braise · Aelys capte orbe rare +4 · combo x3 (+2)",
        )

    def test_format_trap_event_uses_named_trap_label(self):
        self.assertEqual(
            format_trap_event(
                "Nox",
                "B",
                trap_kind="spike_trap",
            ),
            "Azur · Nox heurte les pointes",
        )


if __name__ == "__main__":
    unittest.main()
