import unittest
from types import SimpleNamespace

from game.arcade_window import (
    ARENA_FLOOR_ASSET,
    SPRITE_ANIMATION_FRAME_MS,
    WINDOW_BACKGROUND_ASSET,
    _format_timer_value,
    _resolve_local_team_rows,
    _resolve_player_frame_spec,
    _resolve_background_texture_path,
    _resolve_sprite_frame_path,
    _resolve_trap_presence,
)


class ArcadeWindowAssetResolutionTests(unittest.TestCase):
    def test_background_texture_paths_exist(self):
        for asset_id in (WINDOW_BACKGROUND_ASSET, ARENA_FLOOR_ASSET):
            background_path = _resolve_background_texture_path(asset_id)

            self.assertIsNotNone(background_path)
            self.assertTrue(background_path.exists())

    def test_left_direction_uses_existing_sprite_frame(self):
        sprite_path, mirrored = _resolve_sprite_frame_path(
            "skeleton_fighter_ember",
            "left",
        )

        self.assertIsNotNone(sprite_path)
        self.assertTrue(sprite_path.exists())
        self.assertTrue(mirrored)

    def test_up_direction_uses_existing_sprite_frame(self):
        sprite_path, mirrored = _resolve_sprite_frame_path(
            "skeleton_fighter_aether",
            "up",
        )

        self.assertIsNotNone(sprite_path)
        self.assertTrue(sprite_path.exists())
        self.assertFalse(mirrored)

    def test_format_timer_value_uses_mm_ss(self):
        self.assertEqual(_format_timer_value(125), "02:05")

    def test_resolve_local_team_rows_applies_sprite_fallback(self):
        players = [
            SimpleNamespace(
                name="Alpha",
                score=5,
                team_code="A",
                color=(243, 201, 107, 255),
                sprite_id=None,
            ),
            SimpleNamespace(
                name="Sigma",
                score=3,
                team_code="B",
                color=(100, 215, 255, 255),
                sprite_id=None,
            ),
        ]

        team_a_rows = _resolve_local_team_rows(players, "A")
        team_b_rows = _resolve_local_team_rows(players, "B")

        self.assertEqual(team_a_rows[0]["sprite_id"], "skeleton_fighter_ember")
        self.assertEqual(
            team_b_rows[0]["sprite_id"],
            "skeleton_fighter_aether",
        )

    def test_resolve_trap_presence_interpolates_toggle(self):
        trap_state = SimpleNamespace(active=True, last_toggle_ms=100.0)

        self.assertGreater(_resolve_trap_presence(trap_state, 210.0), 0.4)
        self.assertLessEqual(_resolve_trap_presence(trap_state, 400.0), 1.0)

    def test_player_frame_spec_animates_when_elapsed_changes(self):
        first_path, first_mirrored = _resolve_player_frame_spec(
            "skeleton_fighter_ember",
            "right",
            elapsed_ms=0.0,
            is_moving=True,
        )
        next_path, next_mirrored = _resolve_player_frame_spec(
            "skeleton_fighter_ember",
            "right",
            elapsed_ms=float(SPRITE_ANIMATION_FRAME_MS),
            is_moving=True,
        )

        self.assertIsNotNone(first_path)
        self.assertIsNotNone(next_path)
        self.assertFalse(first_mirrored)
        self.assertFalse(next_mirrored)
        self.assertNotEqual(first_path, next_path)


if __name__ == "__main__":
    unittest.main()
