import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
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


def _noop_tk_callback(*_args, **_kwargs):
    return None


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


def _find_button(widget, text: str):
    for child in _walk_widgets(widget):
        try:
            if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
                return child
        except TclError:
            continue
    return None


def _is_destroyed(widget) -> bool:
    try:
        return not bool(widget.winfo_exists())
    except TclError:
        return True


def _cancel_pending_after_callbacks(widget) -> None:
    auto_update_module.cancel_pending_after_callbacks(widget)


class _FakeWindow:
    def __init__(self):
        self._exists = True
        self._after_callback = None
        self._after_id = None
        self._width = 420
        self._req_width = 420

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

    def update_idletasks(self):
        return None

    def winfo_width(self):
        return self._width

    def winfo_reqwidth(self):
        return self._req_width

    def trigger_after(self):
        if self._after_callback is not None:
            self._after_callback()

    def destroy_window(self):
        self._exists = False


class _FakeAfterWidget:
    class _FakeTk:
        def __init__(self, callback_ids):
            self._callback_ids = callback_ids

        def call(self, command_name, sub_command):
            if (command_name, sub_command) != ("after", "info"):
                raise TclError()
            return self._callback_ids

    def __init__(self, callback_ids):
        self.tk = self._FakeTk(callback_ids)
        self.cancelled_ids = []

    def after_cancel(self, callback_id):
        self.cancelled_ids.append(callback_id)


class _FakeNotice:
    def __init__(self, master=None, **_kwargs):
        self.master = master
        self._exists = True
        self.init_kwargs = dict(_kwargs)
        self.place_kwargs = None

    def place(self, **_kwargs):
        self.place_kwargs = dict(_kwargs)
        return None

    def lift(self):
        return None

    def dismiss(self):
        self._exists = False

    def winfo_exists(self):
        return self._exists


class _ImmediateThread:
    def __init__(
        self, group=None, target=None, name=None, args=(), kwargs=None, daemon=None
    ):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target is not None:
            self._target(*self._args, **self._kwargs)


