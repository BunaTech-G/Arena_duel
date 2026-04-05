import customtkinter as ctk
from collections import Counter

from db.matches import get_match_history
from game.audio import play_click


class MatchCard(ctk.CTkFrame):
    def __init__(self, master, match_data):
        super().__init__(master, corner_radius=14)

        self.match_data = match_data
        self._build_ui()

    def _build_ui(self):
        match_id, p1, p2, winner, s1, s2, duration, played_at = self.match_data
        winner_display = winner if winner else "Égalité"

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            self,
            text=f"Match #{match_id}",
            font=("Arial", 20, "bold")
        )
        title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        date_label = ctk.CTkLabel(
            self,
            text=str(played_at),
            font=("Arial", 13)
        )
        date_label.grid(row=0, column=1, padx=16, pady=(14, 8), sticky="e")

        duel_label = ctk.CTkLabel(
            self,
            text=f"{p1}  VS  {p2}",
            font=("Arial", 16, "bold")
        )
        duel_label.grid(row=1, column=0, columnspan=2, padx=16, pady=4, sticky="w")

        score_label = ctk.CTkLabel(
            self,
            text=f"Score : {s1} - {s2}",
            font=("Arial", 15)
        )
        score_label.grid(row=2, column=0, padx=16, pady=4, sticky="w")

        duration_label = ctk.CTkLabel(
            self,
            text=f"Durée : {duration}s",
            font=("Arial", 15)
        )
        duration_label.grid(row=2, column=1, padx=16, pady=4, sticky="e")

        winner_label = ctk.CTkLabel(
            self,
            text=f"Gagnant : {winner_display}",
            font=("Arial", 15, "bold")
        )
        winner_label.grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 14), sticky="w")


class HistoryView(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.title("Historique des parties")
        self.geometry("980x640")
        self.minsize(980, 640)

        # IMPORTANT : forcer l'ouverture au premier plan
        self.transient(parent)
        self.lift()
        self.focus_force()
        self.grab_set()

        # Petit hack Windows pour être sûr que ça passe devant
        self.after(100, lambda: self.attributes("-topmost", True))
        self.after(200, lambda: self.attributes("-topmost", False))

        self._build_ui()
        self.refresh_history()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Historique / Scores",
            font=("Arial", 30, "bold")
        )
        title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.summary_frame = ctk.CTkFrame(self, corner_radius=16)
        self.summary_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.summary_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.total_matches_label = ctk.CTkLabel(
            self.summary_frame,
            text="Parties : 0",
            font=("Arial", 18, "bold")
        )
        self.total_matches_label.grid(row=0, column=0, padx=20, pady=18, sticky="w")

        self.players_label = ctk.CTkLabel(
            self.summary_frame,
            text="Joueurs vus : 0",
            font=("Arial", 18, "bold")
        )
        self.players_label.grid(row=0, column=1, padx=20, pady=18, sticky="w")

        self.top_winner_label = ctk.CTkLabel(
            self.summary_frame,
            text="Top gagnant : -",
            font=("Arial", 18, "bold")
        )
        self.top_winner_label.grid(row=0, column=2, padx=20, pady=18, sticky="w")

        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=14)
        self.scroll_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=0)

        self.status_label = ctk.CTkLabel(
            action_frame,
            text="",
            font=("Arial", 14)
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        refresh_btn = ctk.CTkButton(
            action_frame,
            text="Actualiser",
            width=160,
            command=self._handle_refresh
        )
        refresh_btn.grid(row=0, column=1, sticky="e")

    def _handle_refresh(self):
        play_click()
        self.refresh_history()

    def refresh_history(self):
        rows = get_match_history()

        # Nettoyer les anciennes cartes
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not rows:
            self.total_matches_label.configure(text="Parties : 0")
            self.players_label.configure(text="Joueurs vus : 0")
            self.top_winner_label.configure(text="Top gagnant : -")
            self.status_label.configure(text="Aucune partie enregistrée.")

            empty_label = ctk.CTkLabel(
                self.scroll_frame,
                text="Aucune partie enregistrée pour le moment.",
                font=("Arial", 18)
            )
            empty_label.grid(row=0, column=0, padx=20, pady=30, sticky="w")
            return

        # Résumé
        unique_players = set()
        winners = []

        for row in rows:
            _, p1, p2, winner, *_ = row
            unique_players.add(p1)
            unique_players.add(p2)
            if winner:
                winners.append(winner)

        self.total_matches_label.configure(text=f"Parties : {len(rows)}")
        self.players_label.configure(text=f"Joueurs vus : {len(unique_players)}")

        if winners:
            winner_counter = Counter(winners)
            top_name, top_count = winner_counter.most_common(1)[0]
            self.top_winner_label.configure(text=f"Top gagnant : {top_name} ({top_count})")
        else:
            self.top_winner_label.configure(text="Top gagnant : aucune victoire")

        self.status_label.configure(text=f"{len(rows)} partie(s) chargée(s).")

        # Cartes de matchs
        for index, row in enumerate(rows):
            card = MatchCard(self.scroll_frame, row)
            card.grid(row=index, column=0, padx=8, pady=8, sticky="ew")