import threading
import customtkinter as ctk
import time
import json
import os

from network.client import NetworkClient
from network.messages import ASSIGN_SLOT, LOBBY_STATE
from network.messages import ASSIGN_SLOT, LOBBY_STATE, START
from game.net_match_window import run_network_match
from game.audio import play_click, init_audio
from network.net_utils import get_local_lan_ip
from runtime_utils import resource_path
from runtime_utils import set_runtime_override



class NetworkLobbyView(ctk.CTkToplevel):
    def __init__(self, parent, default_server_ip=None, host_mode=False):
        super().__init__(parent)

        self.title("Arena Duel - Lobby Réseau")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except Exception:
            pass
        self.geometry("620x650")
        self.resizable(False, False)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        
        self.client = None
        self.running = False

        self.config_file = "client_lan_config.json"
        self.detected_local_ip = get_local_lan_ip()
        self.default_server_ip = default_server_ip
        self.host_mode = host_mode

        self.config_file = "client_lan_config.json"
        self.detected_local_ip = get_local_lan_ip()

        self.my_slot = None
        self.my_team = None
        self.my_name = None
        self.ready_state = False

        self._build_ui()
        if self.host_mode:
            self.info_label.configure(
                text="Serveur LAN démarré. Entrez votre pseudo puis cliquez sur Se connecter."
            )

    def _build_ui(self):
        # === Connexion ===
        self.ip_entry = ctk.CTkEntry(self, placeholder_text="IP du serveur")
        self.ip_entry.pack(pady=(10, 6))

        default_ip = self._load_saved_server_ip()
        if default_ip:
            self.ip_entry.insert(0, default_ip)

        self.local_ip_label = ctk.CTkLabel(
            self,
            text=f"Mon IP locale : {self.detected_local_ip}"
        )
        self.local_ip_label.pack(pady=(0, 6))

        self.use_local_ip_btn = ctk.CTkButton(
            self,
            text="Utiliser 127.0.0.1 (même PC que le serveur)",
            command=self._use_loopback_ip,
            width=280
        )
        self.use_local_ip_btn.pack(pady=(0, 10))

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Pseudo")
        self.name_entry.pack(pady=10)

        self.connect_btn = ctk.CTkButton(
            self, text="Se connecter", command=self._connect
        )
        self.connect_btn.pack(pady=10)

        # === Infos joueur ===
        self.info_label = ctk.CTkLabel(self, text="")
        self.info_label.pack(pady=10)

        # === Lobby ===
        self.lobby_box = ctk.CTkTextbox(self, width=500, height=200)
        self.lobby_box.pack(pady=10)
        self.lobby_box.configure(state="disabled")

        # === Ready ===
        self.ready_btn = ctk.CTkButton(
            self, text="Je suis prêt", state="disabled", command=self._toggle_ready
        )
        self.ready_btn.pack(pady=10)

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

    # =========================
    # Connexion réseau
    # =========================
    def _connect(self):
        try:
            play_click()
        except Exception:
            pass

        ip = self.ip_entry.get().strip()
        name = self.name_entry.get().strip()

        if not ip or not name:
            self.info_label.configure(text="IP et pseudo requis")
            return

        self.client = NetworkClient()

        try:
            self.client.connect(ip, 5000, name)
        except Exception as e:
            self.info_label.configure(text=f"Erreur connexion : {e}")
            return

        self.info_label.configure(text=f"Connecté en tant que {name}")
        self.connect_btn.configure(state="disabled")
        self.ready_btn.configure(state="normal")

        self.my_name = name
        self._save_server_ip(ip)

        # DB selon le mode :
        # - host -> localhost
        # - join -> IP du serveur
        if self.host_mode:
            set_runtime_override("db_host", "localhost")
        else:
            set_runtime_override("db_host", ip)

        self._start_network_thread()

        if self.host_mode:
            self.info_label.configure(text=f"Connecté en tant que {name} | DB locale")
        else:
            self.info_label.configure(text=f"Connecté en tant que {name} | DB du serveur {ip}")

    # =========================
    # Réception réseau
    # =========================
    def _network_loop(self):
        while self.running:
            if not self.client:
                break

            for msg in self.client.poll_messages():
                self.after(0, lambda m=msg: self._handle_message(m))

            time.sleep(0.02)  # 20 ms -> boucle plus légère

    def _handle_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == ASSIGN_SLOT:
            slot = msg["slot"]
            team = msg["team"]

            self.my_slot = slot
            self.my_team = team

            self.info_label.configure(
                text=f"Slot {slot} | Équipe {team}"
            )

        elif msg_type == LOBBY_STATE:
            self._update_lobby(msg["players"])

        elif msg_type == START:
            self.info_label.configure(text="Match en cours...")
            self.ready_btn.configure(state="disabled")
            self.after(50, self._launch_match)

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
            line = f"Slot {p['slot']} | {p['name']} | Équipe {p['team']} | "
            line += "✅ Prêt" if p["ready"] else "⏳ Pas prêt"
            self.lobby_box.insert("end", line + "\n")

        self.lobby_box.configure(state="disabled")

    # =========================
    # Ready
    # =========================
    def _toggle_ready(self):
        try:
            play_click()
        except Exception:
            pass

        self.ready_state = not self.ready_state
        self.client.send_ready(self.ready_state)

        if self.ready_state:
            self.ready_btn.configure(text="Je ne suis plus prêt")
        else:
            self.ready_btn.configure(text="Je suis prêt")

    def _launch_match(self):
        if not self.client or self.my_slot is None or not self.my_name:
            return

        # on stoppe la boucle lobby pendant le match
        self.running = False

        # on cache le lobby
        self.withdraw()
        self.update()

        # on lance le match réseau
        run_network_match(self.client, self.my_slot, self.my_name, self.my_team)

        try:
            init_audio()
        except Exception:
            pass

        # retour au lobby après le match
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

        # reset visuel du ready
        self.ready_state = False
        self.ready_btn.configure(
            text="Je suis prêt",
            state="normal"
        )

        self.info_label.configure(text="Retour au lobby...")

        # relance la boucle réseau lobby
        self._start_network_thread()

    def shutdown(self):
            self.running = False
            try:
                if self.client:
                    self.client.close()
            except Exception:
                pass
            self.destroy()
