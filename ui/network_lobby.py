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
    get_network_logger,
    get_lan_address_info,
    is_loopback_host,
    load_lan_runtime_config,
    parse_server_invitation,
)
from ui.history_view import HistoryView
from ui.player_select import (
    FIGHTER_DISPLAY_BY_SPRITE_ID,
    FIGHTER_SPRITE_ID_BY_DISPLAY,
    get_default_fighter_id,
)
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    apply_window_icon,
    create_badge,
    create_button,
    create_option_menu,
    enable_large_window,
    present_window,
    set_textbox_content,
    style_entry,
    style_frame,
    style_scrollable_frame,
    style_textbox,
    style_window,
    update_badge,
)


LOGGER = get_network_logger()
LAN_MATCH_LAUNCH_ERRORS = (
    AttributeError,
    RuntimeError,
    OSError,
    TypeError,
    ValueError,
)


class HallGuideWindow(ctk.CTkToplevel):
    def __init__(self, parent: "NetworkLobbyView"):
        super().__init__(parent)
        self.parent_view = parent
        style_window(self)

        self.title("Arena Duel - Guide du hall LAN")
        apply_window_icon(self, retry_after_ms=220)

        self.geometry("760x560")
        enable_large_window(self, 680, 480, start_zoomed=False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=20)
        style_frame(
            header,
            tone="panel_deep",
            border_color=PALETTE["cyan_dim"],
        )
        header.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        create_badge(header, "Guide LAN", tone="info").grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 10),
            sticky="w",
        )
        ctk.CTkLabel(
            header,
            text="Ouvrir ou rejoindre un hall sans bruit inutile",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, padx=16, sticky="w")

        self.context_label = ctk.CTkLabel(
            header,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=680,
        )
        self.context_label.grid(
            row=2,
            column=0,
            padx=16,
            pady=(8, 16),
            sticky="w",
        )

        content = ctk.CTkScrollableFrame(
            self,
            corner_radius=18,
            fg_color=PALETTE["panel_soft"],
            border_width=0,
            border_color=PALETTE["divider"],
        )
        style_scrollable_frame(
            content,
            tone="panel_soft",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        content.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="nsew")
        content.grid_columnconfigure(0, weight=1)

        host_card = ctk.CTkFrame(content, corner_radius=16)
        style_frame(
            host_card,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        host_card.grid(row=0, column=0, padx=12, pady=(12, 10), sticky="ew")
        host_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            host_card,
            text="Ouvrir un hall",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        self.host_rules_box = ctk.CTkTextbox(host_card, height=150)
        self.host_rules_box.grid(
            row=1,
            column=0,
            padx=14,
            pady=(0, 14),
            sticky="ew",
        )
        style_textbox(self.host_rules_box)

        guest_card = ctk.CTkFrame(content, corner_radius=16)
        style_frame(
            guest_card,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        guest_card.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        guest_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            guest_card,
            text="Rejoindre un hall",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        self.guest_rules_box = ctk.CTkTextbox(guest_card, height=150)
        self.guest_rules_box.grid(
            row=1,
            column=0,
            padx=14,
            pady=(0, 14),
            sticky="ew",
        )
        style_textbox(self.guest_rules_box)

        footer = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color=PALETTE["panel_deep"],
            border_width=0,
            border_color=PALETTE["divider"],
        )
        footer.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="ew")

        create_button(
            footer,
            "Fermer",
            self.destroy,
            variant="ghost",
            height=40,
            width=120,
        ).grid(row=0, column=0, padx=16, pady=12, sticky="e")

        self.refresh_content()
        present_window(self)

    def refresh_content(self):
        mode_label = "Hôte" if self.parent_view.host_mode else "Client"
        duration_label = format_match_duration_label(
            self.parent_view.get_selected_match_duration()
        )
        invitation_text = self.parent_view.ip_entry.get().strip()
        if self.parent_view.host_mode or not invitation_text:
            invitation_text = self.parent_view.get_shareable_invitation_text()
        self.context_label.configure(
            text=(
                f"Mode actuel : {mode_label} · Durée : {duration_label} · "
                f"Invitation : {invitation_text}."
            )
        )
        set_textbox_content(
            self.host_rules_box,
            self.parent_view.build_host_guide_text(),
        )
        set_textbox_content(
            self.guest_rules_box,
            self.parent_view.build_guest_guide_text(),
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
        self.duration_values = [str(duration) for duration in MATCH_DURATION_OPTIONS]
        self.match_duration_var = ctk.StringVar(value=str(MATCH_DURATION_SECONDS))
        self.fighter_values = list(FIGHTER_SPRITE_ID_BY_DISPLAY.keys())
        self._fighter_explicitly_selected = False
        default_fighter_id = get_default_fighter_id("A")
        self.fighter_var = ctk.StringVar(
            value=FIGHTER_DISPLAY_BY_SPRITE_ID[default_fighter_id]
        )

        self.title("Arena Duel - Hall LAN")
        apply_window_icon(self, retry_after_ms=220)

        self.geometry("1320x860")
        enable_large_window(self, 1120, 780)

        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.client = None
        self.running = False
        self._connect_in_progress = False
        self._ready_request_pending = False
        self.history_request_pending = False
        self.server_port = int(server_port or self.network_config.port)

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
        self.my_sprite_id = default_fighter_id
        self.ready_state = False
        self.match_running = False
        self.history_window = None
        self.guide_window = None

        self.mode_badge = None
        self.mode_label = None
        self.flow_label = None
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
        self.fighter_menu = None
        self.duration_status_label = None
        self.roster_badge = None
        self.roster_total_value = None
        self.roster_ready_value = None
        self.roster_balance_value = None
        self.roster_list_frame = None
        self.info_label = None

        self._build_ui()
        present_window(self)
        self._refresh_mode_label()

        start_menu_music()

        self.info_label.configure(text=self._build_initial_info_text())

    def _resolve_parent_lobby_attr_name(self) -> str | None:
        parent = self.master
        for attr_name in ("host_lobby_window", "join_lobby_window"):
            if getattr(parent, attr_name, None) is self:
                return attr_name
        return None

    def hydrate_resumed_session(
        self,
        invitation: str,
        *,
        client,
        my_slot,
        my_team,
        my_name,
        my_sprite_id=None,
    ) -> None:
        self.client = client
        self.my_slot = my_slot
        self.my_team = my_team
        self.my_name = my_name
        self.my_sprite_id = str(my_sprite_id or self.my_sprite_id or "").strip() or (
            get_default_fighter_id(my_team) if my_team else get_default_fighter_id("A")
        )
        self.ready_state = False
        self.match_running = False

        if my_name:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, my_name)

        self._set_selected_fighter(
            self.my_sprite_id,
            mark_manual=self._fighter_explicitly_selected,
        )

        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, invitation)
        self._sync_invitation_spotlight(invitation)
        self._refresh_mode_label()
        self._sync_controls_state()

    def resume_after_match(self, match_summary: dict) -> None:
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

        self.ready_state = False
        self.match_running = False
        self._sync_controls_state()

        status_text = self._format_post_match_status(
            match_summary.get("end_message", {})
        )
        self.info_label.configure(text=status_text)

        if self.client and self.client.running:
            self._start_network_thread()
        else:
            self._handle_disconnect("Connexion interrompue à la fin du match.")

    def _build_resumed_lobby(self, invitation: str):
        parent = self.master
        resumed_lobby = NetworkLobbyView(
            parent,
            default_server_invitation=invitation,
            server_port=self.server_port,
            host_mode=self.host_mode,
        )
        resumed_lobby.hydrate_resumed_session(
            invitation,
            client=self.client,
            my_slot=self.my_slot,
            my_team=self.my_team,
            my_name=self.my_name,
            my_sprite_id=self.my_sprite_id,
        )
        return resumed_lobby

    def _get_live_window(self, window):
        if window is None:
            return None

        try:
            return window if window.winfo_exists() else None
        except TclError:
            return None

    def _show_history_window(self, history_rows, source_label: str):
        existing_window = self._get_live_window(self.history_window)
        if existing_window is not None:
            existing_window.destroy()

        self.history_window = HistoryView(
            self,
            history_rows=history_rows,
            source_label=source_label,
            allow_refresh=False,
        )
        present_window(self.history_window)

    def _sync_controls_state(self):
        connected = bool(self.client and self.client.running)
        connect_locked = connected or self._connect_in_progress or self.match_running
        idle_connect_text = (
            "Ouvrir et rejoindre le hall" if self.host_mode else "Rejoindre le hall"
        )
        connected_connect_text = (
            "Gardien dans le hall" if self.host_mode else "Dans le hall"
        )

        self.connect_btn.configure(
            text=(
                "Connexion..."
                if self._connect_in_progress
                else (connected_connect_text if connected else idle_connect_text)
            ),
            state="disabled" if connect_locked else "normal",
        )
        self.ip_entry.configure(state="disabled" if connect_locked else "normal")
        self.name_entry.configure(state="disabled" if connect_locked else "normal")
        if self.fighter_menu is not None:
            self.fighter_menu.configure(
                state="disabled" if connect_locked else "normal"
            )
        self.use_local_ip_btn.configure(
            state="disabled" if connect_locked else "normal"
        )
        if self.copy_invite_btn is not None:
            self.copy_invite_btn.configure(
                state=(
                    "disabled"
                    if self._connect_in_progress or self.match_running
                    else "normal"
                )
            )

        self.ready_btn.configure(
            text=(
                "Transmission..."
                if self._ready_request_pending
                else ("Retirer mon prêt" if self.ready_state else "Me déclarer prêt")
            ),
            state=(
                "normal"
                if (
                    connected
                    and not self._connect_in_progress
                    and not self._ready_request_pending
                    and not self.match_running
                )
                else "disabled"
            ),
        )
        self.history_btn.configure(
            text=(
                "Lecture en cours..."
                if self.history_request_pending
                else "Voir les chroniques"
            ),
            state=(
                "normal"
                if (
                    connected
                    and not self._connect_in_progress
                    and not self.history_request_pending
                    and not self.match_running
                )
                else "disabled"
            ),
        )
        self.duration_menu.configure(
            state=(
                "normal"
                if self.host_mode
                and not self._connect_in_progress
                and not self.match_running
                else "disabled"
            )
        )

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_connection_panel()
        self._build_roster_panel()
        self._clear_roster_display()
        self._apply_match_duration(MATCH_DURATION_SECONDS)
        self._sync_controls_state()

    def _build_header(self):
        header = ctk.CTkFrame(self, corner_radius=20)
        style_frame(
            header,
            tone="panel",
            border_color=(
                PALETTE["gold_dim"] if self.host_mode else PALETTE["cyan_dim"]
            ),
            border_width=0,
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
            text="Hall LAN",
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
                "Invitation, roster et départ sans texte de procédure en plein écran."
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
        style_frame(
            panel,
            tone="panel",
            border_color=(PALETTE["gold_dim"] if self.host_mode else PALETTE["border"]),
            border_width=0,
        )
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
            text=("Poste hôte" if self.host_mode else "Poste client"),
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        title.grid(row=0, column=0, padx=18, pady=(16, 6), sticky="w")

        self.local_ip_label = ctk.CTkLabel(
            panel,
            text=(
                "Invitation à partager" if self.host_mode else "Invitation à rejoindre"
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
                PALETTE["cyan_dim"] if self.host_mode else PALETTE["border_strong"]
            ),
            border_width=0,
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
            text=("Invitation LAN" if self.host_mode else "Invitation ciblée"),
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
        style_entry(self.ip_entry, tone="panel_soft")
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
        self.ip_entry.bind("<Return>", lambda _event: self._connect())
        self._sync_invitation_spotlight(self.ip_entry.get().strip())

        self.name_entry = ctk.CTkEntry(
            panel,
            placeholder_text="Nom du combattant qui rejoint le hall",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        style_entry(self.name_entry, tone="panel_soft")
        self.name_entry.grid(
            row=2,
            column=1,
            padx=(8, 18),
            pady=(0, 10),
            sticky="ew",
        )
        self.name_entry.bind("<Return>", lambda _event: self._connect())

        fighter_panel = ctk.CTkFrame(panel, corner_radius=16)
        style_frame(
            fighter_panel,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
        )
        fighter_panel.grid(
            row=3,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 10),
            sticky="ew",
        )
        fighter_panel.grid_columnconfigure(1, weight=1)

        fighter_title = ctk.CTkLabel(
            fighter_panel,
            text="Combattant engagé",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        fighter_title.grid(row=0, column=0, padx=(16, 10), pady=14, sticky="w")

        self.fighter_menu = create_option_menu(
            fighter_panel,
            values=self.fighter_values,
            variable=self.fighter_var,
            command=self._handle_fighter_change,
            width=240,
            height=40,
            state="normal",
        )
        self.fighter_menu.grid(
            row=0,
            column=1,
            padx=(0, 16),
            pady=10,
            sticky="e",
        )

        action_row = ctk.CTkFrame(panel, fg_color="transparent")
        action_row.grid(
            row=4,
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
            "Tester sur ce PC",
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
            row=5,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 12),
            sticky="ew",
        )
        action_row_secondary.grid_columnconfigure((0, 1), weight=1)

        self.ready_btn = create_button(
            action_row_secondary,
            "Me déclarer prêt",
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
            "Voir les chroniques",
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
            border_width=0,
        )
        duration_panel.grid(
            row=6,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        duration_panel.grid_columnconfigure((0, 1), weight=1)

        duration_title = ctk.CTkLabel(
            duration_panel,
            text="Durée de la joute",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        duration_title.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        duration_hint = ctk.CTkLabel(
            duration_panel,
            text=("Réglage hôte" if self.host_mode else "Lecture seule"),
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
            text=f"Durée courante : {duration_text}",
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
        style_frame(
            lobby_panel,
            tone="panel",
            border_color=PALETTE["border"],
            border_width=0,
        )
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
            text="Participants du hall",
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
            border_width=0,
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
            "Prêts",
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
            border_width=0,
            border_color=PALETTE["border"],
        )
        style_scrollable_frame(
            self.roster_list_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
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
            border_width=0,
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
            text="État du hall",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        info_title.grid(row=0, column=0, padx=18, pady=(14, 4), sticky="w")

        create_button(
            info_panel,
            "Guide LAN",
            self._open_guide_window,
            variant="ghost",
            height=34,
            width=120,
        ).grid(row=0, column=1, padx=18, pady=(12, 4), sticky="e")

        self.info_label = ctk.CTkLabel(
            info_panel,
            text="",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=520,
            justify="left",
        )
        self.info_label.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 16),
            sticky="ew",
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
                text = "Hôte en place · invitation active"
                update_badge(self.mode_badge, "Hôte", "gold")
            else:
                if self.detected_local_ip:
                    text = "Hôte prêt · invitation disponible"
                    update_badge(self.mode_badge, "Hôte", "warning")
                else:
                    text = "Hôte prêt · test local seulement"
                    update_badge(self.mode_badge, "Hôte", "danger")
        else:
            if self.client and self.client.running:
                text = "Client dans le hall"
                update_badge(self.mode_badge, "Client", "info")
            else:
                text = "Client en attente d'une invitation"
                update_badge(self.mode_badge, "Client", "neutral")

        self.mode_label.configure(text=text)

    def _refresh_guide_window(self):
        guide_window = self._get_live_window(self.guide_window)
        if guide_window is None:
            self.guide_window = None
            return
        guide_window.refresh_content()

    def _open_guide_window(self):
        guide_window = self._get_live_window(self.guide_window)
        if guide_window is None:
            self.guide_window = HallGuideWindow(self)
            return

        present_window(guide_window)

    def _build_host_guide_text(self) -> str:
        invitation_text = self._get_shareable_invitation_text()
        return (
            "1. Entre ton nom puis ouvre le hall.\n"
            "2. Partage l'invitation affichée.\n"
            "3. Choisis la durée de la joute.\n"
            "4. Attends les autres joueurs puis déclare-toi prêt.\n"
            "5. Le départ se fait quand tout le hall est prêt.\n\n"
            f"Invitation à transmettre : {invitation_text}.\n"
            "Le bouton de test local sert seulement sur ce PC."
        )

    def _build_guest_guide_text(self) -> str:
        return (
            "1. Colle l'invitation de l'hôte.\n"
            "2. Entre ton nom et choisis ton combattant.\n"
            "3. Rejoins le hall puis déclare-toi prêt.\n"
            "4. Attends que tous les participants soient prêts.\n\n"
            "Le bouton de test local ne sert pas depuis un autre ordinateur."
        )

    def build_host_guide_text(self) -> str:
        return self._build_host_guide_text()

    def build_guest_guide_text(self) -> str:
        return self._build_guest_guide_text()

    def get_selected_match_duration(self) -> int:
        return self._get_selected_match_duration()

    def get_shareable_invitation_text(self) -> str:
        return self._get_shareable_invitation_text()

    def _reset_lobby_state(self):
        self.my_slot = None
        self.my_team = None
        self.my_name = None
        self.my_sprite_id = get_default_fighter_id("A")
        self.ready_state = False
        self._connect_in_progress = False
        self._ready_request_pending = False
        self.match_running = False
        self.history_request_pending = False
        self._fighter_explicitly_selected = False
        self._set_selected_fighter(self.my_sprite_id, mark_manual=False)

        self._clear_roster_display()
        self._sync_controls_state()
        self._refresh_mode_label()

    def _handle_disconnect(self, message: str):
        play_alert()

        self.running = False
        self._connect_in_progress = False
        self._ready_request_pending = False
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
                    "Hall prêt. Partage l'invitation, règle la durée puis "
                    "ouvre le hall.\n\n"
                    "Invitation actuelle : "
                    f"{self._get_shareable_invitation_text()}"
                )

            return (
                "Hall prêt en local, mais aucune IP LAN exploitable n'a été "
                "détectée. "
                "Invitation réseau indisponible pour le moment."
            )

        return "Colle une invitation, entre ton nom puis rejoins le hall."

    def _build_lobby_status_text(self, players) -> str:
        total_players = len(players)
        ready_players = sum(1 for player in players if player.get("ready"))

        if total_players == 0:
            if self.host_mode:
                return "Hall vide. Entre ton nom puis ouvre le hall."
            return "Hall vide sur ce poste. Entre ton nom puis rejoins."

        if total_players == 1:
            if self.host_mode:
                return "1 combattant en place. Il faut encore un autre joueur."
            return "1 combattant en place. Il en faut 2 pour partir."

        if ready_players < total_players:
            return (
                f"{ready_players}/{total_players} prêts. Départ quand tous sont prêts."
            )

        return f"Tous prêts ({total_players}/{total_players}). Départ imminent."

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

            last_mode = str(data.get("last_connection_mode") or "").strip().lower()
            if not self.host_mode and last_mode == "local":
                return ""

            invitation = str(data.get("last_server_invitation") or "").strip()
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

    def _handle_fighter_change(self, _choice=None):
        self.my_sprite_id = self._get_selected_fighter_id()
        self._fighter_explicitly_selected = True

    def _get_selected_fighter_id(self) -> str:
        return FIGHTER_SPRITE_ID_BY_DISPLAY.get(
            self.fighter_var.get().strip(),
            self.my_sprite_id or get_default_fighter_id(self.my_team or "A"),
        )

    def _set_selected_fighter(
        self,
        sprite_id: str,
        *,
        mark_manual: bool,
    ) -> None:
        normalized_sprite_id = str(sprite_id or "").strip() or get_default_fighter_id(
            self.my_team or "A"
        )
        fallback_fighter_id = get_default_fighter_id(self.my_team or "A")
        fighter_label = FIGHTER_DISPLAY_BY_SPRITE_ID.get(
            normalized_sprite_id,
            FIGHTER_DISPLAY_BY_SPRITE_ID[fallback_fighter_id],
        )
        self.my_sprite_id = normalized_sprite_id
        self.fighter_var.set(fighter_label)
        self._fighter_explicitly_selected = mark_manual

    def _copy_bastion_address(self):
        play_click()

        shareable_invitation = self._get_shareable_invitation_text()
        if shareable_invitation == "IP LAN indisponible":
            self.info_label.configure(
                text=("Aucune IP LAN exploitable détectée pour inviter un autre PC.")
            )
            return

        try:
            self.clipboard_clear()
            self.clipboard_append(shareable_invitation)
            self.info_label.configure(text="Invitation LAN copiée.")
        except (RuntimeError, TclError):
            self.info_label.configure(
                text=f"Invitation à partager : {shareable_invitation}"
            )

    # =========================
    # Connexion réseau
    # =========================
    def _connect(self):
        if self._connect_in_progress or (self.client and self.client.running):
            return

        play_transition()

        invitation = self.ip_entry.get().strip()
        name = self.name_entry.get().strip()

        if not invitation or not name:
            play_error()
            self.info_label.configure(
                text="Renseigne une invitation et un nom avant d'ouvrir le hall."
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

        self._connect_in_progress = True
        self.info_label.configure(text="Connexion au hall en cours...")
        self._sync_controls_state()
        self.update_idletasks()

        self.client = NetworkClient()

        try:
            self.client.connect(
                host,
                port,
                name,
                is_host=self.host_mode,
                timeout_seconds=self.network_config.connect_timeout_seconds,
                sprite_id=self._get_selected_fighter_id(),
            )
        except (ConnectionError, OSError) as error:
            self._connect_in_progress = False
            self.client = None
            self._sync_controls_state()
            play_alert()
            self.info_label.configure(text=f"Impossible de rejoindre le hall : {error}")
            return

        self._connect_in_progress = False

        normalized_invitation = format_endpoint(host, port)
        self.server_port = port
        self.local_test_invitation = format_endpoint("127.0.0.1", port)
        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, normalized_invitation)
        self._sync_controls_state()

        self.info_label.configure(text=f"Lien scellé pour {name}. Entrée dans le hall.")

        self.my_name = name
        self.my_sprite_id = self._get_selected_fighter_id()
        self._save_server_invitation(
            normalized_invitation,
            "local" if is_loopback_host(host) else "lan",
        )

        self._start_network_thread()
        if self.host_mode:
            if not self.client.send_match_duration(self._get_selected_match_duration()):
                play_error()
                self.info_label.configure(
                    text=("Hall rejoint, mais la durée n'a pas pu être transmise.")
                )
        self._refresh_mode_label()

        if self.host_mode:
            if is_loopback_host(host):
                self.info_label.configure(
                    text=f"{name} tient le hall en local sur ce PC."
                )
            else:
                self.info_label.configure(
                    text=(
                        f"{name} tient le hall. Invitation active : "
                        f"{normalized_invitation}."
                    )
                )
        else:
            if is_loopback_host(host):
                self.info_label.configure(
                    text=f"{name} a rejoint un hall local sur ce PC."
                )
            else:
                self.info_label.configure(
                    text=f"{name} a rejoint le hall {normalized_invitation}."
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
            assigned_sprite_id = str(msg.get("sprite_id") or "").strip()
            if assigned_sprite_id:
                self.my_sprite_id = assigned_sprite_id
            elif not self._fighter_explicitly_selected:
                self.my_sprite_id = get_default_fighter_id(team)
            self._set_selected_fighter(
                self.my_sprite_id,
                mark_manual=self._fighter_explicitly_selected,
            )

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
            self._sync_controls_state()

            if not msg.get("ok", False):
                play_error()
                self.info_label.configure(
                    text=msg.get(
                        "message",
                        ("Les chroniques du hall sont indisponibles pour le moment."),
                    )
                )
                return

            source_label = (
                "Chroniques du hall local"
                if self.host_mode
                else ("Chroniques du hall rejoint")
            )
            self.info_label.configure(
                text=(
                    f"{len(msg.get('rows', []))} chronique(s) reçue(s) depuis le hall."
                )
            )
            self._show_history_window(
                msg.get("rows", []),
                source_label,
            )

        elif msg_type == ERROR:
            play_error()
            self.info_label.configure(
                text=msg.get("message", "Le hall a signalé une erreur.")
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
                caption = "A transmettre aux autres PC du LAN."
            else:
                caption = "Pas d'IP LAN détectée. Test local seulement."
        else:
            active_value = ip_value.strip() or "En attente"
            caption = "Invitation actuellement ciblée."
            try:
                host, port = parse_server_invitation(
                    active_value,
                    self.server_port,
                )
                active_value = format_endpoint(host, port)
                if is_loopback_host(host):
                    caption = "Adresse locale: ce PC uniquement."
            except ValueError:
                pass

        self.invite_value_label.configure(text=active_value)
        self.invite_caption_label.configure(text=caption)
        self._refresh_guide_window()

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
                    "Aucun combattant dans le hall.\n\n"
                    + (
                        "Ouvre le hall puis partage l'invitation."
                        if self.host_mode
                        else "Colle une invitation puis rejoins le hall."
                    )
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
                PALETTE["gold_dim"] if player["team"] == "A" else PALETTE["cyan_dim"]
            )
            fighter_id = str(player.get("sprite_id") or "").strip()
            fighter_label = FIGHTER_DISPLAY_BY_SPRITE_ID.get(
                fighter_id,
                "Combattant du hall",
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

            if player["slot"] == self.my_slot:
                self_badge = create_badge(
                    player_card,
                    "Moi",
                    tone="gold" if self.host_mode else "info",
                )
                self_badge.grid(
                    row=0,
                    column=3,
                    padx=(0, 8),
                    pady=(12, 4),
                    sticky="e",
                )
                ready_column = 4
            else:
                ready_column = 3

            ready_badge = create_badge(
                player_card,
                "Prêt" if player["ready"] else "En veille",
                tone="success" if player["ready"] else "warning",
            )
            ready_badge.grid(
                row=0,
                column=ready_column,
                padx=(0, 14),
                pady=(12, 4),
                sticky="e",
            )

            detail_text = (
                f"Combattant : {fighter_label}. Poste local sélectionné."
                if player["slot"] == self.my_slot
                else (f"Combattant : {fighter_label}. En attente du départ.")
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

        if self.my_slot is not None:
            for player in players:
                if int(player.get("slot", 0) or 0) != int(self.my_slot):
                    continue

                roster_sprite_id = str(player.get("sprite_id") or "").strip()
                if roster_sprite_id:
                    self.my_sprite_id = roster_sprite_id
                    self._set_selected_fighter(
                        roster_sprite_id,
                        mark_manual=self._fighter_explicitly_selected,
                    )
                break

        total_players = len(players)
        ready_players = sum(1 for player in players if player.get("ready"))
        team_a_count = sum(1 for player in players if player.get("team") == "A")
        team_b_count = sum(1 for player in players if player.get("team") == "B")

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
        if not self.match_running:
            self.info_label.configure(text=self._build_lobby_status_text(players))

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
        self.duration_status_label.configure(text=f"Durée courante : {duration_text}")
        self._refresh_guide_window()

    def _get_selected_match_duration(self) -> int:
        try:
            return int(self.match_duration_var.get().strip())
        except ValueError:
            return MATCH_DURATION_SECONDS

    # =========================
    # Ready
    # =========================
    def _toggle_ready(self):
        if not self.client or not self.client.running or self._ready_request_pending:
            return

        play_select()

        next_ready_state = not self.ready_state
        self._ready_request_pending = True
        self.info_label.configure(text="Transmission du prêt au hall...")
        self._sync_controls_state()
        self.update_idletasks()

        if not self.client.send_ready(next_ready_state):
            self._ready_request_pending = False
            self._sync_controls_state()
            play_error()
            self.info_label.configure(text="Impossible de transmettre le prêt au hall.")
            return

        self.ready_state = next_ready_state
        self._ready_request_pending = False
        self._sync_controls_state()
        self.info_label.configure(
            text=(
                "Prêt envoyé. Le hall attend les autres."
                if self.ready_state
                else "Prêt retiré. Poste repasse en attente."
            )
        )

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
        self.info_label.configure(text="Lecture des chroniques du hall...")
        self._sync_controls_state()

        if not self.client.send_request_history():
            self.history_request_pending = False
            self._sync_controls_state()
            play_error()
            self.info_label.configure(
                text="Impossible d'appeler les chroniques du hall."
            )

    def _format_post_match_status(self, end_message: dict) -> str:
        team_a_score = end_message.get("team_a_score", 0)
        team_b_score = end_message.get("team_b_score", 0)
        base_text = (
            f"Joute close · {format_compact_scoreline(team_a_score, team_b_score)}"
        )

        if end_message.get("history_saved", False):
            match_id = end_message.get("match_id")
            if match_id is not None:
                return f"{base_text} · chronique du hall archivée (joute #{match_id})"
            return f"{base_text} · chronique du hall archivée"

        history_error = end_message.get("history_error", "Erreur inconnue")
        return f"{base_text} · archivage du hall échoué : {history_error}"

    def _launch_match(self):
        if not self.client or self.my_slot is None or not self.my_name:
            return

        parent = self.master
        parent_was_visible = False
        try:
            parent_was_visible = bool(parent.winfo_viewable())
        except TclError:
            parent_was_visible = False

        parent_lobby_attr_name = self._resolve_parent_lobby_attr_name()
        invitation_text = self.ip_entry.get().strip() or self.local_test_invitation

        # on stoppe la boucle lobby pendant le match
        self.running = False
        self.match_running = True
        self._sync_controls_state()
        stop_music(fade_ms=180)

        if parent_was_visible:
            parent.withdraw()
            parent.update_idletasks()

        # Le hall est détruit avant le match pour éviter un rendu noir
        # lorsque Tk conserve un Toplevel vivant pendant la boucle de jeu.
        self.destroy()

        # On lance le match réseau.
        try:
            match_summary = run_network_match(
                self.client,
                self.my_slot,
                self.my_name,
                self.my_team,
            )
        except LAN_MATCH_LAUNCH_ERRORS as error:
            LOGGER.exception("Crash pendant le lancement du match LAN")
            match_summary = {
                "completed": False,
                "end_message": None,
                "deferred_messages": [],
                "disconnect_message": (f"Le match LAN a planté au lancement : {error}"),
            }

        if parent_was_visible:
            parent.deiconify()
            present_window(parent)

        resumed_lobby = self._build_resumed_lobby(invitation_text)
        if parent_lobby_attr_name is not None:
            setattr(parent, parent_lobby_attr_name, resumed_lobby)

        init_audio()
        start_menu_music()
        resumed_lobby.resume_after_match(match_summary)

    def shutdown(self):
        self.running = False
        if self.client:
            self.client.close()
        self.destroy()
