import unittest
from unittest import mock

from game.runtime_backend import (
    BACKEND_ARCADE,
    BACKEND_PYGAME,
    get_local_game_backend_status,
    normalize_gameplay_backend,
    resolve_local_game_backend,
)


class LocalGameRuntimeBackendTests(unittest.TestCase):
    def test_unknown_backend_falls_back_to_pygame(self):
        self.assertEqual(normalize_gameplay_backend("unknown"), BACKEND_PYGAME)

    def test_runtime_default_backend_prefers_arcade(self):
        with mock.patch(
            "game.runtime_backend.load_runtime_config",
            return_value={"gameplay_backend": BACKEND_ARCADE},
        ):
            backend = resolve_local_game_backend()

        self.assertEqual(backend, BACKEND_ARCADE)

    def test_runtime_config_can_request_arcade(self):
        backend = resolve_local_game_backend({"gameplay_backend": BACKEND_ARCADE})
        self.assertEqual(backend, BACKEND_ARCADE)

    def test_arcade_request_falls_back_when_dependency_missing(self):
        with mock.patch(
            "game.runtime_backend.is_arcade_available",
            return_value=False,
        ):
            status = get_local_game_backend_status({"gameplay_backend": BACKEND_ARCADE})

        self.assertEqual(status["requested"], BACKEND_ARCADE)
        self.assertEqual(status["effective"], BACKEND_PYGAME)
        self.assertEqual(status["fallback_reason"], "arcade_unavailable")


if __name__ == "__main__":
    unittest.main()
