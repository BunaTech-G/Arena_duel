import os
import shutil
import sys
import tempfile
import types
import unittest
import importlib
from datetime import datetime


TEST_APPDATA_DIR = tempfile.mkdtemp(prefix="arena_duel_demo_tests_")
os.environ["APPDATA"] = TEST_APPDATA_DIR

if "mariadb" not in sys.modules:
    sys.modules["mariadb"] = types.SimpleNamespace(
        Error=Exception,
        IntegrityError=Exception,
        connect=lambda **_kwargs: None,
    )


runtime_utils = importlib.import_module("runtime_utils")
players_module = importlib.import_module("db.players")
matches_module = importlib.import_module("db.matches")


class DemoStorageTests(unittest.TestCase):
    def setUp(self):
        self.test_appdata_dir = tempfile.mkdtemp(prefix="arena_duel_demo_case_")
        os.environ["APPDATA"] = self.test_appdata_dir
        runtime_utils.clear_runtime_override()
        runtime_utils.set_runtime_override("demo_local_storage_enabled", True)
        runtime_utils.set_runtime_override("demo_local_storage_force", True)
        runtime_utils.set_runtime_override(
            "demo_seed_players",
            ["Aegis", "Selene", "Orion", "Nyx"],
        )

    def tearDown(self):
        runtime_utils.clear_runtime_override()
        shutil.rmtree(self.test_appdata_dir, ignore_errors=True)

    def test_demo_registry_exposes_seed_players_without_database(self):
        available, rows = players_module.get_player_registry_snapshot()

        self.assertTrue(available)
        self.assertEqual(
            [row[1] for row in rows],
            ["Aegis", "Nyx", "Orion", "Selene"],
        )

    def test_demo_storage_can_create_player_and_archive_match(self):
        ok, message = players_module.create_player("Iris")

        self.assertTrue(ok)
        self.assertIn("Iris", message)

        finished_at = datetime(2026, 4, 16, 12, 0, 0)

        archived, archive_message = matches_module.save_team_match(
            [
                {
                    "name": "Aegis",
                    "team": "A",
                    "individual_score": 5,
                    "control_mode": "human",
                    "is_ai": False,
                    "slot_number": 1,
                },
                {
                    "name": "Iris",
                    "team": "B",
                    "individual_score": 3,
                    "control_mode": "human",
                    "is_ai": False,
                    "slot_number": 2,
                },
            ],
            5,
            3,
            90,
            winner_team="A",
            mode_code="LOCAL_HUMAN",
            arena_code="forgotten_sanctum",
            finished_at=finished_at,
        )

        self.assertTrue(archived)
        self.assertIn("archivee", archive_message)

        history_rows = matches_module.get_match_history()

        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0]["team_a_players"], "Aegis")
        self.assertEqual(history_rows[0]["team_b_players"], "Iris")
        self.assertEqual(history_rows[0]["team_a_score"], 5)
        self.assertEqual(history_rows[0]["team_b_score"], 3)
        self.assertEqual(history_rows[0]["winner_team"], "A")
        self.assertEqual(history_rows[0]["winner_display"], "Bastion braise")
        self.assertEqual(history_rows[0]["arena_code"], "forgotten_sanctum")
        self.assertEqual(history_rows[0]["mode_code"], "LOCAL_HUMAN")
        self.assertEqual(history_rows[0]["source_code"], "LOCAL")
        self.assertEqual(history_rows[0]["played_at"], "2026-04-16 12:00:00")


if __name__ == "__main__":
    unittest.main()