class AutoUpdateLogicTests(unittest.TestCase):
    def test_current_game_version_reads_local_manifest_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = os.path.join(temp_dir, "version.json")
            with open(manifest_path, "w", encoding="utf-8") as file_handle:
                json.dump({"version": "2.4.1"}, file_handle)

            version_text = auto_update_module.current_game_version(manifest_path)

        self.assertEqual(version_text, "2.4.1")

    def test_cancel_pending_after_callbacks_cancels_all_known_ids(self):
        widget = _FakeAfterWidget(("after#1", "after#2"))

        auto_update_module.cancel_pending_after_callbacks(widget)

        self.assertEqual(widget.cancelled_ids, ["after#1", "after#2"])

    def test_configured_manifest_url_uses_environment_override(self):
        with mock.patch.dict(
            os.environ,
            {
                auto_update_module.AUTO_UPDATE_MANIFEST_URL_ENV: (
                    "https://example.com/test-version.json"
                )
            },
            clear=False,
        ):
            manifest_url = auto_update_module.configured_update_manifest_url()

        self.assertEqual(
            manifest_url,
            "https://example.com/test-version.json",
        )

    def test_configured_manifest_url_uses_runtime_config_override(self):
        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.object(
                auto_update_module,
                "load_runtime_config",
                return_value={
                    auto_update_module.AUTO_UPDATE_MANIFEST_URL_CONFIG_KEY: (
                        "https://updates.example.com/arena/version.json"
                    )
                },
            ),
        ):
            manifest_url = auto_update_module.configured_update_manifest_url()

        self.assertEqual(
            manifest_url,
            "https://updates.example.com/arena/version.json",
        )

    def test_configured_update_page_url_uses_runtime_config_override(self):
        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.object(
                auto_update_module,
                "load_runtime_config",
                return_value={
                    auto_update_module.AUTO_UPDATE_PAGE_URL_CONFIG_KEY: (
                        "https://updates.example.com/arena/releases"
                    )
                },
            ),
        ):
            page_url = auto_update_module.configured_update_page_url()

        self.assertEqual(
            page_url,
            "https://updates.example.com/arena/releases",
        )

    def test_environment_update_manifest_url_keeps_priority_over_runtime_config(self):
        with (
            mock.patch.dict(
                os.environ,
                {
                    auto_update_module.AUTO_UPDATE_MANIFEST_URL_ENV: (
                        "https://env.example.com/version.json"
                    )
                },
                clear=False,
            ),
            mock.patch.object(
                auto_update_module,
                "load_runtime_config",
                return_value={
                    auto_update_module.AUTO_UPDATE_MANIFEST_URL_CONFIG_KEY: (
                        "https://config.example.com/version.json"
                    )
                },
            ),
        ):
            manifest_url = auto_update_module.configured_update_manifest_url()

        self.assertEqual(manifest_url, "https://env.example.com/version.json")

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

    def test_check_for_available_update_accepts_local_manifest_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = os.path.join(temp_dir, "version.test.json")
            with open(manifest_path, "w", encoding="utf-8") as file_handle:
                json.dump(
                    {
                        "version": "1.2.0",
                        "update_url": "https://example.com/update",
                    },
                    file_handle,
                    ensure_ascii=False,
                )

            update = auto_update_module.check_for_available_update(
                current_version="1.0.0",
                manifest_url=manifest_path,
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

    def test_check_for_available_update_reads_installer_sha256(self):
        payload = json.dumps(
            {
                "version": "1.2.0",
                "windows_installer_url": ("https://example.com/Setup_ArenaDuel.exe"),
                "windows_installer_sha256": ("A" * 64),
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
        self.assertEqual(update.installer_sha256, "a" * 64)

    def test_check_for_available_update_reads_release_notes(self):
        payload = json.dumps(
            {
                "version": "1.2.0",
                "update_url": "https://example.com/update",
                "release_notes": [
                    "Nouveau menu online plus clair",
                    "Fermeture propre des sessions fantômes",
                ],
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
        self.assertEqual(
            update.release_notes,
            (
                "Nouveau menu online plus clair",
                "Fermeture propre des sessions fantômes",
            ),
        )

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

    def test_open_update_page_starts_local_windows_installer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            installer_path = os.path.join(temp_dir, "Setup_ArenaDuel.exe")
            with open(installer_path, "wb") as file_handle:
                file_handle.write(b"test")

            with (
                mock.patch.object(
                    auto_update_module.sys,
                    "platform",
                    "win32",
                ),
                mock.patch.object(
                    auto_update_module.os,
                    "startfile",
                    create=True,
                ) as startfile,
            ):
                result = auto_update_module.open_update_page(installer_path)

        self.assertTrue(result)
        startfile.assert_called_once_with(installer_path)

    def test_open_update_page_downloads_remote_windows_installer(self):
        payload_chunks = [b"chunk-a", b"chunk-b", b""]
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = payload_chunks
        response.headers.get.return_value = str(len(b"chunk-achunk-b"))

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                mock.patch.object(
                    auto_update_module.sys,
                    "platform",
                    "win32",
                ),
                mock.patch.object(
                    auto_update_module,
                    "runtime_user_file_path",
                    return_value=os.path.join(temp_dir, "updates"),
                ),
                mock.patch.object(
                    auto_update_module.urllib.request,
                    "urlopen",
                    return_value=response,
                ) as urlopen,
                mock.patch.object(
                    auto_update_module.os,
                    "startfile",
                    create=True,
                ) as startfile,
            ):
                result = auto_update_module.open_update_page(
                    "https://example.com/Setup_ArenaDuel.exe"
                )

            target_path = os.path.join(temp_dir, "updates", "Setup_ArenaDuel.exe")
            with open(target_path, "rb") as file_handle:
                self.assertEqual(file_handle.read(), b"chunk-achunk-b")

        self.assertTrue(result)
        urlopen.assert_called_once()
        startfile.assert_called_once_with(target_path)

    def test_download_remote_installer_reports_progress(self):
        payload_chunks = [b"abc", b"defg", b""]
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = payload_chunks
        response.headers.get.return_value = "7"
        progress_events = []

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                mock.patch.object(
                    auto_update_module,
                    "runtime_user_file_path",
                    return_value=os.path.join(temp_dir, "updates"),
                ),
                mock.patch.object(
                    auto_update_module.urllib.request,
                    "urlopen",
                    return_value=response,
                ),
            ):
                installer_path = auto_update_module._download_remote_installer(
                    "https://example.com/Setup_ArenaDuel.exe",
                    progress_callback=lambda current, total: progress_events.append(
                        (current, total)
                    ),
                )

        self.assertEqual(
            progress_events,
            [(0, 7), (3, 7), (7, 7)],
        )
        self.assertIsNotNone(installer_path)

    def test_download_remote_installer_rejects_hash_mismatch(self):
        payload_chunks = [b"abc", b""]
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = payload_chunks
        response.headers.get.return_value = "3"

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                mock.patch.object(
                    auto_update_module,
                    "runtime_user_file_path",
                    return_value=os.path.join(temp_dir, "updates"),
                ),
                mock.patch.object(
                    auto_update_module.urllib.request,
                    "urlopen",
                    return_value=response,
                ),
            ):
                installer_path = auto_update_module._download_remote_installer(
                    "https://example.com/Setup_ArenaDuel.exe",
                    installer_sha256="f" * 64,
                )

            target_path = os.path.join(temp_dir, "updates", "Setup_ArenaDuel.exe")

        self.assertIsNone(installer_path)
        self.assertFalse(os.path.exists(target_path))

    def test_open_update_page_falls_back_to_browser_when_remote_download_fails(self):
        with (
            mock.patch.object(
                auto_update_module.sys,
                "platform",
                "win32",
            ),
            mock.patch.object(
                auto_update_module.urllib.request,
                "urlopen",
                side_effect=auto_update_module.urllib.error.URLError("offline"),
            ),
            mock.patch.object(
                auto_update_module.os,
                "startfile",
                create=True,
            ) as startfile,
            mock.patch.object(
                auto_update_module.webbrowser,
                "open_new_tab",
                return_value=True,
            ) as open_new_tab,
        ):
            result = auto_update_module.open_update_page(
                "https://example.com/Setup_ArenaDuel.exe"
            )

        self.assertTrue(result)
        startfile.assert_not_called()
        open_new_tab.assert_called_once_with("https://example.com/Setup_ArenaDuel.exe")

    def test_later_choice_persists_snooze_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            service = auto_update_module.AutoUpdateService(
                state_path=state_path,
                now_provider=lambda: 100,
                reprompt_after_launches=2,
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
        self.assertEqual(state.remind_after_epoch, 0)
        self.assertEqual(state.launches_until_prompt, 2)

    def test_service_consumes_launch_counter_before_reprompt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            auto_update_module.save_auto_update_state(
                auto_update_module.AutoUpdateState(
                    snoozed_version="1.2.0",
                    launches_until_prompt=2,
                ),
                state_path,
            )

            first_launch_service = auto_update_module.AutoUpdateService(
                state_path=state_path,
            )
            first_launch_state = auto_update_module.load_auto_update_state(state_path)

            second_launch_service = auto_update_module.AutoUpdateService(
                state_path=state_path,
            )
            second_launch_state = auto_update_module.load_auto_update_state(state_path)

        self.assertEqual(first_launch_state.launches_until_prompt, 1)
        self.assertEqual(second_launch_state.launches_until_prompt, 0)
        self.assertTrue(
            getattr(first_launch_service, "_is_update_snoozed")(
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                )
            )
        )
        self.assertFalse(
            getattr(second_launch_service, "_is_update_snoozed")(
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                )
            )
        )

    def test_dismiss_choice_masks_same_version_until_new_release(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "auto_update_state.json")
            service = auto_update_module.AutoUpdateService(
                state_path=state_path,
            )

            service.dismiss_update_offer(
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                )
            )

            state = auto_update_module.load_auto_update_state(state_path)

        self.assertEqual(state.dismissed_version, "1.2.0")
        self.assertTrue(
            getattr(service, "_is_update_snoozed")(
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                )
            )
        )
        self.assertFalse(
            getattr(service, "_is_update_snoozed")(
                auto_update_module.AvailableUpdate(
                    version="1.3.0",
                    update_url="https://example.com/update",
                )
            )
        )

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

    def test_service_places_a_wider_notice_on_compact_window(self):
        service = auto_update_module.AutoUpdateService()
        window = _FakeWindow()

        with mock.patch.object(
            auto_update_module,
            "AutoUpdateNotice",
            side_effect=_FakeNotice,
        ):
            setattr(service, "_check_started", True)
            getattr(service, "_result_queue").put(
                auto_update_module.AvailableUpdate(
                    version="1.2.0",
                    update_url="https://example.com/update",
                )
            )
            service.attach_window(window)
            window.trigger_after()

        notice = getattr(window, auto_update_module.WINDOW_NOTICE_ATTR)
        self.assertIsNotNone(notice)
        self.assertEqual(notice.init_kwargs["width"], 384)

    def test_run_startup_update_gate_stays_silent_without_update(self):
        service = mock.Mock()
        service.startup_available_update.return_value = None

        with (
            mock.patch.object(
                auto_update_module,
                "get_auto_update_service",
                return_value=service,
            ),
            mock.patch.object(
                auto_update_module,
                "AutoUpdatePromptApp",
            ) as prompt_cls,
        ):
            auto_update_module.run_startup_update_gate()

        prompt_cls.assert_not_called()

    def test_run_startup_update_gate_opens_reserved_window(self):
        service = mock.Mock()
        update = auto_update_module.AvailableUpdate(
            version="1.2.0",
            update_url="https://example.com/update",
        )
        service.startup_available_update.return_value = update

        with (
            mock.patch.object(
                auto_update_module,
                "get_auto_update_service",
                return_value=service,
            ),
            mock.patch.object(
                auto_update_module,
                "AutoUpdatePromptApp",
            ) as prompt_cls,
        ):
            auto_update_module.run_startup_update_gate()

        prompt_cls.assert_called_once_with(service, update)
        prompt_cls.return_value.mainloop.assert_called_once_with()

    def test_service_launch_update_passes_installer_sha256(self):
        update = auto_update_module.AvailableUpdate(
            version="1.2.0",
            update_url="https://example.com/Setup_ArenaDuel.exe",
            installer_sha256="c" * 64,
        )
        service = auto_update_module.AutoUpdateService()
        worker = mock.Mock()

        with mock.patch.object(
            auto_update_module.threading,
            "Thread",
            return_value=worker,
        ) as thread_ctor:
            service.launch_update(update)

        thread_ctor.assert_called_once()
        self.assertEqual(
            thread_ctor.call_args.kwargs["kwargs"],
            {"installer_sha256": "c" * 64},
        )
        worker.start.assert_called_once_with()


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
            mock.patch.object(
                ctk_tk.CTk,
                "_windows_set_titlebar_color",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                ctk_tk.CTk,
                "_windows_set_titlebar_icon",
                new=_noop_tk_callback,
            ),
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
            update=auto_update_module.AvailableUpdate(
                version="1.2.0",
                update_url="https://example.com/update",
            ),
            on_update=lambda: None,
            on_later=lambda: None,
            on_never=lambda: None,
        )
        self.notice.pack()
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        try:
            if self.app.winfo_exists():
                _cancel_pending_after_callbacks(self.app)
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
        self.assertIn(
            "Installe-la maintenant, repousse-la à dans deux lancements, ou masque cette version.",
            _collect_label_texts(self.notice),
        )
        self.assertIn("Mettre à jour", _collect_button_texts(self.notice))
        self.assertIn("Plus tard", _collect_button_texts(self.notice))
        self.assertIn("Ne plus me demander", _collect_button_texts(self.notice))

    def test_notice_summarizes_release_notes_when_present(self):
        detail_text = auto_update_module._notice_detail_text(
            auto_update_module.AvailableUpdate(
                version="1.2.0",
                update_url="https://example.com/update",
                release_notes=(
                    "Détection Wi-Fi corrigée",
                    "Nettoyage des salons abandonnés",
                ),
            )
        )

        self.assertIn("2 changements disponibles", detail_text)


