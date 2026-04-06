import threading
import customtkinter as ctk

from network.client import NetworkClient
from network.messages import ASSIGN_SLOT, LOBBY_STATE
from network.messages import ASSIGN_SLOT, LOBBY_STATE, START
from game.net_match_window import run_network_match


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

        self.my_slot = None
        self.my_team = None
        self.my_name = None
        self.ready_state = False

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
        self.my_name = name
        self.connect_btn.configure(state="disabled")
        self.ready_btn.configure(state="normal")

        self._start_network_thread()

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
            self.after(150, self._launch_match)

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
        run_network_match(self.client, self.my_slot, self.my_name)

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
