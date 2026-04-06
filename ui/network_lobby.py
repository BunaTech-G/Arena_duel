import threading
import customtkinter as ctk
import time
import json
import os

from network.client import NetworkClient
from network.messages import ASSIGN_SLOT, LOBBY_STATE, START, ERROR, DISCONNECTED, HISTORY_DATA
from game.net_match_window import run_network_match
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
from game.match_text import format_compact_scoreline, format_roster_entry, format_team_assignment
from network.net_utils import get_local_lan_ip
from runtime_utils import resource_path, load_runtime_config
from ui.history_view import HistoryView
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    enable_large_window,
    load_ctk_image,
    style_window,
    style_frame,
    style_textbox,
    create_button,
    create_badge,
    update_badge,
)



class NetworkLobbyView(ctk.CTkToplevel):
    def __init__(self, parent, default_server_ip=None, server_port=None, host_mode=False):
        super().__init__(parent)
        style_window(self)

        runtime_config = load_runtime_config()

        self.title("Arena Duel - Hall des bastions")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except Exception:
            pass
        self.geometry("1240x820")
        enable_large_window(self, 1080, 760)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.protocol("WM_DELETE_WINDOW", self.shutdown)
        
        self.client = None
        self.running = False
        self.history_request_pending = False
        self.server_port = int(server_port or runtime_config.get("tcp_port", 5000))

        self.config_file = "client_lan_config.json"
        self.detected_local_ip = get_local_lan_ip()
        self.default_server_ip = default_server_ip
        self.host_mode = host_mode
        self.lobby_preview_image = load_ctk_image(
            "assets",
            "backgrounds",
            "launcher_sanctum_bg.png",
            size=(240, 126),
            fallback_label="sanctum",
        )
        self.lobby_portrait_image = load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(62, 62),
            fallback_label="mascot",
        )

        self.config_file = "client_lan_config.json"
        self.detected_local_ip = get_local_lan_ip()

        self.my_slot = None
        self.my_team = None
        self.my_name = None
        self.ready_state = False
        self.match_running = False

        self._build_ui()
        self._refresh_mode_label()
        try:
            start_menu_music()
        except Exception:
            pass
        if self.host_mode:
            self.info_label.configure(
                text=(
                    "Le bastion est pret. Copie l'invitation du hall puis inscris ton nom de combattant pour ouvrir la joute."
                )
            )
        else:
            self.info_label.configure(
                text="Saisis l'invitation transmise par le gardien du hall et ton nom de combattant pour rejoindre la joute."
            )

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        viewport = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        viewport.grid(row=0, column=0, sticky="nsew")
        viewport.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(viewport, corner_radius=20)
        style_frame(header, tone="panel", border_color=PALETTE["cyan_dim"])
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
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
        self.mode_badge.grid(row=0, column=0, padx=18, pady=(16, 6), sticky="e")

        subtitle = ctk.CTkLabel(
            header,
            text="Rassemble les combattants, veille sur l'appel du bastion et ouvre la joute des que chacun a leve son etendard.",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=760,
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
        self.mode_label.grid(row=2, column=0, padx=18, pady=(0, 16), sticky="w")

        preview_card = ctk.CTkFrame(header, corner_radius=18)
        style_frame(preview_card, tone="panel_soft", border_color=PALETTE["cyan_dim"])
        preview_card.grid(row=0, column=1, rowspan=3, padx=(10, 18), pady=16, sticky="nsew")
        preview_card.grid_columnconfigure(1, weight=1)

        preview_image = ctk.CTkLabel(preview_card, text="", image=self.lobby_preview_image)
        preview_image.grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 10), sticky="ew")

        portrait = ctk.CTkLabel(preview_card, text="", image=self.lobby_portrait_image)
        portrait.grid(row=1, column=0, padx=(12, 10), pady=(0, 12), sticky="w")

        preview_title = ctk.CTkLabel(
            preview_card,
            text="Veille du sanctum",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        preview_title.grid(row=1, column=1, padx=(0, 12), pady=(2, 0), sticky="sw")

        preview_hint = ctk.CTkLabel(
            preview_card,
            text="Tableau vivant du sanctum\net du hall",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
        )
        preview_hint.grid(row=1, column=1, padx=(0, 12), pady=(0, 12), sticky="nw")

        connection_panel = ctk.CTkFrame(viewport, corner_radius=18)
        style_frame(connection_panel, tone="panel", border_color=PALETTE["border"])
        connection_panel.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        connection_panel.grid_columnconfigure(0, weight=1)
        connection_panel.grid_columnconfigure(1, weight=1)

        connection_title = ctk.CTkLabel(
            connection_panel,
            text="Entree du hall",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        connection_title.grid(row=0, column=0, padx=18, pady=(16, 6), sticky="w")

        self.local_ip_label = ctk.CTkLabel(
            connection_panel,
            text=(
                "Invitation du bastion prete a etre partagee"
                if self.host_mode
                else "Entre l'invitation transmise par le gardien"
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            wraplength=380,
            justify="right",
        )
        self.local_ip_label.grid(row=0, column=1, padx=18, pady=(16, 6), sticky="e")

        self.ip_entry = ctk.CTkEntry(
            connection_panel,
            placeholder_text="Invitation du bastion",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        self.ip_entry.grid(row=1, column=0, padx=(18, 8), pady=(0, 10), sticky="ew")

        default_ip = self._load_saved_server_ip()
        if default_ip:
            self.ip_entry.insert(0, default_ip)
        elif self.host_mode:
            self.ip_entry.insert(0, self.detected_local_ip)

        self.name_entry = ctk.CTkEntry(
            connection_panel,
            placeholder_text="Nom de combattant",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        self.name_entry.grid(row=1, column=1, padx=(8, 18), pady=(0, 10), sticky="ew")

        action_row = ctk.CTkFrame(connection_panel, fg_color="transparent")
        action_row.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="ew")
        for column in range(5):
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
            self.copy_invite_btn.grid(row=0, column=action_column, padx=(0, 8), sticky="ew")
            action_column += 1
        else:
            self.copy_invite_btn = None

        self.use_local_ip_btn = create_button(
            action_row,
            "Jouer sur ce poste",
            self._use_loopback_ip,
            variant="ghost",
            font=TYPOGRAPHY["button_small"],
            height=40,
        )
        self.use_local_ip_btn.grid(row=0, column=action_column, padx=(0, 8), sticky="ew")
        action_column += 1

        self.connect_btn = create_button(
            action_row,
            "Rejoindre le hall",
            self._connect,
            variant="accent",
            height=40,
        )
        self.connect_btn.grid(row=0, column=action_column, padx=8, sticky="ew")
        action_column += 1

        self.ready_btn = create_button(
            action_row,
            "Se déclarer prêt",
            self._toggle_ready,
            variant="success",
            height=40,
            state="disabled",
        )
        self.ready_btn.grid(row=0, column=action_column, padx=8, sticky="ew")
        action_column += 1

        self.history_btn = create_button(
            action_row,
            "Consulter les chroniques",
            self._request_history,
            variant="secondary",
            height=40,
            state="disabled",
        )
        self.history_btn.grid(row=0, column=action_column, padx=(8, 0), sticky="ew")

        lobby_panel = ctk.CTkFrame(viewport, corner_radius=18)
        style_frame(lobby_panel, tone="panel", border_color=PALETTE["border"])
        lobby_panel.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        lobby_panel.grid_columnconfigure(0, weight=1)

        lobby_title = ctk.CTkLabel(
            lobby_panel,
            text="Compagnons du hall",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        lobby_title.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self.lobby_box = ctk.CTkTextbox(lobby_panel, height=220)
        self.lobby_box.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="nsew")
        style_textbox(self.lobby_box)
        self.lobby_box.configure(state="disabled")

        info_panel = ctk.CTkFrame(viewport, corner_radius=18)
        style_frame(info_panel, tone="panel_soft", border_color=PALETTE["border"])
        info_panel.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
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
            wraplength=920,
            justify="left",
        )
        self.info_label.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="w")

    def _refresh_mode_label(self):
        if self.host_mode:
            if self.client and self.client.running:
                text = "Hall tenu par le gardien · joute prete · chroniques gardees ici"
                update_badge(self.mode_badge, "Gardien", "gold")
            else:
                text = "Bastion pret · hall en veille"
                update_badge(self.mode_badge, "Gardien", "warning")
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

        self.lobby_box.configure(state="normal")
        self.lobby_box.delete("1.0", "end")
        self.lobby_box.configure(state="disabled")
        self._refresh_mode_label()

    def _handle_disconnect(self, message: str):
        try:
            play_alert()
        except Exception:
            pass

        self.running = False
        self.history_request_pending = False

        if self.client:
            try:
                self.client.close()
            except Exception:
                pass

        self.client = None
        self.deiconify()
        self.lift()
        self.focus_force()
        self._reset_lobby_state()
        self.info_label.configure(text=message)

    def _load_saved_server_ip(self) -> str:
        if self.default_server_ip:
            return self.default_server_ip

        try:
            if not os.path.exists(self.config_file):
                return ""

            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            ip = data.get("last_server_ip", "").strip()
            return ip

        except Exception:
            return ""

    def _save_server_ip(self, ip: str):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"last_server_ip": ip}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _use_loopback_ip(self):
        try:
            play_click()
        except Exception:
            pass

        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, "127.0.0.1")

    def _copy_bastion_address(self):
        try:
            play_click()
        except Exception:
            pass

        try:
            self.clipboard_clear()
            self.clipboard_append(self.detected_local_ip)
            self.info_label.configure(text="Invitation du bastion copiee dans le presse-papiers.")
        except Exception:
            self.info_label.configure(text=f"Partage cette invitation du bastion : {self.detected_local_ip}")

    # =========================
    # Connexion réseau
    # =========================
    def _connect(self):
        try:
            play_transition()
        except Exception:
            pass

        ip = self.ip_entry.get().strip()
        name = self.name_entry.get().strip()

        if not ip or not name:
            play_error()
            self.info_label.configure(text="Renseigne l'invitation du bastion et un nom de combattant avant d'ouvrir le hall.")
            return

        self.client = NetworkClient()

        try:
            self.client.connect(ip, self.server_port, name)
        except Exception as e:
            play_alert()
            self.info_label.configure(text=f"Impossible de rejoindre le hall du bastion : {e}")
            return

        self.info_label.configure(text=f"Lien scelle pour {name}. Le hall prepare ton entree dans la joute.")
        self.connect_btn.configure(state="disabled")
        self.ready_btn.configure(state="normal")
        self.history_btn.configure(state="normal")
        self.ip_entry.configure(state="disabled")
        self.name_entry.configure(state="disabled")
        self.use_local_ip_btn.configure(state="disabled")

        self.my_name = name
        self._save_server_ip(ip)

        self._start_network_thread()
        self._refresh_mode_label()

        if self.host_mode:
            self.info_label.configure(
                text=(
                    f"{name} veille sur le bastion. Les chroniques du hall seront gardees sur ce poste."
                )
            )
        else:
            self.info_label.configure(
                text=(
                    f"{name} a rejoint le hall. Les chroniques seront lues depuis le bastion rejoint."
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
                except Exception:
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
            self._update_lobby(msg["players"])

        elif msg_type == START:
            if self.match_running:
                return
            self.info_label.configure(text="Tous les combattants sont prêts. La joute s'ouvre...")
            self.ready_btn.configure(state="disabled")
            self.history_btn.configure(state="disabled")
            self.after(50, self._launch_match)

        elif msg_type == HISTORY_DATA:
            self.history_request_pending = False
            if self.client and self.client.running:
                self.history_btn.configure(state="normal")

            if not msg.get("ok", False):
                play_error()
                self.info_label.configure(text=msg.get("message", "Les chroniques du hall sont indisponibles pour le moment."))
                return

            source_label = "Chroniques du hall local" if self.host_mode else (
                "Chroniques du hall rejoint"
            )
            self.info_label.configure(text=f"{len(msg.get('rows', []))} chronique(s) recue(s) depuis le hall.")
            HistoryView(
                self,
                history_rows=msg.get("rows", []),
                source_label=source_label,
                allow_refresh=False,
            )

        elif msg_type == ERROR:
            play_error()
            self.info_label.configure(text=msg.get("message", "Le hall a signale une erreur."))

        elif msg_type == DISCONNECTED:
            self._handle_disconnect(msg.get("message", "Connexion fermée."))

    def _start_network_thread(self):
        self.running = True
        threading.Thread(target=self._network_loop, daemon=True).start()

    # =========================
    # Lobby UI
    # =========================
    def _update_lobby(self, players):
        self.lobby_box.configure(state="normal")
        self.lobby_box.delete("1.0", "end")

        for p in players:
            line = format_roster_entry(p["slot"], p["name"], p["team"], p["ready"])
            self.lobby_box.insert("end", line + "\n")

        self.lobby_box.configure(state="disabled")

    # =========================
    # Ready
    # =========================
    def _toggle_ready(self):
        try:
            play_select()
        except Exception:
            pass

        self.ready_state = not self.ready_state
        self.client.send_ready(self.ready_state)

        if self.ready_state:
            self.ready_btn.configure(text="Retirer l'état prêt")
        else:
            self.ready_btn.configure(text="Se déclarer prêt")

    def _request_history(self):
        try:
            play_transition()
        except Exception:
            pass

        if not self.client or not self.client.running:
            play_error()
            self.info_label.configure(text="Rejoins d'abord le hall pour consulter les chroniques.")
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
            self.info_label.configure(text="Impossible d'appeler les chroniques du hall.")

    def _format_post_match_status(self, end_message: dict) -> str:
        team_a_score = end_message.get("team_a_score", 0)
        team_b_score = end_message.get("team_b_score", 0)
        base_text = f"Joute close · {format_compact_scoreline(team_a_score, team_b_score)}"

        if end_message.get("history_saved", False):
            match_id = end_message.get("match_id")
            if match_id is not None:
                return f"{base_text} · chronique du hall archivee (joute #{match_id})"
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
        match_summary = run_network_match(self.client, self.my_slot, self.my_name, self.my_team)

        try:
            init_audio()
        except Exception:
            pass
        try:
            start_menu_music()
        except Exception:
            pass

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
            self._handle_disconnect(match_summary.get("disconnect_message", "Connexion interrompue pendant le match."))
            return

        # reset visuel du ready
        self.ready_state = False
        self.ready_btn.configure(
            text="Se déclarer prêt",
            state="normal"
        )
        self.history_btn.configure(state="normal")

        self.info_label.configure(self._format_post_match_status(match_summary.get("end_message", {})))

        # relance la boucle réseau lobby
        if self.client and self.client.running:
            self._start_network_thread()
        else:
            self._handle_disconnect("Connexion interrompue à la fin du match.")

    def shutdown(self):
        self.running = False
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.destroy()