class AutoUpdatePromptTests(unittest.TestCase):
    def setUp(self):
        tracker = appearance_mode_tracker.AppearanceModeTracker
        scaling_tracker.ScalingTracker.window_widgets_dict.clear()
        scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
        scaling_tracker.ScalingTracker.update_loop_running = False
        tracker.callback_list.clear()
        tracker.app_list.clear()
        tracker.update_loop_running = False

        self.patchers = [
            mock.patch.object(auto_update_module, "init_audio"),
            mock.patch.object(auto_update_module, "play_alert"),
            mock.patch.object(auto_update_module, "play_click"),
            mock.patch.object(auto_update_module, "play_transition"),
            mock.patch.object(auto_update_module, "apply_window_icon"),
            mock.patch.object(auto_update_module, "present_window"),
            mock.patch.object(
                ctk_tk.CTk,
                "_windows_set_titlebar_color",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                ctk_tk.CTk,
                "_windows_set_titlebar_icon",
                new=_noop_tk_callback,
            ),
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

        self.service = mock.Mock()
        self.app = auto_update_module.AutoUpdatePromptApp(
            self.service,
            auto_update_module.AvailableUpdate(
                version="1.2.0",
                update_url="https://example.com/update",
            ),
        )
        self.app.update_idletasks()
        self.app.update()
        auto_update_module.init_audio.reset_mock()
        auto_update_module.play_alert.reset_mock()
        auto_update_module.play_click.reset_mock()
        auto_update_module.play_transition.reset_mock()

    def tearDown(self):
        try:
            if self.app.winfo_exists():
                _cancel_pending_after_callbacks(self.app)
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

    def test_prompt_uses_reserved_window_text_and_actions(self):
        self.assertEqual(self.app.title(), "Arena Duel - Mise à jour")
        self.assertIn(
            "Version 1.2.0 prête pour l'arène",
            _collect_label_texts(self.app),
        )
        self.assertIn(
            "Version actuelle",
            _collect_label_texts(self.app),
        )
        self.assertIn(
            auto_update_module.current_game_version(),
            _collect_label_texts(self.app),
        )
        self.assertIn(
            "Version disponible",
            _collect_label_texts(self.app),
        )
        self.assertIn(
            (
                "Installe cette version maintenant, repousse-la à dans deux "
                "lancements, ou masque cette version tant qu'une nouvelle "
                "release n'arrive pas."
            ),
            _collect_label_texts(self.app),
        )
        self.assertIn("Mettre à jour", _collect_button_texts(self.app))
        self.assertIn("Plus tard", _collect_button_texts(self.app))
        self.assertIn(
            "Ne plus me demander pour 1.2.0",
            _collect_button_texts(self.app),
        )

    def test_prompt_shows_release_notes_when_manifest_provides_them(self):
        self.app._update = auto_update_module.AvailableUpdate(
            version="1.2.0",
            update_url="https://example.com/update",
            release_notes=(
                "Détection Wi-Fi et Ethernet fiabilisée",
                "Fermeture propre des sessions online",
            ),
        )

        self.app._build_release_notes_ui(self.app.shell, row=4)
        self.app.update_idletasks()
        self.app.update()

        label_texts = _collect_label_texts(self.app)
        self.assertIn("Nouveautés", label_texts)
        self.assertTrue(
            any(
                "Détection Wi-Fi et Ethernet fiabilisée" in text for text in label_texts
            )
        )
        self.assertTrue(
            any("Fermeture propre des sessions online" in text for text in label_texts)
        )

    def test_prompt_later_button_disables_actions_and_schedules_close(self):
        later_button = _find_button(self.app, "Plus tard")
        self.assertIsNotNone(later_button)

        later_button.invoke()

        self.assertEqual(self.app.selection, "later")
        auto_update_module.play_click.assert_called_once_with()
        self.service.defer_update.assert_called_once()
        self.assertEqual(self.app.update_button.cget("state"), "disabled")
        self.assertEqual(self.app.later_button.cget("state"), "disabled")
        self.assertEqual(self.app.never_button.cget("state"), "disabled")
        self.assertIsNotNone(self.app._close_after_id)
        self.assertFalse(_is_destroyed(self.app))

    def test_prompt_update_button_disables_actions_and_schedules_close(self):
        update_button = _find_button(self.app, "Mettre à jour")
        self.assertIsNotNone(update_button)

        update_button.invoke()

        self.assertEqual(self.app.selection, "update")
        auto_update_module.play_transition.assert_called_once_with()
        self.service.launch_update.assert_called_once()
        self.assertEqual(self.app.update_button.cget("state"), "disabled")
        self.assertEqual(self.app.later_button.cget("state"), "disabled")
        self.assertEqual(self.app.never_button.cget("state"), "disabled")
        self.assertIsNotNone(self.app._close_after_id)
        self.assertFalse(_is_destroyed(self.app))

    def test_prompt_never_button_disables_actions_and_schedules_close(self):
        never_button = _find_button(self.app, "Ne plus me demander pour 1.2.0")
        self.assertIsNotNone(never_button)

        never_button.invoke()

        self.assertEqual(self.app.selection, "never")
        auto_update_module.play_click.assert_called_once_with()
        self.service.dismiss_update_offer.assert_called_once()
        self.assertEqual(self.app.update_button.cget("state"), "disabled")
        self.assertEqual(self.app.later_button.cget("state"), "disabled")
        self.assertEqual(self.app.never_button.cget("state"), "disabled")
        self.assertIsNotNone(self.app._close_after_id)

    def test_prompt_later_mouse_click_path_closes_under_mainloop(self):
        later_button = _find_button(self.app, "Plus tard")
        self.assertIsNotNone(later_button)
        forced_close = {"called": False}

        def _force_close_if_needed():
            if _is_destroyed(self.app):
                return
            forced_close["called"] = True
            self.app.destroy()

        self.app.after(10, getattr(later_button, "_clicked"))
        self.app.after(500, _force_close_if_needed)
        self.app.mainloop()

        self.assertFalse(forced_close["called"])
        self.assertEqual(self.app.selection, "later")
        self.service.defer_update.assert_called_once()

    def test_prompt_update_mouse_click_path_closes_under_mainloop(self):
        update_button = _find_button(self.app, "Mettre à jour")
        self.assertIsNotNone(update_button)
        forced_close = {"called": False}

        def _force_close_if_needed():
            if _is_destroyed(self.app):
                return
            forced_close["called"] = True
            self.app.destroy()

        self.app.after(10, getattr(update_button, "_clicked"))
        self.app.after(500, _force_close_if_needed)
        self.app.mainloop()

        self.assertFalse(forced_close["called"])
        self.assertEqual(self.app.selection, "update")
        self.service.launch_update.assert_called_once()

    def test_prompt_remote_installer_switches_to_progress_flow(self):
        update_button = _find_button(self.app, "Mettre à jour")
        self.assertIsNotNone(update_button)

        self.app._update = auto_update_module.AvailableUpdate(
            version="1.2.0",
            update_url="https://example.com/Setup_ArenaDuel.exe",
        )

        with (
            mock.patch.object(
                auto_update_module.sys,
                "platform",
                "win32",
            ),
            mock.patch.object(
                auto_update_module.threading,
                "Thread",
                side_effect=_ImmediateThread,
            ),
            mock.patch.object(
                auto_update_module,
                "_download_remote_installer",
                return_value=Path("C:/Temp/Setup_ArenaDuel.exe"),
            ) as download_installer,
            mock.patch.object(
                auto_update_module.os,
                "startfile",
                create=True,
            ) as startfile,
        ):
            update_button.invoke()
            self.app.update_idletasks()
            self.app.update()

        self.service.launch_update.assert_not_called()
        download_installer.assert_called_once_with(
            "https://example.com/Setup_ArenaDuel.exe",
            progress_callback=mock.ANY,
            installer_sha256=None,
        )
        startfile.assert_called_once_with(
            os.path.normpath("C:/Temp/Setup_ArenaDuel.exe")
        )
        self.assertIsNotNone(self.app.progress_bar)
        self.assertEqual(self.app.selection, "update")
        self.assertIsNotNone(self.app._close_after_id)

    def test_prompt_remote_installer_passes_hash_to_download_flow(self):
        update_button = _find_button(self.app, "Mettre à jour")
        self.assertIsNotNone(update_button)

        self.app._update = auto_update_module.AvailableUpdate(
            version="1.2.0",
            update_url="https://example.com/Setup_ArenaDuel.exe",
            installer_sha256="b" * 64,
        )

        with (
            mock.patch.object(
                auto_update_module.sys,
                "platform",
                "win32",
            ),
            mock.patch.object(
                auto_update_module.threading,
                "Thread",
                side_effect=_ImmediateThread,
            ),
            mock.patch.object(
                auto_update_module,
                "_download_remote_installer",
                return_value=Path("C:/Temp/Setup_ArenaDuel.exe"),
            ) as download_installer,
            mock.patch.object(
                auto_update_module.os,
                "startfile",
                create=True,
            ),
        ):
            update_button.invoke()
            self.app.update_idletasks()
            self.app.update()

        download_installer.assert_called_once_with(
            "https://example.com/Setup_ArenaDuel.exe",
            progress_callback=mock.ANY,
            installer_sha256="b" * 64,
        )
