import unittest

from game.runtime_backend import (
    BACKEND_PYGAME,
    get_local_game_backend_status,
    normalize_gameplay_backend,
    resolve_local_game_backend,
)


class LocalGameRuntimeBackendTests(unittest.TestCase):
    def test_unknown_backend_falls_back_to_pygame(self):
        self.assertEqual(normalize_gameplay_backend("unknown"), BACKEND_PYGAME)

    def test_runtime_backend_is_locked_to_pygame(self):
        backend = resolve_local_game_backend()
        self.assertEqual(backend, BACKEND_PYGAME)

    def test_runtime_config_ignores_legacy_backend_request(self):
        backend = resolve_local_game_backend({"gameplay_backend": "legacy"})
        self.assertEqual(backend, BACKEND_PYGAME)

    def test_backend_status_reports_pygame_only(self):
        status = get_local_game_backend_status({"gameplay_backend": "legacy"})

        self.assertEqual(status["requested"], BACKEND_PYGAME)
        self.assertEqual(status["effective"], BACKEND_PYGAME)
        self.assertEqual(status["requested_label"], "Pygame")
        self.assertEqual(status["effective_label"], "Pygame")
        self.assertIsNone(status["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
