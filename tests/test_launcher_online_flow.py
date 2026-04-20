import os
import tempfile
import unittest
import importlib
from tkinter import TclError
from unittest import mock

import customtkinter as ctk


TEST_APPDATA_DIR = tempfile.mkdtemp(prefix="arena_duel_launcher_ui_")
os.environ.setdefault("APPDATA", TEST_APPDATA_DIR)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

launcher_module = importlib.import_module("ui.launcher")
online_lobby_module = importlib.import_module("ui.online_lobby")


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


def _set_current_room_status(window, **kwargs):
    getattr(window, "_set_current_room_status")(**kwargs)


class LauncherOnlineFlowTests(unittest.TestCase):
    def setUp(self):
        self.patchers = [
            mock.patch.object(launcher_module, "play_transition"),
            mock.patch.object(launcher_module, "play_click"),
            mock.patch.object(launcher_module, "play_alert"),
            mock.patch.object(launcher_module, "play_error"),
            mock.patch.object(launcher_module, "start_menu_music"),
            mock.patch.object(launcher_module, "stop_music"),
            mock.patch.object(
                launcher_module.LauncherApp,
                "_hydrate_visual_assets",
            ),
            mock.patch.object(
                online_lobby_module.messagebox,
                "askyesno",
                return_value=False,
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

    def tearDown(self):
        try:
            online_window = getattr(self.app, "online_lobby_window", None)
            if online_window is not None and online_window.winfo_exists():
                join_window = getattr(online_window, "join_window", None)
                if join_window is not None and join_window.winfo_exists():
                    join_window.shutdown()

                create_window = getattr(online_window, "create_window", None)
                if create_window is not None and create_window.winfo_exists():
                    create_window.shutdown()

                online_window.shutdown()

            if self.app.winfo_exists():
                self.app.destroy()
        except TclError:
            pass
        finally:
            for patcher in reversed(self.patchers):
                patcher.stop()

    def _update_ui(self):
        self.app.update_idletasks()
        self.app.update()

    def test_launcher_opens_online_lobby_and_session_windows(self):
        launcher_buttons = _collect_button_texts(self.app)
        self.assertIn("Jouer en ligne", launcher_buttons)

        self.app.open_online_lobby()
        self._update_ui()

        online_window = self.app.online_lobby_window
        self.assertIsNotNone(online_window)
        self.assertEqual(online_window.title(), "Arena Duel - Jouer en ligne")

        online_labels = _collect_label_texts(online_window)
        self.assertIn("Choisis ton parcours", online_labels)
        self.assertIn("Rejoindre une session", online_labels)
        self.assertIn("Créer une session", online_labels)

        online_buttons = _collect_button_texts(online_window)
        self.assertIn("Ouvrir la fenêtre de rejoindre", online_buttons)
        self.assertIn("Ouvrir la fenêtre de création", online_buttons)

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
        self.assertEqual(
            create_window.btn_start_match.cget("state"),
            "disabled",
        )
        self.assertEqual(
            create_window.btn_ready.cget("text"),
            "Se mettre prêt",
        )
        self.assertEqual(
            create_window.btn_ready.cget("state"),
            "disabled",
        )
        self.assertEqual(
            create_window.active_room_title_label.cget("text"),
            "Aucune session créée",
        )

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
            "disabled",
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
            "disabled",
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


if __name__ == "__main__":
    unittest.main()
