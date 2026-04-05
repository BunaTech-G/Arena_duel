import customtkinter as ctk
from tkinter import messagebox

from db.players import get_all_players, create_player
from db.matches import save_team_match
from ui.history_view import HistoryView
from game.audio import play_click


class PlayerSlotRow(ctk.CTkFrame):
    def __init__(self, master, slot_number, player_values):
        super().__init__(master, corner_radius=12)

        self.slot_number = slot_number
        self.player_values = player_values if player_values else [""]

        self.grid_columnconfigure(1, weight=1)

        self.active_checkbox = ctk.CTkCheckBox(
            self,
            text=f"Slot {slot_number}",
            command=self._toggle_active
        )
        self.active_checkbox.grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")

        self.player_combo = ctk.CTkComboBox(
            self,
            values=self.player_values,
            state="disabled"
        )
        self.player_combo.grid(row=0, column=1, padx=10, pady=12, sticky="ew")

        self.team_combo = ctk.CTkComboBox(
            self,
            values=["A", "B"],
            width=90,
            state="disabled"
        )
        self.team_combo.grid(row=0, column=2, padx=(10, 14), pady=12, sticky="e")
        self.team_combo.set("A" if slot_number % 2 == 1 else "B")

    def _toggle_active(self):
        is_active = self.active_checkbox.get() == 1

        if is_active:
            self.player_combo.configure(state="normal")
            self.team_combo.configure(state="normal")
        else:
            self.player_combo.configure(state="disabled")
            self.team_combo.configure(state="disabled")

    def set_player_values(self, values):
        self.player_values = values if values else [""]
        self.player_combo.configure(values=self.player_values)

        current_value = self.player_combo.get().strip()
        if current_value not in self.player_values:
            self.player_combo.set(self.player_values[0])

    def get_data(self):
        if self.active_checkbox.get() != 1:
            return None

        return {
            "slot": self.slot_number,
            "name": self.player_combo.get().strip(),
            "team": self.team_combo.get().strip().upper()
        }


