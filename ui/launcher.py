import customtkinter as ctk
import pygame
from db.database import test_connection
from game.audio import init_audio
from ui.player_select import PlayerSelectView
from ui.history_view import HistoryView
import pygame
from game.audio import init_audio, play_click


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Arena Duel")
        self.geometry("900x560")
        self.minsize(900, 560)
        
        # Init audio UI
        pygame.mixer.pre_init(44100, -16, 2, 512)
        try:
            pygame.init()
        except:
            pass
        init_audio()# Init audio UI
        

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
            font=("Arial", 34, "bold")
        )
        title.grid(row=0, column=0, pady=(25, 5), padx=20)

        subtitle = ctk.CTkLabel(
            container,
            text="Projet full Python : jeu Pygame + UI CustomTkinter + MariaDB",
            font=("Arial", 16)
        )
        subtitle.grid(row=1, column=0, pady=(0, 20), padx=20)

        self.db_status_label = ctk.CTkLabel(
            container,
            text="État MariaDB : test non lancé",
            font=("Arial", 15)
        )
        self.db_status_label.grid(row=2, column=0, pady=10, padx=20)

        test_db_btn = ctk.CTkButton(
            container,
            text="Tester la connexion MariaDB",
            command=self._handle_test_db,
            width=260,
            height=42
        )
        test_db_btn.grid(row=3, column=0, pady=10, padx=20)

        start_btn = ctk.CTkButton(
            container,
            text="Nouvelle partie",
            command=self._handle_new_game,
            width=260,
            height=46
        )
        start_btn.grid(row=4, column=0, pady=10, padx=20)

        history_btn = ctk.CTkButton(
            container,
            text="Historique / Scores",
            command=self._handle_history,
            width=260,
            height=42
        )
        history_btn.grid(row=5, column=0, pady=10, padx=20)

        quit_btn = ctk.CTkButton(
            container,
            text="Quitter",
            command=self.destroy,
            width=260,
            height=42,
            fg_color="#B33939",
            hover_color="#922B2B"
        )
        quit_btn.grid(row=6, column=0, pady=(10, 25), padx=20)

        self.info_box = ctk.CTkTextbox(container, width=600, height=140)
        self.info_box.grid(row=7, column=0, pady=(0, 25), padx=20, sticky="ew")
        self.info_box.insert("0.0", "Bienvenue dans Arena Duel.\n\nÉtape 1 : structure + connexion MariaDB.")
        self.info_box.configure(state="disabled")

    def _set_info(self, text):
        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", text)
        self.info_box.configure(state="disabled")

    def _handle_test_db(self):
        play_click()
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
                "- le user/password dans db/database.py\n"
                "- que la base arena_duel_v2_db existe"
            )

    def _handle_new_game(self):
        play_click()
        window = PlayerSelectView(self)
        window.lift()
        window.focus_force()

    def _handle_history(self):
        play_click()
        window = HistoryView(self)
        window.lift()
        window.focus_force()

def run_launcher():
    app = LauncherApp()
    app.mainloop()
