import os
import tempfile
import unittest
import importlib
from tkinter import TclError
from unittest import mock

import customtkinter as ctk
import customtkinter.windows.ctk_tk as ctk_tk
import customtkinter.windows.ctk_toplevel as ctk_toplevel
import pygame
from customtkinter.windows.widgets.appearance_mode import (
    appearance_mode_tracker,
)
from customtkinter.windows.widgets.scaling import scaling_tracker


TEST_APPDATA_DIR = tempfile.mkdtemp(prefix="arena_duel_launcher_ui_")
os.environ.setdefault("APPDATA", TEST_APPDATA_DIR)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

launcher_module = importlib.import_module("ui.launcher")
online_client_module = importlib.import_module("ui.online_client")
online_lobby_module = importlib.import_module("ui.online_lobby")
player_select_module = importlib.import_module("ui.player_select")
network_lobby_module = importlib.import_module("ui.network_lobby")


def _make_network_status(
    *,
    transport_kind: str = "ethernet",
    transport_label: str = "Ethernet",
    tone: str = "success",
    signal_bars: int = 4,
    online_available: bool = True,
    is_connected: bool = True,
    quality_label: str = "Stable",
    latency_ms: int | None = 45,
):
    return online_client_module.OnlineNetworkStatus(
        transport_kind=transport_kind,
        transport_label=transport_label,
        tone=tone,
        signal_bars=signal_bars,
        online_available=online_available,
        is_connected=is_connected,
        quality_label=quality_label,
        latency_ms=latency_ms,
    )


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
                text = child.cget("text")
            else:
                continue
        except TclError:
            continue

        if text:
            texts.append(text)
    return texts


def _collect_player_panel_labels(window) -> list[str]:
    player_panel = getattr(window, "active_room_players_frame")
    if player_panel is None:
        return []
    return _collect_label_texts(player_panel)


def _set_current_room_status(window, **kwargs):
    getattr(window, "_set_current_room_status")(**kwargs)


def _deiconify_window_without_ctk_callbacks(window):
    window.tk.call("wm", "deiconify", window._w)


def _cancel_pending_after_callbacks(widget):
    try:
        callback_ids = widget.tk.call("after", "info")
    except TclError:
        return

    if not callback_ids:
        return

    if isinstance(callback_ids, str):
        callback_ids = (callback_ids,)

    for callback_id in callback_ids:
        try:
            widget.after_cancel(callback_id)
        except TclError:
            continue


def _window_is_destroyed(widget) -> bool:
    try:
        return not bool(widget.winfo_exists())
    except TclError:
        return True


class _FakeAfterWindow:
    def __init__(self):
        self.tk = object()
        self.delay_ms = None
        self.callback = None

    def after(self, delay_ms, callback):
        self.delay_ms = delay_ms
        self.callback = callback
        return "after#1"

    def winfo_exists(self):
        return True


class MenuAudioBootstrapTests(unittest.TestCase):
    def test_schedule_menu_audio_boot_initializes_audio_and_starts_music(self):
        fake_window = _FakeAfterWindow()

        with (
            mock.patch.object(pygame.mixer, "pre_init") as pre_init,
            mock.patch.object(launcher_module, "init_audio") as init_audio,
            mock.patch.object(
                launcher_module,
                "start_menu_music",
            ) as start_menu_music,
        ):
            launcher_module._schedule_menu_audio_boot(fake_window)

            self.assertEqual(fake_window.delay_ms, 100)
            self.assertIsNotNone(fake_window.callback)
            fake_window.callback()

        pre_init.assert_called_once_with(44100, -16, 2, 512)
        init_audio.assert_called_once_with()
        start_menu_music.assert_called_once_with()