class PlayerSelectView(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.player_options = []

        self.title("Sélection des joueurs - Mode équipes")
        self.geometry("1080x720")
        self.minsize(1080, 720)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.grab_set()
        self.after(100, lambda: self.attributes("-topmost", True))
        self.after(200, lambda: self.attributes("-topmost", False))

        self._build_ui()
        self.refresh_players()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Préparation du match en équipe",
            font=("Arial", 30, "bold")
        )
        title.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 8), sticky="w")

        subtitle = ctk.CTkLabel(
            self,
            text="Formats autorisés : 1v1, 2v2, 3v3. Active les slots, choisis les joueurs, assigne A/B, puis lance.",
            font=("Arial", 15)
        )
        subtitle.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 12), sticky="w")

        # ----------------------
        # Colonne gauche : slots
        # ----------------------
        left_frame = ctk.CTkFrame(self, corner_radius=16)
        left_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        slots_title = ctk.CTkLabel(
            left_frame,
            text="Joueurs du match (6 max)",
            font=("Arial", 22, "bold")
        )
        slots_title.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="w")

        self.slots_frame = ctk.CTkScrollableFrame(left_frame, corner_radius=12)
        self.slots_frame.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.slots_frame.grid_columnconfigure(0, weight=1)

        self.slot_rows = []
        for i in range(6):
            row = PlayerSlotRow(self.slots_frame, i + 1, [""])
            row.grid(row=i, column=0, padx=6, pady=6, sticky="ew")
            self.slot_rows.append(row)

        # ----------------------
        # Colonne droite
        # ----------------------
        right_frame = ctk.CTkFrame(self, corner_radius=16)
        right_frame.grid(row=2, column=1, padx=(10, 20), pady=10, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(5, weight=1)

        rules_title = ctk.CTkLabel(
            right_frame,
            text="Règles de validation",
            font=("Arial", 22, "bold")
        )
        rules_title.grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")

        rules_box = ctk.CTkTextbox(right_frame, height=120)
        rules_box.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="ew")
        rules_box.insert(
            "0.0",
            "Formats autorisés :\n"
            "- 1v1 → 2 joueurs\n"
            "- 2v2 → 4 joueurs\n"
            "- 3v3 → 6 joueurs\n\n"
            "Conditions :\n"
            "- équipes équilibrées\n"
            "- pas de doublon de joueur\n"
            "- aucun slot actif vide"
        )
        rules_box.configure(state="disabled")

        create_title = ctk.CTkLabel(
            right_frame,
            text="Créer un joueur",
            font=("Arial", 22, "bold")
        )
        create_title.grid(row=2, column=0, padx=18, pady=(4, 8), sticky="w")

        self.new_player_entry = ctk.CTkEntry(
            right_frame,
            placeholder_text="Pseudo du nouveau joueur"
        )
        self.new_player_entry.grid(row=3, column=0, padx=18, pady=(0, 10), sticky="ew")

        add_btn = ctk.CTkButton(
            right_frame,
            text="Ajouter le joueur",
            height=42,
            command=self._handle_add_player
        )
        add_btn.grid(row=4, column=0, padx=18, pady=(0, 16), sticky="ew")

        existing_title = ctk.CTkLabel(
            right_frame,
            text="Joueurs enregistrés",
            font=("Arial", 22, "bold")
        )
        existing_title.grid(row=5, column=0, padx=18, pady=(0, 8), sticky="nw")

        self.players_box = ctk.CTkTextbox(right_frame, height=180)
        self.players_box.grid(row=6, column=0, padx=18, pady=(0, 14), sticky="nsew")

        self.info_label = ctk.CTkLabel(
            right_frame,
            text="Configure la sélection puis lance la partie.",
            font=("Arial", 14),
            wraplength=320,
            justify="left"
        )
        self.info_label.grid(row=7, column=0, padx=18, pady=(0, 14), sticky="w")

        validate_btn = ctk.CTkButton(
            right_frame,
            text="Valider et lancer",
            height=44,
            command=self._handle_validate_and_launch
        )
        validate_btn.grid(row=8, column=0, padx=18, pady=(0, 10), sticky="ew")

        history_btn = ctk.CTkButton(
            right_frame,
            text="Voir l’historique",
            height=42,
            command=self._open_history
        )
        history_btn.grid(row=9, column=0, padx=18, pady=(0, 10), sticky="ew")

        refresh_btn = ctk.CTkButton(
            right_frame,
            text="Actualiser la liste",
            height=42,
            command=self.refresh_players
        )
        refresh_btn.grid(row=10, column=0, padx=18, pady=(0, 10), sticky="ew")

        close_btn = ctk.CTkButton(
            right_frame,
            text="Fermer",
            height=42,
            fg_color="#B33939",
            hover_color="#922B2B",
            command=self._handle_close
        )
        close_btn.grid(row=11, column=0, padx=18, pady=(0, 18), sticky="ew")

    def refresh_players(self):
        rows = get_all_players()
        self.player_options = [row[1] for row in rows]

        if not self.player_options:
            self.player_options = [""]

        for row in self.slot_rows:
            row.set_player_values(self.player_options)

        self.players_box.configure(state="normal")
        self.players_box.delete("0.0", "end")

        if rows:
            lines = [f"{idx + 1}. {row[1]}" for idx, row in enumerate(rows)]
            self.players_box.insert("0.0", "\n".join(lines))
        else:
            self.players_box.insert("0.0", "Aucun joueur enregistré.")

        self.players_box.configure(state="disabled")
        self.info_label.configure(text=f"{len(rows)} joueur(s) disponible(s).")

    def _handle_add_player(self):
        play_click()
        username = self.new_player_entry.get().strip()
        ok, message = create_player(username)

        self.info_label.configure(text=message)

        if ok:
            self.new_player_entry.delete(0, "end")
            self.refresh_players()

    def _collect_selected_players(self):
        selected = []
        for row in self.slot_rows:
            data = row.get_data()
            if data is not None:
                selected.append(data)
        return selected

    def _validate_selection(self, players_data):
        total = len(players_data)

        if total not in (2, 4, 6):
            return False, "Tu dois sélectionner 2 joueurs (1v1), 4 joueurs (2v2) ou 6 joueurs (3v3)."

        names = [p["name"] for p in players_data]
        if any(not name for name in names):
            return False, "Un slot actif est vide."

        if len(names) != len(set(names)):
            return False, "Un même joueur est sélectionné plusieurs fois."

        team_a = [p for p in players_data if p["team"] == "A"]
        team_b = [p for p in players_data if p["team"] == "B"]

        expected_per_team = total // 2

        if len(team_a) != expected_per_team or len(team_b) != expected_per_team:
            return False, (
                f"Répartition invalide : pour {total} joueurs, "
                f"il faut {expected_per_team} joueur(s) dans chaque équipe."
            )

        return True, "Sélection valide."

    def _handle_validate_and_launch(self):
        play_click()
        players_data = self._collect_selected_players()
        ok, message = self._validate_selection(players_data)

        self.info_label.configure(text=message)

        if not ok:
            messagebox.showwarning("Sélection invalide", message)
            return

        self.parent.withdraw()
        self.destroy()

        from game.game_window import run_game
        result = run_game(players_data)

        self.parent.deiconify()

        if result:
            ok, save_message = save_team_match(
                result["players_data"],
                result["team_a_score"],
                result["team_b_score"],
                result["duration_seconds"],
            )
            messagebox.showinfo(
                "Fin de partie",
                f"{result['winner_text']}\n\n{save_message}"
           )

    def _open_history(self):
        play_click()
        HistoryView(self)

    def _handle_close(self):
        play_click()
        self.grab_release()
        self.destroy()