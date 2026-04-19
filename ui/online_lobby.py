import customtkinter as ctk
from ui.online_client import OnlineClient
from ui.theme import apply_theme_settings, apply_window_icon, present_window

DEFAULT_HOST = "165.227.166.21"
DEFAULT_PORT = 27015


class OnlineLobbyWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Arena Duel - Online Lobby")
        apply_window_icon(self, default=True, retry_after_ms=220)
        self.geometry("900x550")

        self.client = OnlineClient()
        self.connected = False

        # --- Top bar (connexion) ---
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=12)

        self.host_var = ctk.StringVar(value=DEFAULT_HOST)
        self.port_var = ctk.StringVar(value=str(DEFAULT_PORT))
        self.pseudo_var = ctk.StringVar(value="osidi")

        ctk.CTkLabel(top, text="Host").pack(side="left", padx=(10, 4))
        ctk.CTkEntry(top, textvariable=self.host_var, width=180).pack(
            side="left", padx=4
        )

        ctk.CTkLabel(top, text="Port").pack(side="left", padx=(12, 4))
        ctk.CTkEntry(top, textvariable=self.port_var, width=90).pack(
            side="left", padx=4
        )

        ctk.CTkLabel(top, text="Pseudo").pack(side="left", padx=(12, 4))
        ctk.CTkEntry(top, textvariable=self.pseudo_var, width=160).pack(
            side="left", padx=4
        )

        self.btn_connect = ctk.CTkButton(top, text="Connect", command=self.on_connect)
        self.btn_connect.pack(side="left", padx=(12, 4))

        self.btn_disconnect = ctk.CTkButton(
            top, text="Disconnect", command=self.on_disconnect, state="disabled"
        )
        self.btn_disconnect.pack(side="left", padx=4)

        self.status = ctk.CTkLabel(top, text="Déconnecté")
        self.status.pack(side="right", padx=10)

        # --- Main area ---
        mid = ctk.CTkFrame(self)
        mid.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = ctk.CTkFrame(mid)
        left.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

        right = ctk.CTkFrame(mid)
        right.pack(side="right", fill="y", padx=(6, 12), pady=12)

        ctk.CTkLabel(left, text="Rooms").pack(anchor="w", padx=10, pady=(10, 6))
        self.rooms_box = ctk.CTkTextbox(left, height=420)
        self.rooms_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.rooms_box.configure(state="disabled")

        self.btn_refresh = ctk.CTkButton(
            right, text="Refresh rooms", command=self.on_list_rooms, state="disabled"
        )
        self.btn_refresh.pack(fill="x", padx=10, pady=(10, 6))

        self.room_name_var = ctk.StringVar(value="RoomTest")
        ctk.CTkLabel(right, text="Nom de room").pack(anchor="w", padx=10, pady=(10, 2))
        ctk.CTkEntry(right, textvariable=self.room_name_var).pack(fill="x", padx=10)

        self.max_players_var = ctk.StringVar(value="2")
        ctk.CTkLabel(right, text="Max joueurs").pack(anchor="w", padx=10, pady=(10, 2))
        ctk.CTkEntry(right, textvariable=self.max_players_var).pack(fill="x", padx=10)

        self.btn_create = ctk.CTkButton(
            right, text="Create room", command=self.on_create_room, state="disabled"
        )
        self.btn_create.pack(fill="x", padx=10, pady=(10, 6))

        self.join_room_id_var = ctk.StringVar(value="")
        ctk.CTkLabel(right, text="Room ID à join").pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        ctk.CTkEntry(right, textvariable=self.join_room_id_var).pack(fill="x", padx=10)

        self.btn_join = ctk.CTkButton(
            right, text="Join room", command=self.on_join_room, state="disabled"
        )
        self.btn_join.pack(fill="x", padx=10, pady=(10, 6))

        self.btn_leave = ctk.CTkButton(
            right, text="Leave room", command=self.on_leave_room, state="disabled"
        )
        self.btn_leave.pack(fill="x", padx=10, pady=(10, 6))

        # close hook
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # tick loop UI-safe
        self.after(50, self.tick)

    def set_status(self, txt: str):
        self.status.configure(text=txt)

    def set_rooms_text(self, txt: str):
        self.rooms_box.configure(state="normal")
        self.rooms_box.delete("1.0", "end")
        self.rooms_box.insert("end", txt)
        self.rooms_box.configure(state="disabled")

    def on_connect(self):
        host = self.host_var.get().strip()
        port = int(self.port_var.get().strip())
        pseudo = self.pseudo_var.get().strip() or "anonymous"
        try:
            self.client.connect(host, port, pseudo)
            self.set_status("Connexion en cours…")
        except Exception as e:
            self.set_status(f"Erreur connect: {e}")

    def on_disconnect(self):
        self.client.disconnect()
        self.connected = False
        self.btn_connect.configure(state="normal")
        self.btn_disconnect.configure(state="disabled")
        for b in (self.btn_refresh, self.btn_create, self.btn_join, self.btn_leave):
            b.configure(state="disabled")
        self.set_status("Déconnecté")

    def on_close(self):
        self.on_disconnect()
        self.destroy()

    def on_list_rooms(self):
        self.client.send({"type": "LIST_ROOMS"})

    def on_create_room(self):
        name = self.room_name_var.get().strip() or "Room"
        maxp = int(self.max_players_var.get().strip() or "2")
        self.client.send({"type": "CREATE_ROOM", "name": name, "max_players": maxp})

    def on_join_room(self):
        rid = self.join_room_id_var.get().strip()
        if rid:
            self.client.send({"type": "JOIN_ROOM", "room_id": rid})

    def on_leave_room(self):
        self.client.send({"type": "LEAVE_ROOM"})

    def tick(self):
        msg = self.client.poll()
        while msg:
            t = msg.get("type")

            if t == "WELCOME":
                self.set_status("Handshake OK")

            elif t == "LOGIN_OK":
                self.connected = True
                self.btn_connect.configure(state="disabled")
                self.btn_disconnect.configure(state="normal")
                for b in (
                    self.btn_refresh,
                    self.btn_create,
                    self.btn_join,
                    self.btn_leave,
                ):
                    b.configure(state="normal")
                self.set_status(f"Connecté: {msg.get('pseudo')}")
                self.on_list_rooms()

            elif t == "ROOMS":
                rooms = msg.get("rooms", [])
                lines = []
                for r in rooms:
                    lines.append(
                        f"{r['room_id']} | {r['name']} | {r['players']}/{r['max_players']} | {r['state']}"
                    )
                self.set_rooms_text(
                    "\n".join(lines) + ("\n" if lines else "(aucune room)\n")
                )

            elif t == "ROOM_CREATED":
                rid = msg.get("room_id", "")
                self.join_room_id_var.set(rid)
                self.set_status(f"Room créée: {rid}")
                self.on_list_rooms()

            elif t == "JOINED":
                self.set_status(f"Joined: {msg.get('room_id')}")
                self.on_list_rooms()

            elif t == "ROOM_UPDATE":
                # rafraîchissement simple
                self.on_list_rooms()

            elif t == "ERROR":
                self.set_status(f"Erreur: {msg.get('code')}")

            elif t == "DISCONNECTED":
                self.set_status(f"Déconnecté: {msg.get('error')}")
                self.on_disconnect()

            msg = self.client.poll()

        self.after(50, self.tick)


def run_online_lobby():
    apply_theme_settings()

    app = ctk.CTk()
    app.withdraw()

    window = OnlineLobbyWindow(app)

    def close_all():
        window.on_close()
        app.destroy()

    window.protocol("WM_DELETE_WINDOW", close_all)
    present_window(window)
    app.mainloop()
