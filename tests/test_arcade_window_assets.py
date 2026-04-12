import unittest

from game.arcade_window import (
    ARENA_FLOOR_ASSET,
    WINDOW_BACKGROUND_ASSET,
    _resolve_background_texture_path,
    _resolve_sprite_frame_path,
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


if __name__ == "__main__":
    unittest.main()
