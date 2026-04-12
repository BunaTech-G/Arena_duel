import unittest

import arcade

from game.arcade_net_match_window import (
    _build_input_state,
    _resolve_combo_ratio,
    _resolve_direction_from_delta,
    _resolve_network_direction,
    _resolve_network_movement,
    _resolve_state_team_rows,
)


class ArcadeNetworkMatchWindowTests(unittest.TestCase):
    def test_build_input_state_supports_multiple_keyboard_layouts(self):
        pressed_keys = {arcade.key.Z, arcade.key.Q}
        up, down, left, right = _build_input_state(pressed_keys)

        self.assertTrue(up)
        self.assertFalse(down)
        self.assertTrue(left)
        self.assertFalse(right)

    def test_team_rows_are_sorted_and_use_sprite_fallbacks(self):
        payload = {
            "players": [
                {"slot": 2, "team": "A", "name": "Bravo", "score": 3},
                {"slot": 1, "team": "A", "name": "Alpha", "score": 5},
                {"slot": 3, "team": "B", "name": "Sigma", "score": 2},
            ]
        }

        team_a_rows = _resolve_state_team_rows(payload, "A")
        team_b_rows = _resolve_state_team_rows(payload, "B")

        self.assertEqual(
            [row["name"] for row in team_a_rows],
            ["Alpha", "Bravo"],
        )
        self.assertEqual(team_a_rows[0]["sprite_id"], "skeleton_fighter_ember")
        self.assertEqual(
            team_b_rows[0]["sprite_id"],
            "skeleton_fighter_aether",
        )

    def test_combo_ratio_is_clamped(self):
        self.assertEqual(_resolve_combo_ratio(-10), 0.0)
        self.assertGreater(_resolve_combo_ratio(1000), 0.0)
        self.assertEqual(_resolve_combo_ratio(999999), 1.0)

    def test_direction_from_delta_prefers_main_axis(self):
        self.assertEqual(
            _resolve_direction_from_delta(4.0, 1.0, "up"),
            "right",
        )
        self.assertEqual(
            _resolve_direction_from_delta(-1.0, 5.0, "left"),
            "down",
        )
        self.assertEqual(
            _resolve_direction_from_delta(0.0, 0.0, "left"),
            "left",
        )

    def test_network_direction_prefers_server_payload_when_available(self):
        self.assertEqual(
            _resolve_network_direction(
                {"direction": "down"},
                4.0,
                -4.0,
                "left",
            ),
            "down",
        )

    def test_network_movement_prefers_server_payload_when_available(self):
        self.assertTrue(_resolve_network_movement({"is_moving": True}, 0.0, 0.0))
        self.assertFalse(_resolve_network_movement({"is_moving": False}, 5.0, 0.0))
        self.assertTrue(_resolve_network_movement({}, 1.0, 0.0))


if __name__ == "__main__":
    unittest.main()
