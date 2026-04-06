import customtkinter as ctk
import pygame
from tkinter import messagebox

from db.database import test_connection
from game.audio import init_audio, play_click
from network.server import start_server_in_background
from ui.player_select import PlayerSelectView
from ui.history_view import HistoryView
from ui.network_lobby import NetworkLobbyView
from runtime_utils import resource_path


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Arena Duel")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except Exception:
            pass
        self.geometry("940x680")
        self.minsize(940, 680)

        self.embedded_server = None
        self.embedded_server_thread = None
        self.embedded_server_ip = None

        # audio
        pygame.mixer.pre_init(44100, -16, 2, 512)
        try:
            pygame.init()
        except Exception:
            pass

        try:
            init_audio()
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._handle_close_app)

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self, corner_radius=18)
        container.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            container,
            text="ARENA DUEL",
            font=("Arial", 36, "bold")
        )
        title.grid(row=0, column=0, pady=(25, 8), padx=20)

        subtitle = ctk.CTkLabel(
            container,
            text="Jeu d’arène local et LAN — Python / Pygame / CustomTkinter / MariaDB",
            font=("Arial", 16)
        )
        subtitle.grid(row=1, column=0, pady=(0, 18), padx=20)

        self.db_status_label = ctk.CTkLabel(
            container,
            text="État MariaDB : test non lancé",
            font=("Arial", 15)
        )
        self.db_status_label.grid(row=2, column=0, pady=6, padx=20)

        self.server_status_label = ctk.CTkLabel(
            container,
            text="Serveur LAN intégré : non démarré",
            font=("Arial", 15)
        )
        self.server_status_label.grid(row=3, column=0, pady=6, padx=20)

        local_btn = ctk.CTkButton(
            container,
            text="Mode local",
            command=self._handle_new_game,
            width=300,
            height=48
        )
        local_btn.grid(row=4, column=0, pady=10, padx=20)

        host_lan_btn = ctk.CTkButton(
            container,
            text="Héberger une partie LAN",
            command=self._handle_host_lan,
            width=300,
            height=48
        )
        host_lan_btn.grid(row=5, column=0, pady=10, padx=20)

        join_lan_btn = ctk.CTkButton(
            container,
            text="Rejoindre une partie LAN",
            command=self._handle_join_lan,
            width=300,
            height=48
        )
        join_lan_btn.grid(row=6, column=0, pady=10, padx=20)

        history_btn = ctk.CTkButton(
            container,
            text="Historique / Scores",
            command=self._handle_history,
            width=300,
            height=44
        )
        history_btn.grid(row=7, column=0, pady=10, padx=20)

        test_db_btn = ctk.CTkButton(
            container,
            text="Tester la connexion MariaDB",
            command=self._handle_test_db,
            width=300,
            height=44
        )
        test_db_btn.grid(row=8, column=0, pady=10, padx=20)

        quit_btn = ctk.CTkButton(
            container,
            text="Quitter",
            command=self._handle_close_app,
            width=300,
            height=44,
            fg_color="#B33939",
            hover_color="#922B2B"
        )
        quit_btn.grid(row=9, column=0, pady=(10, 25), padx=20)

        self.info_box = ctk.CTkTextbox(container, width=700, height=170)
        self.info_box.grid(row=10, column=0, pady=(0, 25), padx=20, sticky="ew")
        self.info_box.insert(
            "0.0",
            "Bienvenue dans Arena Duel.\n\n"
            "Modes disponibles :\n"
            "- Mode local\n"
            "- Héberger une partie LAN\n"
            "- Rejoindre une partie LAN\n"
            "- Historique / Scores\n\n"
            "Conseil présentation :\n"
            "1. Héberger sur le PC serveur\n"
            "2. Rejoindre sur les autres PC\n"
            "3. Jouer une partie réseau\n"
            "4. Vérifier l’historique ensuite"
        )
        self.info_box.configure(state="disabled")

    def _set_info(self, text):
        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", text)
        self.info_box.configure(state="disabled")

    def _handle_test_db(self):
        try:
            play_click()
        except Exception:
            pass

        ok = test_connection()
        if ok:
            self.db_status_label.configure(text="État MariaDB : connexion réussie ✅")
            self._set_info("Connexion MariaDB réussie.\nLa base semble accessible.")
        else:
            self.db_status_label.configure(text="État MariaDB : connexion échouée ❌")
            self._set_info(
                "Connexion MariaDB échouée.\n"
                "Vérifie :\n"
                "- XAMPP lancé\n"
                "- Apache et MySQL démarrés\n"
                "- les paramètres dans db/database.py\n"
                "- que la base arena_duel_v2_db existe"
            )

    def _handle_new_game(self):
        try:
            play_click()
        except Exception:
            pass

        window = PlayerSelectView(self)
        window.lift()
        window.focus_force()

    def _handle_history(self):
        try:
            play_click()
        except Exception:
            pass

        window = HistoryView(self)
        window.lift()
        window.focus_force()

    def _handle_host_lan(self):
        try:
            play_click()
        except Exception:
            pass

        # si le serveur est déjà démarré, on réutilise l'IP
        if self.embedded_server is None:
            try:
                server, thread, local_ip = start_server_in_background("0.0.0.0", 5000)
                self.embedded_server = server
                self.embedded_server_thread = thread
                self.embedded_server_ip = local_ip

                self.server_status_label.configure(
                    text=f"Serveur LAN intégré : actif sur {local_ip}:5000 ✅"
                )

                self._set_info(
                    f"Serveur LAN démarré.\n\n"
                    f"Adresse à communiquer aux clients : {local_ip}:5000\n\n"
                    f"Ensuite, entre ton pseudo dans le lobby et connecte-toi."
                )

            except Exception as e:
                messagebox.showerror("Erreur serveur LAN", f"Impossible de démarrer le serveur LAN : {e}")
                return

        window = NetworkLobbyView(
            self,
            default_server_ip="127.0.0.1",
            host_mode=True
        )
        window.lift()
        window.focus_force()

    def _handle_join_lan(self):
        try:
            play_click()
        except Exception:
            pass

        window = NetworkLobbyView(self)
        window.lift()
        window.focus_force()

    def _handle_close_app(self):
        # arrêt propre du serveur embarqué si actif
        try:
            if self.embedded_server is not None:
                self.embedded_server.shutdown()
                self.embedded_server.server_close()
        except Exception:
            pass

        self.destroy()


def run_launcher():
    app = LauncherApp()
    app.mainloop()
