import threading
import customtkinter as ctk

from network.client import NetworkClient
from network.messages import ASSIGN_SLOT, LOBBY_STATE


class NetworkLobbyView(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.title("Arena Duel - Lobby Réseau")
        self.geometry("600x500")
        self.resizable(False, False)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        
        self.client = None
        self.running = False

        self._build_ui()

    def _build_ui(self):
        # === Connexion ===
        self.ip_entry = ctk.CTkEntry(self, placeholder_text="IP du serveur")
        self.ip_entry.pack(pady=10)
        self.ip_entry.insert(0, "127.0.0.1")

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

    # =========================
    # Connexion réseau
    # =========================
    def _connect(self):
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

        self.running = True
        threading.Thread(target=self._network_loop, daemon=True).start()

    # =========================
    # Réception réseau
    # =========================
    def _network_loop(self):
        while self.running:
            for msg in self.client.poll_messages():
                self.after(0, lambda m=msg: self._handle_message(m))

    def _handle_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == ASSIGN_SLOT:
            slot = msg["slot"]
            team = msg["team"]
            self.info_label.configure(
                text=f"Slot {slot} | Équipe {team}"
            )

        elif msg_type == LOBBY_STATE:
            self._update_lobby(msg["players"])

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
        self.client.send_ready(True)
