import importlib
import json
import os
import tempfile
import unittest
from tkinter import TclError
from unittest import mock

import customtkinter as ctk
import customtkinter.windows.ctk_tk as ctk_tk
from customtkinter.windows.widgets.appearance_mode import (
    appearance_mode_tracker,
)
from customtkinter.windows.widgets.scaling import scaling_tracker


auto_update_module = importlib.import_module("ui.auto_update")


def _register_widget_without_dpi_loop(cls, widget_callback, widget):
    window_root = cls.get_window_root_of_widget(widget)

    if window_root not in cls.window_widgets_dict:
        cls.window_widgets_dict[window_root] = [widget_callback]
    else:
        cls.window_widgets_dict[window_root].append(widget_callback)

    if window_root not in cls.window_dpi_scaling_dict:
        cls.window_dpi_scaling_dict[window_root] = cls.get_window_dpi_scaling(
            window_root
        )


def _register_appearance_callback_without_loop(cls, callback, widget=None):
    cls.callback_list.append(callback)

    if widget is None:
        return

    app = cls.get_tk_root_of_widget(widget)
    if app not in cls.app_list:
        cls.app_list.append(app)


def _walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


def _collect_button_texts(widget) -> list[str]:
    texts = []
    for child in _walk_widgets(widget):
        try:
            if isinstance(child, ctk.CTkButton):
                texts.append(child.cget("text"))
        except TclError:
            continue
    return texts


def _collect_label_texts(widget) -> list[str]:
    texts = []
    for child in _walk_widgets(widget):
        try:
            if isinstance(child, ctk.CTkLabel):
                texts.append(child.cget("text"))
        except TclError:
            continue
    return [text for text in texts if text]


class _FakeWindow:
    def __init__(self):
        self._exists = True
        self._after_callback = None
        self._after_id = None

    def bind(self, *_args, **_kwargs):
        return None

    def after(self, _delay_ms, callback):
        self._after_callback = callback
        self._after_id = "after#1"
        return self._after_id

    def after_cancel(self, callback_id):
        if self._after_id == callback_id:
            self._after_id = None

    def winfo_exists(self):
        return self._exists

    def trigger_after(self):
        if self._after_callback is not None:
            self._after_callback()

    def destroy_window(self):
        self._exists = False


class _FakeNotice:
    def __init__(self, master=None, **_kwargs):
        self.master = master
        self._exists = True

    def place(self, **_kwargs):
        return None

    def lift(self):
        return None

    def dismiss(self):
        self._exists = False

    def winfo_exists(self):
        return self._exists


