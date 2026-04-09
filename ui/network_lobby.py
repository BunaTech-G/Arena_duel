import json
import threading
import time
from tkinter import TclError

import customtkinter as ctk

from game.audio import (
    init_audio,
    play_alert,
    play_click,
    play_error,
    play_select,
    play_transition,
    start_menu_music,
    stop_music,
)
from game.match_text import (
    format_compact_scoreline,
    format_team_assignment,
)
from game.net_match_window import run_network_match
from game.settings import (
    MATCH_DURATION_OPTIONS,
    MATCH_DURATION_SECONDS,
    format_match_duration_label,
)
from network.client import NetworkClient
from network.messages import (
    ASSIGN_SLOT,
    DISCONNECTED,
    ERROR,
    HISTORY_DATA,
    LOBBY_STATE,
    START,
)
from network.net_utils import (
    format_endpoint,
    get_lan_address_info,
    is_loopback_host,
    load_lan_runtime_config,
    parse_server_invitation,
)
from runtime_utils import resource_path
from ui.history_view import HistoryView
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    create_badge,
    create_button,
    create_option_menu,
    enable_large_window,
    style_frame,
    style_window,
    update_badge,
)


class NetworkLobbyView(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        default_server_invitation=None,
        server_port=None,
        host_mode=False,
    ):
        super().__init__(parent)
        style_window(self)

        self.network_config = load_lan_runtime_config()
        self.duration_values = [
            str(duration) for duration in MATCH_DURATION_OPTIONS
        ]
        self.match_duration_var = ctk.StringVar(
            value=str(MATCH_DURATION_SECONDS)
        )

        self.title("Arena Duel - Hall des bastions")
        _ico = resource_path("assets", "icons", "app.ico")
        self.after(200, lambda: self._apply_icon(_ico))

        self.geometry("1320x860")
        enable_large_window(self, 1120, 780)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.client = None
        self.running = False
        self.history_request_pending = False
        self.server_port = int(
            server_port or self.network_config.port
        )

        self.config_file = self.network_config.client_state_path
        self.address_info = get_lan_address_info()
        self.detected_local_ip = self.address_info.primary_ip or ""
        self.default_server_invitation = default_server_invitation
        self.local_test_invitation = format_endpoint(
            "127.0.0.1",
            self.server_port,
        )
        self.host_mode = host_mode

        self.my_slot = None
        self.my_team = None
        self.my_name = None
        self.ready_state = False
        self.match_running = False

        self.mode_badge = None
        self.mode_label = None
        self.local_ip_label = None
        self.invite_value_label = None
        self.invite_caption_label = None
        self.ip_entry = None
        self.name_entry = None
        self.copy_invite_btn = None
        self.use_local_ip_btn = None
        self.connect_btn = None
        self.ready_btn = None
        self.history_btn = None
        self.duration_menu = None
        self.duration_status_label = None
        self.roster_badge = None
        self.roster_total_value = None
        self.roster_ready_value = None
        self.roster_balance_value = None
        self.roster_list_frame = None
        self.info_label = None

        self._build_ui()
        self._refresh_mode_label()

        start_menu_music()

        self.info_label.configure(text=self._build_initial_info_text())

    def _apply_icon(self, path: str):
        try:
            self.iconbitmap(path)
        except (OSError, TclError):
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_connection_panel()
        self._build_roster_panel()
        self._clear_roster_display()
        self._apply_match_duration(MATCH_DURATION_SECONDS)

    def _build_header(self):
        header = ctk.CTkFrame(self, corner_radius=20)
        style_frame(
            header,
            tone="panel",
            border_color=PALETTE["cyan_dim"],
        )
        header.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=20,
            pady=(20, 10),
            sticky="ew",
        )
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            header,
            text="Hall des bastions",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        )
        title.grid(row=0, column=0, padx=18, pady=(16, 6), sticky="w")

        self.mode_badge = create_badge(header, "Hall", tone="info")
        self.mode_badge.grid(
            row=0,
            column=0,
            padx=18,
            pady=(16, 6),
            sticky="e",
        )

        subtitle = ctk.CTkLabel(
            header,
            text=(
                "Le hall presente l'invitation, le roster, l'etat pret "
                "et la duree de la joute dans une vraie composition "
                "desktop, sans longue colonne scrolllee."
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=720,
            justify="left",
        )
        subtitle.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        self.mode_label = ctk.CTkLabel(
            header,
            text="",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            fg_color=PALETTE["panel_soft"],
            corner_radius=999,
            padx=14,
            pady=8,
        )
        self.mode_label.grid(
            row=2,
            column=0,
            padx=18,
            pady=(0, 16),
            sticky="w",
        )

    def _build_connection_panel(self):
        panel = ctk.CTkFrame(self, corner_radius=18)
        style_frame(panel, tone="panel", border_color=PALETTE["border"])
        panel.grid(
            row=1,
            column=0,
            padx=(20, 10),
            pady=(0, 20),
            sticky="nsew",
        )
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            panel,
            text="Entree du hall",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        title.grid(row=0, column=0, padx=18, pady=(16, 6), sticky="w")

        self.local_ip_label = ctk.CTkLabel(
            panel,
            text=(
                "Invitation LAN a partager avec les autres PC"
                if self.host_mode
                else (
                    "Colle l'invitation LAN du gardien "
                    "ou choisis un test local"
                )
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            wraplength=300,
            justify="right",
        )
        self.local_ip_label.grid(
            row=0,
            column=1,
            padx=18,
            pady=(16, 6),
            sticky="e",
        )

        invite_panel = ctk.CTkFrame(panel, corner_radius=16)
        style_frame(
            invite_panel,
            tone="panel_soft",
            border_color=(
                PALETTE["cyan_dim"]
                if self.host_mode
                else PALETTE["border_strong"]
            ),
        )
        invite_panel.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 10),
            sticky="ew",
        )
        invite_panel.grid_columnconfigure(0, weight=1)

        invite_title = ctk.CTkLabel(
            invite_panel,
            text=(
                "Invitation LAN a partager"
                if self.host_mode
                else "Invitation actuellement ciblee"
            ),
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        invite_title.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.invite_value_label = ctk.CTkLabel(
            invite_panel,
            text="-",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        self.invite_value_label.grid(
            row=1,
            column=0,
            padx=16,
            pady=(0, 4),
            sticky="w",
        )

        self.invite_caption_label = ctk.CTkLabel(
            invite_panel,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
        )
        self.invite_caption_label.grid(
            row=2,
            column=0,
            padx=16,
            pady=(0, 14),
            sticky="w",
        )

        self.ip_entry = ctk.CTkEntry(
            panel,
            placeholder_text="Invitation LAN ou IP:port du hall",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        self.ip_entry.grid(
            row=2,
            column=0,
            padx=(18, 8),
            pady=(0, 10),
            sticky="ew",
        )

        default_invitation = self._load_saved_server_invitation()
        if default_invitation:
            self.ip_entry.insert(0, default_invitation)
        elif self.host_mode:
            self.ip_entry.insert(
                0,
                self._get_shareable_invitation_text()
                if self.detected_local_ip
                else self.local_test_invitation,
            )
        self.ip_entry.bind("<KeyRelease>", self._handle_ip_entry_change)
        self._sync_invitation_spotlight(self.ip_entry.get().strip())

        self.name_entry = ctk.CTkEntry(
            panel,
            placeholder_text="Nom de combattant",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        self.name_entry.grid(
            row=2,
            column=1,
            padx=(8, 18),
            pady=(0, 10),
            sticky="ew",
        )

        action_row = ctk.CTkFrame(panel, fg_color="transparent")
        action_row.grid(
            row=3,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 8),
            sticky="ew",
        )
        for column in range(3):
            action_row.grid_columnconfigure(column, weight=1)

        action_column = 0
        if self.host_mode:
            self.copy_invite_btn = create_button(
                action_row,
                "Copier l'invitation",
                self._copy_bastion_address,
                variant="ghost",
                font=TYPOGRAPHY["button_small"],
                height=40,
            )
            self.copy_invite_btn.grid(
                row=0,
                column=action_column,
                padx=(0, 8),
                sticky="ew",
            )
            action_column += 1
        else:
            self.copy_invite_btn = None

        self.use_local_ip_btn = create_button(
            action_row,
            "Tester sur ce PC (local)",
            self._use_loopback_ip,
            variant="ghost",
            font=TYPOGRAPHY["button_small"],
            height=40,
        )
        self.use_local_ip_btn.grid(
            row=0,
            column=action_column,
            padx=(0, 8),
            sticky="ew",
        )
        action_column += 1

        connect_pad = (8, 0) if action_column else (0, 0)
        self.connect_btn = create_button(
            action_row,
            "Entrer dans le hall",
            self._connect,
            variant="accent",
            height=40,
        )
        self.connect_btn.grid(
            row=0,
            column=action_column,
            padx=connect_pad,
            sticky="ew",
        )

        action_row_secondary = ctk.CTkFrame(panel, fg_color="transparent")
        action_row_secondary.grid(
            row=4,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 12),
            sticky="ew",
        )
        action_row_secondary.grid_columnconfigure((0, 1), weight=1)

        self.ready_btn = create_button(
            action_row_secondary,
            "Se declarer pret",
            self._toggle_ready,
            variant="success",
            height=40,
            state="disabled",
        )
        self.ready_btn.grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="ew",
        )

        self.history_btn = create_button(
            action_row_secondary,
            "Consulter les chroniques",
            self._request_history,
            variant="secondary",
            height=40,
            state="disabled",
        )
        self.history_btn.grid(
            row=0,
            column=1,
            padx=(8, 0),
            sticky="ew",
        )

        self._build_duration_panel(panel)

    def _build_duration_panel(self, master):
        duration_panel = ctk.CTkFrame(master, corner_radius=16)
        style_frame(
            duration_panel,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        duration_panel.grid(
            row=5,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        duration_panel.grid_columnconfigure((0, 1), weight=1)

        duration_title = ctk.CTkLabel(
            duration_panel,
            text="Duree de la joute",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        duration_title.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        duration_hint = ctk.CTkLabel(
            duration_panel,
            text=(
                "Reglage du gardien"
                if self.host_mode
                else "Annonce du gardien"
            ),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
        )
        duration_hint.grid(row=0, column=1, padx=16, pady=(14, 6), sticky="e")

        self.duration_menu = create_option_menu(
            duration_panel,
            values=self.duration_values,
            variable=self.match_duration_var,
            command=self._handle_duration_change,
            width=160,
            height=42,
            state="normal" if self.host_mode else "disabled",
        )
        self.duration_menu.grid(
            row=1,
            column=0,
            padx=16,
            pady=(0, 14),
            sticky="w",
        )

        duration_text = format_match_duration_label(MATCH_DURATION_SECONDS)
        self.duration_status_label = ctk.CTkLabel(
            duration_panel,
            text=f"Duree courante : {duration_text}",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        self.duration_status_label.grid(
            row=1,
            column=1,
            padx=16,
            pady=(0, 14),
            sticky="e",
        )

    def _build_roster_panel(self):
        lobby_panel = ctk.CTkFrame(self, corner_radius=18)
        style_frame(lobby_panel, tone="panel", border_color=PALETTE["border"])
        lobby_panel.grid(
            row=1,
            column=1,
            padx=(10, 20),
            pady=(0, 20),
            sticky="nsew",
        )
        lobby_panel.grid_columnconfigure(0, weight=1)
        lobby_panel.grid_rowconfigure(2, weight=1)

        lobby_title = ctk.CTkLabel(
            lobby_panel,
            text="Compagnons du hall",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        lobby_title.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self.roster_badge = create_badge(
            lobby_panel,
            "Hall vide",
            tone="neutral",
        )
        self.roster_badge.grid(
            row=0,
            column=0,
            padx=18,
            pady=(16, 8),
            sticky="e",
        )

        summary_frame = ctk.CTkFrame(lobby_panel, corner_radius=16)
        style_frame(
            summary_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        summary_frame.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
        summary_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.roster_total_value = self._build_roster_stat_card(
            summary_frame,
            0,
            "Combattants",
            "0",
        )
        self.roster_ready_value = self._build_roster_stat_card(
            summary_frame,
            1,
            "Prets",
            "0",
        )
        self.roster_balance_value = self._build_roster_stat_card(
            summary_frame,
            2,
            "Bastions",
            "-",
        )

        self.roster_list_frame = ctk.CTkScrollableFrame(
            lobby_panel,
            corner_radius=14,
            fg_color=PALETTE["panel_soft"],
            border_width=1,
            border_color=PALETTE["border"],
        )
        self.roster_list_frame.grid(
            row=2,
            column=0,
            padx=18,
            pady=(0, 16),
            sticky="nsew",
        )
        self.roster_list_frame.grid_columnconfigure(0, weight=1)

        info_panel = ctk.CTkFrame(lobby_panel, corner_radius=18)
        style_frame(
            info_panel,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        info_panel.grid(
            row=3,
            column=0,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        info_panel.grid_columnconfigure(0, weight=1)

        info_title = ctk.CTkLabel(
            info_panel,
            text="Echos du hall",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        info_title.grid(row=0, column=0, padx=18, pady=(14, 4), sticky="w")

        self.info_label = ctk.CTkLabel(
            info_panel,
            text="",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=420,
            justify="left",
        )
        self.info_label.grid(
            row=1,
            column=0,
            padx=18,
            pady=(0, 16),
            sticky="w",
        )

    def _build_roster_stat_card(
        self,
        master,
        column,
        label_text: str,
        value_text: str,
    ):
        card = ctk.CTkFrame(master, corner_radius=14)
        style_frame(card, tone="panel", border_color=PALETTE["border"])
        card.grid(row=0, column=column, padx=8, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            card,
            text=label_text,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        label.grid(row=0, column=0, padx=14, pady=(12, 2), sticky="w")

        value = ctk.CTkLabel(
            card,
            text=value_text,
            font=TYPOGRAPHY["stat"],
            text_color=PALETTE["text"],
        )
        value.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")
        return value

    def _refresh_mode_label(self):
        if self.host_mode:
            if self.client and self.client.running:
                text = (
                    "Hall tenu par le gardien · joute prete · chroniques "
                    "gardees ici"
                )
                update_badge(self.mode_badge, "Gardien", "gold")
            else:
                if self.detected_local_ip:
                    text = "Bastion pret · invitation LAN disponible"
                    update_badge(self.mode_badge, "Gardien", "warning")
                else:
                    text = "Bastion pret · test local uniquement"
                    update_badge(self.mode_badge, "Gardien", "danger")
        else:
            if self.client and self.client.running:
                text = "Hall rejoint · serment scelle · chroniques du bastion"
                update_badge(self.mode_badge, "Compagnon", "info")
            else:
                text = "Hall en attente d'une invitation"
                update_badge(self.mode_badge, "Compagnon", "neutral")

        self.mode_label.configure(text=text)

    def _reset_lobby_state(self):
        self.my_slot = None
        self.my_team = None
        self.my_name = None
        self.ready_state = False
        self.match_running = False
        self.history_request_pending = False

        self.ready_btn.configure(text="Se déclarer prêt", state="disabled")
        self.history_btn.configure(state="disabled")
        self.connect_btn.configure(state="normal")
        self.ip_entry.configure(state="normal")
        self.name_entry.configure(state="normal")
        self.use_local_ip_btn.configure(state="normal")
        self._clear_roster_display()
        self._refresh_mode_label()

    def _handle_disconnect(self, message: str):
        play_alert()

        self.running = False
        self.history_request_pending = False

        if self.client:
            self.client.close()

        self.client = None
        self.deiconify()
        self.lift()
        self.focus_force()
        self._reset_lobby_state()
        self.info_label.configure(text=message)

    def _build_initial_info_text(self) -> str:
        if self.host_mode:
            if self.detected_local_ip:
                return (
                    "Le bastion est pret. Partage l'invitation LAN, "
                    "choisis la duree puis inscris ton nom de combattant.\n\n"
                    "Invitation LAN actuelle : "
                    f"{self._get_shareable_invitation_text()}"
                )

            return (
                "Le bastion est pret, mais aucune IP LAN exploitable "
                "n'a ete detectee. Tu peux encore tester le hall "
                "en local sur ce PC, mais pas inviter un autre "
                "ordinateur tant que le reseau local n'est pas disponible."
            )

        return (
            "Saisis l'invitation LAN du gardien et ton nom de combattant "
            "pour rejoindre la joute partagee. "
            "Le mode local sur ce PC reste separe."
        )

    def _get_shareable_invitation_text(self) -> str:
        if not self.detected_local_ip:
            return "IP LAN indisponible"
        return format_endpoint(self.detected_local_ip, self.server_port)

    def _load_saved_server_invitation(self) -> str:
        if self.default_server_invitation:
            return self.default_server_invitation

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            last_mode = str(
                data.get("last_connection_mode") or ""
            ).strip().lower()
            if not self.host_mode and last_mode == "local":
                return ""

            invitation = str(
                data.get("last_server_invitation") or ""
            ).strip()
            if invitation:
                return invitation

            legacy_ip = str(data.get("last_server_ip") or "").strip()
            if legacy_ip:
                return format_endpoint(legacy_ip, self.server_port)

            return ""

        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return ""

    def _save_server_invitation(self, invitation: str, mode: str):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_server_invitation": invitation,
                        "last_connection_mode": mode,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def _use_loopback_ip(self):
        play_click()

        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, self.local_test_invitation)
        self._sync_invitation_spotlight(self.local_test_invitation)

    def _copy_bastion_address(self):
        play_click()

        shareable_invitation = self._get_shareable_invitation_text()
        if shareable_invitation == "IP LAN indisponible":
            self.info_label.configure(
                text=(
                    "Aucune IP LAN exploitable n'a ete detectee. "
                    "Verifie le reseau "
                    "local avant d'inviter un autre PC."
                )
            )
            return

        try:
            self.clipboard_clear()
            self.clipboard_append(shareable_invitation)
            self.info_label.configure(
                text="Invitation LAN copiee dans le presse-papiers."
            )
        except (RuntimeError, TclError):
            self.info_label.configure(
                text=(
                    "Partage cette invitation LAN : "
                    f"{shareable_invitation}"
                )
            )

    # =========================
    # Connexion réseau
    # =========================
    def _connect(self):
        play_transition()

        invitation = self.ip_entry.get().strip()
        name = self.name_entry.get().strip()

        if not invitation or not name:
            play_error()
            self.info_label.configure(
                text=(
                    "Renseigne l'invitation du bastion et un nom de "
                    "combattant avant d'ouvrir le hall."
                )
            )
            return

        try:
            host, port = parse_server_invitation(
                invitation,
                self.server_port,
            )
        except ValueError as error:
            play_error()
            self.info_label.configure(text=str(error))
            return

        self.client = NetworkClient()

        try:
            self.client.connect(
                host,
                port,
                name,
                is_host=self.host_mode,
                timeout_seconds=self.network_config.connect_timeout_seconds,
            )
        except (ConnectionError, OSError) as error:
            play_alert()
            self.info_label.configure(
                text=(
                    "Impossible de rejoindre le hall du bastion : "
                    f"{error}"
                )
            )
            return

        normalized_invitation = format_endpoint(host, port)
        self.server_port = port
        self.local_test_invitation = format_endpoint("127.0.0.1", port)
        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, normalized_invitation)

        self.info_label.configure(
            text=(
                f"Lien scelle pour {name}. Le hall prepare ton entree "
                "dans la joute."
            )
        )
        self.connect_btn.configure(state="disabled")
        self.ready_btn.configure(state="normal")
        self.history_btn.configure(state="normal")
        self.ip_entry.configure(state="disabled")
        self.name_entry.configure(state="disabled")
        self.use_local_ip_btn.configure(state="disabled")

        self.my_name = name
        self._save_server_invitation(
            normalized_invitation,
            "local" if is_loopback_host(host) else "lan",
        )

        self._start_network_thread()
        if self.host_mode:
            self.client.send_match_duration(
                self._get_selected_match_duration()
            )
        self._refresh_mode_label()

        if self.host_mode:
            if is_loopback_host(host):
                self.info_label.configure(
                    text=(
                        f"{name} veille sur le bastion en mode local "
                        "sur ce PC. Invitation LAN a partager : "
                        f"{self._get_shareable_invitation_text()}."
                    )
                )
            else:
                self.info_label.configure(
                    text=(
                        f"{name} veille sur le bastion. "
                        "Invitation LAN active : "
                        f"{normalized_invitation}."
                    )
                )
        else:
            if is_loopback_host(host):
                self.info_label.configure(
                    text=(
                        f"{name} a rejoint un hall local sur ce PC. "
                        "N'utilise pas cette adresse depuis "
                        "un autre ordinateur."
                    )
                )
            else:
                self.info_label.configure(
                    text=(
                        f"{name} a rejoint le hall {normalized_invitation}. "
                        "Les chroniques seront lues depuis ce bastion."
                    )
                )

    # =========================
    # Réception réseau
    # =========================
    def _network_loop(self):
        while self.running:
            if not self.client:
                break

            for msg in self.client.poll_messages():
                try:
                    self.after(0, lambda m=msg: self._handle_message(m))
                except (RuntimeError, TclError):
                    self.running = False
                    break

            time.sleep(0.02)  # 20 ms -> boucle plus légère

    def _handle_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == ASSIGN_SLOT:
            slot = msg["slot"]
            team = msg["team"]

            self.my_slot = slot
            self.my_team = team

            self.info_label.configure(text=format_team_assignment(slot, team))

        elif msg_type == LOBBY_STATE:
            self._update_lobby(
                msg["players"],
                msg.get("match_duration_seconds", MATCH_DURATION_SECONDS),
            )

        elif msg_type == START:
            if self.match_running:
                return
            self.info_label.configure(
                text="Tous les combattants sont prêts. La joute s'ouvre..."
            )
            self.ready_btn.configure(state="disabled")
            self.history_btn.configure(state="disabled")
            self.after(50, self._launch_match)

        elif msg_type == HISTORY_DATA:
            self.history_request_pending = False
            if self.client and self.client.running:
                self.history_btn.configure(state="normal")

            if not msg.get("ok", False):
                play_error()
                self.info_label.configure(
                    text=msg.get(
                        "message",
                        (
                            "Les chroniques du hall sont indisponibles "
                            "pour le moment."
                        ),
                    )
                )
                return

            source_label = "Chroniques du hall local" if self.host_mode else (
                "Chroniques du hall rejoint"
            )
            self.info_label.configure(
                text=(
                    f"{len(msg.get('rows', []))} chronique(s) recue(s) "
                    "depuis le hall."
                )
            )
            HistoryView(
                self,
                history_rows=msg.get("rows", []),
                source_label=source_label,
                allow_refresh=False,
            )

        elif msg_type == ERROR:
            play_error()
            self.info_label.configure(
                text=msg.get("message", "Le hall a signale une erreur.")
            )

        elif msg_type == DISCONNECTED:
            self._handle_disconnect(msg.get("message", "Connexion fermée."))

    def _start_network_thread(self):
        self.running = True
        threading.Thread(target=self._network_loop, daemon=True).start()

    # =========================
    # Lobby UI
    # =========================
    def _handle_ip_entry_change(self, _event=None):
        self._sync_invitation_spotlight(self.ip_entry.get().strip())

    def _sync_invitation_spotlight(self, ip_value: str):
        if self.host_mode:
            active_value = self._get_shareable_invitation_text()
            if self.detected_local_ip:
                caption = (
                    "Invitation LAN reelle a transmettre aux autres PC "
                    "du reseau local."
                )
            else:
                caption = (
                    "Aucune IP LAN exploitable detectee. "
                    "Le test local sur ce PC reste possible."
                )
        else:
            active_value = ip_value.strip() or "En attente"
            caption = (
                "Invitation LAN actuellement preparee "
                "pour rejoindre le hall."
            )
            try:
                host, port = parse_server_invitation(
                    active_value,
                    self.server_port,
                )
                active_value = format_endpoint(host, port)
                if is_loopback_host(host):
                    caption = (
                        "Mode local sur ce PC. Ne pas utiliser "
                        "cette adresse depuis un autre ordinateur."
                    )
            except ValueError:
                pass

        self.invite_value_label.configure(text=active_value)
        self.invite_caption_label.configure(text=caption)

    def _clear_roster_display(self):
        self.roster_total_value.configure(text="0")
        self.roster_ready_value.configure(text="0")
        self.roster_balance_value.configure(text="-")
        update_badge(self.roster_badge, "Hall vide", "neutral")
        self._render_roster_cards([])

    def _render_roster_cards(self, players):
        for widget in self.roster_list_frame.winfo_children():
            widget.destroy()

        if not players:
            empty_state = ctk.CTkLabel(
                self.roster_list_frame,
                text=(
                    "Aucun combattant n'a encore rejoint le hall.\n\n"
                    "L'invitation, le serment pret et la duree choisie "
                    "apparaitront ici."
                ),
                font=TYPOGRAPHY["body"],
                text_color=PALETTE["text_soft"],
                justify="left",
                anchor="w",
            )
            empty_state.grid(row=0, column=0, padx=16, pady=18, sticky="ew")
            return

        for index, player in enumerate(players):
            team_tone = "gold" if player["team"] == "A" else "info"
            border_color = (
                PALETTE["gold_dim"]
                if player["team"] == "A"
                else PALETTE["cyan_dim"]
            )

            player_card = ctk.CTkFrame(
                self.roster_list_frame,
                corner_radius=14,
            )
            style_frame(player_card, tone="panel", border_color=border_color)
            player_card.grid(
                row=index,
                column=0,
                padx=12,
                pady=(12 if index == 0 else 0, 10),
                sticky="ew",
            )
            player_card.grid_columnconfigure(1, weight=1)

            slot_badge = create_badge(
                player_card,
                f"Poste {player['slot']}",
                tone=team_tone,
            )
            slot_badge.grid(
                row=0,
                column=0,
                padx=(14, 10),
                pady=(12, 4),
                sticky="w",
            )

            name_label = ctk.CTkLabel(
                player_card,
                text=player["name"],
                font=TYPOGRAPHY["body_bold"],
                text_color=PALETTE["text"],
            )
            name_label.grid(
                row=0,
                column=1,
                padx=(0, 12),
                pady=(12, 4),
                sticky="w",
            )

            team_badge = create_badge(
                player_card,
                f"Bastion {player['team']}",
                tone=team_tone,
            )
            team_badge.grid(
                row=0,
                column=2,
                padx=(8, 8),
                pady=(12, 4),
                sticky="e",
            )

            ready_badge = create_badge(
                player_card,
                "Pret" if player["ready"] else "En veille",
                tone="success" if player["ready"] else "warning",
            )
            ready_badge.grid(
                row=0,
                column=3,
                padx=(0, 14),
                pady=(12, 4),
                sticky="e",
            )

            detail_text = (
                "Ton poste dans la joute."
                if player["slot"] == self.my_slot
                else "Compagnon du hall en attente du depart."
            )
            detail_label = ctk.CTkLabel(
                player_card,
                text=detail_text,
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_soft"],
                justify="left",
            )
            detail_label.grid(
                row=1,
                column=1,
                columnspan=3,
                padx=(0, 14),
                pady=(0, 12),
                sticky="w",
            )

    def _update_lobby(self, players, match_duration_seconds=None):
        if match_duration_seconds is not None:
            self._apply_match_duration(match_duration_seconds)

        total_players = len(players)
        ready_players = sum(1 for player in players if player.get("ready"))
        team_a_count = sum(
            1 for player in players if player.get("team") == "A"
        )
        team_b_count = sum(
            1 for player in players if player.get("team") == "B"
        )

        self.roster_total_value.configure(text=str(total_players))
        self.roster_ready_value.configure(
            text=f"{ready_players}/{total_players}" if total_players else "0"
        )
        self.roster_balance_value.configure(
            text=f"{team_a_count}/{team_b_count}" if total_players else "-"
        )

        badge_tone = "neutral"
        if total_players:
            badge_tone = (
                "success"
                if total_players >= 2 and ready_players == total_players
                else "warning"
            )
        update_badge(
            self.roster_badge,
            f"{total_players} combattant{'s' if total_players != 1 else ''}",
            badge_tone,
        )
        self._render_roster_cards(players)

    def _handle_duration_change(self, _choice=None):
        duration_seconds = self._get_selected_match_duration()
        self._apply_match_duration(duration_seconds)

        if self.host_mode and self.client and self.client.running:
            if not self.client.send_match_duration(duration_seconds):
                play_error()
                self.info_label.configure(
                    text="Impossible de transmettre la nouvelle durée au hall."
                )

    def _apply_match_duration(self, duration_seconds: int):
        value = str(int(duration_seconds))
        self.match_duration_var.set(value)
        self.duration_menu.set(value)
        duration_text = format_match_duration_label(int(duration_seconds))
        self.duration_status_label.configure(
            text=f"Durée courante : {duration_text}"
        )

    def _get_selected_match_duration(self) -> int:
        try:
            return int(self.match_duration_var.get().strip())
        except ValueError:
            return MATCH_DURATION_SECONDS

    # =========================
    # Ready
    # =========================
    def _toggle_ready(self):
        play_select()

        self.ready_state = not self.ready_state
        self.client.send_ready(self.ready_state)

        if self.ready_state:
            self.ready_btn.configure(text="Retirer l'état prêt")
        else:
            self.ready_btn.configure(text="Se déclarer prêt")

    def _request_history(self):
        play_transition()

        if not self.client or not self.client.running:
            play_error()
            self.info_label.configure(
                text="Rejoins d'abord le hall pour consulter les chroniques."
            )
            return

        if self.history_request_pending:
            return

        self.history_request_pending = True
        self.history_btn.configure(state="disabled")
        self.info_label.configure(text="Lecture des chroniques du hall...")

        if not self.client.send_request_history():
            self.history_request_pending = False
            if self.client and self.client.running:
                self.history_btn.configure(state="normal")
            play_error()
            self.info_label.configure(
                text="Impossible d'appeler les chroniques du hall."
            )

    def _format_post_match_status(self, end_message: dict) -> str:
        team_a_score = end_message.get("team_a_score", 0)
        team_b_score = end_message.get("team_b_score", 0)
        base_text = (
            f"Joute close · "
            f"{format_compact_scoreline(team_a_score, team_b_score)}"
        )

        if end_message.get("history_saved", False):
            match_id = end_message.get("match_id")
            if match_id is not None:
                return (
                    f"{base_text} · chronique du hall archivee "
                    f"(joute #{match_id})"
                )
            return f"{base_text} · chronique du hall archivee"

        history_error = end_message.get("history_error", "Erreur inconnue")
        return f"{base_text} · archivage du hall echoue : {history_error}"

    def _launch_match(self):
        if not self.client or self.my_slot is None or not self.my_name:
            return

        # on stoppe la boucle lobby pendant le match
        self.running = False
        self.match_running = True
        stop_music(fade_ms=180)

        # on cache le lobby
        self.withdraw()
        self.update()

        # on lance le match réseau
        match_summary = run_network_match(
            self.client,
            self.my_slot,
            self.my_name,
            self.my_team,
        )

        init_audio()
        start_menu_music()

        # retour au lobby après le match
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.match_running = False

        for msg in match_summary.get("deferred_messages", []):
            self._handle_message(msg)

        if not match_summary.get("completed"):
            self._handle_disconnect(
                match_summary.get(
                    "disconnect_message",
                    "Connexion interrompue pendant le match.",
                )
            )
            return

        # reset visuel du ready
        self.ready_state = False
        self.ready_btn.configure(text="Se déclarer prêt", state="normal")
        self.history_btn.configure(state="normal")

        status_text = self._format_post_match_status(
            match_summary.get("end_message", {})
        )
        self.info_label.configure(
            status_text
        )

        # relance la boucle réseau lobby
        if self.client and self.client.running:
            self._start_network_thread()
        else:
            self._handle_disconnect("Connexion interrompue à la fin du match.")

    def shutdown(self):
        self.running = False
        if self.client:
            self.client.close()
        self.destroy()