class _CompactMenuTestCase(unittest.TestCase):
    menu_class = None

    def setUp(self):
        tracker = appearance_mode_tracker.AppearanceModeTracker
        scaling_tracker.ScalingTracker.window_widgets_dict.clear()
        scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
        scaling_tracker.ScalingTracker.update_loop_running = False
        tracker.callback_list.clear()
        tracker.app_list.clear()
        tracker.update_loop_running = False

        self.patchers = [
            mock.patch.object(launcher_module, "init_audio"),
            mock.patch.object(launcher_module, "start_menu_music"),
            mock.patch.object(launcher_module, "play_transition"),
            mock.patch.object(launcher_module, "play_click"),
            mock.patch.object(launcher_module, "play_alert"),
            mock.patch.object(launcher_module, "play_error"),
            mock.patch.object(launcher_module, "apply_window_icon"),
            mock.patch.object(launcher_module, "bind_auto_update_window"),
            mock.patch.object(launcher_module, "present_window"),
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

        menu_class = self.menu_class
        self.assertIsNotNone(menu_class)
        self.app = menu_class()
        self._update_ui()
        launcher_module.init_audio.reset_mock()
        launcher_module.start_menu_music.reset_mock()
        launcher_module.play_transition.reset_mock()
        launcher_module.play_click.reset_mock()
        launcher_module.play_alert.reset_mock()
        launcher_module.play_error.reset_mock()

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

    def _update_ui(self):
        self.app.update_idletasks()
        self.app.update()


class StartupModeAppTests(unittest.TestCase):
    def setUp(self):
        tracker = appearance_mode_tracker.AppearanceModeTracker
        scaling_tracker.ScalingTracker.window_widgets_dict.clear()
        scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
        scaling_tracker.ScalingTracker.update_loop_running = False
        tracker.callback_list.clear()
        tracker.app_list.clear()
        tracker.update_loop_running = False

        self.patchers = [
            mock.patch.object(launcher_module, "init_audio"),
            mock.patch.object(launcher_module, "start_menu_music"),
            mock.patch.object(launcher_module, "play_transition"),
            mock.patch.object(launcher_module, "play_click"),
            mock.patch.object(launcher_module, "play_alert"),
            mock.patch.object(launcher_module, "play_error"),
            mock.patch.object(launcher_module, "apply_window_icon"),
            mock.patch.object(launcher_module, "bind_auto_update_window"),
            mock.patch.object(launcher_module, "present_window"),
            mock.patch.object(launcher_module, "enable_large_window"),
            mock.patch.object(
                launcher_module,
                "load_app_icon_image",
                return_value=None,
            ),
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

        self.app = launcher_module.StartupModeApp()
        self.app.update_idletasks()
        self.app.update()
        launcher_module.init_audio.reset_mock()
        launcher_module.start_menu_music.reset_mock()
        launcher_module.play_transition.reset_mock()
        launcher_module.play_click.reset_mock()
        launcher_module.play_alert.reset_mock()
        launcher_module.play_error.reset_mock()

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

    def test_startup_mode_window_is_maximized(self):
        self.assertEqual(self.app.title(), "Arena Duel - Démarrage")
        self.assertIn(
            "Lancer avec base de données",
            _collect_button_texts(self.app),
        )
        self.assertIn(
            "Lancer sans base de données",
            _collect_button_texts(self.app),
        )
        launcher_module.enable_large_window.assert_called_once_with(
            self.app,
            560,
            360,
            start_zoomed=True,
        )

    def test_startup_mode_binds_auto_update_service(self):
        launcher_module.bind_auto_update_window.assert_called_once_with(self.app)


class ModeSelectionMenuTests(_CompactMenuTestCase):
    menu_class = launcher_module.ModeSelectionMenuApp

    def test_mode_selection_binds_auto_update_service(self):
        launcher_module.bind_auto_update_window.assert_called_once_with(self.app)

    def test_mode_selection_menu_is_compact_and_fixed(self):
        self.assertEqual(self.app.title(), "Arena Duel - Menu")
        self.assertIn("Arena Duel - Menu", _collect_label_texts(self.app))
        self.assertIn(
            "Choisissez votre mode de jeu",
            _collect_label_texts(self.app),
        )

        button_texts = _collect_button_texts(self.app)
        self.assertIn("Jouer en Local", button_texts)
        self.assertIn("Jouer en Online", button_texts)
        self.assertIn("Quitter", button_texts)
        self.assertTrue(self.app.geometry().startswith("420x430+"))
        self.assertEqual(
            tuple(int(value) for value in self.app.resizable()),
            (0, 0),
        )

    def test_local_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_local")()

        self.assertEqual(self.app.selection, "local")
        destroy.assert_called_once_with()

    def test_local_selection_plays_transition_sound(self):
        with mock.patch.object(self.app, "destroy"):
            getattr(self.app, "_handle_local")()

        launcher_module.play_transition.assert_called_once_with()
        launcher_module.play_click.assert_not_called()

    def test_online_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_online")()

        self.assertEqual(self.app.selection, "online")
        destroy.assert_called_once_with()

    def test_quit_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_quit")()

        self.assertEqual(self.app.selection, "quit")
        destroy.assert_called_once_with()

    def test_quit_selection_plays_click_sound(self):
        with mock.patch.object(self.app, "destroy"):
            getattr(self.app, "_handle_quit")()

        launcher_module.play_click.assert_called_once_with()
        launcher_module.play_transition.assert_not_called()


class LocalModeMenuTests(_CompactMenuTestCase):
    menu_class = launcher_module.LocalModeMenuApp

    def test_local_mode_menu_is_compact_and_fixed(self):
        self.assertEqual(self.app.title(), "Arena Duel - Local")
        self.assertIn("Arena Duel - Local", _collect_label_texts(self.app))
        self.assertIn(
            (
                "Choisissez une joute locale, un hall LAN hôte "
                "ou un hall LAN à rejoindre."
            ),
            _collect_label_texts(self.app),
        )

        button_texts = _collect_button_texts(self.app)
        self.assertIn("LAN Admin", button_texts)
        self.assertIn("LAN Rejoindre", button_texts)
        self.assertIn("Local", button_texts)
        self.assertIn("Retour", button_texts)
        self.assertTrue(self.app.geometry().startswith("440x520+"))
        self.assertEqual(
            tuple(int(value) for value in self.app.resizable()),
            (0, 0),
        )

    def test_lan_host_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_lan_host")()

        self.assertEqual(self.app.selection, "lan_host")
        destroy.assert_called_once_with()

    def test_lan_join_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_lan_join")()

        self.assertEqual(self.app.selection, "lan_join")
        destroy.assert_called_once_with()

    def test_local_game_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_local_game")()

        self.assertEqual(self.app.selection, "local")
        destroy.assert_called_once_with()

    def test_back_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_back")()

        self.assertEqual(self.app.selection, "back")
        destroy.assert_called_once_with()


class OnlineModeMenuTests(_CompactMenuTestCase):
    menu_class = launcher_module.OnlineModeMenuApp

    def test_online_mode_menu_is_compact_and_fixed(self):
        self.assertEqual(self.app.title(), "Arena Duel - Online")
        self.assertIn("Arena Duel - Online", _collect_label_texts(self.app))
        self.assertIn(
            ("Voulez-vous héberger une session ou rejoindre une session existante ?"),
            _collect_label_texts(self.app),
        )

        button_texts = _collect_button_texts(self.app)
        self.assertIn("Héberger", button_texts)
        self.assertIn("Rejoindre", button_texts)
        self.assertIn("Retour", button_texts)
        self.assertTrue(self.app.geometry().startswith("420x430+"))
        self.assertEqual(
            tuple(int(value) for value in self.app.resizable()),
            (0, 0),
        )

    def test_host_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_host")()

        self.assertEqual(self.app.selection, "host")
        destroy.assert_called_once_with()

    def test_join_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_join")()

        self.assertEqual(self.app.selection, "join")
        destroy.assert_called_once_with()

    def test_back_selection_closes_menu(self):
        with mock.patch.object(self.app, "destroy") as destroy:
            getattr(self.app, "_handle_back")()

        self.assertEqual(self.app.selection, "back")
        destroy.assert_called_once_with()


class MainModeMenuDispatchTests(unittest.TestCase):
    def test_run_main_mode_menu_dispatches_local_forge(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["local", "local"],
            ) as run_menu,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
            mock.patch.object(
                launcher_module,
                "run_lan_host_lobby",
            ) as run_lan_host,
            mock.patch.object(
                launcher_module,
                "run_lan_join_lobby",
            ) as run_lan_join,
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.LocalModeMenuApp),
            ],
        )
        run_local.assert_called_once_with()
        run_lan_host.assert_not_called()
        run_lan_join.assert_not_called()
        run_online_host.assert_not_called()
        run_online_join.assert_not_called()

    def test_run_main_mode_menu_dispatches_lan_host_then_reopens_local_menu(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["local", "lan_host", "back", None],
            ) as run_menu,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
            mock.patch.object(
                launcher_module,
                "run_lan_host_lobby",
            ) as run_lan_host,
            mock.patch.object(
                launcher_module,
                "run_lan_join_lobby",
            ) as run_lan_join,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.LocalModeMenuApp),
                mock.call(launcher_module.LocalModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        run_lan_host.assert_called_once_with()
        run_local.assert_not_called()
        run_lan_join.assert_not_called()

    def test_run_main_mode_menu_dispatches_lan_join_then_reopens_local_menu(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["local", "lan_join", "back", None],
            ) as run_menu,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
            mock.patch.object(
                launcher_module,
                "run_lan_host_lobby",
            ) as run_lan_host,
            mock.patch.object(
                launcher_module,
                "run_lan_join_lobby",
            ) as run_lan_join,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.LocalModeMenuApp),
                mock.call(launcher_module.LocalModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        run_lan_join.assert_called_once_with()
        run_local.assert_not_called()
        run_lan_host.assert_not_called()

    def test_run_main_mode_menu_reopens_main_menu_after_local_back(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["local", "back", None],
            ) as run_menu,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
            mock.patch.object(
                launcher_module,
                "run_lan_host_lobby",
            ) as run_lan_host,
            mock.patch.object(
                launcher_module,
                "run_lan_join_lobby",
            ) as run_lan_join,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.LocalModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        run_local.assert_not_called()
        run_lan_host.assert_not_called()
        run_lan_join.assert_not_called()

    def test_run_main_mode_menu_dispatches_online_host(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["online", "host", "back", None],
            ) as run_menu,
            mock.patch.object(
                launcher_module,
                "probe_online_service",
                return_value=True,
            ) as probe_online,
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        probe_online.assert_called_once_with()
        run_online_host.assert_called_once_with()
        run_online_join.assert_not_called()
        run_local.assert_not_called()

    def test_run_main_mode_menu_dispatches_online_join(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["online", "join", "back", None],
            ) as run_menu,
            mock.patch.object(
                launcher_module,
                "probe_online_service",
                return_value=True,
            ) as probe_online,
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        probe_online.assert_called_once_with()
        run_online_join.assert_called_once_with()
        run_online_host.assert_not_called()
        run_local.assert_not_called()

    def test_run_main_mode_menu_reopens_online_menu_after_session_close(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["online", "host", "back", None],
            ) as run_menu,
            mock.patch.object(
                launcher_module,
                "probe_online_service",
                return_value=True,
            ),
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        run_online_host.assert_called_once_with()
        run_online_join.assert_not_called()

    def test_run_main_mode_menu_reopens_main_menu_after_online_back(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["online", "back", None],
            ) as run_menu,
            mock.patch.object(
                launcher_module,
                "probe_online_service",
                return_value=True,
            ) as probe_online,
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.OnlineModeMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        probe_online.assert_called_once_with()
        run_online_host.assert_not_called()
        run_online_join.assert_not_called()

    def test_run_main_mode_menu_reopens_main_menu_after_offline_probe(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                side_effect=["online", None],
            ) as run_menu,
            mock.patch.object(
                launcher_module,
                "probe_online_service",
                return_value=False,
            ) as probe_online,
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
            mock.patch.object(launcher_module, "play_error") as play_error,
            mock.patch.object(
                launcher_module.messagebox,
                "showwarning",
            ) as showwarning,
        ):
            launcher_module.run_main_mode_menu()

        self.assertEqual(
            run_menu.call_args_list,
            [
                mock.call(launcher_module.ModeSelectionMenuApp),
                mock.call(launcher_module.ModeSelectionMenuApp),
            ],
        )
        probe_online.assert_called_once_with()
        play_error.assert_called_once_with()
        showwarning.assert_called_once_with(
            launcher_module.ONLINE_ENTRY_REQUIRED_TITLE,
            launcher_module.ONLINE_ENTRY_REQUIRED_MESSAGE,
        )
        run_online_host.assert_not_called()
        run_online_join.assert_not_called()

    def test_run_main_mode_menu_returns_without_selection(self):
        with (
            mock.patch.object(
                launcher_module,
                "_run_menu",
                return_value=None,
            ) as run_menu,
            mock.patch.object(launcher_module, "run_local_forge") as run_local,
            mock.patch.object(
                launcher_module,
                "run_lan_host_lobby",
            ) as run_lan_host,
            mock.patch.object(
                launcher_module,
                "run_lan_join_lobby",
            ) as run_lan_join,
            mock.patch.object(
                launcher_module,
                "run_online_host_session",
            ) as run_online_host,
            mock.patch.object(
                launcher_module,
                "run_online_join_session",
            ) as run_online_join,
        ):
            launcher_module.run_main_mode_menu()

        run_menu.assert_called_once_with(launcher_module.ModeSelectionMenuApp)
        run_local.assert_not_called()
        run_lan_host.assert_not_called()
        run_lan_join.assert_not_called()
        run_online_host.assert_not_called()
        run_online_join.assert_not_called()


