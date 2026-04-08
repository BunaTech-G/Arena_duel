import customtkinter as ctk
import pygame
from tkinter import TclError, messagebox

from db.database import test_connection
from game.audio import (
    init_audio,
    play_alert,
    play_click,
    play_error,
    play_transition,
    start_menu_music,
    stop_music,
)
from network.server import start_server_in_background
from runtime_utils import (
    load_runtime_config,
    resource_path,
    set_runtime_override,
)
from ui.history_view import HistoryView
from ui.network_lobby import NetworkLobbyView
from ui.player_select import PlayerSelectView
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    apply_theme_settings,
    create_badge,
    create_button,
    enable_large_window,
    load_ctk_image,
    set_textbox_content,
    style_frame,
    style_textbox,
    style_window,
    update_badge,
)


apply_theme_settings()


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        style_window(self)

        self.title("Arena Duel - Bastion central")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except (OSError, TclError):
            pass

        self.geometry("1360x860")
        enable_large_window(self, 1240, 780)

        self.embedded_server = None
        self.embedded_server_thread = None
        self.embedded_server_ip = None
        self.current_db_mode = "local"
        self.tcp_port = int(load_runtime_config().get("tcp_port", 5000))
        self._set_db_mode_local()

        self.launcher_background_image = load_ctk_image(
            "assets",
            "backgrounds",
            "launcher_twilight_bastion_bg.png",
            size=(1360, 765),
            fallback_label="twilight bastion",
        )

        pygame.mixer.pre_init(44100, -16, 2, 512)
        init_audio()
        start_menu_music()

        self.protocol("WM_DELETE_WINDOW", self._handle_close_app)

        self._build_ui()
        self._set_info(
            self._default_journal_text(),
            badge_text="Voie de demo",
            tone="gold",
        )
        self._set_db_status("Chroniques en veille", "neutral")
        self._set_server_status("Hall au repos", "neutral")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(
            self, corner_radius=30, fg_color="transparent",
        )
        shell.grid(row=0, column=0, padx=22, pady=22, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        backdrop = ctk.CTkLabel(
            shell,
            text="",
            image=self.launcher_background_image,
        )
        backdrop.place(relx=0.5, rely=0.5, anchor="center")

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.grid(row=0, column=0, padx=30, pady=(26, 12), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        create_badge(header, "Bastion central", tone="gold").grid(
            row=0,
            column=0,
            sticky="w",
        )

        status_panel = ctk.CTkFrame(header, corner_radius=18)
        style_frame(
            status_panel,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        status_panel.grid(row=0, column=1, sticky="e")
        status_panel.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            status_panel,
            text="Chroniques",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
        ).grid(row=0, column=0, padx=(14, 8), pady=(10, 4), sticky="w")

        ctk.CTkLabel(
            status_panel,
            text="Hall LAN",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
        ).grid(row=0, column=1, padx=(8, 14), pady=(10, 4), sticky="w")

        self.db_badge = create_badge(
            status_panel,
            "Chroniques en veille",
            tone="neutral",
        )
        self.db_badge.grid(
            row=1,
            column=0,
            padx=(14, 8),
            pady=(0, 12),
            sticky="w",
        )

        self.server_badge = create_badge(
            status_panel,
            "Hall au repos",
            tone="neutral",
        )
        self.server_badge.grid(
            row=1,
            column=1,
            padx=(8, 14),
            pady=(0, 12),
            sticky="w",
        )

        center_zone = ctk.CTkFrame(shell, fg_color="transparent")
        center_zone.grid(row=1, column=0, padx=40, pady=(6, 12), sticky="nsew")
        center_zone.grid_columnconfigure(0, weight=1)
        center_zone.grid_rowconfigure(1, weight=1)

        title_panel = ctk.CTkFrame(
            center_zone, corner_radius=22, fg_color="transparent",
        )
        title_panel.grid(row=0, column=0, pady=(12, 18))
        title_panel.grid_columnconfigure(0, weight=1)

        create_badge(
            title_panel,
            "Forgotten Bastion - ecran titre",
            tone="info",
        ).grid(row=0, column=0, padx=26, pady=(18, 10))

        ctk.CTkLabel(
            title_panel,
            text="Arena Duel",
            font=(TYPOGRAPHY["display"][0], 54, "bold"),
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, padx=34, pady=(0, 2))

        ctk.CTkLabel(
            title_panel,
            text=(
                "Ecran principal simplifie : fond 2D du bastion, actions "
                "centrees et lecture immediate."
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=560,
            justify="center",
        ).grid(row=2, column=0, padx=26, pady=(0, 18))

        menu_panel = ctk.CTkFrame(
            center_zone, corner_radius=24, fg_color="transparent",
        )
        menu_panel.grid(row=1, column=0, pady=(0, 14))
        menu_panel.grid_columnconfigure((0, 1), weight=1)

        create_button(
            menu_panel,
            "Ouvrir la forge locale",
            self._handle_new_game,
            variant="primary",
            width=460,
            height=50,
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            padx=22,
            pady=(22, 10),
            sticky="ew",
        )

        create_button(
            menu_panel,
            "Ouvrir le hall LAN",
            self._handle_host_lan,
            variant="accent",
            width=460,
            height=50,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            padx=22,
            pady=(0, 10),
            sticky="ew",
        )

        create_button(
            menu_panel,
            "Rejoindre un hall",
            self._handle_join_lan,
            variant="secondary",
            width=460,
            height=50,
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            padx=22,
            pady=(0, 16),
            sticky="ew",
        )

        create_button(
            menu_panel,
            "Chroniques",
            self._handle_history,
            variant="secondary",
            height=42,
        ).grid(row=3, column=0, padx=(22, 10), pady=(0, 10), sticky="ew")

        create_button(
            menu_panel,
            "Verifier le sanctuaire",
            self._handle_test_db,
            variant="ghost",
            height=42,
        ).grid(row=3, column=1, padx=(10, 22), pady=(0, 10), sticky="ew")

        create_button(
            menu_panel,
            "Fermer le bastion",
            self._handle_close_app,
            variant="danger",
            height=44,
        ).grid(
            row=4,
            column=0,
            columnspan=2,
            padx=22,
            pady=(0, 16),
            sticky="ew",
        )

        ctk.CTkLabel(
            menu_panel,
            text="Fond 2D du jeu - menu simple - aucune colonne inutile",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="center",
        ).grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 18))

        info_panel = ctk.CTkFrame(
            shell, corner_radius=22, fg_color="transparent",
        )
        info_panel.grid(row=2, column=0, padx=34, pady=(0, 24), sticky="ew")
        info_panel.grid_columnconfigure(0, weight=1)
        info_panel.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            info_panel,
            text="Journal du bastion",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")

        self.info_badge = create_badge(
            info_panel,
            "Veille du bastion",
            tone="neutral",
        )
        self.info_badge.grid(
            row=0,
            column=1,
            padx=18,
            pady=(16, 4),
            sticky="e",
        )

        self.info_box = ctk.CTkTextbox(info_panel, height=98)
        self.info_box.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        style_textbox(self.info_box, tone="panel_soft")

    def _default_journal_text(self):
        return (
            "Le bastion est pret.\n\n"
            "Voie de demo :\n"
            "1. Forge locale pour sentir la map\n"
            "2. Hall partage sur le poste gardien\n"
            "3. Compagnon dans le hall puis joute\n"
            "4. Lecture de la chronique finale"
        )

    def _db_ready_journal_text(self):
        return (
            "Le sanctuaire des chroniques repond.\n\n"
            "Le bastion peut enregistrer les combattants, conserver les "
            "verdicts et relire les chroniques locales comme partagees."
        )

    def _db_error_journal_text(self):
        return (
            "Le sanctuaire des chroniques ne repond pas.\n\n"
            "L'archive est indisponible pour le moment. Verifie le bastion "
            "gardien avant de reprendre la joute."
        )

    def _relay_opened_journal_text(self, local_ip: str):
        return (
            "Hall ouvert.\n\n"
            f"Invitation du bastion a transmettre : {local_ip}\n\n"
            "Ouvre le hall, inscris les combattants puis lance la joute "
            "quand tous les etendards sont leves."
        )

    def _relay_join_journal_text(self):
        return (
            "Le hall s'ouvre.\n\n"
            "Prepare l'invitation du bastion et le nom du combattant avant "
            "d'entrer dans l'arene partagee."
        )

    def _set_info(self, text, badge_text="Veille du bastion", tone="neutral"):
        update_badge(self.info_badge, badge_text, tone)
        set_textbox_content(self.info_box, text)

    def _set_db_status(self, text: str, tone: str):
        update_badge(self.db_badge, text, tone)

    def _set_server_status(self, text: str, tone: str):
        update_badge(self.server_badge, text, tone)

    def _set_db_mode_local(self):
        set_runtime_override("db_host", "localhost")
        self.current_db_mode = "local"

    def _set_db_mode_remote(self, server_ip: str):
        set_runtime_override("db_host", server_ip)
        self.current_db_mode = f"remote:{server_ip}"

    def _handle_test_db(self):
        play_click()

        ok = test_connection()
        if ok:
            self._set_db_status("Chroniques pretes", "success")
            self._set_info(
                self._db_ready_journal_text(),
                badge_text="Chroniques pretes",
                tone="success",
            )
        else:
            play_error()
            self._set_db_status("Sanctuaire indisponible", "danger")
            self._set_info(
                self._db_error_journal_text(),
                badge_text="Alerte du sanctuaire",
                tone="danger",
            )

    def _handle_new_game(self):
        play_transition()
        self._set_db_mode_local()
        self._set_info(
            "La forge locale s'ouvre.\n\n"
            "Prepare deux bastions equilibres avant de sceller la prochaine "
            "joute.",
            badge_text="Forge ouverte",
            tone="gold",
        )

        window = PlayerSelectView(self)
        window.lift()
        window.focus_force()

    def _handle_history(self):
        play_transition()
        self._set_db_mode_local()
        self._set_info(
            "Ouverture des chroniques locales.\n\n"
            "Relis les verdicts recents et la tendance dominante des "
            "bastions.",
            badge_text="Chroniques ouvertes",
            tone="gold",
        )

        window = HistoryView(
            self,
            source_label="Chroniques locales du bastion",
        )
        window.lift()
        window.focus_force()

    def _handle_host_lan(self):
        play_transition()

        if self.embedded_server is None:
            try:
                server, thread, local_ip = start_server_in_background(
                    "0.0.0.0",
                    self.tcp_port,
                )
                self.embedded_server = server
                self.embedded_server_thread = thread
                self.embedded_server_ip = local_ip

                self._set_server_status(
                    "Hall ouvert - invitation prete",
                    "info",
                )
                self._set_info(
                    self._relay_opened_journal_text(local_ip),
                    badge_text="Invitation prete",
                    tone="info",
                )
            except (OSError, RuntimeError) as error:
                play_alert()
                self._set_info(
                    "Le hall n'a pas pu s'ouvrir.\n\n"
                    "Le bastion n'a pas reussi a preparer une invitation "
                    "stable pour la joute.",
                    badge_text="Hall indisponible",
                    tone="danger",
                )
                messagebox.showerror(
                    "Hall indisponible",
                    f"Impossible d'ouvrir le hall : {error}",
                )
                return
        else:
            self._set_server_status(
                "Hall deja ouvert - invitation prete",
                "info",
            )
            self._set_info(
                self._relay_opened_journal_text(self.embedded_server_ip),
                badge_text="Invitation prete",
                tone="info",
            )

        self._set_db_mode_local()

        window = NetworkLobbyView(
            self,
            default_server_ip="127.0.0.1",
            server_port=self.tcp_port,
            host_mode=True,
        )
        window.lift()
        window.focus_force()

    def _handle_join_lan(self):
        play_transition()
        self._set_db_mode_local()
        self._set_info(
            self._relay_join_journal_text(),
            badge_text="Hall en approche",
            tone="info",
        )

        window = NetworkLobbyView(self, server_port=self.tcp_port)
        window.lift()
        window.focus_force()

    def _handle_close_app(self):
        if self.embedded_server is not None:
            try:
                self.embedded_server.shutdown()
                self.embedded_server.server_close()
            except (OSError, RuntimeError):
                pass

        stop_music(fade_ms=150)
        self.destroy()


def run_launcher():
    app = LauncherApp()
    app.mainloop()
