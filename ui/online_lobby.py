from __future__ import annotations

from datetime import datetime
from time import monotonic
from tkinter import TclError, messagebox

import customtkinter as ctk

from game.net_match_window import run_network_match
from ui.online_client import (
    DEFAULT_ONLINE_HOST,
    DEFAULT_ONLINE_PORT,
    OnlineClient,
    OnlineConnectionError,
)
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    apply_theme_settings,
    apply_window_icon,
    create_badge,
    create_button,
    create_option_menu,
    enable_large_window,
    present_window,
    style_entry,
    style_frame,
    style_scrollable_frame,
    style_window,
    update_badge,
)


POLL_INTERVAL_MS = 80
MANUAL_REFRESH_FEEDBACK_SECONDS = 0.45
ROOM_CREATED_JOIN_FALLBACK_MS = 700

MODE_JOIN = "join"
MODE_CREATE = "create"
MIN_ONLINE_ROOM_PLAYERS = 2
MAX_ONLINE_ROOM_PLAYERS = 6
ONLINE_MATCH_LAUNCH_DELAY_MS = 50
ONLINE_MATCH_LAUNCH_ERRORS = (
    AttributeError,
    RuntimeError,
    OSError,
    TypeError,
    ValueError,
)
START_MATCH_BUTTON_LABEL = "Lancer le jeu"
READY_UP_BUTTON_LABEL = "Se mettre prêt"
READY_CANCEL_BUTTON_LABEL = "Annuler prêt"


class OnlineLobbyWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        style_window(self)
        self.configure(fg_color=PALETTE["launcher_blend"])

        self.title("Arena Duel - Jouer en ligne")
        apply_window_icon(self, default=True, retry_after_ms=220)
        self.geometry("920x620")
        enable_large_window(self, 820, 560, start_zoomed=False)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.join_window = None
        self.create_window = None

        self._build_ui()
        present_window(self)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=28)
        style_frame(
            header,
            tone="panel_deep",
            border_color=PALETTE["cyan_dim"],
            border_width=0,
        )
        header.grid(row=0, column=0, padx=24, pady=(24, 16), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        create_badge(header, "Online", tone="info").grid(
            row=0,
            column=0,
            padx=20,
            pady=(20, 10),
            sticky="w",
        )

        ctk.CTkLabel(
            header,
            text="Choisis ton parcours",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, padx=20, sticky="w")

        ctk.CTkLabel(
            header,
            text=(
                "Les joueurs ne voient aucun paramètre serveur. "
                "Ils choisissent seulement rejoindre une session "
                "existante ou créer la leur."
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=720,
        ).grid(row=2, column=0, padx=20, pady=(8, 18), sticky="w")

        content = ctk.CTkFrame(
            self,
            fg_color="transparent",
            bg_color="transparent",
        )
        content.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        content.grid_columnconfigure(0, weight=1, uniform="choice")
        content.grid_columnconfigure(1, weight=1, uniform="choice")
        content.grid_rowconfigure(0, weight=1)

        self._build_choice_card(
            content,
            column=0,
            badge_text="Rejoindre",
            badge_tone="info",
            title="Rejoindre une session",
            description=(
                "Le joueur saisit son pseudo, charge les sessions déjà "
                "ouvertes puis rejoint celle qu'il veut."
            ),
            button_text="Ouvrir la fenêtre de rejoindre",
            button_variant="accent",
            command=self.open_join_window,
        )
        self._build_choice_card(
            content,
            column=1,
            badge_text="Créer",
            badge_tone="gold",
            title="Créer une session",
            description=(
                "Le joueur choisit son pseudo, le nom de la session et "
                "le nombre de joueurs, puis il attend les arrivées."
            ),
            button_text="Ouvrir la fenêtre de création",
            button_variant="primary",
            command=self.open_create_window,
        )

        footer = ctk.CTkFrame(self, corner_radius=20)
        style_frame(
            footer,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        footer.grid(row=2, column=0, padx=24, pady=(0, 24), sticky="ew")

        ctk.CTkLabel(
            footer,
            text=(
                "Le serveur online par défaut reste utilisé en interne. "
                "Cette fenêtre sert seulement à orienter le joueur vers "
                "la bonne expérience."
            ),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=820,
        ).grid(row=0, column=0, padx=18, pady=18, sticky="w")

    def _build_choice_card(
        self,
        parent,
        *,
        column: int,
        badge_text: str,
        badge_tone: str,
        title: str,
        description: str,
        button_text: str,
        button_variant: str,
        command,
    ) -> None:
        card = ctk.CTkFrame(parent, corner_radius=28)
        style_frame(
            card,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        card.grid(
            row=0,
            column=column,
            padx=(0, 12) if column == 0 else (12, 0),
            sticky="nsew",
        )
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)

        create_badge(card, badge_text, tone=badge_tone).grid(
            row=0,
            column=0,
            padx=20,
            pady=(20, 12),
            sticky="w",
        )

        ctk.CTkLabel(
            card,
            text=title,
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
            justify="left",
        ).grid(row=1, column=0, padx=20, sticky="w")

        ctk.CTkLabel(
            card,
            text=description,
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=360,
        ).grid(row=2, column=0, padx=20, pady=(10, 16), sticky="w")

        ctk.CTkLabel(
            card,
            text="Une fenêtre dédiée s'ouvre ensuite pour ce choix.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
            wraplength=360,
        ).grid(row=3, column=0, padx=20, pady=(0, 16), sticky="nw")

        create_button(
            card,
            button_text,
            command,
            variant=button_variant,
            height=48,
            width=280,
        ).grid(row=4, column=0, padx=20, pady=(0, 20), sticky="ew")

    def _focus_or_open_window(self, attr_name: str, factory) -> None:
        current_window = getattr(self, attr_name)
        if current_window is not None:
            try:
                if current_window.winfo_exists():
                    present_window(current_window)
                    return
            except TclError:
                pass

        window = factory()
        setattr(self, attr_name, window)
        window.bind(
            "<Destroy>",
            lambda _event, name=attr_name, ref=window: self._clear_child_reference(
                name, ref
            ),
            add="+",
        )

    def _clear_child_reference(self, attr_name: str, window) -> None:
        current_window = getattr(self, attr_name)
        if current_window is window:
            setattr(self, attr_name, None)

    def open_join_window(self) -> None:
        self._focus_or_open_window(
            "join_window",
            lambda: OnlineSessionWindow(self, mode=MODE_JOIN),
        )

    def open_create_window(self) -> None:
        self._focus_or_open_window(
            "create_window",
            lambda: OnlineSessionWindow(self, mode=MODE_CREATE),
        )

    def shutdown(self) -> None:
        for attr_name in ("join_window", "create_window"):
            child_window = getattr(self, attr_name)
            if child_window is None:
                continue

            try:
                if child_window.winfo_exists():
                    child_window.shutdown()
            except TclError:
                pass
            setattr(self, attr_name, None)

        self.destroy()


class OnlineSessionWindow(ctk.CTkToplevel):
    def __init__(self, master=None, *, mode: str):
        if mode not in {MODE_JOIN, MODE_CREATE}:
            raise ValueError(f"Mode online inconnu : {mode}")

        super().__init__(master)
        style_window(self)
        self.configure(fg_color=PALETTE["launcher_blend"])

        self.mode = mode
        self.title(self._window_title())
        apply_window_icon(self, default=True, retry_after_ms=220)
        self.geometry("1160x760")
        enable_large_window(self, 960, 640, start_zoomed=False)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.client = OnlineClient()
        self.connected = False
        self.connecting = False
        self._poll_after_id = None
        self._manual_refresh_feedback = False
        self._manual_refresh_started_at = 0.0
        self._manual_refresh_after_id = None
        self._pending_rooms = None
        self._room_created_join_after_id = None
        self._pending_created_room_id: str | None = None
        self._match_launch_after_id = None

        self.host_var = ctk.StringVar(value=DEFAULT_ONLINE_HOST)
        self.port_var = ctk.StringVar(value=str(DEFAULT_ONLINE_PORT))
        self.pseudo_var = ctk.StringVar(value="")
        self.room_name_var = ctk.StringVar(value="Session Arena")
        self.max_players_var = ctk.StringVar(value=str(MIN_ONLINE_ROOM_PLAYERS))

        self.status_badge = None
        self.status_label = None
        self.rooms_meta_label = None
        self.rooms_scroll = None
        self.active_room_title_label = None
        self.active_room_meta_label = None
        self.active_room_state_label = None
        self.active_room_hint_label = None
        self.active_room_players_frame = None
        self.waiting_room_action_label = None
        self.pseudo_entry = None
        self.room_name_entry = None
        self.max_players_entry = None
        self.btn_connect = None
        self.btn_disconnect = None
        self.btn_refresh = None
        self.btn_create = None
        self.btn_copy_room_id = None
        self.btn_ready = None
        self.btn_start_match = None
        self.match_running = False
        self.last_refresh_text = "jamais"
        self.current_room_id: str | None = None
        self.current_room_name: str | None = None
        self.current_room_state: str | None = None
        self.current_room_state_code: str | None = None
        self.current_room_players: list[str] = []
        self.current_room_ready_players: set[str] = set()
        self.current_room_player_count = 0
        self.current_room_capacity: str | None = None
        self.current_room_max_players: int | None = None
        self.current_room_host_pseudo: str | None = None
        self.local_slot: int | None = None
        self.local_team: str | None = None
        self.local_sprite_id: str | None = None
        self._known_rooms_by_id: dict[str, dict] = {}
        self._match_start_prompt_signature: tuple[str, tuple[str, ...], int] | None = (
            None
        )
        self._last_completed_match_signature: (
            tuple[str, tuple[str, ...], int] | None
        ) = None
        self._last_match_status_text: str | None = None

        self._build_ui()
        self._apply_disconnected_state(
            self._default_disconnected_message(),
            tone="neutral",
        )
        present_window(self)
        self._schedule_poll()

    def _window_title(self) -> str:
        if self.mode == MODE_JOIN:
            return "Arena Duel - Rejoindre une session"
        return "Arena Duel - Créer une session"

    def _mode_badge_text(self) -> str:
        if self.mode == MODE_JOIN:
            return "Rejoindre"
        return "Créer"

    def _mode_badge_tone(self) -> str:
        if self.mode == MODE_JOIN:
            return "info"
        return "gold"

    def _hero_title(self) -> str:
        if self.mode == MODE_JOIN:
            return "Rejoins une session ouverte"
        return "Crée ta session et attends les joueurs"

    def _hero_subtitle(self) -> str:
        if self.mode == MODE_JOIN:
            return (
                "Saisis ton pseudo, charge la liste des sessions ouvertes "
                "puis rejoins celle qui t'intéresse."
            )
        return (
            "Saisis ton pseudo, définis ta session, puis garde cette "
            "fenêtre ouverte pendant que les autres joueurs arrivent."
        )

    def _profile_hint_text(self) -> str:
        if self.mode == MODE_JOIN:
            return (
                "Aucun réglage technique à faire ici. Entre seulement ton "
                "pseudo pour charger les sessions ouvertes."
            )
        return (
            "Le serveur online est déjà configuré dans le client. "
            "Tu choisis uniquement ton pseudo et les infos de la session."
        )

    def _connect_button_text(self) -> str:
        if self.mode == MODE_JOIN:
            return "Voir les sessions"
        return "Préparer la création"

    def _left_panel_badge_text(self) -> str:
        if self.mode == MODE_JOIN:
            return "Sessions"
        return "Nouvelle session"

    def _left_panel_title(self) -> str:
        if self.mode == MODE_JOIN:
            return "Sessions déjà ouvertes"
        return "Configurer la session"

    def _left_panel_body(self) -> str:
        if self.mode == MODE_JOIN:
            return (
                "Les sessions publiques apparaissent ici après la connexion. "
                "Choisis-en une pour entrer dans son salon d'attente."
            )
        return (
            "Choisis un nom et un nombre de joueurs. Après création, "
            "le salon d'attente s'ouvre à droite et le bouton "
            f"{START_MATCH_BUTTON_LABEL} se débloque quand la session "
            "est complète."
        )

    def _idle_room_title(self) -> str:
        if self.mode == MODE_JOIN:
            return "Aucune session rejointe"
        return "Aucune session créée"

    def _idle_room_meta(self) -> str:
        if self.mode == MODE_JOIN:
            return "Charge les sessions à gauche, puis rejoins celle que tu veux."
        return "Crée ta session à gauche pour ouvrir ton propre salon d'attente."

    def _idle_room_hint(self) -> str:
        if self.mode == MODE_JOIN:
            return "Les joueurs de la session apparaîtront ici après la connexion."
        return "Les joueurs qui entrent dans ta session apparaîtront ici."

    def _idle_placeholder_title(self) -> str:
        if self.mode == MODE_JOIN:
            return "En attente d'une session"
        return "En attente de création"

    def _idle_placeholder_body(self) -> str:
        if self.mode == MODE_JOIN:
            return (
                "Entre ton pseudo puis charge la liste des sessions pour en "
                "rejoindre une."
            )
        return (
            "Entre ton pseudo, crée une session et garde cette fenêtre "
            "ouverte pendant l'arrivée des autres joueurs."
        )

    def _default_disconnected_message(self) -> str:
        if self.mode == MODE_JOIN:
            return "Entre ton pseudo puis charge les sessions ouvertes."
        return "Entre ton pseudo pour préparer ta session."

    def _connected_ready_message(self, pseudo: str) -> str:
        if self.mode == MODE_JOIN:
            return f"Connecté en tant que {pseudo}. Chargement des sessions..."
        return f"Connecté en tant que {pseudo}. Tu peux créer ta session."

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=28)
        style_frame(
            header,
            tone="panel_deep",
            border_color=PALETTE["cyan_dim"],
            border_width=0,
        )
        header.grid(row=0, column=0, padx=24, pady=(24, 16), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        create_badge(
            header,
            self._mode_badge_text(),
            tone=self._mode_badge_tone(),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        ctk.CTkLabel(
            header,
            text=self._hero_title(),
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
            justify="left",
        ).grid(row=1, column=0, padx=20, sticky="w")

        ctk.CTkLabel(
            header,
            text=self._hero_subtitle(),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=720,
        ).grid(row=2, column=0, padx=20, pady=(8, 18), sticky="w")

        status_shell = ctk.CTkFrame(header, fg_color="transparent")
        status_shell.grid(
            row=0,
            column=1,
            rowspan=3,
            padx=(12, 20),
            pady=20,
            sticky="e",
        )

        self.status_badge = create_badge(
            status_shell,
            "Déconnecté",
            tone="neutral",
        )
        self.status_badge.grid(row=0, column=0, sticky="e")

        self.status_label = ctk.CTkLabel(
            status_shell,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="right",
            wraplength=320,
        )
        self.status_label.grid(row=1, column=0, pady=(10, 0), sticky="e")

        content = ctk.CTkFrame(
            self,
            fg_color="transparent",
            bg_color="transparent",
        )
        content.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        content.grid_columnconfigure(0, weight=11, uniform="session")
        content.grid_columnconfigure(1, weight=9, uniform="session")
        content.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(content, corner_radius=26)
        style_frame(
            left_panel,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        left_panel.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        self._build_profile_card(left_panel)
        if self.mode == MODE_JOIN:
            self._build_join_panel(left_panel)
        else:
            self._build_create_panel(left_panel)

        right_panel = ctk.CTkFrame(content, corner_radius=26)
        style_frame(
            right_panel,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        right_panel.grid(row=0, column=1, padx=(12, 0), sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)
        self._build_waiting_room_panel(right_panel)

    def _build_profile_card(self, parent) -> None:
        card = ctk.CTkFrame(parent, corner_radius=20)
        style_frame(
            card,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
        )
        card.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)

        create_badge(card, "Profil", tone="info").grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 10),
            sticky="w",
        )

        ctk.CTkLabel(
            card,
            text=self._profile_hint_text(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=560,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            padx=16,
            pady=(0, 10),
            sticky="w",
        )

        self.pseudo_entry = self._build_entry_field(
            card,
            row=2,
            label="Ton pseudo",
            variable=self.pseudo_var,
            columnspan=2,
        )

        self.btn_connect = create_button(
            card,
            self._connect_button_text(),
            self.on_connect,
            variant="accent",
            height=44,
        )
        self.btn_connect.grid(
            row=4,
            column=0,
            padx=(16, 8),
            pady=(8, 16),
            sticky="ew",
        )

        self.btn_disconnect = create_button(
            card,
            "Se déconnecter",
            self.on_disconnect,
            variant="danger",
            height=44,
        )
        self.btn_disconnect.grid(
            row=4,
            column=1,
            padx=(8, 16),
            pady=(8, 16),
            sticky="ew",
        )

    def _build_join_panel(self, parent) -> None:
        sessions_card = ctk.CTkFrame(parent, corner_radius=20)
        style_frame(
            sessions_card,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
        )
        sessions_card.grid(
            row=1,
            column=0,
            padx=20,
            pady=(0, 20),
            sticky="nsew",
        )
        sessions_card.grid_columnconfigure(0, weight=1)
        sessions_card.grid_rowconfigure(4, weight=1)

        create_badge(
            sessions_card,
            self._left_panel_badge_text(),
            tone="gold",
        ).grid(row=0, column=0, padx=16, pady=(16, 10), sticky="w")

        ctk.CTkLabel(
            sessions_card,
            text=self._left_panel_title(),
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, padx=16, sticky="w")

        ctk.CTkLabel(
            sessions_card,
            text=self._left_panel_body(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=620,
        ).grid(row=2, column=0, padx=16, pady=(6, 10), sticky="w")

        actions_row = ctk.CTkFrame(sessions_card, fg_color="transparent")
        actions_row.grid(
            row=3,
            column=0,
            padx=16,
            pady=(0, 12),
            sticky="ew",
        )
        actions_row.grid_columnconfigure(0, weight=1)
        actions_row.grid_columnconfigure(1, weight=0)

        self.rooms_meta_label = ctk.CTkLabel(
            actions_row,
            text="Connecte-toi pour charger les sessions.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
        )
        self.rooms_meta_label.grid(row=0, column=0, padx=(0, 12), sticky="w")

        self.btn_refresh = create_button(
            actions_row,
            "Actualiser",
            self.on_list_rooms,
            variant="secondary",
            width=150,
            height=40,
        )
        self.btn_refresh.grid(row=0, column=1, sticky="e")

        self.rooms_scroll = ctk.CTkScrollableFrame(
            sessions_card,
            corner_radius=18,
            fg_color=PALETTE["panel"],
            border_width=0,
            border_color=PALETTE["divider"],
        )
        style_scrollable_frame(
            self.rooms_scroll,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        self.rooms_scroll.grid(
            row=4,
            column=0,
            padx=16,
            pady=(0, 16),
            sticky="nsew",
        )
        self.rooms_scroll.grid_columnconfigure(0, weight=1)

    def _build_create_panel(self, parent) -> None:
        create_card = ctk.CTkFrame(parent, corner_radius=20)
        style_frame(
            create_card,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
        )
        create_card.grid(
            row=1,
            column=0,
            padx=20,
            pady=(0, 20),
            sticky="nsew",
        )
        create_card.grid_columnconfigure(0, weight=1)
        create_card.grid_rowconfigure(7, weight=1)

        create_badge(
            create_card,
            self._left_panel_badge_text(),
            tone="gold",
        ).grid(row=0, column=0, padx=16, pady=(16, 10), sticky="w")

        ctk.CTkLabel(
            create_card,
            text=self._left_panel_title(),
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, padx=16, sticky="w")

        ctk.CTkLabel(
            create_card,
            text=self._left_panel_body(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=620,
        ).grid(row=2, column=0, padx=16, pady=(6, 10), sticky="w")

        self.room_name_entry = self._build_entry_field(
            create_card,
            row=3,
            label="Nom de la session",
            variable=self.room_name_var,
        )
        self.max_players_entry = self._build_option_field(
            create_card,
            row=5,
            label="Nombre de joueurs (2 à 6)",
            variable=self.max_players_var,
            values=[
                str(value)
                for value in range(
                    MIN_ONLINE_ROOM_PLAYERS,
                    MAX_ONLINE_ROOM_PLAYERS + 1,
                )
            ],
        )

        self.btn_create = create_button(
            create_card,
            "Créer la session",
            self.on_create_room,
            variant="primary",
            height=44,
        )
        self.btn_create.grid(
            row=7,
            column=0,
            padx=16,
            pady=(8, 16),
            sticky="ew",
        )

    def _build_waiting_room_panel(self, parent) -> None:
        waiting_card = ctk.CTkFrame(parent, corner_radius=20)
        style_frame(
            waiting_card,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
        )
        waiting_card.grid(
            row=0,
            column=0,
            padx=20,
            pady=20,
            sticky="nsew",
        )
        waiting_card.grid_columnconfigure(0, weight=1)
        waiting_card.grid_rowconfigure(5, weight=1)

        create_badge(waiting_card, "Salon d'attente", tone="success").grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 10),
            sticky="w",
        )

        self.active_room_title_label = ctk.CTkLabel(
            waiting_card,
            text=self._idle_room_title(),
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
            justify="left",
        )
        self.active_room_title_label.grid(
            row=1,
            column=0,
            padx=16,
            sticky="w",
        )

        self.active_room_meta_label = ctk.CTkLabel(
            waiting_card,
            text=self._idle_room_meta(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=360,
        )
        self.active_room_meta_label.grid(
            row=2,
            column=0,
            padx=16,
            pady=(6, 0),
            sticky="w",
        )

        self.active_room_state_label = ctk.CTkLabel(
            waiting_card,
            text="",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            justify="left",
            wraplength=360,
        )
        self.active_room_state_label.grid(
            row=3,
            column=0,
            padx=16,
            pady=(10, 0),
            sticky="w",
        )

        actions_row = ctk.CTkFrame(waiting_card, fg_color="transparent")
        actions_row.grid(
            row=4,
            column=0,
            padx=16,
            pady=(12, 10),
            sticky="ew",
        )
        actions_row.grid_columnconfigure(0, weight=0)
        actions_row.grid_columnconfigure(1, weight=0)
        actions_row.grid_columnconfigure(2, weight=0)
        actions_row.grid_columnconfigure(3, weight=1)

        self.btn_copy_room_id = create_button(
            actions_row,
            "Copier l'ID",
            self.on_copy_room_id,
            variant="secondary",
            height=40,
            width=140,
        )
        self.btn_copy_room_id.grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="ew",
        )

        self.btn_ready = create_button(
            actions_row,
            READY_UP_BUTTON_LABEL,
            self.on_toggle_ready,
            variant="accent",
            height=40,
            width=160,
        )
        self.btn_ready.grid(
            row=0,
            column=1,
            padx=(0, 8),
            sticky="ew",
        )

        self.btn_start_match = create_button(
            actions_row,
            START_MATCH_BUTTON_LABEL,
            self.on_start_match,
            variant="primary",
            height=40,
            width=170,
        )
        self.btn_start_match.grid(
            row=0,
            column=2,
            padx=(0, 8),
            sticky="ew",
        )

        self.waiting_room_action_label = ctk.CTkLabel(
            actions_row,
            text="Pour quitter la session, utilise Se déconnecter.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="right",
            wraplength=180,
        )
        self.waiting_room_action_label.grid(
            row=0,
            column=3,
            padx=(0, 0),
            sticky="e",
        )

        self.active_room_hint_label = ctk.CTkLabel(
            waiting_card,
            text=self._idle_room_hint(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=360,
        )
        self.active_room_hint_label.grid(
            row=5,
            column=0,
            padx=16,
            pady=(0, 10),
            sticky="w",
        )

        self.active_room_players_frame = ctk.CTkScrollableFrame(
            waiting_card,
            corner_radius=16,
            fg_color=PALETTE["panel"],
            border_width=0,
            border_color=PALETTE["divider"],
            height=260,
        )
        style_scrollable_frame(
            self.active_room_players_frame,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        self.active_room_players_frame.grid(
            row=6,
            column=0,
            padx=16,
            pady=(0, 16),
            sticky="nsew",
        )
        self.active_room_players_frame.grid_columnconfigure(0, weight=1)

    def _build_entry_field(
        self,
        parent,
        *,
        row: int,
        label: str,
        variable,
        columnspan: int = 1,
    ):
        ctk.CTkLabel(
            parent,
            text=label,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(
            row=row,
            column=0,
            columnspan=columnspan,
            padx=16,
            pady=(0, 4),
            sticky="w",
        )

        entry = ctk.CTkEntry(parent, textvariable=variable)
        style_entry(entry)
        entry.grid(
            row=row + 1,
            column=0,
            columnspan=columnspan,
            padx=16,
            pady=(0, 10),
            sticky="ew",
        )
        return entry

    def _build_option_field(
        self,
        parent,
        *,
        row: int,
        label: str,
        variable,
        values: list[str],
    ):
        ctk.CTkLabel(
            parent,
            text=label,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(
            row=row,
            column=0,
            padx=16,
            pady=(0, 4),
            sticky="w",
        )

        option_menu = create_option_menu(
            parent,
            values=values,
            variable=variable,
            width=220,
            height=42,
        )
        option_menu.grid(
            row=row + 1,
            column=0,
            padx=16,
            pady=(0, 10),
            sticky="ew",
        )
        return option_menu

    def _schedule_poll(self) -> None:
        self._poll_after_id = self.after(
            POLL_INTERVAL_MS,
            self._process_events,
        )

    def _process_events(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except TclError:
            return

        while True:
            message = self.client.poll()
            if message is None:
                break
            self._handle_message(message)

        self._schedule_poll()

    def _handle_message(self, message: dict) -> None:
        message_type = str(message.get("type") or "").strip().upper()

        if message_type == "WELCOME":
            if not self.connected:
                self._set_status(
                    "Serveur prêt. Authentification en cours.",
                    tone="info",
                    badge_text="Serveur OK",
                )
            return

        if message_type == "ASSIGN_SLOT":
            try:
                self.local_slot = int(message.get("slot"))
            except (TypeError, ValueError):
                self.local_slot = None

            team_code = str(message.get("team") or "").strip().upper()
            self.local_team = team_code or None
            sprite_id = str(message.get("sprite_id") or "").strip()
            self.local_sprite_id = sprite_id or None
            return

        if message_type == "LOGIN_OK":
            pseudo = str(message.get("pseudo") or self.pseudo_var.get()).strip()
            self.connected = True
            self.connecting = False
            self._sync_controls_state()
            self._set_status(
                self._connected_ready_message(pseudo),
                tone="success",
                badge_text="Connecté",
            )
            self._request_rooms_refresh()
            return

        if message_type == "ROOMS":
            rooms = message.get("rooms", [])
            if not isinstance(rooms, list):
                rooms = []

            self._known_rooms_by_id = {
                str(room.get("room_id") or "").strip(): room
                for room in rooms
                if str(room.get("room_id") or "").strip()
            }
            self._refresh_current_room_from_directory()

            if self.mode != MODE_JOIN:
                self.last_refresh_text = self._current_time_label()
                self._sync_controls_state()
                return

            if self._manual_refresh_feedback:
                elapsed = monotonic() - self._manual_refresh_started_at
                remaining = MANUAL_REFRESH_FEEDBACK_SECONDS - elapsed
                if remaining > 0:
                    self._pending_rooms = rooms
                    self._cancel_manual_refresh_timer()
                    self._manual_refresh_after_id = self.after(
                        max(1, int(remaining * 1000)),
                        self._flush_pending_rooms,
                    )
                    return

            self._apply_rooms_update(rooms)
            return

        if message_type == "ROOM_CREATED":
            room_id = str(message.get("room_id") or "").strip()
            if room_id:
                self._clear_current_room(
                    f"Session créée : {room_id}. Attente de confirmation..."
                )
                self._set_status(
                    f"Session créée : {room_id}. Attente de confirmation...",
                    tone="success",
                    badge_text="Créée",
                )
                self._schedule_room_created_join_fallback(room_id)
                self._request_rooms_refresh()
                return

            self._set_status(
                f"Session créée : {room_id or 'id inconnu'}.",
                tone="success",
                badge_text="Créée",
            )
            self._request_rooms_refresh()
            return

        if message_type == "JOINED":
            room_id = str(message.get("room_id") or "").strip()
            if room_id:
                if room_id == self._pending_created_room_id:
                    self._pending_created_room_id = None
                    self._cancel_room_created_join_timer()

                room_info = self._known_rooms_by_id.get(room_id, {})
                local_pseudo = self.pseudo_var.get().strip()
                players = [local_pseudo] if local_pseudo else []
                room_name = str(room_info.get("name") or "").strip() or None
                host_pseudo = str(room_info.get("host_pseudo") or "").strip() or None
                if room_name is None and self.mode == MODE_CREATE:
                    room_name = self.room_name_var.get().strip() or None
                if host_pseudo is None and self.mode == MODE_CREATE:
                    host_pseudo = local_pseudo or None
                max_players = self._room_max_players(room_info)
                if max_players is None:
                    max_players = self._selected_max_players_or_none()

                capacity = self._format_room_capacity(room_info)
                if capacity is None:
                    capacity = self._fallback_capacity_for_join()

                self._set_current_room_status(
                    room_id=room_id,
                    room_name=room_name,
                    state_code="lobby",
                    state_text=self._format_room_state("lobby"),
                    players=players,
                    ready_players=[],
                    max_players=max_players,
                    capacity=capacity,
                    host_pseudo=host_pseudo,
                    is_active=True,
                )

            self._set_status(
                f"Session rejointe : {room_id or 'id inconnu'}.",
                tone="success",
                badge_text="Dans le salon",
            )
            self._request_rooms_refresh()
            return

        if message_type == "ROOM_UPDATE":
            room_payload = message.get("room")
            if isinstance(room_payload, dict):
                room_id = str(room_payload.get("room_id") or "").strip() or None
                players = [
                    str(player).strip()
                    for player in room_payload.get("players", [])
                    if str(player).strip()
                ]
                ready_players = [
                    str(player).strip()
                    for player in room_payload.get("ready_players", [])
                    if str(player).strip()
                ]
                room_info = dict(self._known_rooms_by_id.get(room_id or "", {}))
                if room_id is not None:
                    room_info["room_id"] = room_id

                raw_state = room_payload.get("state")
                if raw_state:
                    room_info["state"] = raw_state
                room_name = str(room_payload.get("name") or "").strip() or None
                if room_name is not None:
                    room_info["name"] = room_name
                if room_payload.get("max_players") is not None:
                    room_info["max_players"] = room_payload.get("max_players")
                host_pseudo = (
                    str(
                        room_payload.get("host_pseudo")
                        or room_info.get("host_pseudo")
                        or ""
                    ).strip()
                    or None
                )
                if host_pseudo is not None:
                    room_info["host_pseudo"] = host_pseudo
                room_info["players"] = len(players)

                room_name = str(room_info.get("name") or "").strip() or None
                if room_name is None and self.mode == MODE_CREATE:
                    room_name = self.room_name_var.get().strip() or None
                if room_id:
                    self._known_rooms_by_id[room_id] = room_info

                self._set_current_room_status(
                    room_id=room_id,
                    room_name=room_name,
                    state_code=self._normalize_room_state_code(raw_state),
                    state_text=self._format_room_state(raw_state),
                    players=players,
                    ready_players=ready_players,
                    max_players=self._room_max_players(room_info),
                    capacity=(
                        self._format_room_capacity(room_info)
                        or self._fallback_capacity_for_join()
                    ),
                    host_pseudo=host_pseudo,
                    is_active=True,
                )

            self._set_status(
                "Salon synchronisé.",
                tone="info",
                badge_text="Update",
            )
            return

        if message_type == "MATCH_STARTED":
            self._clear_post_match_feedback()
            room_id = str(message.get("room_id") or "").strip() or None
            host_pseudo = str(message.get("host_pseudo") or "").strip() or None

            if room_id:
                room_info = dict(self._known_rooms_by_id.get(room_id, {}))
                room_info["room_id"] = room_id
                room_info["state"] = "in_game"
                if host_pseudo is not None:
                    room_info["host_pseudo"] = host_pseudo
                self._known_rooms_by_id[room_id] = room_info

            if room_id and room_id == self.current_room_id:
                self.current_room_state_code = "in_game"
                self.current_room_state = self._format_room_state("in_game")
                if host_pseudo is not None:
                    self.current_room_host_pseudo = host_pseudo
                self._render_waiting_room_panel()
                self._sync_controls_state()
                if self.mode == MODE_JOIN:
                    self._render_rooms(self._ordered_rooms())

            started_by = host_pseudo or "l'hôte"
            self._set_status(
                f"Partie lancée par {started_by}.",
                tone="success",
                badge_text="Match",
            )
            if room_id and room_id == self.current_room_id:
                self._schedule_match_launch()
            return

        if message_type == "START":
            if self.current_room_id is None:
                return

            self._clear_post_match_feedback()
            self.current_room_state_code = "in_game"
            self.current_room_state = self._format_room_state("in_game")
            self._set_status(
                "La joute s'ouvre. Préparation du runtime de match.",
                tone="success",
                badge_text="Match",
            )
            self._schedule_match_launch()
            return

        if message_type == "HOST_CHANGED":
            room_id = str(message.get("room_id") or "").strip() or None
            host_pseudo = str(message.get("host_pseudo") or "").strip() or None
            if room_id and host_pseudo:
                room_info = dict(self._known_rooms_by_id.get(room_id, {}))
                room_info["room_id"] = room_id
                room_info["host_pseudo"] = host_pseudo
                self._known_rooms_by_id[room_id] = room_info

                if room_id == self.current_room_id:
                    self.current_room_host_pseudo = host_pseudo
                    self._render_waiting_room_panel()
                    if self.mode == MODE_JOIN:
                        self._render_rooms(self._ordered_rooms())

                self._set_status(
                    f"Nouvel hôte : {host_pseudo}.",
                    tone="info",
                    badge_text="Hôte",
                )
            return

        if message_type == "ERROR":
            code = self._format_server_error(message)
            raw_code = str(message.get("code") or "").strip().upper()
            raw_got = str(message.get("got") or "").strip().upper()
            is_ready_compatibility_error = (
                raw_code == "UNKNOWN_TYPE" and raw_got == "SET_READY"
            )
            self._set_status(
                f"Erreur serveur : {code}",
                tone=("warning" if is_ready_compatibility_error else "danger"),
                badge_text=("Serveur" if is_ready_compatibility_error else "Erreur"),
            )
            return

        if message_type == "DISCONNECTED":
            reason = str(message.get("error") or "Connexion online interrompue.")
            self.client.disconnect()
            self._apply_disconnected_state(reason, tone="danger")

    def _fallback_capacity_for_join(self) -> str | None:
        raw_value = self.max_players_var.get().strip()
        try:
            max_players = int(raw_value)
        except ValueError:
            return None

        local_count = max(1, len(self.current_room_players) or 1)
        return f"Places : {local_count}/{max_players}"

    def _ordered_rooms(self, rooms: list[dict] | None = None) -> list[dict]:
        if rooms is None:
            rooms = list(self._known_rooms_by_id.values())

        def sort_key(room_info: dict) -> tuple:
            room_id = str(room_info.get("room_id") or "").strip()
            room_name = str(room_info.get("name") or room_id or "").lower()
            is_current = room_id == (self.current_room_id or "")
            has_slot = self._room_is_joinable(room_info)
            return (
                0 if is_current else 1,
                0 if has_slot else 1,
                room_name,
                room_id,
            )

        return sorted(list(rooms), key=sort_key)

    def _room_player_count(self, room_info: dict) -> int:
        raw_players = room_info.get("players", 0)
        if isinstance(raw_players, list):
            return sum(1 for player in raw_players if str(player).strip())

        try:
            return max(0, int(raw_players))
        except (TypeError, ValueError):
            return 0

    def _room_max_players(self, room_info: dict) -> int | None:
        raw_max = room_info.get("max_players")
        try:
            return int(raw_max)
        except (TypeError, ValueError):
            return None

    def _room_has_available_slot(self, room_info: dict) -> bool:
        max_players = self._room_max_players(room_info)
        if max_players is None:
            return True
        return self._room_player_count(room_info) < max_players

    def _room_is_joinable(self, room_info: dict) -> bool:
        return self._normalize_room_state_code(
            room_info.get("state")
        ) == "lobby" and self._room_has_available_slot(room_info)

    def _normalize_room_state_code(self, raw_state: object) -> str:
        state = str(raw_state or "").strip().lower()
        if not state or state == "lobby":
            return "lobby"
        if state in {"countdown", "starting", "ready"}:
            return "starting"
        if state in {"in_game", "in-game", "game", "running"}:
            return "in_game"
        return state

    def _format_room_state(self, raw_state: object) -> str:
        state = self._normalize_room_state_code(raw_state)
        if state == "lobby":
            return "Salon en attente"
        if state == "starting":
            return "Préparation du départ"
        if state == "in_game":
            return "Partie lancée"
        return state.replace("_", " ").capitalize()

    def _format_room_capacity(self, room_info: dict) -> str | None:
        max_players = self._room_max_players(room_info)
        if max_players is None:
            return None
        player_count = self._room_player_count(room_info)
        return f"Places : {player_count}/{max_players}"

    def _room_host_pseudo(self, room_info: dict) -> str | None:
        host_pseudo = str(room_info.get("host_pseudo") or "").strip()
        return host_pseudo or None

    def _room_badge(self, room_info: dict) -> tuple[str, str]:
        room_id = str(room_info.get("room_id") or "").strip()
        if room_id and room_id == self.current_room_id:
            return ("Ta session", "success")
        if self._normalize_room_state_code(room_info.get("state")) != "lobby":
            return (self._format_room_state(room_info.get("state")), "gold")
        if not self._room_has_available_slot(room_info):
            return ("Complet", "warning")
        if self._normalize_room_state_code(room_info.get("state")) == "lobby":
            return ("Ouverte", "info")
        return (self._format_room_state(room_info.get("state")), "gold")

    def _clear_container(self, container) -> None:
        if container is None:
            return
        for child in container.winfo_children():
            child.destroy()

    def _render_rooms(self, rooms: list[dict]) -> None:
        if self.rooms_scroll is None:
            return

        self._clear_container(self.rooms_scroll)
        rooms = self._ordered_rooms(rooms)
        if not rooms:
            empty_card = ctk.CTkFrame(self.rooms_scroll, corner_radius=18)
            style_frame(
                empty_card,
                tone="panel",
                border_color=PALETTE["divider"],
                border_width=0,
            )
            empty_card.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
            empty_card.grid_columnconfigure(0, weight=1)

            if self.connected:
                title = "Aucune session publique trouvée"
                detail = (
                    "Aucune session n'est ouverte pour le moment. "
                    "Actualise plus tard ou demande à un ami d'en créer une."
                )
            else:
                title = "Connecte-toi pour voir les sessions"
                detail = (
                    "Dès que tu es connecté, les sessions publiques déjà "
                    "ouvertes apparaissent ici."
                )

            ctk.CTkLabel(
                empty_card,
                text=title,
                font=TYPOGRAPHY["body_bold"],
                text_color=PALETTE["text"],
                justify="left",
            ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")

            ctk.CTkLabel(
                empty_card,
                text=detail,
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_soft"],
                justify="left",
                wraplength=620,
            ).grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")
            return

        for index, room_info in enumerate(rooms):
            self._render_room_card(index, room_info)

    def _render_room_card(self, row_index: int, room_info: dict) -> None:
        if self.rooms_scroll is None:
            return

        room_id = str(room_info.get("room_id") or "").strip()
        room_name = str(room_info.get("name") or room_id or "Sans nom").strip()
        state_text = self._format_room_state(room_info.get("state"))
        capacity_text = self._format_room_capacity(room_info) or "Places : ?"
        host_pseudo = self._room_host_pseudo(room_info)
        badge_text, badge_tone = self._room_badge(room_info)
        is_current = room_id == (self.current_room_id or "")
        can_join = (
            self.connected
            and not self.connecting
            and not self._manual_refresh_feedback
            and self.current_room_id is None
            and self._room_is_joinable(room_info)
            and bool(room_id)
        )

        card = ctk.CTkFrame(self.rooms_scroll, corner_radius=18)
        style_frame(
            card,
            tone="panel_deep" if is_current else "panel",
            border_color=(PALETTE["success"] if is_current else PALETTE["divider"]),
            border_width=1 if is_current else 0,
        )
        card.grid(
            row=row_index,
            column=0,
            padx=4,
            pady=(0, 10),
            sticky="ew",
        )
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        create_badge(card, badge_text, tone=badge_tone).grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 8),
            sticky="w",
        )

        ctk.CTkLabel(
            card,
            text=room_name,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            justify="left",
        ).grid(row=1, column=0, padx=16, sticky="w")

        ctk.CTkLabel(
            card,
            text=f"ID : {room_id or 'inconnu'}",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
        ).grid(row=2, column=0, padx=16, pady=(6, 0), sticky="w")

        ctk.CTkLabel(
            card,
            text=f"{state_text} • {capacity_text}",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
        ).grid(row=3, column=0, padx=16, pady=(4, 16), sticky="w")

        button_rowspan = 4
        if host_pseudo:
            button_rowspan = 5
            ctk.CTkLabel(
                card,
                text=f"Hôte : {host_pseudo}",
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_soft"],
                justify="left",
            ).grid(row=4, column=0, padx=16, pady=(0, 16), sticky="w")

        button_text = "Déjà dedans" if is_current else "Rejoindre"
        if (
            self._normalize_room_state_code(room_info.get("state")) != "lobby"
            and not is_current
        ):
            button_text = "Indisponible"
        elif not self._room_has_available_slot(room_info) and not is_current:
            button_text = "Complet"

        join_button = create_button(
            card,
            button_text,
            lambda rid=room_id: self._join_room_id(rid),
            variant="primary" if not is_current else "secondary",
            width=150,
            height=40,
        )
        join_button.grid(
            row=0,
            column=1,
            rowspan=button_rowspan,
            padx=(12, 16),
            pady=16,
            sticky="e",
        )
        join_button.configure(state="normal" if can_join else "disabled")

    def _render_waiting_room_panel(self) -> None:
        if (
            self.active_room_title_label is None
            or self.active_room_meta_label is None
            or self.active_room_state_label is None
            or self.active_room_hint_label is None
            or self.active_room_players_frame is None
            or self.btn_copy_room_id is None
        ):
            return

        self._clear_container(self.active_room_players_frame)
        local_pseudo = self.pseudo_var.get().strip()

        if self.current_room_id is None:
            self.active_room_title_label.configure(
                text=self._idle_room_title(),
                text_color=PALETTE["text"],
            )
            self.active_room_meta_label.configure(
                text=self._idle_room_meta(),
                text_color=PALETTE["text_soft"],
            )
            self.active_room_state_label.configure(
                text=(self.current_room_state or self._default_disconnected_message()),
                text_color=PALETTE["text_muted"],
            )
            self.active_room_hint_label.configure(
                text=self._idle_room_hint(),
                text_color=PALETTE["text_soft"],
            )
            self.btn_copy_room_id.configure(state="disabled")

            placeholder = ctk.CTkFrame(
                self.active_room_players_frame,
                corner_radius=16,
            )
            style_frame(
                placeholder,
                tone="panel",
                border_color=PALETTE["divider"],
                border_width=0,
            )
            placeholder.grid(
                row=0,
                column=0,
                padx=4,
                pady=4,
                sticky="ew",
            )
            placeholder.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                placeholder,
                text=self._idle_placeholder_title(),
                font=TYPOGRAPHY["body_bold"],
                text_color=PALETTE["text"],
            ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")

            ctk.CTkLabel(
                placeholder,
                text=self._idle_placeholder_body(),
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_soft"],
                justify="left",
                wraplength=340,
            ).grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")
            self._refresh_waiting_room_actions()
            return

        room_title = self.current_room_name or self.current_room_id
        room_meta_parts = [f"ID : {self.current_room_id}"]
        if self.current_room_capacity:
            room_meta_parts.append(self.current_room_capacity)
        if self.current_room_host_pseudo:
            room_meta_parts.append(f"Hôte : {self.current_room_host_pseudo}")

        self.active_room_title_label.configure(
            text=room_title,
            text_color=PALETTE["text"],
        )
        self.active_room_meta_label.configure(
            text=" • ".join(room_meta_parts),
            text_color=PALETTE["text_soft"],
        )
        self.active_room_state_label.configure(
            text=self.current_room_state or "Salon en attente",
            text_color=PALETTE["success"],
        )
        self.active_room_hint_label.configure(
            text=self._build_waiting_room_hint_text(),
            text_color=PALETTE["text_soft"],
        )
        self.btn_copy_room_id.configure(state="normal")

        players = list(self.current_room_players)
        if not players and local_pseudo:
            players = [local_pseudo]

        for index, player_name in enumerate(players):
            self._render_player_card(
                index,
                player_name,
                player_name == self.current_room_host_pseudo,
                player_name in self.current_room_ready_players,
            )

        if players:
            self._refresh_waiting_room_actions()
            return

        placeholder = ctk.CTkFrame(
            self.active_room_players_frame,
            corner_radius=16,
        )
        style_frame(
            placeholder,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        placeholder.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        placeholder.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            placeholder,
            text="Aucun autre joueur pour le moment",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")

        ctk.CTkLabel(
            placeholder,
            text=(
                "Le serveur mettra la liste à jour quand de nouveaux "
                "joueurs entreront dans la session."
            ),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=340,
        ).grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")
        self._refresh_waiting_room_actions()

    def _render_player_card(
        self,
        row_index: int,
        player_name: str,
        is_host_player: bool,
        is_ready_player: bool,
    ) -> None:
        if self.active_room_players_frame is None:
            return

        local_pseudo = self.pseudo_var.get().strip()
        is_local_player = bool(local_pseudo) and player_name == local_pseudo

        card = ctk.CTkFrame(self.active_room_players_frame, corner_radius=16)
        style_frame(
            card,
            tone="panel",
            border_color=(PALETTE["gold"] if is_local_player else PALETTE["divider"]),
            border_width=1 if is_local_player else 0,
        )
        card.grid(
            row=row_index,
            column=0,
            padx=4,
            pady=(0, 10),
            sticky="ew",
        )
        card.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=14, pady=(14, 8), sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_row,
            text=player_name,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        if is_local_player and is_host_player:
            badge_text = "Toi / Hôte"
            badge_tone = "gold"
        elif is_host_player:
            badge_text = "Hôte"
            badge_tone = "success"
        elif is_local_player:
            badge_text = "Toi"
            badge_tone = "gold"
        else:
            badge_text = "Connecté"
            badge_tone = "info"
        create_badge(title_row, badge_text, tone=badge_tone).grid(
            row=0,
            column=1,
            sticky="e",
        )

        if is_local_player and is_host_player:
            subtitle = "Tu es l'hôte actuel de cette session."
        elif is_host_player:
            subtitle = "Hôte actuel de cette session."
        elif is_local_player:
            subtitle = "Tu es dans le salon d'attente de cette session."
        else:
            subtitle = "Joueur présent dans cette session."
        ctk.CTkLabel(
            card,
            text=subtitle,
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=320,
        ).grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        ctk.CTkLabel(
            card,
            text=("Statut : prêt" if is_ready_player else "Statut : en attente"),
            font=TYPOGRAPHY["small_bold"],
            text_color=(
                PALETTE["success"] if is_ready_player else PALETTE["text_muted"]
            ),
            justify="left",
        ).grid(row=2, column=0, padx=14, pady=(0, 14), sticky="w")

    def _apply_rooms_update(self, rooms: list[dict]) -> None:
        self.last_refresh_text = self._current_time_label()
        self._set_rooms_meta(
            (f"{len(rooms)} session(s) ouverte(s) • synchro {self.last_refresh_text}")
        )
        self._render_rooms(rooms)
        self._manual_refresh_feedback = False
        self._pending_rooms = None
        self._cancel_manual_refresh_timer()
        self._sync_controls_state()
        self._set_status(
            f"{len(rooms)} session(s) chargée(s) à {self.last_refresh_text}.",
            tone="info",
            badge_text="Sessions",
        )

    def _flush_pending_rooms(self) -> None:
        self._manual_refresh_after_id = None
        rooms = self._pending_rooms or []
        self._apply_rooms_update(rooms)

    def _set_rooms_meta(self, text: str) -> None:
        if self.rooms_meta_label is None:
            return
        self.rooms_meta_label.configure(text=text)

    def _set_current_room_status(
        self,
        *,
        room_id: str | None,
        room_name: str | None,
        state_code: str | None,
        state_text: str,
        players: list[str],
        ready_players: list[str] | set[str] | None,
        max_players: int | None,
        capacity: str | None,
        host_pseudo: str | None,
        is_active: bool,
    ) -> None:
        previous_room_id = self.current_room_id
        if not is_active or room_id != previous_room_id:
            self._clear_post_match_feedback()

        self.current_room_id = room_id if is_active else None
        self.current_room_name = room_name if is_active else None
        self.current_room_state = state_text
        self.current_room_state_code = state_code if is_active else None
        self.current_room_players = list(players) if is_active else []
        if not is_active:
            self.current_room_ready_players = set()
        elif ready_players is None:
            self.current_room_ready_players = {
                player_name
                for player_name in self.current_room_ready_players
                if player_name in self.current_room_players
            }
        else:
            self.current_room_ready_players = {
                player_name
                for player_name in ready_players
                if player_name in self.current_room_players
            }
        self.current_room_player_count = len(self.current_room_players)
        self.current_room_capacity = capacity if is_active else None
        self.current_room_max_players = max_players if is_active else None
        self.current_room_host_pseudo = host_pseudo if is_active else None

        if is_active and room_id and room_id == self._pending_created_room_id:
            self._pending_created_room_id = None
            self._cancel_room_created_join_timer()

        self._render_waiting_room_panel()
        if self.mode == MODE_JOIN:
            self._render_rooms(self._ordered_rooms())

    def _clear_current_room(self, text: str) -> None:
        self._set_current_room_status(
            room_id=None,
            room_name=None,
            state_code=None,
            state_text=text,
            players=[],
            ready_players=[],
            max_players=None,
            capacity=None,
            host_pseudo=None,
            is_active=False,
        )

    def _refresh_current_room_from_directory(self) -> None:
        if self.current_room_id is None:
            return

        room_info = self._known_rooms_by_id.get(self.current_room_id)
        if room_info is None:
            return

        room_name = str(room_info.get("name") or "").strip() or self.current_room_name
        raw_state = room_info.get("state")
        if raw_state is not None:
            state_code = self._normalize_room_state_code(raw_state)
            state_text = self._format_room_state(raw_state)
        else:
            state_code = self.current_room_state_code
            state_text = self.current_room_state or "Salon en attente"

        self._set_current_room_status(
            room_id=self.current_room_id,
            room_name=room_name,
            state_code=state_code,
            state_text=state_text,
            players=self.current_room_players,
            ready_players=None,
            max_players=(
                self._room_max_players(room_info) or self.current_room_max_players
            ),
            capacity=(
                self._format_room_capacity(room_info) or self.current_room_capacity
            ),
            host_pseudo=(
                self._room_host_pseudo(room_info) or self.current_room_host_pseudo
            ),
            is_active=True,
        )

    def _current_time_label(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _clear_post_match_feedback(
        self,
        *,
        clear_completed_signature: bool = True,
    ) -> None:
        self._last_match_status_text = None
        if clear_completed_signature:
            self._last_completed_match_signature = None

    def _format_post_match_status(self, end_message: dict) -> str:
        score_text = (
            f"{end_message.get('team_a_score', 0)} - "
            f"{end_message.get('team_b_score', 0)}"
        )
        winner_text = str(end_message.get("winner_text") or "").strip()
        if winner_text:
            return f"Dernière joute : {score_text} · {winner_text}."
        return f"Dernière joute : {score_text}."

    def _build_waiting_room_hint_text(self) -> str:
        if self.current_room_state_code == "lobby" and self._last_match_status_text:
            return f"{self._last_match_status_text} Le salon est de nouveau ouvert."

        return (
            "Partage l'ID si besoin et garde cette fenêtre ouverte. "
            "Les joueurs présents apparaissent ici."
        )

    def _cancel_manual_refresh_timer(self) -> None:
        if self._manual_refresh_after_id is None:
            return

        try:
            self.after_cancel(self._manual_refresh_after_id)
        except TclError:
            pass

        self._manual_refresh_after_id = None

    def _cancel_room_created_join_timer(self) -> None:
        if self._room_created_join_after_id is None:
            return

        try:
            self.after_cancel(self._room_created_join_after_id)
        except TclError:
            pass

        self._room_created_join_after_id = None

    def _cancel_match_launch_timer(self) -> None:
        if self._match_launch_after_id is None:
            return

        try:
            self.after_cancel(self._match_launch_after_id)
        except TclError:
            pass

        self._match_launch_after_id = None

    def _schedule_room_created_join_fallback(self, room_id: str) -> None:
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return

        self._pending_created_room_id = normalized_room_id
        self._cancel_room_created_join_timer()

        def _fallback() -> None:
            self._room_created_join_after_id = None

            try:
                if not self.winfo_exists():
                    return
            except TclError:
                return

            if not self.connected:
                return

            if self._pending_created_room_id != normalized_room_id:
                return

            if self.current_room_id == normalized_room_id:
                self._pending_created_room_id = None
                return

            self._join_room_id(normalized_room_id, show_status=False)

        self._room_created_join_after_id = self.after(
            ROOM_CREATED_JOIN_FALLBACK_MS,
            _fallback,
        )

    def _set_status(
        self,
        text: str,
        *,
        tone: str = "neutral",
        badge_text: str | None = None,
    ) -> None:
        if self.status_badge is None or self.status_label is None:
            return

        badge_map = {
            "neutral": "Déconnecté",
            "info": "Info",
            "success": "Connecté",
            "warning": "Connexion...",
            "danger": "Erreur",
            "gold": "Online",
        }
        color_map = {
            "neutral": PALETTE["text_muted"],
            "info": PALETTE["cyan"],
            "success": PALETTE["success"],
            "warning": PALETTE["warning"],
            "danger": PALETTE["danger"],
            "gold": PALETTE["gold"],
        }

        update_badge(
            self.status_badge,
            badge_text or badge_map.get(tone, "Info"),
            tone=tone,
        )
        self.status_label.configure(
            text=text,
            text_color=color_map.get(tone, PALETTE["text_muted"]),
        )

    def _selected_max_players_or_none(self) -> int | None:
        raw_value = self.max_players_var.get().strip()
        try:
            return int(raw_value)
        except ValueError:
            return None

    def _schedule_match_launch(self) -> None:
        if self.match_running or self._match_launch_after_id is not None:
            return

        if self.client is None or self.local_slot is None or self.local_team is None:
            return

        self._match_launch_after_id = self.after(
            ONLINE_MATCH_LAUNCH_DELAY_MS,
            self._launch_match,
        )

    def _resume_after_match(self, match_summary: dict) -> None:
        for message in match_summary.get("deferred_messages", []):
            self._handle_message(message)

        disconnect_message = str(match_summary.get("disconnect_message") or "").strip()
        if disconnect_message:
            self.client.disconnect()
            self._apply_disconnected_state(disconnect_message, tone="danger")
            return

        end_message = match_summary.get("end_message") or {}
        if end_message:
            self._last_match_status_text = self._format_post_match_status(end_message)
            self._last_completed_match_signature = self._match_start_offer_signature()
            self._set_status(
                self._last_match_status_text,
                tone="success",
                badge_text="Fin",
            )

        if self.client.running:
            if self._poll_after_id is None:
                self._schedule_poll()
            self._request_rooms_refresh()
        else:
            self.client.disconnect()
            self._apply_disconnected_state(
                "Connexion interrompue à la fin du match.",
                tone="danger",
            )
            return

        self._sync_controls_state()

    def _launch_match(self) -> None:
        self._match_launch_after_id = None
        if self.match_running or self.client is None or self.local_slot is None:
            return

        self.match_running = True
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except TclError:
                pass
            self._poll_after_id = None

        parent = self.master
        parent_hidden = False
        try:
            if parent is not None and parent.winfo_exists() and parent.winfo_viewable():
                parent.withdraw()
                parent_hidden = True
        except TclError:
            parent_hidden = False

        try:
            self.withdraw()
            self.update_idletasks()
        except TclError:
            pass

        try:
            match_summary = run_network_match(
                self.client,
                self.local_slot,
                self.pseudo_var.get().strip(),
                self.local_team,
            )
        except ONLINE_MATCH_LAUNCH_ERRORS as error:
            match_summary = {
                "completed": False,
                "end_message": None,
                "deferred_messages": [],
                "disconnect_message": (
                    f"Le match online a échoué au lancement : {error}"
                ),
            }

        self.match_running = False

        try:
            if parent_hidden and parent is not None and parent.winfo_exists():
                parent.deiconify()
        except TclError:
            pass

        try:
            if self.winfo_exists():
                self.deiconify()
                present_window(self)
        except TclError:
            return

        self._resume_after_match(match_summary)

    def _is_local_host(self) -> bool:
        local_pseudo = self.pseudo_var.get().strip()
        return bool(local_pseudo) and (local_pseudo == self.current_room_host_pseudo)

    def _filtered_current_room_ready_players(self) -> set[str]:
        return {
            player_name
            for player_name in self.current_room_ready_players
            if player_name in self.current_room_players
        }

    def _current_ready_count(self) -> int:
        return len(self._filtered_current_room_ready_players())

    def _is_local_ready(self) -> bool:
        local_pseudo = self.pseudo_var.get().strip()
        return bool(local_pseudo) and (
            local_pseudo in self._filtered_current_room_ready_players()
        )

    def _all_current_players_ready(self) -> bool:
        if self.current_room_player_count <= 0:
            return False
        return self._current_ready_count() >= self.current_room_player_count

    def _can_start_current_match(self) -> bool:
        if not self.connected or self.current_room_id is None:
            return False
        if not self._is_local_host():
            return False
        if self.current_room_state_code != "lobby":
            return False
        if self.current_room_max_players is None:
            return False
        if self.current_room_player_count < MIN_ONLINE_ROOM_PLAYERS:
            return False
        if self.current_room_player_count < self.current_room_max_players:
            return False
        return self._all_current_players_ready()

    def _match_start_offer_signature(
        self,
    ) -> tuple[str, tuple[str, ...], int] | None:
        if not self._can_start_current_match():
            return None

        return (
            self.current_room_id or "",
            tuple(self.current_room_players),
            self.current_room_max_players or 0,
        )

    def _format_waiting_room_action_text(self) -> str:
        if self.current_room_id is None:
            return "Pour quitter la session, utilise Se déconnecter."
        if self.current_room_state_code != "lobby":
            return "Le jeu a déjà été lancé pour cette session."

        if self.current_room_max_players is not None and (
            self.current_room_player_count < self.current_room_max_players
        ):
            return (
                f"En attente des joueurs {self.current_room_player_count}/"
                f"{self.current_room_max_players} avant le départ."
            )

        if self._is_local_host():
            if self.current_room_max_players is None:
                return "L'hôte pourra lancer le jeu quand la session sera prête."
            if self._can_start_current_match():
                return "Tous les joueurs sont prêts. Tu peux lancer le jeu."
            return (
                f"En attente des prêts {self._current_ready_count()}/"
                f"{self.current_room_player_count} avant le départ."
            )

        if not self._is_local_ready():
            return "Passe en prêt pour signaler que tu es prêt."
        if self.current_room_host_pseudo:
            return (
                f"Tu es prêt. En attente que {self.current_room_host_pseudo} "
                "lance le jeu."
            )
        return "Tu es prêt. En attente que l'hôte lance le jeu."

    def _refresh_waiting_room_actions(self) -> None:
        if (
            self.btn_ready is None
            or self.btn_start_match is None
            or self.waiting_room_action_label is None
        ):
            return

        if self.current_room_id is None:
            ready_text = READY_UP_BUTTON_LABEL
            ready_state = "disabled"
            button_text = START_MATCH_BUTTON_LABEL
            button_state = "disabled"
        elif self.current_room_state_code != "lobby":
            ready_text = "Prêt verrouillé"
            ready_state = "disabled"
            button_text = "Jeu lancé"
            button_state = "disabled"
        elif self._is_local_ready():
            ready_text = READY_CANCEL_BUTTON_LABEL
            ready_state = "normal"
            if self._is_local_host():
                button_text = START_MATCH_BUTTON_LABEL
                button_state = (
                    "normal" if self._can_start_current_match() else "disabled"
                )
            else:
                button_text = "Lancement réservé à l'hôte"
                button_state = "disabled"
        elif self._is_local_host():
            ready_text = READY_UP_BUTTON_LABEL
            ready_state = "normal"
            button_text = START_MATCH_BUTTON_LABEL
            button_state = "disabled"
        else:
            ready_text = READY_UP_BUTTON_LABEL
            ready_state = "normal"
            button_text = "Lancement réservé à l'hôte"
            button_state = "disabled"

        self.btn_ready.configure(
            text=ready_text,
            state=ready_state,
        )
        self.btn_start_match.configure(
            text=button_text,
            state=button_state,
        )
        self.waiting_room_action_label.configure(
            text=self._format_waiting_room_action_text()
        )
        self._maybe_offer_match_start()

    def _maybe_offer_match_start(self) -> None:
        signature = self._match_start_offer_signature()
        if signature is None:
            self._match_start_prompt_signature = None
            return

        if self._last_completed_match_signature == signature:
            return

        if self._match_start_prompt_signature == signature:
            return

        self._match_start_prompt_signature = signature
        should_start = messagebox.askyesno(
            "Session prête",
            (
                "Le nombre de joueurs prévu est atteint. "
                "Veux-tu lancer le jeu maintenant ?"
            ),
            parent=self,
        )
        if should_start:
            self.on_start_match()

    def _format_server_error(self, message: dict) -> str:
        code = str(message.get("message") or message.get("code") or "").strip()
        if not code:
            return "Erreur inconnue"

        raw_code = code.upper()
        raw_got = str(message.get("got") or "").strip().upper()

        if raw_code == "UNKNOWN_TYPE" and raw_got == "SET_READY":
            return (
                "Le serveur online n'accepte pas encore le bouton prêt. "
                "Il faut lancer un serveur mis à jour avec cette branche."
            )

        translations = {
            "BAD_HANDSHAKE": "Le serveur online a rejeté la poignée de main.",
            "HOST_ONLY": "Seul l'hôte peut lancer le jeu.",
            "LOGIN_REQUIRED": "Le serveur online exige une authentification.",
            "MATCH_ALREADY_STARTED": "Cette session a déjà lancé sa partie.",
            "NEED_MORE_PLAYERS": ("Il faut au moins deux joueurs pour démarrer."),
            "NOT_IN_ROOM": "Tu n'es dans aucune session.",
            "PLAYERS_NOT_READY": ("Attends que tous les joueurs passent en prêt."),
            "PROTO_MISMATCH": ("Le serveur online utilise un protocole incompatible."),
            "ROOM_FULL": "Cette session est déjà complète.",
            "ROOM_NOT_FOUND": "Session introuvable.",
            "ROOM_NOT_FULL": (
                "Attends que tous les joueurs prévus soient dans la session."
            ),
            "UNKNOWN_TYPE": "Le serveur online a rejeté une commande inconnue.",
        }
        return translations.get(code, code)

    def _sync_controls_state(self) -> None:
        if (
            self.pseudo_entry is None
            or self.btn_connect is None
            or self.btn_disconnect is None
            or self.btn_copy_room_id is None
        ):
            return

        profile_state = "disabled" if self.connected or self.connecting else "normal"
        connect_state = "disabled" if self.connected or self.connecting else "normal"
        disconnect_state = "normal" if self.connected or self.connecting else "disabled"
        copy_state = "normal" if self.current_room_id is not None else "disabled"

        self.pseudo_entry.configure(state=profile_state)
        self.btn_connect.configure(
            text=self._connect_button_text(),
            state=connect_state,
        )
        self.btn_disconnect.configure(state=disconnect_state)
        self.btn_copy_room_id.configure(state=copy_state)
        self._refresh_waiting_room_actions()

        if self.mode == MODE_JOIN:
            if self.btn_refresh is not None:
                refresh_state = (
                    "normal"
                    if self.connected
                    and not self.connecting
                    and not self._manual_refresh_feedback
                    and self.current_room_id is None
                    else "disabled"
                )
                self.btn_refresh.configure(state=refresh_state)
            self._render_rooms(self._ordered_rooms())
            return

        room_action_state = (
            "normal"
            if (self.connected and not self.connecting and self.current_room_id is None)
            else "disabled"
        )
        if self.room_name_entry is not None:
            self.room_name_entry.configure(state=room_action_state)
        if self.max_players_entry is not None:
            self.max_players_entry.configure(state=room_action_state)
        if self.btn_create is not None:
            self.btn_create.configure(state=room_action_state)

    def _apply_disconnected_state(
        self,
        message: str,
        *,
        tone: str,
    ) -> None:
        self.connected = False
        self.connecting = False
        self.match_running = False
        self._manual_refresh_feedback = False
        self._pending_rooms = None
        self._pending_created_room_id = None
        self._known_rooms_by_id = {}
        self.local_slot = None
        self.local_team = None
        self.local_sprite_id = None
        self._match_start_prompt_signature = None
        self._clear_post_match_feedback()
        self._cancel_manual_refresh_timer()
        self._cancel_room_created_join_timer()
        self._cancel_match_launch_timer()
        self._clear_current_room(message)
        if self.mode == MODE_JOIN:
            self._set_rooms_meta("Connecte-toi pour charger les sessions.")
            self._render_rooms([])
        self._sync_controls_state()
        self._set_status(message, tone=tone, badge_text="Déconnecté")

    def _parse_port(self) -> int:
        raw_port = self.port_var.get().strip()
        try:
            port = int(raw_port)
        except ValueError as error:
            raise ValueError("Le port doit être un entier valide.") from error

        if not 1 <= port <= 65535:
            raise ValueError("Le port doit rester entre 1 et 65535.")
        return port

    def _parse_max_players(self) -> int:
        raw_value = self.max_players_var.get().strip()
        try:
            max_players = int(raw_value)
        except ValueError as error:
            raise ValueError(
                "Le nombre de joueurs doit être un entier valide."
            ) from error

        if not (MIN_ONLINE_ROOM_PLAYERS <= max_players <= MAX_ONLINE_ROOM_PLAYERS):
            raise ValueError("Le nombre de joueurs doit rester entre 2 et 6.")
        return max_players

    def _send_message(self, payload: dict, *, action_label: str) -> bool:
        try:
            self.client.send(payload)
        except OnlineConnectionError as error:
            self.client.disconnect()
            self._apply_disconnected_state(str(error), tone="danger")
            messagebox.showerror(
                "Connexion online perdue",
                f"Impossible de {action_label} : {error}",
            )
            return False

        return True

    def on_connect(self) -> None:
        if self.connected or self.connecting:
            return

        host = self.host_var.get().strip()
        pseudo = self.pseudo_var.get().strip()

        try:
            port = self._parse_port()
            self.client.connect(host, port, pseudo)
        except (OnlineConnectionError, ValueError) as error:
            self._apply_disconnected_state(str(error), tone="danger")
            messagebox.showerror(
                "Connexion online impossible",
                str(error),
            )
            return

        self.connecting = True
        self._sync_controls_state()
        self._set_status(
            "Connexion au serveur online en cours.",
            tone="warning",
            badge_text="Connexion...",
        )

    def on_disconnect(self) -> None:
        self.client.disconnect()
        self._apply_disconnected_state(
            "Connexion online fermée.",
            tone="neutral",
        )

    def _request_rooms_refresh(self, *, manual: bool = False) -> None:
        if not self._send_message(
            {"type": "LIST_ROOMS"},
            action_label="charger les sessions",
        ):
            return

        if not manual or self.mode != MODE_JOIN:
            return

        self._manual_refresh_feedback = True
        self._manual_refresh_started_at = monotonic()
        self._pending_rooms = None
        self._cancel_manual_refresh_timer()
        self._render_rooms(self._ordered_rooms())
        self._sync_controls_state()
        self._set_rooms_meta("Synchronisation des sessions en cours...")
        self._set_status(
            "Actualisation des sessions demandée au serveur online.",
            tone="info",
            badge_text="Refresh",
        )

    def on_list_rooms(self) -> None:
        self._request_rooms_refresh(manual=True)

    def _join_room_id(self, room_id: str, *, show_status: bool = True) -> bool:
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return False

        if not self._send_message(
            {"type": "JOIN_ROOM", "room_id": normalized_room_id},
            action_label="rejoindre la session",
        ):
            return False

        if show_status:
            self._set_status(
                f"Demande envoyée pour rejoindre {normalized_room_id}.",
                tone="info",
                badge_text="Join",
            )
        return True

    def on_copy_room_id(self) -> None:
        if self.current_room_id is None:
            return

        self.clipboard_clear()
        self.clipboard_append(self.current_room_id)
        try:
            self.update_idletasks()
        except TclError:
            pass

        self._set_status(
            f"ID de session copié : {self.current_room_id}",
            tone="info",
            badge_text="Copié",
        )

    def on_create_room(self) -> None:
        room_name = self.room_name_var.get().strip() or "Session Arena"

        try:
            max_players = self._parse_max_players()
        except ValueError as error:
            messagebox.showerror("Paramètres invalides", str(error))
            return

        if not self._send_message(
            {
                "type": "CREATE_ROOM",
                "name": room_name,
                "max_players": max_players,
            },
            action_label="créer la session",
        ):
            return

        self._set_status(
            f"Création de la session {room_name} en cours.",
            tone="info",
            badge_text="Création",
        )

    def on_toggle_ready(self) -> None:
        if self.current_room_id is None or self.current_room_state_code != "lobby":
            return

        next_ready_state = not self._is_local_ready()
        action_label = "mettre à jour le statut prêt"
        if not self._send_message(
            {"type": "SET_READY", "ready": next_ready_state},
            action_label=action_label,
        ):
            return

        self._set_status(
            (
                "Demande prêt envoyée au serveur online."
                if next_ready_state
                else "Annulation du prêt envoyée au serveur online."
            ),
            tone="info",
            badge_text="Prêt",
        )

    def on_start_match(self) -> None:
        if not self._can_start_current_match():
            return

        if not self._send_message(
            {"type": "START_MATCH"},
            action_label="lancer le jeu",
        ):
            return

        self._clear_post_match_feedback()
        self._set_status(
            "Demande de lancement du jeu envoyée au serveur online.",
            tone="warning",
            badge_text="Départ",
        )

    def shutdown(self) -> None:
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except TclError:
                pass
            self._poll_after_id = None

        self._cancel_manual_refresh_timer()
        self._cancel_room_created_join_timer()
        self._cancel_match_launch_timer()
        self.client.disconnect()
        self.destroy()


def run_online_lobby() -> None:
    apply_theme_settings()

    app = ctk.CTk()
    app.withdraw()

    window = OnlineLobbyWindow(app)

    def close_all() -> None:
        window.shutdown()
        try:
            if app.winfo_exists():
                app.destroy()
        except TclError:
            pass

    window.protocol("WM_DELETE_WINDOW", close_all)
    app.mainloop()