class AutoUpdateLogicTests(unittest.TestCase):
    def test_check_for_available_update_detects_newer_manifest(self):
        payload = json.dumps(
            {
                "version": "1.2.0",
                "update_url": "https://example.com/update",
            }
        ).encode("utf-8")
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = payload

        with mock.patch.object(
            auto_update_module.urllib.request,
            "urlopen",
            return_value=response,
        ):
            update = auto_update_module.check_for_available_update(
                current_version="1.0.0",
                manifest_url="https://example.com/version.json",
            )

        self.assertIsNotNone(update)
        self.assertEqual(update.version, "1.2.0")
        self.assertEqual(update.update_url, "https://example.com/update")

    def test_check_for_available_update_prefers_windows_installer_url(self):
        payload = json.dumps(
            {
                "version": "1.2.0",
                "update_url": "https://example.com/releases",
                "windows_installer_url": ("https://example.com/Setup_ArenaDuel.exe"),
            }
        ).encode("utf-8")
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = payload

        with (
            mock.patch.object(
                auto_update_module.urllib.request,
                "urlopen",
                return_value=response,
            ),
            mock.patch.object(
                auto_update_module.sys,
                "platform",
                "win32",
            ),
        ):
            update = auto_update_module.check_for_available_update(
                current_version="1.0.0",
                manifest_url="https://example.com/version.json",
            )

        self.assertIsNotNone(update)
        self.assertEqual(
            update.update_url,
            "https://example.com/Setup_ArenaDuel.exe",
        )

    def test_check_for_available_update_reads_remind_later_hours(self):
        payload = json.dumps(
            {
                "version": "1.2.0",
                "update_url": "https://example.com/update",
                "remind_later_hours": 6,
            }
        ).encode("utf-8")
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = payload

        with mock.patch.object(
            auto_update_module.urllib.request,
            "urlopen",
            return_value=response,
        ):
            update = auto_update_module.check_for_available_update(
                current_version="1.0.0",
                manifest_url="https://example.com/version.json",
            )

        self.assertIsNotNone(update)
        self.assertEqual(update.remind_later_seconds, 6 * 60 * 60)

    def test_check_for_available_update_stays_silent_when_up_to_date(self):
        payload = json.dumps(
            {
                "version": "1.0.0",
                "update_url": "https://example.com/update",
            }
        ).encode("utf-8")
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = payload

        with mock.patch.object(
            auto_update_module.urllib.request,
            "urlopen",
            return_value=response,
        ):
            update = auto_update_module.check_for_available_update(
                current_version="1.0.0",
                manifest_url="https://example.com/version.json",
            )

        self.assertIsNone(update)

    def test_check_for_available_update_stays_silent_without_network(self):
        with mock.patch.object(
            auto_update_module.urllib.request,
            "urlopen",
            side_effect=auto_update_module.urllib.error.URLError("offline"),
        ):
            update = auto_update_module.check_for_available_update(
                current_version="1.0.0",
                manifest_url="https://example.com/version.json",
            )

        self.assertIsNone(update)

    def test_open_update_page_swallows_browser_errors(self):
        with mock.patch.object(
            auto_update_module.webbrowser,
            "open_new_tab",
            side_effect=auto_update_module.webbrowser.Error(),
        ):
            result = auto_update_module.open_update_page("https://example.com/update")

        self.assertFalse(result)

    def test_later_choice_persists_snooze_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            service = auto_update_module.AutoUpdateService(
                state_path=state_path,
                now_provider=lambda: 100,
                remind_later_seconds=300,
            )

            getattr(service, "_handle_later_choice")(
                _FakeWindow(),
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                ),
            )

            state = auto_update_module.load_auto_update_state(state_path)

        self.assertEqual(state.snoozed_version, "1.2.0")
        self.assertEqual(state.remind_after_epoch, 400)

    def test_later_choice_uses_release_specific_snooze_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            service = auto_update_module.AutoUpdateService(
                state_path=state_path,
                now_provider=lambda: 100,
                remind_later_seconds=300,
            )

            getattr(service, "_handle_later_choice")(
                _FakeWindow(),
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                    remind_later_seconds=900,
                ),
            )

            state = auto_update_module.load_auto_update_state(state_path)

        self.assertEqual(state.snoozed_version, "1.2.0")
        self.assertEqual(state.remind_after_epoch, 1_000)

    def test_service_stays_silent_for_snoozed_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            auto_update_module.save_auto_update_state(
                auto_update_module.AutoUpdateState(
                    snoozed_version="1.2.0",
                    remind_after_epoch=2_000,
                ),
                state_path,
            )
            service = auto_update_module.AutoUpdateService(
                state_path=state_path,
                now_provider=lambda: 1_000,
            )
            window = _FakeWindow()

            with mock.patch.object(
                auto_update_module,
                "AutoUpdateNotice",
                side_effect=_FakeNotice,
            ) as notice_cls:
                setattr(service, "_check_started", True)
                getattr(service, "_result_queue").put(
                    auto_update_module.AvailableUpdate(
                        version="1.2.0",
                        update_url="https://example.com/update",
                    )
                )
                service.attach_window(window)
                window.trigger_after()

            self.assertEqual(notice_cls.call_count, 0)

    def test_service_ignores_snooze_for_newer_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            auto_update_module.save_auto_update_state(
                auto_update_module.AutoUpdateState(
                    snoozed_version="1.2.0",
                    remind_after_epoch=2_000,
                ),
                state_path,
            )
            service = auto_update_module.AutoUpdateService(
                state_path=state_path,
                now_provider=lambda: 1_000,
            )
            window = _FakeWindow()

            with mock.patch.object(
                auto_update_module,
                "AutoUpdateNotice",
                side_effect=_FakeNotice,
            ) as notice_cls:
                setattr(service, "_check_started", True)
                getattr(service, "_result_queue").put(
                    auto_update_module.AvailableUpdate(
                        version="1.3.0",
                        update_url="https://example.com/update",
                    )
                )
                service.attach_window(window)
                window.trigger_after()

            self.assertEqual(notice_cls.call_count, 1)

    def test_service_reoffers_update_on_next_window_until_choice(self):
        service = auto_update_module.AutoUpdateService()
        first_window = _FakeWindow()
        second_window = _FakeWindow()

        with mock.patch.object(
            auto_update_module,
            "AutoUpdateNotice",
            side_effect=_FakeNotice,
        ) as notice_cls:
            setattr(service, "_check_started", True)
            getattr(service, "_result_queue").put(
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                )
            )
            service.attach_window(first_window)
            first_window.trigger_after()

            self.assertEqual(notice_cls.call_count, 1)
            self.assertIs(getattr(service, "_notice_window"), first_window)

            first_window.destroy_window()

            service.attach_window(second_window)
            second_window.trigger_after()

        self.assertEqual(notice_cls.call_count, 2)
        self.assertIs(getattr(service, "_notice_window"), second_window)


class AutoUpdateNoticeTests(unittest.TestCase):
    def setUp(self):
        tracker = appearance_mode_tracker.AppearanceModeTracker
        scaling_tracker.ScalingTracker.window_widgets_dict.clear()
        scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
        scaling_tracker.ScalingTracker.update_loop_running = False
        tracker.callback_list.clear()
        tracker.app_list.clear()
        tracker.update_loop_running = False

        self.patchers = [
            mock.patch.object(ctk_tk.CTk, "_windows_set_titlebar_color"),
            mock.patch.object(ctk_tk.CTk, "_windows_set_titlebar_icon"),
            mock.patch.object(
                scaling_tracker.ScalingTracker,
                "add_widget",
                new=classmethod(_register_widget_without_dpi_loop),
            ),
            mock.patch.object(
                appearance_mode_tracker.AppearanceModeTracker,
                "add",
                new=classmethod(_register_appearance_callback_without_loop),
            ),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.app = ctk.CTk()
        self.notice = auto_update_module.AutoUpdateNotice(
            self.app,
            on_update=lambda: None,
            on_later=lambda: None,
        )
        self.notice.pack()
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        try:
            if self.app.winfo_exists():
                self.app.destroy()
        except TclError:
            pass
        finally:
            tracker = appearance_mode_tracker.AppearanceModeTracker
            scaling_tracker.ScalingTracker.window_widgets_dict.clear()
            scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
            scaling_tracker.ScalingTracker.update_loop_running = False
            tracker.callback_list.clear()
            tracker.app_list.clear()
            tracker.update_loop_running = False
            for patcher in reversed(self.patchers):
                patcher.stop()

    def test_notice_uses_player_facing_text_and_actions(self):
        self.assertIn(
            "Une mise à jour est disponible",
            _collect_label_texts(self.notice),
        )
        self.assertIn("Mettre à jour", _collect_button_texts(self.notice))
        self.assertIn("Plus tard", _collect_button_texts(self.notice))
