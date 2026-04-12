import unittest

import arcade

from game.arcade_net_match_window import _build_input_state


class ArcadeNetworkMatchWindowTests(unittest.TestCase):
    def test_build_input_state_supports_multiple_keyboard_layouts(self):
        pressed_keys = {arcade.key.Z, arcade.key.Q}
        up, down, left, right = _build_input_state(pressed_keys)

        self.assertTrue(up)
        self.assertFalse(down)
        self.assertTrue(left)
        self.assertFalse(right)


if __name__ == "__main__":
    unittest.main()
