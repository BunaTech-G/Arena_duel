import unittest
from unittest import mock

from ui import shutdown


class _FakeTk:
    def call(self, *args):
        if args[:2] == ("after", "info"):
            return ()
        return ()


class ShutdownHelpersTests(unittest.TestCase):
    def test_destroy_root_window_gracefully_quits_before_destroying(self):
        call_order = []
        fake_window = mock.Mock()
        fake_window.tk = _FakeTk()
        fake_window.winfo_exists.return_value = True
        setattr(fake_window, "_arena_after_callback_ids", set())
        fake_window.quit.side_effect = lambda: call_order.append("quit")
        fake_window.destroy.side_effect = lambda: call_order.append("destroy")

        result = shutdown.destroy_root_window_gracefully(fake_window)

        self.assertTrue(result)
        self.assertEqual(call_order, ["quit", "destroy"])


if __name__ == "__main__":
    unittest.main()
