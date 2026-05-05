from __future__ import annotations

import queue
import threading
from datetime import datetime
from functools import lru_cache
from time import monotonic
from tkinter import TclError, messagebox

import customtkinter as ctk

from game.net_match_window import run_network_match
from game.settings import MATCH_DURATION_SECONDS
from ui.online_client import (
    DEFAULT_ONLINE_HOST,
    DEFAULT_ONLINE_PORT,
    OnlineClient,
    OnlineConnectionError,
    OnlineNetworkStatus,
    OnlineProtocolError,
    fetch_public_room_directory,
    get_online_network_status,
    probe_online_service,
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
NETWORK_STATUS_REFRESH_MS = 2400
NETWORK_STATUS_POLL_MS = 40
ROOM_PREVIEW_POLL_MS = 40

MODE_JOIN = "join"
MODE_CREATE = "create"
MIN_ONLINE_ROOM_PLAYERS = 2
MAX_ONLINE_ROOM_PLAYERS = 6
ONLINE_MATCH_DURATION_OPTIONS_SECONDS = (30, 45, 60, 90, 120, 180)
DEFAULT_ONLINE_MATCH_DURATION_SECONDS = (
    MATCH_DURATION_SECONDS
    if MATCH_DURATION_SECONDS in ONLINE_MATCH_DURATION_OPTIONS_SECONDS
    else 60
)
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
ONLINE_ENTRY_REQUIRED_TITLE = "Connexion requise"
ONLINE_ENTRY_REQUIRED_MESSAGE = "Active Internet avant d'ouvrir l'Online."


@lru_cache(maxsize=1)
def _audio_module():
    from game import audio as audio_module

    return audio_module


def init_audio():
    return _audio_module().init_audio()


def play_alert():
    return _audio_module().play_alert()


def play_click():
    return _audio_module().play_click()


def play_error():
    return _audio_module().play_error()


def play_transition():
    return _audio_module().play_transition()


def _schedule_window_sound(
    widget,
    *,
    tone: str = "transition",
    delay_ms: int = 70,
) -> None:
    if getattr(widget, "tk", None) is None:
        return

    def _play_sound() -> None:
        try:
            if not widget.winfo_exists():
                return
        except TclError:
            return

        init_audio()
        if tone == "click":
            play_click()
            return
        if tone == "alert":
            play_alert()
            return
        if tone == "error":
            play_error()
            return
        play_transition()

    try:
        widget.after(delay_ms, _play_sound)
    except (AttributeError, TclError):
        pass


class OnlineWifiIndicator(ctk.CTkFrame):
    def __init__(
        self,
        master=None,
        *,
        available: bool,
        host_getter=None,
        port_getter=None,
    ):
        super().__init__(master, fg_color="transparent")
        self.available = bool(available)
        self._bars: list[ctk.CTkFrame] = []
        self._host_getter = host_getter or (lambda: DEFAULT_ONLINE_HOST)
        self._port_getter = port_getter or (lambda: DEFAULT_ONLINE_PORT)
        self._status_result_queue: "queue.Queue[tuple[int, OnlineNetworkStatus]]" = (
            queue.Queue()
        )
        self._status_request_token = 0
        self._status_probe_in_progress = False
        self._status_refresh_after_id = None
        self._status_poll_after_id = None
        self.last_status: OnlineNetworkStatus | None = None
        self.grid_columnconfigure(1, weight=0)

        bars_shell = ctk.CTkFrame(self, fg_color="transparent")
        bars_shell.grid(row=0, column=0, sticky="e")
        bars_shell.grid_rowconfigure(0, weight=1)

        for column, height in enumerate((6, 10, 14, 18)):
            bar = ctk.CTkFrame(
                bars_shell,
                width=5,
                height=height,
                corner_radius=2,
            )
            bar.grid(
                row=0,
                column=column,
                padx=(0, 3) if column < 3 else 0,
                sticky="s",
            )
            bar.grid_propagate(False)
            self._bars.append(bar)

        self.label = ctk.CTkLabel(
            self,
            text="Wi-Fi",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        self.label.grid(row=0, column=1, padx=(8, 0), sticky="e")

        self.set_available(self.available)
        self.bind("<Destroy>", self._handle_destroy, add="+")
        self.after(90, self.refresh_network_status)

    def _handle_destroy(self, _event=None) -> None:
        self.shutdown()

    def _initial_status(self, available: bool) -> OnlineNetworkStatus:
        if available:
            return OnlineNetworkStatus(
                transport_kind="network",
                transport_label="Réseau",
                tone="success",
                signal_bars=4,
                online_available=True,
                is_connected=True,
                quality_label="Stable",
            )

        return OnlineNetworkStatus(
            transport_kind="offline",
            transport_label="Hors ligne",
            tone="neutral",
            signal_bars=0,
            online_available=False,
            is_connected=False,
            quality_label="Aucun",
        )

    def _probe_target(self) -> tuple[str, int]:
        host = DEFAULT_ONLINE_HOST
        port = DEFAULT_ONLINE_PORT

        try:
            host = str(self._host_getter() or DEFAULT_ONLINE_HOST).strip()
        except (AttributeError, TclError, TypeError, ValueError):
            host = DEFAULT_ONLINE_HOST

        try:
            port = int(self._port_getter())
        except (AttributeError, TclError, TypeError, ValueError):
            port = DEFAULT_ONLINE_PORT

        return host or DEFAULT_ONLINE_HOST, port

    def _schedule_next_refresh(self) -> None:
        if self._status_refresh_after_id is not None:
            try:
                self.after_cancel(self._status_refresh_after_id)
            except TclError:
                pass
            self._status_refresh_after_id = None

        try:
            self._status_refresh_after_id = self.after(
                NETWORK_STATUS_REFRESH_MS,
                self.refresh_network_status,
            )
        except TclError:
            self._status_refresh_after_id = None

    def _status_worker(
        self,
        request_token: int,
        host: str,
        port: int,
    ) -> None:
        status = get_online_network_status(host=host, port=port)
        self._status_result_queue.put((request_token, status))

    def refresh_network_status(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except TclError:
            return

        if self._status_probe_in_progress:
            return

        self._status_request_token += 1
        request_token = self._status_request_token
        self._status_probe_in_progress = True
        host, port = self._probe_target()

        worker = threading.Thread(
            target=self._status_worker,
            args=(request_token, host, port),
            daemon=True,
        )
        worker.start()
        self._status_poll_after_id = self.after(
            NETWORK_STATUS_POLL_MS,
            self._drain_network_status_results,
        )

    def _drain_network_status_results(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except TclError:
            return

        received_current_result = False
        while True:
            try:
                request_token, status = self._status_result_queue.get_nowait()
            except queue.Empty:
                break

            if request_token != self._status_request_token:
                continue

            received_current_result = True
            self._status_probe_in_progress = False
            self.apply_network_status(status)

        if self._status_probe_in_progress and not received_current_result:
            self._status_poll_after_id = self.after(
                NETWORK_STATUS_POLL_MS,
                self._drain_network_status_results,
            )
            return

        self._status_poll_after_id = None
        self._schedule_next_refresh()

    def apply_network_status(self, status: OnlineNetworkStatus) -> None:
        tone_colors = {
            "success": PALETTE["success"],
            "warning": PALETTE["warning"],
            "danger": PALETTE["danger"],
            "neutral": PALETTE["neutral"],
        }
        active_color = tone_colors.get(status.tone, PALETTE["neutral"])
        inactive_color = PALETTE["neutral_dim"]
        active_bars = max(0, min(4, int(status.signal_bars)))

        self.available = bool(status.online_available)
        self.last_status = status

        for index, bar in enumerate(self._bars, start=1):
            bar.configure(
                fg_color=(active_color if index <= active_bars else inactive_color)
            )

        self.label.configure(
            text=status.transport_label,
            text_color=active_color,
        )

    def set_available(self, available: bool) -> None:
        self.apply_network_status(self._initial_status(available))

    def shutdown(self) -> None:
        for after_id_name in (
            "_status_refresh_after_id",
            "_status_poll_after_id",
        ):
            after_id = getattr(self, after_id_name)
            if after_id is None:
                continue

            try:
                self.after_cancel(after_id)
            except TclError:
                pass
            setattr(self, after_id_name, None)

        self._status_probe_in_progress = False


class OnlineLobbyWindow(ctk.CTkToplevel):
    def __init__(self, master=None, *, network_available: bool = True):
        super().__init__(master)
        style_window(self)
        self.configure(fg_color=PALETTE["launcher_blend"])

        self.title("Arena Duel - Jouer en ligne")
        apply_window_icon(self, default=True, retry_after_ms=220)
        self.geometry("920x620")
        enable_large_window(self, 820, 560, start_zoomed=True)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.join_window = None
        self.create_window = None
        self.network_available = bool(network_available)
        self.network_indicator = None

        self._build_ui()
        present_window(self)
        _schedule_window_sound(self)

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
        header.grid_columnconfigure(1, weight=0)

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
                "Choisis rejoindre ou créer, puis entre dans la session qui "
                "te correspond."
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=720,
        ).grid(row=2, column=0, padx=20, pady=(8, 18), sticky="w")

        self.network_indicator = OnlineWifiIndicator(
            header,
            available=self.network_available,
        )
        self.network_indicator.grid(
            row=0,
            column=1,
            rowspan=3,
            padx=(12, 20),
            pady=20,
            sticky="ne",
        )

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
                "Le serveur online reste configuré en interne. Cette fenêtre "
                "sert seulement à orienter le joueur vers la bonne expérience."
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
        self._close_other_child_windows(attr_name)

        current_window = getattr(self, attr_name)
        if current_window is not None:
            try:
                if current_window.winfo_exists():
                    self._hide_for_child_window()
                    present_window(current_window)
                    return
            except TclError:
                pass

        window = factory()
        self._hide_for_child_window()
        setattr(self, attr_name, window)
        window.bind(
            "<Destroy>",
            lambda event, name=attr_name, ref=window: self._clear_child_reference(
                name, ref, event.widget
            ),
            add="+",
        )

    def _hide_for_child_window(self) -> None:
        try:
            if self.winfo_exists() and self.winfo_viewable():
                self.withdraw()
                self.update_idletasks()
        except TclError:
            pass

    def _close_other_child_windows(self, keep_attr_name: str) -> None:
        for attr_name in ("join_window", "create_window"):
            if attr_name == keep_attr_name:
                continue

            child_window = getattr(self, attr_name)
            if child_window is None:
                continue

            try:
                if child_window.winfo_exists():
                    child_window.shutdown(restore_parent=False)
            except TclError:
                pass
            finally:
                if getattr(self, attr_name) is child_window:
                    setattr(self, attr_name, None)

    def _clear_child_reference(self, attr_name: str, window, event_widget=None) -> None:
        if event_widget is not None and event_widget is not window:
            return

        current_window = getattr(self, attr_name)
        if current_window is window:
            setattr(self, attr_name, None)

    def open_join_window(self) -> None:
        play_transition()
        self._focus_or_open_window(
            "join_window",
            lambda: OnlineSessionWindow(
                self,
                mode=MODE_JOIN,
                network_available=self.network_available,
            ),
        )

    def open_create_window(self) -> None:
        play_transition()
        self._focus_or_open_window(
            "create_window",
            lambda: OnlineSessionWindow(
                self,
                mode=MODE_CREATE,
                network_available=self.network_available,
            ),
        )

    def shutdown(self) -> None:
        parent = self.master
        play_click()

        if self.network_indicator is not None:
            self.network_indicator.shutdown()

        for attr_name in ("join_window", "create_window"):
            child_window = getattr(self, attr_name)
            if child_window is None:
                continue

            try:
                if child_window.winfo_exists():
                    child_window.shutdown(play_sound=False)
            except TclError:
                pass
            setattr(self, attr_name, None)

        self.destroy()
        try:
            if parent is not None and parent.winfo_exists():
                present_window(parent)
        except TclError:
            pass


class RoomIdPromptWindow(ctk.CTkToplevel):
    def __init__(self, master: OnlineSessionWindow):
        super().__init__(master)
        style_window(self)
        self.configure(fg_color=PALETTE["launcher_blend"])

        self.title("Arena Duel - Entrer un ID")
        apply_window_icon(self, default=True, retry_after_ms=220)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.entry = None
        self.feedback_label = None
        self.submit_button = None

        self._build_ui()
        self._fit_window_to_content()
        present_window(self)
        _schedule_window_sound(self, tone="click", delay_ms=0)
        self.after(40, self.focus_input)

    def _fit_window_to_content(self) -> None:
        try:
            self.update_idletasks()
        except TclError:
            return

        width = max(500, self.winfo_reqwidth())
        height = max(340, self.winfo_reqheight())
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, corner_radius=24)
        style_frame(
            card,
            tone="panel_soft",
            border_color=PALETTE["border"],
            border_width=0,
        )
        card.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        create_badge(card, "ID", tone="info").grid(
            row=0,
            column=0,
            padx=18,
            pady=(18, 10),
            sticky="w",
        )

        ctk.CTkLabel(
            card,
            text="Rejoindre avec un ID de session",
            font=TYPOGRAPHY["subtitle"],
            text_color=PALETTE["text"],
            justify="left",
        ).grid(row=1, column=0, padx=18, sticky="w")

        ctk.CTkLabel(
            card,
            text=(
                "Colle l'ID partagé par l'hôte, puis confirme pour "
                "envoyer la demande au serveur online."
            ),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=380,
        ).grid(row=2, column=0, padx=18, pady=(8, 10), sticky="w")

        ctk.CTkLabel(
            card,
            text="ID de session",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(row=3, column=0, padx=18, pady=(0, 4), sticky="w")

        self.entry = ctk.CTkEntry(
            card,
            textvariable=self.master.room_id_var,
            placeholder_text="Ex. room-7A9F",
        )
        style_entry(self.entry)
        self.entry.grid(
            row=4,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="ew",
        )
        self.entry.bind("<Return>", lambda _event: self.submit())

        self.feedback_label = ctk.CTkLabel(
            card,
            text="",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["warning"],
            justify="left",
            wraplength=380,
        )
        self.feedback_label.grid(
            row=5,
            column=0,
            padx=18,
            pady=(0, 10),
            sticky="w",
        )
        self.feedback_label.grid_remove()

        actions_row = ctk.CTkFrame(card, fg_color="transparent")
        actions_row.grid(
            row=6,
            column=0,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        actions_row.grid_columnconfigure(0, weight=1)
        actions_row.grid_columnconfigure(1, weight=0)

        create_button(
            actions_row,
            "Annuler",
            self._handle_cancel,
            variant="ghost",
            width=120,
            height=40,
            font=TYPOGRAPHY["button_small"],
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.submit_button = create_button(
            actions_row,
            "Rejoindre",
            self.submit,
            variant="accent",
            width=140,
            height=40,
            font=TYPOGRAPHY["button_small"],
        )
        self.submit_button.grid(row=0, column=1, sticky="e")

    def focus_input(self) -> None:
        if self.entry is None:
            return
        try:
            self.entry.focus_force()
        except TclError:
            pass

    def set_interaction_state(self, state: str) -> None:
        if self.entry is not None:
            self.entry.configure(state=state)
        if self.submit_button is not None:
            self.submit_button.configure(state=state)

    def show_feedback(self, text: str, *, tone: str = "warning") -> None:
        if self.feedback_label is None:
            return

        color_map = {
            "info": PALETTE["cyan"],
            "success": PALETTE["success"],
            "warning": PALETTE["warning"],
            "danger": PALETTE["danger"],
        }
        self.feedback_label.configure(
            text=text,
            text_color=color_map.get(tone, PALETTE["text_soft"]),
        )
        if text:
            self.feedback_label.grid()
        else:
            self.feedback_label.grid_remove()

    def submit(self) -> None:
        master = self.master
        try:
            if master is None or not master.winfo_exists():
                return
        except TclError:
            return

        self.show_feedback("")

        if master.on_join_room_id():
            self.close(play_sound=False)

    def _handle_cancel(self) -> None:
        play_click()
        self.close(play_sound=False)

    def close(self, *, play_sound: bool = True) -> None:
        if play_sound:
            play_click()
        try:
            if self.winfo_exists():
                self.destroy()
        except TclError:
            pass


class OnlineSessionWindow(ctk.CTkToplevel):
    def __init__(
        self,
        master=None,
        *,
        mode: str,
        network_available: bool = True,
        restore_parent_on_close: bool = True,
        destroy_parent_on_close: bool = False,
    ):
        if mode not in {MODE_JOIN, MODE_CREATE}:
            raise ValueError(f"Mode online inconnu : {mode}")

        super().__init__(master)
        style_window(self)
        self.configure(fg_color=PALETTE["launcher_blend"])

        self.mode = mode
        self.network_available = bool(network_available)
        self._restore_parent_on_close = bool(restore_parent_on_close)
        self._destroy_parent_on_close = bool(destroy_parent_on_close)
        self.title(self._window_title())
        apply_window_icon(self, default=True, retry_after_ms=220)
        self.geometry("1160x760")
        enable_large_window(self, 960, 640, start_zoomed=True)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.client = OnlineClient()
        self.connected = False
        self.connecting = False
        self._shutdown_requested = False
        self._poll_after_id = None
        self._manual_refresh_feedback = False
        self._manual_refresh_started_at = 0.0
        self._manual_refresh_after_id = None
        self._pending_rooms = None
        self._room_created_join_after_id = None
        self._pending_created_room_id: str | None = None
        self._pending_join_room_id: str | None = None
        self._match_launch_after_id = None
        self._room_id_prompt_window = None

        self.host_var = ctk.StringVar(value=DEFAULT_ONLINE_HOST)
        self.port_var = ctk.StringVar(value=str(DEFAULT_ONLINE_PORT))
        self.pseudo_var = ctk.StringVar(value="")
        self.room_name_var = ctk.StringVar(value="Session Arena")
        self.max_players_var = ctk.StringVar(value=str(MIN_ONLINE_ROOM_PLAYERS))
        self.match_duration_var = ctk.StringVar(
            value=str(DEFAULT_ONLINE_MATCH_DURATION_SECONDS)
        )
        self.room_id_var = ctk.StringVar(value="")

        self.status_badge = None
        self.status_label = None
        self.rooms_meta_label = None
        self.rooms_scroll = None
        self.room_id_entry = None
        self.host_entry = None
        self.port_entry = None
        self.active_room_title_label = None
        self.active_room_meta_label = None
        self.active_room_state_label = None
        self.active_room_hint_label = None
        self.active_room_players_frame = None
        self.waiting_room_action_label = None
        self.pseudo_entry = None
        self.room_name_entry = None
        self.max_players_entry = None
        self.match_duration_entry = None
        self.btn_connect = None
        self.btn_disconnect = None
        self.btn_refresh = None
        self.btn_join_room_id = None
        self.btn_create = None
        self.btn_copy_room_id = None
        self.btn_ready = None
        self.btn_start_match = None
        self.match_running = False
        self.network_indicator = None
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
        self.current_room_match_duration_seconds: int | None = None
        self.current_room_host_pseudo: str | None = None
        self.local_slot: int | None = None
        self.local_team: str | None = None
        self.local_sprite_id: str | None = None
        self._known_rooms_by_id: dict[str, dict] = {}
        self.server_capabilities: dict[str, bool] = {}
        self._match_start_prompt_signature: tuple[str, tuple[str, ...], int] | None = (
            None
        )
        self._last_completed_match_signature: (
            tuple[str, tuple[str, ...], int] | None
        ) = None
        self._last_match_status_text: str | None = None
        self._pending_host_change_pseudo: str | None = None
        self._pending_match_room_notice: str | None = None
        self._room_preview_result_queue: "queue.Queue[tuple[int, list[dict] | None, str | None]]" = queue.Queue()
        self._room_preview_request_token = 0
        self._room_preview_manual_request_token: int | None = None
        self._room_preview_in_progress = False
        self._room_preview_poll_after_id = None

        self._build_ui()
        self._apply_disconnected_state(
            self._default_disconnected_message(),
            tone="neutral",
        )
        self._show_connection_required()
        present_window(self)
        _schedule_window_sound(self)

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
                "Les sessions visibles se chargent tout de suite, même si une "
                "partie est déjà lancée. Entre ton pseudo quand tu veux en "
                "rejoindre une."
            )
        return (
            "Saisis ton pseudo, définis ta session, choisis la durée de la "
            "partie, puis garde cette fenêtre ouverte pendant que les autres "
            "joueurs arrivent."
        )

    def _profile_hint_text(self) -> str:
        if self.mode == MODE_JOIN:
            return "Entre ton pseudo pour jouer en ligne."
        return "Entre ton pseudo pour ouvrir une session en ligne."

    def _connect_button_text(self) -> str:
        if self.connecting:
            return "Connexion..."
        if self.connected:
            return "Connecté"
        return "Se connecter"

    def _secondary_profile_button_text(self) -> str:
        if self.connected or self.connecting:
            return "Se déconnecter"
        return "Retour"

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
                "Les sessions publiques visibles apparaissent ici dès "
                "l'ouverture, y compris celles déjà en cours. Entre ton pseudo "
                "pour rejoindre un salon encore ouvert, ou utilise le bouton ID "
                "si l'hôte t'en a envoyé un."
            )
        return (
            "Choisis un nom, un nombre de joueurs et une durée. Après "
            "création, le salon d'attente s'ouvre à droite et le bouton "
            f"{START_MATCH_BUTTON_LABEL} se débloque quand la session "
            "est complète."
        )

    def _idle_room_title(self) -> str:
        if self.mode == MODE_JOIN:
            return "Aucune session rejointe"
        return "Aucune session créée"

    def _idle_room_meta(self) -> str:
        if self.mode == MODE_JOIN:
            return "Les sessions visibles se chargent à gauche avant la connexion."
        return "Crée ta session à gauche pour ouvrir ton propre salon d'attente."

    def _idle_room_hint(self) -> str:
        if self.mode == MODE_JOIN:
            return "Les joueurs de la session apparaîtront ici après la connexion."
        return "Les joueurs qui entrent dans ta session apparaîtront ici."

    def _idle_placeholder_title(self) -> str:
        if not self.connected and not self.connecting:
            return "Connexion requise"
        if self.mode == MODE_JOIN:
            return "En attente d'une session"
        return "En attente de création"

    def _idle_placeholder_body(self) -> str:
        if not self.connected and not self.connecting:
            if self.mode == MODE_JOIN:
                return (
                    "Entre ton pseudo pour rejoindre une session, ou reviens au menu."
                )
            return "Choisis Se connecter ou Retour."
        if self.mode == MODE_JOIN:
            return (
                "Choisis une session visible à gauche, puis rejoins-la, ou "
                "ouvre la saisie d'ID si l'hôte t'en a donné un."
            )
        return (
            "Entre ton pseudo, crée une session et garde cette fenêtre "
            "ouverte pendant l'arrivée des autres joueurs."
        )

    def _default_disconnected_message(self) -> str:
        return "Vous devez être connecté pour jouer en ligne."

    def _player_connection_issue(
        self,
        raw_message: str,
    ) -> tuple[str, str, str]:
        detailed_message = str(raw_message or "").strip()
        normalized = detailed_message.lower()

        if "pseudo" in normalized:
            return (
                "Pseudo requis",
                "Entre ton pseudo avant de te connecter.",
                "Entre ton pseudo avant de jouer en ligne.",
            )

        if any(
            token in normalized
            for token in (
                "injoignable",
                "indisponible",
                "introuvable",
                "refuse",
                "impossible",
                "invalide",
                "joignable",
                "repond plus",
            )
        ):
            return (
                "Serveur indisponible",
                (detailed_message or "Réessaie plus tard ou reviens au menu."),
                detailed_message or "Serveur indisponible.",
            )

        if any(
            token in normalized
            for token in (
                "perdue",
                "interrompue",
                "fermée",
                "fermee",
                "coupée",
                "coupee",
                "rompu",
            )
        ):
            return (
                "Connexion perdue",
                detailed_message or "Reconnecte-toi pour jouer en ligne.",
                detailed_message or "Connexion perdue.",
            )

        return (
            "Connexion requise",
            "Choisis Se connecter ou Retour.",
            self._default_disconnected_message(),
        )

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
        status_shell.grid_columnconfigure(0, weight=1)

        self.network_indicator = OnlineWifiIndicator(
            status_shell,
            available=self.network_available,
            host_getter=self.host_var.get,
            port_getter=self.port_var.get,
        )
        self.network_indicator.grid(row=0, column=0, sticky="e")

        self.status_badge = create_badge(
            status_shell,
            "Déconnecté",
            tone="neutral",
        )
        self.status_badge.grid(row=1, column=0, pady=(10, 0), sticky="e")

        self.status_label = ctk.CTkLabel(
            status_shell,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="right",
            wraplength=320,
        )
        self.status_label.grid(row=2, column=0, pady=(10, 0), sticky="e")

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
        card.grid_columnconfigure(0, weight=5)
        card.grid_columnconfigure(1, weight=4)

        create_badge(card, "Profil", tone="info").grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 10),
            sticky="w",
        )

        pseudo_shell = ctk.CTkFrame(card, fg_color="transparent")
        pseudo_shell.grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(12, 16),
            pady=(16, 10),
            sticky="nsew",
        )
        pseudo_shell.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            pseudo_shell,
            text="Ton pseudo",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(row=0, column=0, pady=(0, 4), sticky="w")

        self.pseudo_entry = ctk.CTkEntry(
            pseudo_shell,
            textvariable=self.pseudo_var,
        )
        style_entry(self.pseudo_entry)
        self.pseudo_entry.grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(
            card,
            text=self._profile_hint_text(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=380,
        ).grid(
            row=1,
            column=0,
            padx=16,
            pady=(0, 10),
            sticky="w",
        )

        self.btn_connect = create_button(
            card,
            self._connect_button_text(),
            self.on_connect,
            variant="accent",
            height=44,
        )
        self.btn_connect.grid(
            row=2,
            column=0,
            padx=(16, 8),
            pady=(8, 16),
            sticky="ew",
        )

        self.btn_disconnect = create_button(
            card,
            self._secondary_profile_button_text(),
            self.on_secondary_profile_action,
            variant="danger",
            height=44,
        )
        self.btn_disconnect.grid(
            row=2,
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
        actions_row.grid_columnconfigure(2, weight=0)

        self.rooms_meta_label = ctk.CTkLabel(
            actions_row,
            text="Connecte-toi pour charger les sessions.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
        )
        self.rooms_meta_label.grid(
            row=0,
            column=0,
            padx=(0, 12),
            sticky="w",
        )

        self.btn_join_room_id = create_button(
            actions_row,
            "Entrer un ID",
            self.open_room_id_prompt,
            variant="accent",
            width=150,
            height=40,
            font=TYPOGRAPHY["button_small"],
        )
        self.btn_join_room_id.grid(row=0, column=1, padx=(0, 8), sticky="e")

        self.btn_refresh = create_button(
            actions_row,
            "Actualiser",
            self.on_list_rooms,
            variant="secondary",
            width=150,
            height=40,
        )
        self.btn_refresh.grid(row=0, column=2, sticky="e")

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
        create_card.grid_rowconfigure(9, weight=1)

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
        self.match_duration_entry = self._build_option_field(
            create_card,
            row=7,
            label="Durée de la partie (secondes)",
            variable=self.match_duration_var,
            values=[str(value) for value in ONLINE_MATCH_DURATION_OPTIONS_SECONDS],
        )

        self.btn_create = create_button(
            create_card,
            "Créer la session",
            self.on_create_room,
            variant="primary",
            height=44,
        )
        self.btn_create.grid(
            row=9,
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
        waiting_card.grid_rowconfigure(6, weight=1)

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
            pady=(0, 6),
            sticky="w",
        )
        self.active_room_hint_label.grid_remove()

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

    def _can_use_join_room_controls(self) -> bool:
        return self.current_room_id is None and not self.match_running

    def open_room_id_prompt(self) -> None:
        if not self._can_use_join_room_controls():
            play_error()
            self._set_status(
                "Quitte le salon en cours avant d'ouvrir une autre jointure par ID.",
                tone="warning",
                badge_text="ID",
            )
            return

        prompt = self._room_id_prompt_window
        if prompt is not None:
            try:
                if prompt.winfo_exists():
                    play_click()
                    present_window(prompt)
                    prompt.focus_input()
                    return
            except TclError:
                pass

        prompt = RoomIdPromptWindow(self)
        self._room_id_prompt_window = prompt
        self.room_id_entry = prompt.entry
        prompt.set_interaction_state("normal")
        prompt.bind(
            "<Destroy>",
            lambda _event, ref=prompt: self._clear_room_id_prompt_reference(ref),
            add="+",
        )

    def _clear_room_id_prompt_reference(self, prompt) -> None:
        if self._room_id_prompt_window is prompt:
            self._room_id_prompt_window = None
        self.room_id_entry = None

    def _close_room_id_prompt(self) -> None:
        prompt = self._room_id_prompt_window
        if prompt is None:
            self.room_id_entry = None
            return

        try:
            if prompt.winfo_exists():
                prompt.close(play_sound=False)
        except TclError:
            pass
        finally:
            if self._room_id_prompt_window is prompt:
                self._room_id_prompt_window = None
            self.room_id_entry = None

    def _show_connection_required(self) -> None:
        self._set_status(
            self._default_disconnected_message(),
            tone="neutral",
            badge_text="Connexion requise",
        )

    def on_secondary_profile_action(self) -> None:
        if self.connected or self.connecting:
            self.on_disconnect()
            return

        play_click()
        self.shutdown(play_sound=False)

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
        if self._shutdown_requested:
            return

        try:
            if not self.winfo_exists():
                return
        except TclError:
            return

        self._poll_after_id = self.after(
            POLL_INTERVAL_MS,
            self._process_events,
        )

    def _should_poll_events(self) -> bool:
        return bool(
            self.connecting
            or self.connected
            or self.match_running
            or self.client.running
        )

    def _process_events(self) -> None:
        self._poll_after_id = None

        if self._shutdown_requested:
            return

        try:
            if not self.winfo_exists():
                return
        except TclError:
            return

        while not self._shutdown_requested:
            message = self.client.poll()
            if message is None:
                break
            self._handle_message(message)

        if self._shutdown_requested:
            return

        if self._should_poll_events():
            self._schedule_poll()

    def _room_preview_worker(
        self,
        request_token: int,
        host: str,
        port: int,
    ) -> None:
        try:
            rooms = fetch_public_room_directory(host=host, port=port)
            self._room_preview_result_queue.put((request_token, rooms, None))
        except (
            OnlineConnectionError,
            OnlineProtocolError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            self._room_preview_result_queue.put((request_token, None, str(error)))

    def _request_room_preview(self, *, manual: bool = False) -> None:
        if self.mode != MODE_JOIN:
            return

        if self.connecting or self.match_running or self.current_room_id is not None:
            return

        if self._room_preview_in_progress:
            return

        host = self.host_var.get().strip()
        if not host:
            self._set_rooms_meta("Adresse du serveur online indisponible.")
            return

        try:
            port = self._parse_port()
        except ValueError as error:
            if manual:
                play_error()
                self._set_status(str(error), tone="warning", badge_text="Sessions")
            self._set_rooms_meta("Port online invalide pour charger les sessions.")
            return

        self._room_preview_request_token += 1
        request_token = self._room_preview_request_token
        self._room_preview_in_progress = True

        if manual:
            self._room_preview_manual_request_token = request_token
            self._manual_refresh_feedback = True
            self._manual_refresh_started_at = monotonic()
            self._cancel_manual_refresh_timer()
            self._pending_rooms = None
            self._set_rooms_meta("Recherche des sessions visibles...")
            self._set_status(
                "Actualisation des sessions visibles en cours.",
                tone="info",
                badge_text="Sessions",
            )
        elif not self._known_rooms_by_id:
            self._set_rooms_meta("Recherche des sessions visibles...")

        worker = threading.Thread(
            target=self._room_preview_worker,
            args=(request_token, host, port),
            daemon=True,
        )
        worker.start()
        self._room_preview_poll_after_id = self.after(
            ROOM_PREVIEW_POLL_MS,
            self._drain_room_preview_results,
        )

    def _drain_room_preview_results(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except TclError:
            return

        received_current_result = False
        while True:
            try:
                request_token, rooms, error_message = (
                    self._room_preview_result_queue.get_nowait()
                )
            except queue.Empty:
                break

            if request_token != self._room_preview_request_token:
                continue

            received_current_result = True
            self._room_preview_in_progress = False
            manual_request = request_token == self._room_preview_manual_request_token
            if manual_request:
                self._room_preview_manual_request_token = None

            if self.connected or self.connecting:
                self._manual_refresh_feedback = False
                self._sync_controls_state()
                continue

            if error_message:
                self._apply_room_preview_error(error_message, manual=manual_request)
            else:
                self._apply_room_preview(rooms or [], manual=manual_request)

        if self._room_preview_in_progress and not received_current_result:
            self._room_preview_poll_after_id = self.after(
                ROOM_PREVIEW_POLL_MS,
                self._drain_room_preview_results,
            )
            return

        self._room_preview_poll_after_id = None

    def _apply_room_preview(self, rooms: list[dict], *, manual: bool) -> None:
        normalized_rooms = [room for room in rooms if isinstance(room, dict)]
        self._known_rooms_by_id = {
            str(room.get("room_id") or "").strip(): room
            for room in normalized_rooms
            if str(room.get("room_id") or "").strip()
        }
        self.last_refresh_text = self._current_time_label()
        self._refresh_current_room_from_directory()
        self._set_rooms_meta(
            f"{len(normalized_rooms)} session(s) visible(s) • aperçu {self.last_refresh_text}"
        )
        self._render_rooms(normalized_rooms)
        self._manual_refresh_feedback = False
        self._pending_rooms = None
        self._cancel_manual_refresh_timer()
        self._sync_controls_state()

        if manual:
            self._set_status(
                f"{len(normalized_rooms)} session(s) visible(s) à {self.last_refresh_text}.",
                tone="info",
                badge_text="Sessions",
            )

    def _apply_room_preview_error(self, error_message: str, *, manual: bool) -> None:
        self._manual_refresh_feedback = False
        self._pending_rooms = None
        self._cancel_manual_refresh_timer()
        self._sync_controls_state()

        if self._known_rooms_by_id:
            self._set_rooms_meta(
                "Aperçu temporairement indisponible. Dernière liste conservée."
            )
            self._render_rooms(self._ordered_rooms())
        else:
            self._set_rooms_meta("Aperçu des sessions indisponible pour le moment.")
            self._render_rooms([])

        if manual:
            self._set_status(
                error_message,
                tone="warning",
                badge_text="Sessions",
            )

    def _handle_message(self, message: dict) -> None:
        message_type = str(message.get("type") or "").strip().upper()

        if message_type == "WELCOME":
            self._update_server_capabilities(message.get("capabilities"))
            self._render_waiting_room_panel()
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
            pending_room_id = self._pending_join_room_id
            self._pending_join_room_id = None
            if pending_room_id:
                self._join_room_id(pending_room_id)
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

                match_duration_seconds = self._room_match_duration_seconds(room_info)
                if match_duration_seconds is None and self.mode == MODE_CREATE:
                    match_duration_seconds = self._selected_match_duration_or_none()

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
                    match_duration_seconds=match_duration_seconds,
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
                previous_room_id = self.current_room_id
                previous_state_code = self.current_room_state_code
                previous_players = list(self.current_room_players)
                previous_host_pseudo = self.current_room_host_pseudo
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
                if room_payload.get("match_duration_seconds") is not None:
                    room_info["match_duration_seconds"] = room_payload.get(
                        "match_duration_seconds"
                    )
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
                    match_duration_seconds=self._room_match_duration_seconds(room_info),
                    capacity=(
                        self._format_room_capacity(room_info)
                        or self._fallback_capacity_for_join()
                    ),
                    host_pseudo=host_pseudo,
                    is_active=True,
                )

                notice = self._build_room_update_notice(
                    room_id=room_id,
                    state_code=self._normalize_room_state_code(raw_state),
                    players=players,
                    previous_room_id=previous_room_id,
                    previous_state_code=previous_state_code,
                    previous_players=previous_players,
                    previous_host_pseudo=previous_host_pseudo,
                )
                if notice is not None:
                    text, tone, badge_text = notice
                    is_match_notice = (
                        previous_state_code == "in_game"
                        or self.current_room_state_code == "in_game"
                    )
                    if is_match_notice:
                        self._pending_match_room_notice = text
                    self._set_status(
                        text,
                        tone=tone,
                        badge_text=badge_text,
                    )
                    return

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
                    self._pending_host_change_pseudo = host_pseudo
            return

        if message_type == "ERROR":
            code = self._format_server_error(message)
            raw_code = str(message.get("code") or "").strip().upper()
            raw_got = str(message.get("got") or "").strip().upper()
            is_ready_compatibility_error = (
                raw_code == "UNKNOWN_TYPE" and raw_got == "SET_READY"
            )
            if is_ready_compatibility_error:
                play_alert()
                self.server_capabilities["ready_state"] = False
                self._render_waiting_room_panel()
            else:
                play_error()
            self._set_status(
                f"Erreur serveur : {code}",
                tone=("warning" if is_ready_compatibility_error else "danger"),
                badge_text=("Serveur" if is_ready_compatibility_error else "Erreur"),
            )
            return

        if message_type == "DISCONNECTED":
            play_alert()
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

    def _room_match_duration_seconds(self, room_info: dict) -> int | None:
        raw_duration = room_info.get("match_duration_seconds")
        try:
            match_duration_seconds = int(raw_duration)
        except (TypeError, ValueError):
            return None

        if match_duration_seconds <= 0:
            return None
        return match_duration_seconds

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

    def _format_room_duration(self, room_info: dict) -> str | None:
        match_duration_seconds = self._room_match_duration_seconds(room_info)
        if match_duration_seconds is None:
            return None
        return f"Durée : {match_duration_seconds} s"

    def _room_host_pseudo(self, room_info: dict) -> str | None:
        host_pseudo = str(room_info.get("host_pseudo") or "").strip()
        return host_pseudo or None

    def _room_badge(self, room_info: dict) -> tuple[str, str]:
        room_id = str(room_info.get("room_id") or "").strip()
        if room_id and room_id == self.current_room_id:
            return ("Ta session", "success")
        if self._normalize_room_state_code(room_info.get("state")) == "in_game":
            return ("En cours", "gold")
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
                    "Actualise plus tard, demande à un ami d'en créer une, "
                    "ou utilise un ID de session si tu en as reçu un."
                )
            else:
                title = "Connecte-toi pour voir les sessions"
                detail = (
                    "Dès que tu es connecté, les sessions publiques déjà "
                    "ouvertes apparaissent ici, et tu peux aussi rejoindre "
                    "une session en collant son ID."
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
        duration_text = self._format_room_duration(room_info)
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

        detail_parts = [state_text, capacity_text]
        if duration_text:
            detail_parts.append(duration_text)

        ctk.CTkLabel(
            card,
            text=" • ".join(detail_parts),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
            wraplength=620,
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
        if not self.connected and not is_current and self._room_is_joinable(room_info):
            button_text = "Entre ton pseudo"
        elif (
            self._normalize_room_state_code(room_info.get("state")) == "in_game"
            and not is_current
        ):
            button_text = "En cours"
        elif (
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
            self.active_room_players_frame.grid_rowconfigure(0, weight=1)
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
                text="",
                text_color=PALETTE["text_soft"],
            )
            self.active_room_hint_label.grid_remove()
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
                sticky="nsew",
            )
            placeholder.grid_columnconfigure(0, weight=1)
            placeholder.grid_rowconfigure(2, weight=1)

            ctk.CTkLabel(
                placeholder,
                text=self._idle_placeholder_title(),
                font=TYPOGRAPHY["subtitle"],
                text_color=PALETTE["text"],
            ).grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")

            ctk.CTkLabel(
                placeholder,
                text=self._idle_placeholder_body(),
                font=TYPOGRAPHY["body"],
                text_color=PALETTE["text_soft"],
                justify="left",
                wraplength=340,
            ).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
            self._refresh_waiting_room_actions()
            return

        self.active_room_players_frame.grid_rowconfigure(0, weight=0)
        self.active_room_hint_label.grid()

        room_title = self.current_room_name or self.current_room_id
        room_meta_parts = [f"ID : {self.current_room_id}"]
        if self.current_room_capacity:
            room_meta_parts.append(self.current_room_capacity)
        if self.current_room_match_duration_seconds is not None:
            room_meta_parts.append(
                f"Durée : {self.current_room_match_duration_seconds} s"
            )
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

        player_status_text, player_status_color = self._player_status_text_and_color(
            is_ready_player
        )

        ctk.CTkLabel(
            card,
            text=player_status_text,
            font=TYPOGRAPHY["small_bold"],
            text_color=player_status_color,
            justify="left",
        ).grid(row=2, column=0, padx=14, pady=(0, 14), sticky="w")

    def _apply_rooms_update(self, rooms: list[dict]) -> None:
        self.last_refresh_text = self._current_time_label()
        self._set_rooms_meta(
            (f"{len(rooms)} session(s) visible(s) • synchro {self.last_refresh_text}")
        )
        self._render_rooms(rooms)
        self._manual_refresh_feedback = False
        self._pending_rooms = None
        self._cancel_manual_refresh_timer()
        self._sync_controls_state()
        self._set_status(
            f"{len(rooms)} session(s) visible(s) à {self.last_refresh_text}.",
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
        match_duration_seconds: int | None = None,
        capacity: str | None,
        host_pseudo: str | None,
        is_active: bool,
    ) -> None:
        previous_room_id = self.current_room_id
        if not is_active or room_id != previous_room_id:
            self._clear_post_match_feedback()
            self._pending_host_change_pseudo = None

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
        if not is_active:
            self.current_room_match_duration_seconds = None
        elif match_duration_seconds is not None:
            self.current_room_match_duration_seconds = match_duration_seconds
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

    def _format_departed_players_notice(
        self,
        departed_players: list[str],
        *,
        in_game: bool,
    ) -> str:
        context = "la joute" if in_game else "la session"
        if len(departed_players) == 1:
            return f"{departed_players[0]} a quitté {context}."
        return f"{', '.join(departed_players)} ont quitté {context}."

    def _build_room_update_notice(
        self,
        *,
        room_id: str | None,
        state_code: str | None,
        players: list[str],
        previous_room_id: str | None,
        previous_state_code: str | None,
        previous_players: list[str],
        previous_host_pseudo: str | None,
    ) -> tuple[str, str, str] | None:
        if room_id is None or room_id != previous_room_id:
            return None

        notice_parts: list[str] = []
        tone = "info"
        badge_text = "Update"
        match_context = state_code == "in_game" or previous_state_code == "in_game"

        departed_players = [
            player_name
            for player_name in previous_players
            if player_name not in players
        ]
        if departed_players:
            notice_parts.append(
                self._format_departed_players_notice(
                    departed_players,
                    in_game=match_context,
                )
            )
            tone = "warning"
            badge_text = "Match" if match_context else "Salon"

        next_host_pseudo = self._pending_host_change_pseudo
        self._pending_host_change_pseudo = None
        if next_host_pseudo and next_host_pseudo != previous_host_pseudo:
            local_pseudo = self.pseudo_var.get().strip()
            if local_pseudo and next_host_pseudo == local_pseudo:
                notice_parts.append("Tu es maintenant l'hôte.")
            else:
                notice_parts.append(f"Nouvel hôte : {next_host_pseudo}.")
            if badge_text == "Update":
                badge_text = "Hôte"

        if not notice_parts:
            return None

        return (" ".join(notice_parts), tone, badge_text)

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
            match_duration_seconds=(
                self._room_match_duration_seconds(room_info)
                or self.current_room_match_duration_seconds
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
        self._pending_match_room_notice = None
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

    def _selected_match_duration_or_none(self) -> int | None:
        raw_value = self.match_duration_var.get().strip()
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

    def _completed_match_signature(
        self,
    ) -> tuple[str, tuple[str, ...], int] | None:
        if self.current_room_id is None:
            return None
        if self.current_room_max_players is None:
            return None
        if not self.current_room_players:
            return None

        return (
            self.current_room_id,
            tuple(self.current_room_players),
            self.current_room_max_players,
        )

    def _restore_waiting_room_after_match(self) -> None:
        if self.current_room_id is None:
            return

        room_id = self.current_room_id
        room_info = dict(self._known_rooms_by_id.get(room_id, {}))
        room_info["room_id"] = room_id
        room_info["state"] = "lobby"
        room_info["players"] = self.current_room_player_count
        if self.current_room_max_players is not None:
            room_info["max_players"] = self.current_room_max_players
        if self.current_room_host_pseudo is not None:
            room_info["host_pseudo"] = self.current_room_host_pseudo
        if self.current_room_name:
            room_info["name"] = self.current_room_name
        self._known_rooms_by_id[room_id] = room_info

        self._set_current_room_status(
            room_id=room_id,
            room_name=(
                str(room_info.get("name") or "").strip() or self.current_room_name
            ),
            state_code="lobby",
            state_text=self._format_room_state("lobby"),
            players=list(self.current_room_players),
            ready_players=[],
            max_players=self._room_max_players(room_info),
            capacity=(
                self._format_room_capacity(room_info) or self.current_room_capacity
            ),
            host_pseudo=(
                self._room_host_pseudo(room_info) or self.current_room_host_pseudo
            ),
            is_active=True,
        )

    def _resume_after_match(self, match_summary: dict) -> None:
        for message in match_summary.get("deferred_messages", []):
            self._handle_message(message)

        disconnect_message = str(match_summary.get("disconnect_message") or "").strip()
        end_message = match_summary.get("end_message") or {}
        post_match_status = None
        room_notice = str(self._pending_match_room_notice or "").strip()
        self._pending_match_room_notice = None

        if end_message:
            post_match_status = self._format_post_match_status(end_message)
            if room_notice:
                post_match_status = f"{post_match_status} {room_notice}"
            self._last_match_status_text = post_match_status
            self._last_completed_match_signature = self._completed_match_signature()
            self._restore_waiting_room_after_match()
            self._set_status(
                post_match_status,
                tone="success",
                badge_text="Fin",
            )

        if disconnect_message:
            if room_notice and not post_match_status:
                disconnect_message = f"{room_notice} {disconnect_message}"
            if post_match_status:
                disconnect_message = f"{post_match_status} {disconnect_message}"
            self.client.disconnect()
            self._apply_disconnected_state(disconnect_message, tone="danger")
            return

        if self.client.running:
            if self._poll_after_id is None:
                self._schedule_poll()
            self._request_rooms_refresh()
        else:
            self.client.disconnect()
            disconnect_text = "Connexion interrompue à la fin du match."
            if room_notice and not post_match_status:
                disconnect_text = f"{room_notice} {disconnect_text}"
            if post_match_status:
                disconnect_text = f"{post_match_status} {disconnect_text}"
            self._apply_disconnected_state(
                disconnect_text,
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

    def _update_server_capabilities(self, raw_capabilities: object) -> None:
        if not isinstance(raw_capabilities, dict):
            self.server_capabilities = {}
            return

        self.server_capabilities = {
            str(name).strip().lower(): bool(value)
            for name, value in raw_capabilities.items()
            if str(name).strip()
        }

    def _ready_state_capability(self) -> bool | None:
        capability = self.server_capabilities.get("ready_state")
        if isinstance(capability, bool):
            return capability
        return None

    def _supports_ready_state(self) -> bool:
        return self._ready_state_capability() is not False

    def _player_status_text_and_color(
        self,
        is_ready_player: bool,
    ) -> tuple[str, str]:
        if not self._supports_ready_state():
            return ("Statut : connecté", PALETTE["cyan"])
        if is_ready_player:
            return ("Statut : prêt", PALETTE["success"])
        return ("Statut : en attente", PALETTE["text_muted"])

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
        if not self._supports_ready_state():
            return True
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
            if not self._supports_ready_state():
                return (
                    "Ce serveur ne gère pas le prêt. Tu peux lancer le jeu "
                    "dès que la session est complète."
                )
            if self._can_start_current_match():
                return "Tous les joueurs sont prêts. Tu peux lancer le jeu."
            return (
                f"En attente des prêts {self._current_ready_count()}/"
                f"{self.current_room_player_count} avant le départ."
            )

        if not self._supports_ready_state():
            if self.current_room_host_pseudo:
                return (
                    "Ce serveur ne gère pas le prêt. En attente que "
                    f"{self.current_room_host_pseudo} lance le jeu."
                )
            return "Ce serveur ne gère pas le prêt. En attente que l'hôte lance le jeu."

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
        elif not self._supports_ready_state():
            ready_text = "Prêt indisponible"
            ready_state = "disabled"
            if self._is_local_host():
                button_text = START_MATCH_BUTTON_LABEL
                button_state = (
                    "normal" if self._can_start_current_match() else "disabled"
                )
            else:
                button_text = "Lancement réservé à l'hôte"
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
        self.btn_disconnect.configure(
            text=self._secondary_profile_button_text(),
            state=("normal" if not self.match_running else disconnect_state),
        )
        self.btn_copy_room_id.configure(state=copy_state)
        self._refresh_waiting_room_actions()

        if self.mode == MODE_JOIN:
            prompt_state = (
                "normal" if self._can_use_join_room_controls() else "disabled"
            )
            refresh_state = (
                "normal"
                if not self.connecting
                and not self.match_running
                and not self._manual_refresh_feedback
                and not self._room_preview_in_progress
                and self.current_room_id is None
                else "disabled"
            )
            if self.btn_refresh is not None:
                self.btn_refresh.configure(state=refresh_state)
            if self.btn_join_room_id is not None:
                self.btn_join_room_id.configure(state=prompt_state)
            prompt = self._room_id_prompt_window
            if prompt is not None:
                prompt.set_interaction_state(prompt_state)
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
        if self.match_duration_entry is not None:
            self.match_duration_entry.configure(state=room_action_state)
        if self.btn_create is not None:
            self.btn_create.configure(state=room_action_state)

    def _apply_disconnected_state(
        self,
        message: str,
        *,
        tone: str,
    ) -> None:
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except TclError:
                pass
            self._poll_after_id = None

        self.connected = False
        self.connecting = False
        self.match_running = False
        self._manual_refresh_feedback = False
        self._pending_rooms = None
        self._pending_created_room_id = None
        self._pending_join_room_id = None
        if self.mode != MODE_JOIN:
            self._known_rooms_by_id = {}
        self.server_capabilities = {}
        self.local_slot = None
        self.local_team = None
        self.local_sprite_id = None
        self._match_start_prompt_signature = None
        self._room_preview_in_progress = False
        self._room_preview_manual_request_token = None
        self._clear_post_match_feedback()
        self._cancel_room_preview_poll()
        self._cancel_manual_refresh_timer()
        self._cancel_room_created_join_timer()
        self._cancel_match_launch_timer()
        self._close_room_id_prompt()
        self._clear_current_room(message)
        if self.mode == MODE_JOIN:
            if self._known_rooms_by_id:
                self._render_rooms(self._ordered_rooms())
            self._set_rooms_meta("Recherche des sessions visibles...")
        self._sync_controls_state()
        self._set_status(message, tone=tone, badge_text="Déconnecté")
        if self.mode == MODE_JOIN:
            self._request_room_preview()

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

    def _parse_match_duration(self) -> int:
        raw_value = self.match_duration_var.get().strip()
        try:
            match_duration_seconds = int(raw_value)
        except ValueError as error:
            raise ValueError(
                "La durée de la partie doit être un entier valide."
            ) from error

        if match_duration_seconds not in ONLINE_MATCH_DURATION_OPTIONS_SECONDS:
            raise ValueError(
                "La durée de la partie doit correspondre à une durée proposée."
            )

        return match_duration_seconds

    def _send_message(self, payload: dict, *, action_label: str) -> bool:
        _ = action_label
        try:
            self.client.send(payload)
        except OnlineConnectionError as error:
            play_error()
            title, dialog_text, status_text = self._player_connection_issue(str(error))
            self.client.disconnect()
            self._apply_disconnected_state(status_text, tone="danger")
            messagebox.showerror(
                title,
                dialog_text,
            )
            return False

        return True

    def on_connect(self) -> None:
        if self.connected or self.connecting:
            return

        play_transition()
        host = self.host_var.get().strip()
        pseudo = self.pseudo_var.get().strip()

        try:
            port = self._parse_port()
            self.client.connect(host, port, pseudo)
        except (OnlineConnectionError, ValueError) as error:
            play_error()
            title, dialog_text, status_text = self._player_connection_issue(str(error))
            self._apply_disconnected_state(status_text, tone="danger")
            messagebox.showerror(
                title,
                dialog_text,
            )
            return

        self.connecting = True
        if self._poll_after_id is None:
            self._schedule_poll()
        self._sync_controls_state()
        self._set_status(
            "Connexion au serveur online en cours.",
            tone="warning",
            badge_text="Connexion...",
        )

    def on_disconnect(self) -> None:
        play_click()
        self.client.disconnect()
        self._apply_disconnected_state(
            self._default_disconnected_message(),
            tone="neutral",
        )
        self._show_connection_required()

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
        self._set_rooms_meta("Synchronisation des sessions visibles en cours...")
        self._set_status(
            "Actualisation des sessions demandée au serveur online.",
            tone="info",
            badge_text="Refresh",
        )

    def on_list_rooms(self) -> None:
        if self.connecting:
            self._set_status(
                "Patiente pendant la connexion avant d'actualiser les sessions.",
                tone="warning",
                badge_text="Sessions",
            )
            return

        play_click()
        if not self.connected:
            self._request_room_preview(manual=True)
            return

        self._request_rooms_refresh(manual=True)

    def on_join_room_id(self) -> bool:
        prompt_window = self._room_id_prompt_window
        room_id = self.room_id_var.get().strip()
        if not room_id:
            play_error()
            self._set_status(
                "Entre l'ID d'une session avant de l'envoyer.",
                tone="warning",
                badge_text="ID",
            )
            if prompt_window is not None:
                prompt_window.show_feedback(
                    "Entre d'abord l'ID de session à rejoindre.",
                    tone="warning",
                )
            if self.room_id_entry is not None:
                try:
                    self.room_id_entry.focus_force()
                except TclError:
                    pass
            return False

        self.room_id_var.set(room_id)

        if self.current_room_id is not None:
            play_error()
            self._set_status(
                "Déconnecte-toi du salon actuel avant de rejoindre un autre ID.",
                tone="warning",
                badge_text="ID",
            )
            if prompt_window is not None:
                prompt_window.show_feedback(
                    "Déconnecte-toi d'abord du salon actuel.",
                    tone="warning",
                )
            return False

        if self.connected:
            if not self._join_room_id(room_id):
                return False

            play_transition()
            self._pending_join_room_id = None
            self._close_room_id_prompt()
            return True

        pseudo = self.pseudo_var.get().strip()
        if not pseudo:
            play_error()
            self._set_status(
                "Entre d'abord ton pseudo avant d'utiliser un ID de session.",
                tone="warning",
                badge_text="Pseudo",
            )
            if prompt_window is not None:
                prompt_window.show_feedback(
                    "Renseigne d'abord ton pseudo dans le panneau Profil.",
                    tone="warning",
                )
            if self.pseudo_entry is not None:
                try:
                    self.pseudo_entry.focus_force()
                except TclError:
                    pass
            return False

        self._pending_join_room_id = room_id

        if self.connecting:
            play_click()
            self._set_status(
                f"ID {room_id} mémorisé. La jointure partira après la connexion.",
                tone="info",
                badge_text="ID",
            )
            self._close_room_id_prompt()
            return True

        self.on_connect()
        if not self.connected and not self.connecting:
            self._pending_join_room_id = None
            return False

        self._set_status(
            f"Connexion lancée. La demande pour {room_id} partira ensuite.",
            tone="info",
            badge_text="ID",
        )
        self._close_room_id_prompt()
        return True

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

        play_click()
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
        if not self.connected:
            play_error()
            self._show_connection_required()
            return

        room_name = self.room_name_var.get().strip() or "Session Arena"

        try:
            max_players = self._parse_max_players()
            match_duration_seconds = self._parse_match_duration()
        except ValueError as error:
            play_error()
            messagebox.showerror("Paramètres invalides", str(error))
            return

        if not self._send_message(
            {
                "type": "CREATE_ROOM",
                "name": room_name,
                "max_players": max_players,
                "match_duration_seconds": match_duration_seconds,
            },
            action_label="créer la session",
        ):
            return

        play_transition()
        self._set_status(
            f"Création de la session {room_name} en cours ({match_duration_seconds} s).",
            tone="info",
            badge_text="Création",
        )

    def _cancel_room_preview_poll(self) -> None:
        if self._room_preview_poll_after_id is None:
            return

        try:
            self.after_cancel(self._room_preview_poll_after_id)
        except TclError:
            pass

        self._room_preview_poll_after_id = None

    def on_toggle_ready(self) -> None:
        if not self.connected:
            play_error()
            self._show_connection_required()
            return

        if self.current_room_id is None or self.current_room_state_code != "lobby":
            return

        if not self._supports_ready_state():
            play_alert()
            self._set_status(
                "Ce serveur online ne gère pas le bouton prêt.",
                tone="warning",
                badge_text="Serveur",
            )
            return

        next_ready_state = not self._is_local_ready()
        action_label = "mettre à jour le statut prêt"
        if not self._send_message(
            {"type": "SET_READY", "ready": next_ready_state},
            action_label=action_label,
        ):
            return

        play_click()
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
        if not self.connected:
            play_error()
            self._show_connection_required()
            return

        if not self._can_start_current_match():
            return

        if not self._send_message(
            {"type": "START_MATCH"},
            action_label="lancer le jeu",
        ):
            return

        play_transition()
        self._clear_post_match_feedback()
        self._set_status(
            "Demande de lancement du jeu envoyée au serveur online.",
            tone="warning",
            badge_text="Départ",
        )

    def shutdown(
        self,
        *,
        restore_parent: bool | None = None,
        destroy_parent: bool | None = None,
        play_sound: bool = True,
    ) -> None:
        parent = self.master
        self._shutdown_requested = True

        if play_sound:
            play_click()

        if restore_parent is None:
            restore_parent = self._restore_parent_on_close
        if destroy_parent is None:
            destroy_parent = self._destroy_parent_on_close

        if self.network_indicator is not None:
            self.network_indicator.shutdown()

        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except TclError:
                pass
            self._poll_after_id = None

        self._cancel_room_preview_poll()
        self._cancel_manual_refresh_timer()
        self._cancel_room_created_join_timer()
        self._cancel_match_launch_timer()
        self._close_room_id_prompt()
        self.client.disconnect()
        self.destroy()

        if not restore_parent and not destroy_parent:
            return

        if restore_parent:
            try:
                if parent is not None and parent.winfo_exists():
                    present_window(parent)
            except TclError:
                pass
            return

        try:
            if parent is not None and parent.winfo_exists():
                parent.destroy()
        except TclError:
            pass


def run_online_lobby() -> None:
    apply_theme_settings()

    app = ctk.CTk()
    app.withdraw()

    network_available = probe_online_service()
    if not network_available:
        messagebox.showwarning(
            ONLINE_ENTRY_REQUIRED_TITLE,
            ONLINE_ENTRY_REQUIRED_MESSAGE,
            parent=app,
        )
        try:
            if app.winfo_exists():
                app.destroy()
        except TclError:
            pass
        return

    window = OnlineLobbyWindow(app, network_available=network_available)

    def close_all() -> None:
        window.shutdown()
        try:
            if app.winfo_exists():
                app.destroy()
        except TclError:
            pass

    window.protocol("WM_DELETE_WINDOW", close_all)
    app.mainloop()
