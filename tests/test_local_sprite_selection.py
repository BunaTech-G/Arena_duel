import importlib
import os
import unittest
from unittest.mock import patch


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


build_human_vs_ai_players = importlib.import_module(
    "game.computer_opponent"
).build_human_vs_ai_players
control_models = importlib.import_module("game.control_models")
AI_CONTROL_MODE = control_models.AI_CONTROL_MODE
HUMAN_CONTROL_MODE = control_models.HUMAN_CONTROL_MODE
build_runtime_players = importlib.import_module(
    "game.game_window"
).build_runtime_players


class LocalSpriteSelectionTests(unittest.TestCase):
    def test_vs_ai_builder_preserves_human_sprite_and_assigns_ai_default(self):
        human_players = [
            {
                "slot": 4,
                "name": "Gardien libre",
                "team": "B",
                "sprite_id": "custom_test_sprite",
            }
        ]

        players = build_human_vs_ai_players(
            human_players,
            human_team="B",
            ai_team="A",
            difficulty="champion",
            prefer_arrow_controls=False,
        )

        human = next(
            player for player in players if player["control_mode"] == HUMAN_CONTROL_MODE
        )
        ai = next(
            player for player in players if player["control_mode"] == AI_CONTROL_MODE
        )

        self.assertEqual(human["sprite_id"], "custom_test_sprite")
        self.assertEqual(human["team"], "B")
        self.assertEqual(ai["team"], "A")
        self.assertEqual(ai["sprite_id"], "skeleton_fighter_ember")
        self.assertEqual(ai["ai_difficulty"], "champion")

    def test_runtime_players_use_selected_sprite_ids(self):
        players_config = [
            {
                "slot": 1,
                "name": "Alpha",
                "team": "A",
                "control_mode": HUMAN_CONTROL_MODE,
                "sprite_id": "skeleton_fighter_aether",
            },
            {
                "slot": 2,
                "name": "Beta",
                "team": "B",
                "control_mode": HUMAN_CONTROL_MODE,
                "sprite_id": "skeleton_fighter_ember",
            },
        ]

        with patch(
            "game.game_window.get_team_spawn_positions_for_layout",
            side_effect=[
                [(120, 140)],
                [(360, 140)],
            ],
        ):
            players, ai_controllers = build_runtime_players(
                players_config,
                layout=object(),
            )

        self.assertEqual(ai_controllers, {})
        players_by_name = {player.name: player for player in players}
        self.assertEqual(
            players_by_name["Alpha"].sprite_id,
            "skeleton_fighter_aether",
        )
        self.assertEqual(
            players_by_name["Beta"].sprite_id,
            "skeleton_fighter_ember",
        )


if __name__ == "__main__":
    unittest.main()
