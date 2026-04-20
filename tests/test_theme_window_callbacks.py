import importlib
import unittest
from types import SimpleNamespace
from unittest import mock


theme_module = importlib.import_module("ui.theme")


class _FakeWindow:
    def __init__(self):
        self.after_calls = {}
        self.after_cancelled = []
        self.bindings = {}
        self._after_index = 0
        self._exists = True

    def after(self, delay_ms, callback):
        self._after_index += 1
        callback_id = f"after#{self._after_index}"
        self.after_calls[callback_id] = {
            "delay_ms": delay_ms,
            "callback": callback,
        }
        return callback_id

    def after_cancel(self, callback_id):
        self.after_cancelled.append(callback_id)
        self.after_calls.pop(callback_id, None)

    def bind(self, event_name, callback, add=None):
        self.bindings[event_name] = {
            "callback": callback,
            "add": add,
        }

    def winfo_exists(self):
        return self._exists

    def deiconify(self):
        return None

    def update_idletasks(self):
        return None

    def state(self, *_args):
        return "normal"

    def lift(self):
        return None

    def focus_force(self):
        return None

    def attributes(self, *_args):
        return None


class ThemeWindowCallbackTests(unittest.TestCase):
    def test_apply_window_icon_retry_is_cancelled_on_destroy(self):
        window = _FakeWindow()

        with mock.patch.object(
            theme_module,
            "_apply_window_icon_once",
        ) as apply_once:
            theme_module.apply_window_icon(
                window,
                default=True,
                retry_after_ms=220,
            )

        self.assertEqual(apply_once.call_count, 1)
        self.assertEqual(len(window.after_calls), 1)

        destroy_callback = window.bindings["<Destroy>"]["callback"]
        destroy_callback(SimpleNamespace(widget=window))

        self.assertEqual(window.after_cancelled, ["after#1"])
        self.assertEqual(getattr(window, "_arena_after_callback_ids"), set())

    def test_present_window_cancels_follow_up_callbacks_on_destroy(self):
        window = _FakeWindow()

        theme_module.present_window(window)

        present_call = window.after_calls.pop("after#1")
        present_call["callback"]()

        self.assertEqual(sorted(window.after_calls), ["after#2", "after#3"])

        destroy_callback = window.bindings["<Destroy>"]["callback"]
        destroy_callback(SimpleNamespace(widget=window))

        self.assertCountEqual(window.after_cancelled, ["after#2", "after#3"])
        self.assertEqual(getattr(window, "_arena_after_callback_ids"), set())


if __name__ == "__main__":
    unittest.main()
