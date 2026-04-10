import customtkinter as ctk
import pygame
from tkinter import TclError, messagebox

from db.database import test_connection
from hardware.service import describe_hardware_runtime_status
from game.audio import (
    init_audio,
    play_alert,
    play_click,
    play_error,
    play_transition,
    start_menu_music,
    stop_music,
)
from network.net_utils import (
    format_endpoint,
    get_lan_address_info,
    load_lan_runtime_config,
)
from network.server import start_server_in_background
from runtime_utils import (
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
    present_window,
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
        self.embedded_server_address_info = None
        self.current_db_mode = "local"
        self.player_select_window = None
        self.history_window = None
        self.host_lobby_window = None
        self.join_lobby_window = None
        self.hardware_status_badge = None
        self.hardware_status_label = None
        self.network_config = load_lan_runtime_config()
        self.tcp_port = self.network_config.port
        self._set_db_mode_local()

        # Taille adaptive : remplit l'écran quelle que soit la résolution
        _sw = max(1360, self.winfo_screenwidth())
        _sh = max(860, self.winfo_screenheight())
        self.launcher_background_image = load_ctk_image(
            "assets",
            "backgrounds",
            "launcher_twilight_bastion_bg.png",
            size=(_sw, _sh),
            fallback_label="twilight bastion",
            brightness=1.5,
        )

        pygame.mixer.pre_init(44100, -16, 2, 512)
        init_audio()
        start_menu_music()

        self.protocol("WM_DELETE_WINDOW", self._handle_close_app)
        self.bind("<FocusIn>", self._handle_focus_in)

        self._build_ui()
        self._refresh_hardware_status()
        self._set_info(
            self._default_journal_text(),
            badge_text="Voie de demo",
            tone="gold",
        )
        self._set_db_status("Chroniques en veille", "neutral")
        self._set_server_status("Hall au repos", "neutral")

    def _build_ui(self):
        backdrop = ctk.CTkLabel(
            self, text="", image=self.launcher_background_image,
        )
        backdrop.place(x=0, y=0, relwidth=1, relheight=1)

        # ── Panneau titre flottant directement sur le fond
        title_panel = ctk.CTkFrame(
            self,
            corner_radius=22,
            fg_color=PALETTE["panel"],
            border_width=1,
            border_color=PALETTE["gold_dim"],
        )
        title_panel.place(relx=0.5, rely=0.12, anchor="n")
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
            text="Forgotten Bastion — Entrez dans l’arène",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=480,
            justify="center",
        ).grid(row=2, column=0, padx=26, pady=(0, 18))

        # ── Panneau menu flottant directement sur le fond
        menu_panel = ctk.CTkFrame(
            self,
            corner_radius=24,
            fg_color=PALETTE["panel"],
            border_width=1,
            border_color=PALETTE["border"],
        )
        menu_panel.place(relx=0.5, rely=0.53, anchor="n")
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
            pady=(0, 18),
            sticky="ew",
        )

        footer_panel = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color=PALETTE["panel"],
            border_width=1,
            border_color=PALETTE["border"],
        )
        footer_panel.place(relx=0.5, rely=0.965, anchor="s", relwidth=0.92)
        footer_panel.grid_columnconfigure(0, weight=1)
        footer_panel.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            footer_panel,
            text="Jeu cree par Ousmane et Gabriel",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(row=0, column=0, padx=18, pady=14, sticky="w")

        hardware_panel = ctk.CTkFrame(footer_panel, fg_color="transparent")
        hardware_panel.grid(row=0, column=1, padx=18, pady=10, sticky="e")
        hardware_panel.grid_columnconfigure(1, weight=1)

        self.hardware_status_badge = create_badge(
            hardware_panel,
            "Bridge Arduino",
            tone="neutral",
        )
        self.hardware_status_badge.grid(
            row=0,
            column=0,
            padx=(0, 10),
            pady=4,
            sticky="e",
        )

        self.hardware_status_label = ctk.CTkLabel(
            hardware_panel,
            text="Bonus materiel en veille.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=330,
        )
        self.hardware_status_label.grid(
            row=0,
            column=1,
            pady=4,
            sticky="w",
        )

        # S'assurer que le fond est en dernière position (derrière tout)
        self.after(0, backdrop.lower)

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

    def _relay_opened_journal_text(
        self,
        invitation_text: str,
        warning_text: str | None = None,
    ):
        message = (
            "Hall ouvert.\n\n"
            f"Invitation LAN a transmettre : {invitation_text}\n\n"
            "Ouvre le hall, inscris les combattants puis lance la joute "
            "quand tous les etendards sont leves."
        )
        if warning_text:
            message += f"\n\nAlerte reseau : {warning_text}"
        return message

    def _relay_join_journal_text(self):
        return (
            "Le hall s'ouvre.\n\n"
            "Prepare l'invitation LAN du bastion et le nom du combattant "
            "avant d'entrer dans l'arene partagee. Le test local sur ce PC "
            "reste disponible comme mode distinct."
        )

    def _set_info(self, text, badge_text="Veille du bastion", tone="neutral"):
        pass

    def _set_db_status(self, text: str, tone: str):
        pass

    def _set_server_status(self, text: str, tone: str):
        pass

    def _set_db_mode_local(self):
        set_runtime_override("db_host", "localhost")
        self.current_db_mode = "local"

    def _handle_focus_in(self, _event=None):
        self._refresh_hardware_status()

    def _refresh_hardware_status(self):
        if (
            self.hardware_status_badge is None
            or self.hardware_status_label is None
        ):
            return

        status = describe_hardware_runtime_status()
        update_badge(
            self.hardware_status_badge,
            status.badge_text,
            status.tone,
        )
        self.hardware_status_label.configure(text=status.detail_text)

    def _get_live_window(self, window):
        if window is None:
            return None

        try:
            return window if window.winfo_exists() else None
        except TclError:
            return None

    def _focus_or_open_window(self, attr_name, factory):
        existing_window = self._get_live_window(getattr(self, attr_name))
        if existing_window is not None:
            present_window(existing_window)
            return existing_window

        window = factory()
        setattr(self, attr_name, window)
        present_window(window)
        return window

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
        self._focus_or_open_window(
            "player_select_window",
            lambda: PlayerSelectView(self),
        )

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
        self._focus_or_open_window(
            "history_window",
            lambda: HistoryView(
                self,
                source_label="Chroniques locales du bastion",
            ),
        )

    def _handle_host_lan(self):
        play_transition()

        if self.embedded_server is None:
            try:
                server, thread, address_info = start_server_in_background(
                    self.network_config.bind_host,
                    self.tcp_port,
                )
                self.embedded_server = server
                self.embedded_server_thread = thread
                self.embedded_server_address_info = address_info

                invitation_text = (
                    format_endpoint(address_info.primary_ip, self.tcp_port)
                    if address_info.primary_ip
                    else (
                        "IP LAN indisponible · test local: "
                        f"127.0.0.1:{self.tcp_port}"
                    )
                )

                self._set_server_status(
                    "Hall ouvert - invitation prete",
                    "info",
                )
                self._set_info(
                    self._relay_opened_journal_text(
                        invitation_text,
                        address_info.warning,
                    ),
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
            self.embedded_server_address_info = get_lan_address_info()
            invitation_text = (
                format_endpoint(
                    self.embedded_server_address_info.primary_ip,
                    self.tcp_port,
                )
                if self.embedded_server_address_info.primary_ip
                else (
                    "IP LAN indisponible · test local: "
                    f"127.0.0.1:{self.tcp_port}"
                )
            )
            self._set_server_status(
                "Hall deja ouvert - invitation prete",
                "info",
            )
            self._set_info(
                self._relay_opened_journal_text(
                    invitation_text,
                    self.embedded_server_address_info.warning,
                ),
                badge_text="Invitation prete",
                tone="info",
            )

        self._set_db_mode_local()
        self._focus_or_open_window(
            "host_lobby_window",
            lambda: NetworkLobbyView(
                self,
                default_server_invitation=(
                    format_endpoint(
                        self.embedded_server_address_info.primary_ip,
                        self.tcp_port,
                    )
                    if self.embedded_server_address_info
                    and self.embedded_server_address_info.primary_ip
                    else f"127.0.0.1:{self.tcp_port}"
                ),
                server_port=self.tcp_port,
                host_mode=True,
            ),
        )

    def _handle_join_lan(self):
        play_transition()
        self._set_db_mode_local()
        self._set_info(
            self._relay_join_journal_text(),
            badge_text="Hall en approche",
            tone="info",
        )
        self._focus_or_open_window(
            "join_lobby_window",
            lambda: NetworkLobbyView(self, server_port=self.tcp_port),
        )

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