class LauncherOnlineFlowTests(unittest.TestCase):
    def setUp(self):
        tracker = appearance_mode_tracker.AppearanceModeTracker
        scaling_tracker.ScalingTracker.window_widgets_dict.clear()
        scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
        scaling_tracker.ScalingTracker.update_loop_running = False
        tracker.callback_list.clear()
        tracker.app_list.clear()
        tracker.update_loop_running = False

        self.patchers = [
            mock.patch.object(launcher_module, "init_audio"),
            mock.patch.object(launcher_module, "play_transition"),
            mock.patch.object(launcher_module, "play_click"),
            mock.patch.object(launcher_module, "play_alert"),
            mock.patch.object(launcher_module, "play_error"),
            mock.patch.object(launcher_module, "start_menu_music"),
            mock.patch.object(launcher_module, "stop_music"),
            mock.patch.object(launcher_module, "apply_window_icon"),
            mock.patch.object(launcher_module, "bind_auto_update_window"),
            mock.patch.object(launcher_module, "present_window"),
            mock.patch.object(launcher_module, "enable_large_window"),
            mock.patch.object(
                launcher_module,
                "probe_online_service",
                return_value=True,
            ),
            mock.patch.object(online_lobby_module, "init_audio"),
            mock.patch.object(online_lobby_module, "play_transition"),
            mock.patch.object(online_lobby_module, "play_click"),
            mock.patch.object(online_lobby_module, "play_alert"),
            mock.patch.object(online_lobby_module, "play_error"),
            mock.patch.object(online_lobby_module, "apply_window_icon"),
            mock.patch.object(online_lobby_module, "present_window"),
            mock.patch.object(online_lobby_module, "enable_large_window"),
            mock.patch.object(
                online_lobby_module,
                "fetch_public_room_directory",
                return_value=[],
            ),
            mock.patch.object(
                online_lobby_module,
                "get_online_network_status",
                return_value=_make_network_status(),
            ),
            mock.patch.object(
                ctk_tk.CTk,
                "_windows_set_titlebar_color",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                ctk_toplevel.CTkToplevel,
                "_windows_set_titlebar_color",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                scaling_tracker.ScalingTracker,
                "add_widget",
                new=classmethod(_register_widget_without_dpi_loop),
            ),
            mock.patch.object(
                ctk_tk.CTk,
                "_windows_set_titlebar_icon",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                ctk_toplevel.CTkToplevel,
                "_windows_set_titlebar_icon",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                appearance_mode_tracker.AppearanceModeTracker,
                "add",
                new=classmethod(_register_appearance_callback_without_loop),
            ),
            mock.patch.object(
                launcher_module.LauncherApp,
                "_hydrate_visual_assets",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                launcher_module.LauncherSettingsWindow,
                "_hydrate_visual_assets",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                launcher_module.LauncherSettingsWindow,
                "_refresh_serial_ports",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                online_lobby_module.messagebox,
                "askyesno",
                return_value=False,
            ),
            mock.patch.object(
                launcher_module.messagebox,
                "showwarning",
            ),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.app = launcher_module.LauncherApp(
            startup_mode="demo",
            startup_db_status="local",
            probe_db_on_start=False,
        )
        self._update_ui()
        launcher_module.init_audio.reset_mock()
        launcher_module.play_transition.reset_mock()
        launcher_module.play_click.reset_mock()
        launcher_module.play_alert.reset_mock()
        launcher_module.play_error.reset_mock()
        online_lobby_module.init_audio.reset_mock()
        online_lobby_module.play_transition.reset_mock()
        online_lobby_module.play_click.reset_mock()
        online_lobby_module.play_alert.reset_mock()
        online_lobby_module.play_error.reset_mock()

    def tearDown(self):
        try:
            settings_window = getattr(self.app, "settings_window", None)
            if settings_window is not None and settings_window.winfo_exists():
                _cancel_pending_after_callbacks(settings_window)
                settings_window.destroy()

            online_window = getattr(self.app, "online_lobby_window", None)
            if online_window is not None and online_window.winfo_exists():
                join_window = getattr(online_window, "join_window", None)
                if join_window is not None and join_window.winfo_exists():
                    _cancel_pending_after_callbacks(join_window)
                    join_window.shutdown()

                create_window = getattr(online_window, "create_window", None)
                if create_window is not None and create_window.winfo_exists():
                    _cancel_pending_after_callbacks(create_window)
                    create_window.shutdown()

                _cancel_pending_after_callbacks(online_window)
                online_window.shutdown()

            for attr_name in ("host_lobby_window", "join_lobby_window"):
                lobby_window = getattr(self.app, attr_name, None)
                if lobby_window is None or not lobby_window.winfo_exists():
                    continue

                _cancel_pending_after_callbacks(lobby_window)
                lobby_window.shutdown()

            if self.app.winfo_exists():
                _cancel_pending_after_callbacks(self.app)
                self.app.destroy()
        except TclError:
            pass
        finally:
            scaling_tracker.ScalingTracker.window_widgets_dict.clear()
            scaling_tracker.ScalingTracker.window_dpi_scaling_dict.clear()
            scaling_tracker.ScalingTracker.update_loop_running = False
            appearance_mode_tracker.AppearanceModeTracker.callback_list.clear()
            appearance_mode_tracker.AppearanceModeTracker.app_list.clear()
            tracker = appearance_mode_tracker.AppearanceModeTracker
            tracker.update_loop_running = False
            for patcher in reversed(self.patchers):
                patcher.stop()

    def _update_ui(self):
        self.app.update_idletasks()
        self.app.update()

    def test_launcher_opens_settings_window_maximized(self):
        launcher_module.enable_large_window.reset_mock()

        self.app._handle_settings()
        self._update_ui()

        settings_window = getattr(self.app, "settings_window", None)
        self.assertIsNotNone(settings_window)
        self.assertEqual(settings_window.title(), "Arena Duel - Réglages")
        launcher_module.enable_large_window.assert_called_once_with(
            settings_window,
            980,
            640,
            start_zoomed=True,
        )

    def test_launcher_binds_auto_update_service_on_start(self):
        launcher_module.bind_auto_update_window.assert_called_once_with(self.app)

    def test_launcher_opens_online_lobby_and_session_windows(self):
        launcher_buttons = _collect_button_texts(self.app)
        self.assertIn("Jouer en ligne", launcher_buttons)

        online_lobby_module.enable_large_window.reset_mock()

        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        self.assertIsNotNone(online_window)
        self.assertEqual(online_window.title(), "Arena Duel - Jouer en ligne")
        online_lobby_module.enable_large_window.assert_called_once_with(
            online_window,
            820,
            560,
            start_zoomed=True,
        )
        self.assertIsNotNone(online_window.network_indicator)
        self.assertTrue(online_window.network_indicator.available)

        online_labels = _collect_label_texts(online_window)
        self.assertIn("Choisis ton parcours", online_labels)
        self.assertIn("Rejoindre une session", online_labels)
        self.assertIn("Créer une session", online_labels)

        online_buttons = _collect_button_texts(online_window)
        self.assertIn("Ouvrir la fenêtre de rejoindre", online_buttons)
        self.assertIn("Ouvrir la fenêtre de création", online_buttons)

        online_lobby_module.enable_large_window.reset_mock()
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        self.assertIsNotNone(create_window)
        self.assertEqual(
            create_window.title(),
            "Arena Duel - Créer une session",
        )
        self.assertEqual(
            create_window.btn_start_match.cget("text"),
            "Lancer le jeu",
        )
        online_lobby_module.enable_large_window.assert_called_once_with(
            create_window,
            960,
            640,
            start_zoomed=True,
        )
        self.assertIsNotNone(create_window.network_indicator)
        self.assertTrue(create_window.network_indicator.available)
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "normal",
        )
        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Se mettre prêt",
        )
        self.assertEqual(
            create_window.btn_ready.cget("state"),
            "normal",
        )
        self.assertEqual(
            create_window.active_room_title_label.cget("text"),
            "Aucune session créée",
        )
        self.assertEqual(
            create_window.btn_connect.cget("text"),
            "Se connecter",
        )
        self.assertIsNone(create_window.host_entry)
        self.assertIsNone(create_window.port_entry)
        self.assertEqual(create_window.btn_disconnect.cget("text"), "Retour")
        self.assertEqual(create_window.btn_disconnect.cget("state"), "normal")
        self.assertEqual(
            create_window.status_badge.cget("text"),
            "Connexion requise",
        )
        self.assertEqual(
            create_window.status_label.cget("text"),
            "Vous devez être connecté pour jouer en ligne.",
        )
        create_player_labels = _collect_player_panel_labels(create_window)
        self.assertIn("Connexion requise", create_player_labels)
        self.assertIn("Choisis Se connecter ou Retour.", create_player_labels)

        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)
        self.assertEqual(
            join_window.title(),
            "Arena Duel - Rejoindre une session",
        )
        self.assertEqual(
            join_window.active_room_title_label.cget("text"),
            "Aucune session rejointe",
        )
        self.assertEqual(
            join_window.btn_connect.cget("text"),
            "Se connecter",
        )
        self.assertIsNone(join_window.host_entry)
        self.assertIsNone(join_window.port_entry)
        self.assertIsNotNone(join_window.network_indicator)
        self.assertTrue(join_window.network_indicator.available)
        self.assertEqual(join_window.btn_disconnect.cget("text"), "Retour")
        self.assertEqual(join_window.btn_disconnect.cget("state"), "normal")
        self.assertFalse(create_window.winfo_exists())
        self.assertIsNone(online_window.create_window)
        self.assertIsNone(getattr(join_window, "_poll_after_id"))

    def test_launcher_blocks_online_lobby_when_probe_fails(self):
        launcher_module.probe_online_service.return_value = False
        launcher_module.play_transition.reset_mock()
        launcher_module.play_error.reset_mock()
        launcher_module.messagebox.showwarning.reset_mock()

        self.app.open_online_lobby()
        self._update_ui()

        self.assertIsNone(getattr(self.app, "online_lobby_window", None))
        launcher_module.play_transition.assert_not_called()
        launcher_module.play_error.assert_called_once_with()
        launcher_module.messagebox.showwarning.assert_called_once_with(
            launcher_module.ONLINE_ENTRY_REQUIRED_TITLE,
            launcher_module.ONLINE_ENTRY_REQUIRED_MESSAGE,
            parent=self.app,
        )

    def test_network_indicator_updates_transport_and_offline_state(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        self.assertIsNotNone(online_window)

        online_window.network_indicator.shutdown()

        online_window.network_indicator.apply_network_status(
            _make_network_status(
                transport_kind="wifi",
                transport_label="Wi-Fi",
                tone="warning",
                signal_bars=3,
                online_available=True,
                is_connected=True,
                quality_label="Moyen",
                latency_ms=280,
            )
        )
        self._update_ui()

        self.assertEqual(
            online_window.network_indicator.label.cget("text"),
            "Wi-Fi",
        )
        self.assertTrue(online_window.network_indicator.available)
        self.assertEqual(
            online_window.network_indicator.last_status.tone,
            "warning",
        )

        online_window.network_indicator.apply_network_status(
            _make_network_status(
                transport_kind="offline",
                transport_label="Hors ligne",
                tone="neutral",
                signal_bars=0,
                online_available=False,
                is_connected=False,
                quality_label="Aucun",
                latency_ms=None,
            )
        )
        self._update_ui()

        self.assertEqual(
            online_window.network_indicator.label.cget("text"),
            "Hors ligne",
        )
        self.assertFalse(online_window.network_indicator.available)

    def test_disconnected_session_window_offers_return_to_online_lobby(self):
        present_parent = online_lobby_module.present_window
        present_parent.side_effect = _deiconify_window_without_ctk_callbacks

        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)
        self.assertEqual(join_window.btn_disconnect.cget("text"), "Retour")

        present_parent.reset_mock()
        join_window.btn_disconnect.invoke()
        self._update_ui()

        present_parent.assert_called_once_with(online_window)
        self.assertFalse(join_window.winfo_exists())
        self.assertIsNone(online_window.join_window)
        self.assertNotEqual(online_window.state(), "withdrawn")

    def test_join_window_supports_manual_room_id_entry(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)
        self.assertIn("Entrer un ID", _collect_button_texts(join_window))

        join_window.connected = False
        join_window.connecting = False
        join_window._sync_controls_state()

        self.assertEqual(join_window.btn_join_room_id.cget("state"), "normal")

        online_lobby_module.play_click.reset_mock()
        join_window.btn_join_room_id.invoke()
        self._update_ui()

        prompt_window = join_window._room_id_prompt_window
        self.assertIsNotNone(prompt_window)
        self.assertIsNotNone(join_window.room_id_entry)
        online_lobby_module.play_click.assert_called_once_with()

        join_window.connected = True
        join_window.connecting = False
        join_window._sync_controls_state()

        join_window.room_id_var.set("  room-manual  ")
        online_lobby_module.play_transition.reset_mock()

        with mock.patch.object(
            join_window,
            "_join_room_id",
            return_value=True,
        ) as join_room_id:
            prompt_window.submit()
            self._update_ui()

        join_room_id.assert_called_once_with("room-manual")
        online_lobby_module.play_transition.assert_called_once_with()
        self.assertEqual(join_window.room_id_var.get(), "room-manual")
        self.assertIsNone(join_window._room_id_prompt_window)
        self.assertIsNone(join_window.room_id_entry)

    def test_join_window_requests_preview_on_open(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window

        with mock.patch.object(
            online_lobby_module.OnlineSessionWindow,
            "_request_room_preview",
            autospec=True,
        ) as request_room_preview:
            online_window.open_join_window()
            self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)
        request_room_preview.assert_called_once_with(join_window)

    def test_join_window_disconnected_refresh_uses_preview(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)
        join_window.connected = False
        join_window.connecting = False

        with mock.patch.object(
            join_window,
            "_request_room_preview",
        ) as request_room_preview:
            join_window.on_list_rooms()

        request_room_preview.assert_called_once_with(manual=True)

    def test_join_window_preview_renders_visible_and_in_game_sessions(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)

        getattr(join_window, "_apply_room_preview")(
            [
                {
                    "room_id": "room-open",
                    "name": "Salon ouvert",
                    "players": 1,
                    "max_players": 2,
                    "match_duration_seconds": 90,
                    "state": "lobby",
                    "host_pseudo": "HostPlayer",
                },
                {
                    "room_id": "room-live",
                    "name": "Partie déjà lancée",
                    "players": 2,
                    "max_players": 2,
                    "match_duration_seconds": 60,
                    "state": "in_game",
                    "host_pseudo": "OtherHost",
                },
            ],
            manual=False,
        )
        self._update_ui()

        room_texts = _collect_label_texts(join_window.rooms_scroll)
        room_buttons = _collect_button_texts(join_window.rooms_scroll)
        self.assertIn("Salon ouvert", room_texts)
        self.assertIn("Partie déjà lancée", room_texts)
        self.assertIn(
            "Partie lancée • Places : 2/2 • Durée : 60 s",
            room_texts,
        )
        self.assertIn("Entre ton pseudo", room_buttons)
        self.assertIn("En cours", room_buttons)
        self.assertIn(
            "session(s) visible(s)",
            join_window.rooms_meta_label.cget("text"),
        )

    def test_join_window_room_card_buttons_show_feedback_instead_of_being_dead(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)

        getattr(join_window, "_apply_room_preview")(
            [
                {
                    "room_id": "room-live",
                    "name": "Partie déjà lancée",
                    "players": 2,
                    "max_players": 2,
                    "match_duration_seconds": 60,
                    "state": "in_game",
                    "host_pseudo": "OtherHost",
                },
            ],
            manual=False,
        )
        self._update_ui()

        action_button = next(
            child
            for child in join_window.rooms_scroll.winfo_children()[0].winfo_children()
            if isinstance(child, ctk.CTkButton) and child.cget("text") == "En cours"
        )

        online_lobby_module.play_error.reset_mock()
        action_button.invoke()
        self._update_ui()

        online_lobby_module.play_error.assert_called_once_with()
        self.assertIn(
            "a déjà lancé sa partie",
            join_window.status_label.cget("text"),
        )

    def test_join_window_room_id_submit_starts_connection_when_needed(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)

        join_window.pseudo_var.set("GuestPlayer")
        join_window.connected = False
        join_window.connecting = False
        join_window.btn_join_room_id.invoke()
        self._update_ui()

        prompt_window = join_window._room_id_prompt_window
        self.assertIsNotNone(prompt_window)
        join_window.room_id_var.set(" room-manual ")

        def fake_connect() -> None:
            join_window.connecting = True

        with (
            mock.patch.object(
                join_window,
                "on_connect",
                side_effect=fake_connect,
            ) as on_connect,
            mock.patch.object(
                join_window,
                "_join_room_id",
                return_value=True,
            ) as join_room_id,
        ):
            prompt_window.submit()
            self._update_ui()

        on_connect.assert_called_once_with()
        join_room_id.assert_not_called()
        self.assertEqual(join_window._pending_join_room_id, "room-manual")
        self.assertIsNone(join_window._room_id_prompt_window)

    def test_join_window_room_id_prompt_shows_missing_pseudo_feedback(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)

        join_window.connected = False
        join_window.connecting = False
        join_window.pseudo_var.set("")
        join_window.btn_join_room_id.invoke()
        self._update_ui()

        prompt_window = join_window._room_id_prompt_window
        self.assertIsNotNone(prompt_window)
        join_window.room_id_var.set("room-manual")
        online_lobby_module.play_error.reset_mock()

        with mock.patch.object(join_window, "on_connect") as on_connect:
            prompt_window.submit()
            self._update_ui()

        on_connect.assert_not_called()
        online_lobby_module.play_error.assert_called_once_with()
        self.assertEqual(
            prompt_window.feedback_label.cget("text"),
            "Renseigne d'abord ton pseudo dans le panneau Profil.",
        )
        self.assertTrue(prompt_window.winfo_exists())

    def test_join_window_manual_room_id_error_mentions_completed_or_closed_session(
        self,
    ):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_join_window()
        self._update_ui()

        join_window = online_window.join_window
        self.assertIsNotNone(join_window)

        join_window.connected = True
        join_window.connecting = False
        join_window._remember_join_attempt("room-old", "manual_id")

        online_lobby_module.play_error.reset_mock()
        join_window._handle_message({"type": "ERROR", "code": "ROOM_NOT_FOUND"})
        self._update_ui()

        online_lobby_module.play_error.assert_called_once_with()
        self.assertIn(
            "n'est plus active",
            join_window.status_label.cget("text"),
        )
        self.assertIn(
            "Demande un nouvel ID",
            join_window.status_label.cget("text"),
        )

    def test_online_lobby_hides_launcher_and_restores_it_on_close(self):
        present_parent = online_lobby_module.present_window
        present_parent.side_effect = _deiconify_window_without_ctk_callbacks

        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        self.assertEqual(self.app.state(), "withdrawn")

        present_parent.reset_mock()
        online_window.shutdown()
        self._update_ui()

        present_parent.assert_called_once_with(self.app)
        self.assertFalse(online_window.winfo_exists())
        self.assertNotEqual(self.app.state(), "withdrawn")

    def test_launcher_close_app_shuts_down_online_lobby_before_destroy(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window

        with mock.patch.object(
            online_window,
            "shutdown",
            wraps=online_window.shutdown,
        ) as shutdown:
            self.app.request_shutdown()

        shutdown.assert_called_once_with()
        launcher_module.stop_music.assert_called_once_with(fade_ms=150)
        self.assertTrue(_window_is_destroyed(self.app))

    def test_launcher_close_app_stops_embedded_server_cleanly(self):
        fake_server = mock.Mock()
        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        self.app.embedded_server = fake_server
        self.app.embedded_server_thread = fake_thread
        self.app.active_server_port = 5000

        self.app.request_shutdown()

        fake_server.shutdown.assert_called_once_with()
        fake_server.server_close.assert_called_once_with()
        fake_thread.join.assert_called_once_with(timeout=0.4)
        self.assertIsNone(self.app.embedded_server)
        self.assertIsNone(self.app.embedded_server_thread)
        self.assertIsNone(self.app.active_server_port)

    def test_launcher_close_app_aborts_when_online_session_close_is_cancelled(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        self.assertIsNotNone(create_window)
        create_window.connected = True
        create_window.connecting = False

        self.app.request_shutdown()
        self._update_ui()

        online_lobby_module.messagebox.askyesno.assert_called_once()
        launcher_module.stop_music.assert_not_called()
        self.assertFalse(_window_is_destroyed(self.app))
        self.assertTrue(online_window.winfo_exists())
        self.assertTrue(create_window.winfo_exists())

    def test_launcher_close_app_aborts_when_lan_lobby_refuses_close(self):
        fake_lobby = mock.Mock()
        fake_lobby.winfo_exists.return_value = True
        fake_lobby.request_close.return_value = False
        self.app.host_lobby_window = fake_lobby

        self.app.request_shutdown()

        fake_lobby.request_close.assert_called_once_with()
        launcher_module.stop_music.assert_not_called()
        self.assertFalse(_window_is_destroyed(self.app))

    def test_online_switch_closes_previous_session_window(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window

        with mock.patch.object(
            create_window,
            "shutdown",
            wraps=create_window.shutdown,
        ) as shutdown:
            online_window.open_join_window()
            self._update_ui()

        shutdown.assert_called_once_with(restore_parent=False)
        self.assertFalse(create_window.winfo_exists())
        self.assertIsNone(online_window.create_window)
        self.assertIsNotNone(online_window.join_window)
        self.assertTrue(online_window.join_window.winfo_exists())

    def test_session_window_hides_online_lobby_and_restores_it_on_close(self):
        present_parent = online_lobby_module.present_window
        present_parent.side_effect = _deiconify_window_without_ctk_callbacks

        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        self.assertEqual(online_window.state(), "withdrawn")

        present_parent.reset_mock()
        create_window.shutdown()
        self._update_ui()

        present_parent.assert_called_once_with(online_window)
        self.assertFalse(create_window.winfo_exists())
        self.assertIsNone(online_window.create_window)
        self.assertNotEqual(online_window.state(), "withdrawn")

    def test_standalone_session_return_does_not_show_hidden_root(self):
        standalone_app = ctk.CTk()
        standalone_app.withdraw()
        session_window = None

        try:
            session_window = online_lobby_module.OnlineSessionWindow(
                standalone_app,
                mode=online_lobby_module.MODE_JOIN,
                network_available=True,
                restore_parent_on_close=False,
                destroy_parent_on_close=True,
            )
            standalone_app.update_idletasks()
            standalone_app.update()

            online_lobby_module.present_window.reset_mock()
            session_window.btn_disconnect.invoke()

            self.assertTrue(_window_is_destroyed(session_window))
            self.assertTrue(_window_is_destroyed(standalone_app))
            online_lobby_module.present_window.assert_not_called()
        finally:
            if session_window is not None and not _window_is_destroyed(session_window):
                _cancel_pending_after_callbacks(session_window)
                session_window.destroy()
            if not _window_is_destroyed(standalone_app):
                _cancel_pending_after_callbacks(standalone_app)
                standalone_app.destroy()

    def test_standalone_player_select_return_does_not_show_hidden_root(self):
        standalone_app = ctk.CTk()
        standalone_app.withdraw()
        player_select_window = None

        try:
            with (
                mock.patch.object(player_select_module, "play_click"),
                mock.patch.object(player_select_module, "play_transition"),
                mock.patch.object(player_select_module, "play_error"),
                mock.patch.object(player_select_module, "init_audio"),
                mock.patch.object(player_select_module, "start_menu_music"),
                mock.patch.object(player_select_module, "stop_music"),
                mock.patch.object(player_select_module, "apply_window_icon"),
                mock.patch.object(player_select_module, "enable_large_window"),
                mock.patch.object(
                    player_select_module,
                    "get_player_registry_snapshot",
                    return_value=[],
                ),
                mock.patch.object(
                    player_select_module,
                    "present_window",
                ) as present_parent,
                mock.patch.object(
                    player_select_module.PlayerSelectView,
                    "_hydrate_visual_assets",
                    new=_noop_tk_callback,
                ),
                mock.patch.object(
                    player_select_module.PlayerSelectView,
                    "_handle_first_paint",
                    new=_noop_tk_callback,
                ),
                mock.patch.object(
                    player_select_module.PlayerSelectView,
                    "_refresh_responsive_layout",
                    new=_noop_tk_callback,
                ),
                mock.patch.object(
                    player_select_module.PlayerSelectView,
                    "refresh_players",
                    new=_noop_tk_callback,
                ),
            ):
                player_select_window = player_select_module.PlayerSelectView(
                    standalone_app,
                    restore_parent_on_close=False,
                    destroy_parent_on_close=True,
                )
                standalone_app.update_idletasks()
                standalone_app.update()

                present_parent.reset_mock()
                _cancel_pending_after_callbacks(player_select_window)
                player_select_window.close_button.invoke()

                self.assertTrue(_window_is_destroyed(player_select_window))
                self.assertTrue(_window_is_destroyed(standalone_app))
                present_parent.assert_not_called()
        finally:
            if player_select_window is not None and not _window_is_destroyed(
                player_select_window
            ):
                _cancel_pending_after_callbacks(player_select_window)
                player_select_window.destroy()
            if not _window_is_destroyed(standalone_app):
                _cancel_pending_after_callbacks(standalone_app)
                standalone_app.destroy()

    def test_run_online_lobby_uses_destroy_parent_on_close_for_hidden_root(self):
        fake_app = mock.Mock()
        fake_window = mock.Mock()
        close_all = mock.Mock()
        restore_signal_handlers = mock.Mock()

        with (
            mock.patch.object(online_lobby_module.ctk, "CTk", return_value=fake_app),
            mock.patch.object(online_lobby_module, "apply_theme_settings"),
            mock.patch.object(
                online_lobby_module,
                "probe_online_service",
                return_value=True,
            ),
            mock.patch.object(
                online_lobby_module,
                "OnlineLobbyWindow",
                return_value=fake_window,
            ) as build_window,
            mock.patch.object(
                online_lobby_module,
                "build_graceful_shutdown",
                return_value=close_all,
            ),
            mock.patch.object(
                online_lobby_module,
                "install_signal_shutdown",
                return_value=restore_signal_handlers,
            ),
        ):
            online_lobby_module.run_online_lobby()

        fake_app.withdraw.assert_called_once_with()
        build_window.assert_called_once_with(
            fake_app,
            network_available=True,
            restore_parent_on_close=False,
            destroy_parent_on_close=True,
        )
        fake_window.protocol.assert_called_once_with("WM_DELETE_WINDOW", close_all)
        fake_app.mainloop.assert_called_once_with()
        restore_signal_handlers.assert_called_once_with()

    def test_standalone_lan_lobby_return_does_not_show_hidden_root(self):
        standalone_app = ctk.CTk()
        standalone_app.withdraw()
        lobby_window = None

        try:
            with (
                mock.patch.object(network_lobby_module, "apply_window_icon"),
                mock.patch.object(network_lobby_module, "enable_large_window"),
                mock.patch.object(network_lobby_module, "start_menu_music"),
                mock.patch.object(
                    network_lobby_module, "present_window"
                ) as present_parent,
                mock.patch.object(
                    network_lobby_module,
                    "load_lan_runtime_config",
                    return_value=mock.Mock(
                        port=5000, client_state_path="lan-state.json"
                    ),
                ),
                mock.patch.object(
                    network_lobby_module,
                    "get_lan_address_info",
                    return_value=mock.Mock(primary_ip="192.168.1.20"),
                ),
            ):
                lobby_window = network_lobby_module.NetworkLobbyView(
                    standalone_app,
                    restore_parent_on_close=False,
                    destroy_parent_on_close=True,
                )
                standalone_app.update_idletasks()
                standalone_app.update()

                present_parent.reset_mock()
                _cancel_pending_after_callbacks(lobby_window)
                lobby_window.shutdown()

                self.assertTrue(_window_is_destroyed(lobby_window))
                self.assertTrue(_window_is_destroyed(standalone_app))
                present_parent.assert_not_called()
        finally:
            if lobby_window is not None and not _window_is_destroyed(lobby_window):
                _cancel_pending_after_callbacks(lobby_window)
                lobby_window.destroy()
            if not _window_is_destroyed(standalone_app):
                _cancel_pending_after_callbacks(standalone_app)
                standalone_app.destroy()

    def test_player_select_hides_launcher_and_restores_it_on_close(self):
        with (
            mock.patch.object(player_select_module, "play_click"),
            mock.patch.object(player_select_module, "play_transition"),
            mock.patch.object(player_select_module, "play_error"),
            mock.patch.object(player_select_module, "init_audio"),
            mock.patch.object(player_select_module, "start_menu_music"),
            mock.patch.object(player_select_module, "stop_music"),
            mock.patch.object(player_select_module, "apply_window_icon"),
            mock.patch.object(player_select_module, "enable_large_window"),
            mock.patch.object(
                player_select_module,
                "get_player_registry_snapshot",
                return_value=[],
            ),
            mock.patch.object(
                player_select_module,
                "present_window",
            ) as present_parent,
            mock.patch.object(
                player_select_module.PlayerSelectView,
                "_hydrate_visual_assets",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                player_select_module.PlayerSelectView,
                "_handle_first_paint",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                player_select_module.PlayerSelectView,
                "_refresh_responsive_layout",
                new=_noop_tk_callback,
            ),
            mock.patch.object(
                player_select_module.PlayerSelectView,
                "refresh_players",
                new=_noop_tk_callback,
            ),
        ):
            present_parent.side_effect = _deiconify_window_without_ctk_callbacks

            self.app._handle_new_game()
            self._update_ui()

            player_select_window = self.app.player_select_window
            self.assertIsNotNone(player_select_window)
            self.assertEqual(self.app.state(), "withdrawn")

            present_parent.reset_mock()
            _cancel_pending_after_callbacks(player_select_window)
            player_select_window.close_button.invoke()
            self._update_ui()

            present_parent.assert_called_once_with(self.app)
            self.assertFalse(player_select_window.winfo_exists())
            self.assertNotEqual(self.app.state(), "withdrawn")

    def test_lan_lobby_hides_launcher_and_restores_it_on_close(self):
        with (
            mock.patch.object(network_lobby_module, "apply_window_icon"),
            mock.patch.object(network_lobby_module, "enable_large_window"),
            mock.patch.object(network_lobby_module, "start_menu_music"),
            mock.patch.object(network_lobby_module, "present_window") as present_parent,
            mock.patch.object(
                network_lobby_module,
                "load_lan_runtime_config",
                return_value=mock.Mock(port=5000, client_state_path="lan-state.json"),
            ),
            mock.patch.object(
                network_lobby_module,
                "get_lan_address_info",
                return_value=mock.Mock(primary_ip="192.168.1.20"),
            ),
        ):
            present_parent.side_effect = _deiconify_window_without_ctk_callbacks

            self.app._handle_join_lan()
            self._update_ui()

            lobby_window = self.app.join_lobby_window
            self.assertIsNotNone(lobby_window)
            self.assertEqual(self.app.state(), "withdrawn")

            present_parent.reset_mock()
            _cancel_pending_after_callbacks(lobby_window)
            lobby_window.shutdown()
            self._update_ui()

            present_parent.assert_called_once_with(self.app)
            self.assertFalse(lobby_window.winfo_exists())
            self.assertNotEqual(self.app.state(), "withdrawn")

    def test_online_connect_starts_poll_loop(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.pseudo_var.set("HostPlayer")

        with (
            mock.patch.object(
                create_window.client,
                "connect",
            ) as connect,
            mock.patch.object(
                create_window,
                "_schedule_poll",
            ) as schedule_poll,
        ):
            create_window.on_connect()

        connect.assert_called_once_with(
            create_window.host_var.get().strip(),
            int(create_window.port_var.get().strip()),
            "HostPlayer",
        )
        schedule_poll.assert_called_once_with()
        self.assertTrue(create_window.connecting)

    def test_create_room_sends_selected_match_duration(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.room_name_var.set("Session longue")
        create_window.max_players_var.set("4")
        create_window.match_duration_var.set("90")

        with mock.patch.object(
            create_window,
            "_send_message",
            return_value=True,
        ) as send_message:
            create_window.on_create_room()

        send_message.assert_called_once_with(
            {
                "type": "CREATE_ROOM",
                "name": "Session longue",
                "max_players": 4,
                "match_duration_seconds": 90,
            },
            action_label="créer la session",
        )

    def test_create_room_accepts_extended_match_duration_choices(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.room_name_var.set("Session marathon")
        create_window.max_players_var.set("4")
        create_window.match_duration_var.set("180")

        with mock.patch.object(
            create_window,
            "_send_message",
            return_value=True,
        ) as send_message:
            create_window.on_create_room()

        send_message.assert_called_once_with(
            {
                "type": "CREATE_ROOM",
                "name": "Session marathon",
                "max_players": 4,
                "match_duration_seconds": 180,
            },
            action_label="créer la session",
        )

    def test_online_connect_shows_detailed_network_error(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.pseudo_var.set("HostPlayer")
        error_message = (
            "Serveur online injoignable sur 165.232.108.225:27015. "
            "Verifie l'hote, le port et la connexion Internet."
        )

        with (
            mock.patch.object(
                create_window.client,
                "connect",
                side_effect=online_client_module.OnlineConnectionError(error_message),
            ) as connect,
            mock.patch.object(
                online_lobby_module.messagebox,
                "showerror",
            ) as showerror,
        ):
            create_window.on_connect()

        connect.assert_called_once_with(
            create_window.host_var.get().strip(),
            int(create_window.port_var.get().strip()),
            "HostPlayer",
        )
        showerror.assert_called_once_with(
            "Serveur indisponible",
            error_message,
        )
        self.assertEqual(
            create_window.status_label.cget("text"),
            error_message,
        )

    def test_online_create_window_enables_start_button_for_ready_host(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")

        _set_current_room_status(
            create_window,
            room_id="room-ready",
            room_name="Session prête",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )
        self._update_ui()

        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Annuler prêt",
        )
        self.assertEqual(create_window.btn_ready.cget("state"), "normal")
        self.assertEqual(
            create_window.btn_start_match.cget("text"),
            "Lancer le jeu",
        )
        self.assertEqual(create_window.btn_start_match.cget("state"), "normal")
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "Tous les joueurs sont prêts. Tu peux lancer le jeu.",
        )

        _set_current_room_status(
            create_window,
            room_id="room-waiting",
            room_name="Session incomplète",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer"],
            ready_players=[],
            max_players=2,
            capacity="Places : 1/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )
        self._update_ui()

        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Se mettre prêt",
        )
        self.assertEqual(create_window.btn_ready.cget("state"), "normal")
        self.assertEqual(
            create_window.btn_start_match.cget("text"),
            "Lancer le jeu",
        )
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "normal",
        )
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "En attente des joueurs 1/2 avant le départ.",
        )

        _set_current_room_status(
            create_window,
            room_id="room-guest",
            room_name="Session hôte distant",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="GuestPlayer",
            is_active=True,
        )
        self._update_ui()

        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Se mettre prêt",
        )
        self.assertEqual(create_window.btn_ready.cget("state"), "normal")
        self.assertEqual(
            create_window.btn_start_match.cget("text"),
            "Lancement réservé à l'hôte",
        )
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "normal",
        )
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "Passe en prêt pour signaler que tu es prêt.",
        )

    def test_ready_unknown_type_shows_compatibility_message(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        getattr(create_window, "_handle_message")(
            {
                "type": "ERROR",
                "code": "UNKNOWN_TYPE",
                "got": "SET_READY",
            }
        )
        self._update_ui()

        self.assertEqual(create_window.status_badge.cget("text"), "Serveur")
        self.assertIn(
            "n'accepte pas encore le bouton prêt",
            create_window.status_label.cget("text"),
        )

    def test_welcome_capability_disables_ready_without_support(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")

        _set_current_room_status(
            create_window,
            room_id="room-legacy",
            room_name="Session legacy",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=[],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )
        getattr(create_window, "_handle_message")(
            {
                "type": "WELCOME",
                "proto": 1,
                "capabilities": {"ready_state": False},
            }
        )
        self._update_ui()

        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Prêt indisponible",
        )
        self.assertEqual(create_window.btn_ready.cget("state"), "normal")
        self.assertEqual(create_window.btn_start_match.cget("state"), "normal")
        self.assertIn(
            "Ce serveur ne gère pas le prêt.",
            create_window.waiting_room_action_label.cget("text"),
        )

        player_labels = _collect_player_panel_labels(create_window)
        self.assertIn("Statut : connecté", player_labels)
        self.assertNotIn("Statut : en attente", player_labels)

    def test_room_update_warns_when_player_leaves_lobby(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")

        _set_current_room_status(
            create_window,
            room_id="room-leave",
            room_name="Session départ",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        getattr(create_window, "_handle_message")(
            {
                "type": "ROOM_UPDATE",
                "room": {
                    "room_id": "room-leave",
                    "name": "Session départ",
                    "state": "lobby",
                    "players": ["HostPlayer"],
                    "ready_players": ["HostPlayer"],
                    "max_players": 2,
                    "host_pseudo": "HostPlayer",
                },
            }
        )
        self._update_ui()

        self.assertEqual(create_window.status_badge.cget("text"), "Salon")
        self.assertEqual(
            create_window.status_label.cget("text"),
            "GuestPlayer a quitté la session.",
        )
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "En attente des joueurs 1/2 avant le départ.",
        )
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "normal",
        )

    def test_host_change_notice_survives_following_room_update(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("GuestPlayer")

        _set_current_room_status(
            create_window,
            room_id="room-host-change",
            room_name="Session migration",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=[],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        getattr(create_window, "_handle_message")(
            {
                "type": "HOST_CHANGED",
                "room_id": "room-host-change",
                "host_pseudo": "GuestPlayer",
            }
        )
        getattr(create_window, "_handle_message")(
            {
                "type": "ROOM_UPDATE",
                "room": {
                    "room_id": "room-host-change",
                    "name": "Session migration",
                    "state": "lobby",
                    "players": ["GuestPlayer"],
                    "ready_players": [],
                    "max_players": 2,
                    "host_pseudo": "GuestPlayer",
                },
            }
        )
        self._update_ui()

        self.assertEqual(create_window.current_room_host_pseudo, "GuestPlayer")
        self.assertEqual(create_window.status_badge.cget("text"), "Salon")
        self.assertEqual(
            create_window.status_label.cget("text"),
            "HostPlayer a quitté la session. Tu es maintenant l'hôte.",
        )
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "En attente des joueurs 1/2 avant le départ.",
        )

    def test_resume_after_match_keeps_in_game_departure_notice(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")
        create_window.client.running = True

        _set_current_room_status(
            create_window,
            room_id="room-mid-leave",
            room_name="Session départ en match",
            state_code="in_game",
            state_text="Partie lancée",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        with (
            mock.patch.object(
                create_window,
                "_request_rooms_refresh",
            ) as request_rooms_refresh,
            mock.patch.object(
                create_window,
                "_schedule_poll",
            ) as schedule_poll,
        ):
            setattr(create_window, "_poll_after_id", None)
            getattr(create_window, "_resume_after_match")(
                {
                    "deferred_messages": [
                        {
                            "type": "ROOM_UPDATE",
                            "room": {
                                "room_id": "room-mid-leave",
                                "name": "Session départ en match",
                                "state": "in_game",
                                "players": ["HostPlayer"],
                                "ready_players": [],
                                "max_players": 2,
                                "host_pseudo": "HostPlayer",
                            },
                        }
                    ],
                    "disconnect_message": None,
                    "end_message": {
                        "team_a_score": 2,
                        "team_b_score": 1,
                        "winner_text": "Victoire équipe A",
                    },
                }
            )

        self.assertEqual(create_window.status_badge.cget("text"), "Fin")
        self.assertEqual(
            create_window.status_label.cget("text"),
            (
                "Dernière joute : 2 - 1 · Victoire équipe A. "
                "GuestPlayer a quitté la joute."
            ),
        )
        self.assertEqual(create_window.current_room_state_code, "lobby")
        self.assertEqual(create_window.current_room_players, ["HostPlayer"])
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "En attente des joueurs 1/2 avant le départ.",
        )
        request_rooms_refresh.assert_called_once_with()
        schedule_poll.assert_called_once_with()

    def test_resume_after_match_keeps_in_game_host_change_notice(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("GuestPlayer")
        create_window.client.running = True

        _set_current_room_status(
            create_window,
            room_id="room-mid-host-change",
            room_name="Session migration en match",
            state_code="in_game",
            state_text="Partie lancée",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        with (
            mock.patch.object(
                create_window,
                "_request_rooms_refresh",
            ) as request_rooms_refresh,
            mock.patch.object(
                create_window,
                "_schedule_poll",
            ) as schedule_poll,
        ):
            setattr(create_window, "_poll_after_id", None)
            getattr(create_window, "_resume_after_match")(
                {
                    "deferred_messages": [
                        {
                            "type": "HOST_CHANGED",
                            "room_id": "room-mid-host-change",
                            "host_pseudo": "GuestPlayer",
                        },
                        {
                            "type": "ROOM_UPDATE",
                            "room": {
                                "room_id": "room-mid-host-change",
                                "name": "Session migration en match",
                                "state": "in_game",
                                "players": ["GuestPlayer"],
                                "ready_players": [],
                                "max_players": 2,
                                "host_pseudo": "GuestPlayer",
                            },
                        },
                    ],
                    "disconnect_message": None,
                    "end_message": {
                        "team_a_score": 0,
                        "team_b_score": 0,
                        "winner_text": "Joute à égalité",
                    },
                }
            )

        self.assertEqual(create_window.status_badge.cget("text"), "Fin")
        self.assertEqual(
            create_window.status_label.cget("text"),
            (
                "Dernière joute : 0 - 0 · Joute à égalité. "
                "HostPlayer a quitté la joute. Tu es maintenant l'hôte."
            ),
        )
        self.assertEqual(create_window.current_room_host_pseudo, "GuestPlayer")
        self.assertEqual(create_window.current_room_state_code, "lobby")
        self.assertEqual(create_window.current_room_players, ["GuestPlayer"])
        request_rooms_refresh.assert_called_once_with()
        schedule_poll.assert_called_once_with()

    def test_resume_after_match_disconnect_resets_online_window(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")
        create_window.client.running = True

        _set_current_room_status(
            create_window,
            room_id="room-disconnect",
            room_name="Session coupée",
            state_code="in_game",
            state_text="Partie lancée",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        getattr(create_window, "_resume_after_match")(
            {
                "deferred_messages": [],
                "end_message": None,
                "disconnect_message": ("Connexion interrompue pendant la joute."),
            }
        )
        self._update_ui()

        self.assertFalse(create_window.connected)
        self.assertIsNone(create_window.current_room_id)
        self.assertEqual(create_window.status_badge.cget("text"), "Déconnecté")
        self.assertEqual(
            create_window.status_label.cget("text"),
            "Connexion interrompue pendant la joute.",
        )
        self.assertEqual(create_window.btn_ready.cget("state"), "normal")
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "normal",
        )

    def test_resume_after_match_completed_requests_refresh(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")
        create_window.client.running = True

        _set_current_room_status(
            create_window,
            room_id="room-finish",
            room_name="Session gagnée",
            state_code="lobby",
            state_text="Salon en attente",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        with (
            mock.patch.object(
                create_window,
                "_request_rooms_refresh",
            ) as request_rooms_refresh,
            mock.patch.object(
                create_window,
                "_schedule_poll",
            ) as schedule_poll,
        ):
            setattr(create_window, "_poll_after_id", None)
            getattr(create_window, "_resume_after_match")(
                {
                    "deferred_messages": [],
                    "disconnect_message": None,
                    "end_message": {
                        "team_a_score": 5,
                        "team_b_score": 3,
                        "winner_text": "Victoire équipe A",
                    },
                }
            )

        self.assertTrue(create_window.connected)
        self.assertEqual(create_window.status_badge.cget("text"), "Fin")
        self.assertIn(
            "Dernière joute : 5 - 3 · Victoire équipe A.",
            create_window.status_label.cget("text"),
        )
        self.assertEqual(create_window.current_room_state_code, "lobby")
        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Se mettre prêt",
        )
        self.assertEqual(create_window.btn_ready.cget("state"), "normal")
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "normal",
        )
        self.assertIn(
            "Le salon est de nouveau ouvert.",
            create_window.active_room_hint_label.cget("text"),
        )
        self.assertEqual(
            create_window.waiting_room_action_label.cget("text"),
            "En attente des prêts 0/2 avant le départ.",
        )
        self.assertEqual(
            getattr(create_window, "_last_completed_match_signature"),
            ("room-finish", ("HostPlayer", "GuestPlayer"), 2),
        )
        request_rooms_refresh.assert_called_once_with()
        schedule_poll.assert_called_once_with()

    def test_resume_after_match_keeps_summary_on_end_disconnect(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")
        create_window.client.running = False

        _set_current_room_status(
            create_window,
            room_id="room-ended",
            room_name="Session finie",
            state_code="in_game",
            state_text="Partie lancée",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        getattr(create_window, "_resume_after_match")(
            {
                "deferred_messages": [],
                "disconnect_message": None,
                "end_message": {
                    "team_a_score": 4,
                    "team_b_score": 2,
                    "winner_text": "Victoire équipe A",
                },
            }
        )

        self.assertFalse(create_window.connected)
        self.assertIsNone(create_window.current_room_id)
        self.assertEqual(create_window.status_badge.cget("text"), "Déconnecté")
        self.assertEqual(
            create_window.status_label.cget("text"),
            (
                "Dernière joute : 4 - 2 · Victoire équipe A. "
                "Connexion interrompue à la fin du match."
            ),
        )

    def test_launch_match_disconnect_restores_window_state(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")
        create_window.local_slot = 1
        create_window.local_team = "A"
        create_window.client.running = True
        setattr(create_window, "_poll_after_id", "poll-token")

        _set_current_room_status(
            create_window,
            room_id="room-live",
            room_name="Session live",
            state_code="in_game",
            state_text="Partie lancée",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        with (
            mock.patch.object(
                create_window,
                "after_cancel",
            ) as after_cancel,
            mock.patch.object(
                online_lobby_module,
                "run_network_match",
                return_value={
                    "completed": False,
                    "end_message": None,
                    "deferred_messages": [],
                    "disconnect_message": (
                        "Le lien au hall s'est rompu pendant la joute."
                    ),
                },
            ) as run_network_match,
            mock.patch.object(
                online_lobby_module,
                "present_window",
            ) as present_window,
        ):
            getattr(create_window, "_launch_match")()

        self._update_ui()

        after_cancel.assert_called_once_with("poll-token")
        run_network_match.assert_called_once_with(
            create_window.client,
            1,
            "HostPlayer",
            "A",
        )
        present_window.assert_called_once_with(create_window)
        self.assertFalse(create_window.match_running)
        self.assertFalse(create_window.connected)
        self.assertIsNone(create_window.current_room_id)
        self.assertNotEqual(create_window.state(), "withdrawn")
        self.assertEqual(online_window.state(), "withdrawn")
        self.assertEqual(create_window.status_badge.cget("text"), "Déconnecté")
        self.assertEqual(
            create_window.status_label.cget("text"),
            "Le lien au hall s'est rompu pendant la joute.",
        )

    def test_launch_match_runtime_error_becomes_disconnect_message(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        create_window.connected = True
        create_window.pseudo_var.set("HostPlayer")
        create_window.local_slot = 1
        create_window.local_team = "A"
        create_window.client.running = True

        _set_current_room_status(
            create_window,
            room_id="room-crash",
            room_name="Session crash",
            state_code="in_game",
            state_text="Partie lancée",
            players=["HostPlayer", "GuestPlayer"],
            ready_players=["HostPlayer", "GuestPlayer"],
            max_players=2,
            capacity="Places : 2/2",
            host_pseudo="HostPlayer",
            is_active=True,
        )

        with (
            mock.patch.object(
                online_lobby_module,
                "run_network_match",
                side_effect=RuntimeError("socket rompue"),
            ),
            mock.patch.object(
                online_lobby_module,
                "present_window",
            ),
        ):
            getattr(create_window, "_launch_match")()

        self._update_ui()

        self.assertFalse(create_window.connected)
        self.assertIsNone(create_window.current_room_id)
        self.assertEqual(create_window.status_badge.cget("text"), "Déconnecté")
        self.assertEqual(
            create_window.status_label.cget("text"),
            "Le match online a échoué au lancement : socket rompue",
        )

    def test_process_events_stops_when_shutdown_is_requested(self):
        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        online_window.open_create_window()
        self._update_ui()

        create_window = online_window.create_window
        setattr(create_window, "_poll_after_id", "after#poll")
        setattr(create_window, "_shutdown_requested", True)

        with (
            mock.patch.object(
                create_window.client,
                "poll",
            ) as poll,
            mock.patch.object(
                create_window,
                "_schedule_poll",
            ) as schedule_poll,
        ):
            getattr(create_window, "_process_events")()

        poll.assert_not_called()
        schedule_poll.assert_not_called()
        self.assertIsNone(getattr(create_window, "_poll_after_id"))


if __name__ == "__main__":
    unittest.main()
