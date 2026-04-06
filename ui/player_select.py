import customtkinter as ctk
from tkinter import messagebox

from db.players import get_all_players, create_player
from db.matches import save_team_match
from game.audio import play_click, play_error, play_transition, start_menu_music, stop_music
from game.match_text import get_team_label
from ui.history_view import HistoryView
from runtime_utils import resource_path
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    enable_large_window,
    load_ctk_image,
    style_window,
    style_frame,
    style_textbox,
    set_textbox_content,
    create_button,
    create_badge,
    update_badge,
)


TEAM_DISPLAY_BY_CODE = {
    "A": get_team_label("A"),
    "B": get_team_label("B"),
}
TEAM_CODE_BY_DISPLAY = {label: code for code, label in TEAM_DISPLAY_BY_CODE.items()}
FORGE_RULES_TEXT = (
    "Formats autorisés :\n"
    "- Duel d'ouverture : 2 combattants\n"
    "- Escarmouche tenue : 4 combattants\n"
    "- Mêlée majeure : 6 combattants\n\n"
    "Conditions de scellage :\n"
    "- un nombre égal pour chaque bastion\n"
    "- aucun doublon dans les noms\n"
    "- aucun emplacement actif laissé vide"
)


class PlayerSlotRow(ctk.CTkFrame):
    def __init__(self, master, slot_number, player_values, on_change=None):
        super().__init__(master, corner_radius=12)
        style_frame(self, tone="panel_alt", border_color=PALETTE["border"])

        self.slot_number = slot_number
        self.on_change = on_change
        self.player_values = player_values if player_values else [""]
        self.default_team_label = TEAM_DISPLAY_BY_CODE["A" if slot_number % 2 == 1 else "B"]

        self.grid_columnconfigure(2, weight=1)

        self.slot_badge = create_badge(self, f"Poste {slot_number}", tone="neutral")
        self.slot_badge.grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")

        self.active_checkbox = ctk.CTkCheckBox(
            self,
            text="Activer",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            fg_color=PALETTE["gold"],
            hover_color=PALETTE["gold_hover"],
            border_color=PALETTE["border_strong"],
            command=self._toggle_active
        )
        self.active_checkbox.grid(row=0, column=1, padx=(0, 10), pady=12, sticky="w")

        self.player_combo = ctk.CTkComboBox(
            self,
            values=self.player_values,
            state="disabled",
            font=TYPOGRAPHY["body"],
            dropdown_font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            button_color=PALETTE["surface"],
            button_hover_color=PALETTE["border_strong"],
            text_color=PALETTE["text_muted"],
        )
        self.player_combo.grid(row=0, column=2, padx=10, pady=12, sticky="ew")

        self.team_combo = ctk.CTkComboBox(
            self,
            values=list(TEAM_CODE_BY_DISPLAY.keys()),
            width=170,
            state="readonly",
            font=TYPOGRAPHY["body_bold"],
            dropdown_font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            button_color=PALETTE["surface"],
            button_hover_color=PALETTE["border_strong"],
            text_color=PALETTE["text_muted"],
            command=self._handle_team_change,
        )
        self.team_combo.grid(row=0, column=3, padx=(10, 14), pady=12, sticky="e")
        self._apply_slot_state(False)
        self.team_combo.set(self.default_team_label)

    def _apply_slot_state(self, is_active: bool):
        team_code = self._current_team_code()
        accent_color = PALETTE["gold"] if team_code == "A" else PALETTE["cyan"]
        accent_hover = PALETTE["gold_hover"] if team_code == "A" else PALETTE["cyan_hover"]
        accent_border = PALETTE["gold_dim"] if team_code == "A" else PALETTE["cyan_dim"]

        self.active_checkbox.configure(
            fg_color=accent_color,
            hover_color=accent_hover,
            border_color=accent_border,
        )

        if is_active:
            self.configure(fg_color=PALETTE["surface"], border_color=accent_border)
            self.player_combo.configure(state="normal", text_color=PALETTE["text"])
            self.team_combo.configure(state="readonly", text_color=PALETTE["text"])
            update_badge(self.slot_badge, f"Poste {self.slot_number}", "gold" if team_code == "A" else "info")
        else:
            self.configure(fg_color=PALETTE["panel_alt"], border_color=PALETTE["border"])
            self.player_combo.configure(state="disabled", text_color=PALETTE["text_soft"])
            self.team_combo.configure(state="readonly", text_color=PALETTE["text_soft"])
            update_badge(self.slot_badge, f"Poste {self.slot_number}", "neutral")

        self.player_combo.configure(border_color=accent_border, button_color=accent_border, button_hover_color=accent_color)
        self.team_combo.configure(border_color=accent_border, button_color=accent_border, button_hover_color=accent_color)

    def _toggle_active(self):
        is_active = self.active_checkbox.get() == 1
        self._apply_slot_state(is_active)
        if not self.team_combo.get().strip():
            self.team_combo.set(self.default_team_label)
        self._notify_change()

    def _current_team_code(self) -> str:
        return TEAM_CODE_BY_DISPLAY.get(self.team_combo.get().strip(), "A")

    def _handle_team_change(self, _choice=None):
        self._apply_slot_state(self.active_checkbox.get() == 1)
        self._notify_change()

    def _notify_change(self):
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception:
            pass

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
            "team": TEAM_CODE_BY_DISPLAY.get(self.team_combo.get().strip(), "A")
        }


class PlayerSelectView(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        style_window(self)

        self.parent = parent
        self.player_options = []
        self.sanctum_preview_image = load_ctk_image(
            "assets",
            "backgrounds",
            "launcher_sanctum_bg.png",
            size=(250, 118),
            fallback_label="sanctum",
        )
        self.mascot_portrait_image = load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(72, 72),
            fallback_label="mascot",
        )

        self.title("Arena Duel - Forge locale")
        self.geometry("1320x860")
        enable_large_window(self, 1100, 760)
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except Exception:
            pass

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

        header = ctk.CTkFrame(self, corner_radius=22)
        style_frame(header, tone="panel", border_color=PALETTE["gold_dim"])
        header.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            header,
            text="Forge de la joute",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        )
        title.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="w")

        self.status_badge = create_badge(header, "Forge en veille", tone="gold")
        self.status_badge.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="e")

        subtitle = ctk.CTkLabel(
            header,
            text="Assemble deux bastions équilibrés, choisis les combattants et prépare une joute en 1v1, 2v2 ou 3v3.",
            font=TYPOGRAPHY["subtitle"],
            text_color=PALETTE["text_muted"],
            wraplength=860,
            justify="left",
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        preview_card = ctk.CTkFrame(header, corner_radius=18)
        style_frame(preview_card, tone="panel_soft", border_color=PALETTE["border_strong"])
        preview_card.grid(row=0, column=1, rowspan=2, padx=(12, 20), pady=16, sticky="nsew")
        preview_card.grid_columnconfigure(1, weight=1)

        preview_image = ctk.CTkLabel(preview_card, text="", image=self.sanctum_preview_image)
        preview_image.grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 10), sticky="ew")

        portrait = ctk.CTkLabel(preview_card, text="", image=self.mascot_portrait_image)
        portrait.grid(row=1, column=0, padx=(12, 10), pady=(0, 12), sticky="w")

        preview_title = ctk.CTkLabel(
            preview_card,
            text="Héraut du sanctum",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        preview_title.grid(row=1, column=1, padx=(0, 12), pady=(2, 0), sticky="sw")

        preview_hint = ctk.CTkLabel(
            preview_card,
            text="Portrait prêt pour\nles cartes et verdicts",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
        )
        preview_hint.grid(row=1, column=1, padx=(0, 12), pady=(0, 12), sticky="nw")

        # ----------------------
        # Colonne gauche : slots
        # ----------------------
        left_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(left_frame, tone="panel", border_color=PALETTE["border"])
        left_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        slots_title = ctk.CTkLabel(
            left_frame,
            text="Lignes des bastions",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        slots_title.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="w")

        self.slots_frame = ctk.CTkScrollableFrame(left_frame, corner_radius=12)
        self.slots_frame.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.slots_frame.grid_columnconfigure(0, weight=1)
        self.slots_frame.configure(fg_color=PALETTE["panel_soft"])

        self.slot_rows = []
        for i in range(6):
            row = PlayerSlotRow(self.slots_frame, i + 1, [""], on_change=self._refresh_forge_state)
            row.grid(row=i, column=0, padx=6, pady=6, sticky="ew")
            self.slot_rows.append(row)

        # ----------------------
        # Colonne droite
        # ----------------------
        right_frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=16,
            fg_color=PALETTE["panel"],
            border_width=1,
            border_color=PALETTE["border"],
        )
        right_frame.grid(row=2, column=1, padx=(10, 20), pady=10, sticky="nsew")
        right_frame.grid_columnconfigure((0, 1), weight=1)

        rules_title = ctk.CTkLabel(
            right_frame,
            text="Cadre de la joute",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        rules_title.grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 8), sticky="w")

        rules_box = ctk.CTkTextbox(right_frame, height=120)
        rules_box.grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="ew")
        style_textbox(rules_box)
        set_textbox_content(rules_box, FORGE_RULES_TEXT)

        pulse_title = ctk.CTkLabel(
            right_frame,
            text="Pouls de la forge",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        pulse_title.grid(row=2, column=0, columnspan=2, padx=18, pady=(4, 8), sticky="w")

        self.selection_frame = ctk.CTkFrame(right_frame, corner_radius=16)
        style_frame(self.selection_frame, tone="panel_soft", border_color=PALETTE["border"])
        self.selection_frame.grid(row=3, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="ew")
        self.selection_frame.grid_columnconfigure((0, 1), weight=1)

        self.active_slots_value = self._build_stat_card(self.selection_frame, 0, 0, "Etendards leves", "0")
        self.format_value = self._build_stat_card(self.selection_frame, 0, 1, "Cadence", "Veille")
        self.balance_value = self._build_stat_card(self.selection_frame, 1, 0, "Equilibre", "-")
        self.registered_value = self._build_stat_card(self.selection_frame, 1, 1, "Registre", "0")

        create_title = ctk.CTkLabel(
            right_frame,
            text="Enrôler un combattant",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        create_title.grid(row=4, column=0, columnspan=2, padx=18, pady=(4, 8), sticky="w")

        self.new_player_entry = ctk.CTkEntry(
            right_frame,
            placeholder_text="Nom du combattant à inscrire",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        self.new_player_entry.grid(row=5, column=0, columnspan=2, padx=18, pady=(0, 10), sticky="ew")

        add_btn = create_button(right_frame, "Enrôler ce combattant", self._handle_add_player, variant="accent", height=42)
        add_btn.grid(row=6, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="ew")

        existing_title = ctk.CTkLabel(
            right_frame,
            text="Registre du bastion",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        existing_title.grid(row=7, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="nw")

        self.players_box = ctk.CTkTextbox(right_frame, height=180)
        self.players_box.grid(row=8, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="nsew")
        style_textbox(self.players_box)

        info_frame = ctk.CTkFrame(right_frame, corner_radius=16)
        style_frame(info_frame, tone="bg_alt", border_color=PALETTE["border"])
        info_frame.grid(row=9, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_columnconfigure(1, weight=0)

        info_title = ctk.CTkLabel(
            info_frame,
            text="Echo de la forge",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        info_title.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        self.info_badge = create_badge(info_frame, "Veille de la forge", tone="neutral")
        self.info_badge.grid(row=0, column=1, padx=14, pady=(14, 6), sticky="e")

        self.info_box = ctk.CTkTextbox(info_frame, height=112)
        self.info_box.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 14), sticky="ew")
        style_textbox(self.info_box)

        validate_btn = create_button(right_frame, "Ouvrir la joute", self._handle_validate_and_launch, variant="primary", height=46)
        validate_btn.grid(row=10, column=0, columnspan=2, padx=18, pady=(0, 10), sticky="ew")

        history_btn = create_button(right_frame, "Lire les chroniques", self._open_history, variant="secondary", height=42)
        history_btn.grid(row=11, column=0, padx=(18, 8), pady=(0, 10), sticky="ew")

        refresh_btn = create_button(right_frame, "Actualiser le registre", self.refresh_players, variant="ghost", height=42)
        refresh_btn.grid(row=11, column=1, padx=(8, 18), pady=(0, 10), sticky="ew")

        close_btn = create_button(right_frame, "Retour au bastion", self._handle_close, variant="danger", height=42)
        close_btn.grid(row=12, column=0, columnspan=2, padx=18, pady=(0, 18), sticky="ew")

    def _build_stat_card(self, master, row: int, column: int, label_text: str, value_text: str):
        card = ctk.CTkFrame(master, corner_radius=14)
        style_frame(card, tone="panel", border_color=PALETTE["border"])
        card.grid(row=row, column=column, padx=8, pady=8, sticky="ew")
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

    def _set_info(self, text: str, badge_text: str = "Veille de la forge", tone: str = "neutral"):
        update_badge(self.info_badge, badge_text, tone)
        set_textbox_content(self.info_box, text)

    def _refresh_forge_state(self):
        selected_players = self._collect_selected_players()
        total = len(selected_players)
        team_a_count = sum(1 for player in selected_players if player["team"] == "A")
        team_b_count = sum(1 for player in selected_players if player["team"] == "B")
        registered_count = len([name for name in self.player_options if name.strip()])

        self.active_slots_value.configure(text=str(total))
        self.balance_value.configure(text=f"{team_a_count} / {team_b_count}" if total else "-")
        self.registered_value.configure(text=str(registered_count))

        format_label = {
            0: "Veille",
            2: "Duel",
            4: "Escarmouche",
            6: "Melee",
        }.get(total, "A completer")
        self.format_value.configure(text=format_label)

        if registered_count == 0:
            update_badge(self.status_badge, "Registre vide", "warning")
            self._set_info(
                "Le registre est vide. Enrole d'abord un combattant pour commencer a forger une joute.",
                badge_text="Registre a remplir",
                tone="warning",
            )
            return

        if total == 0:
            update_badge(self.status_badge, "Forge prete", "gold")
            self._set_info(
                "Active 2, 4 ou 6 postes, choisis les combattants puis garde le meme nombre de guerriers dans chaque bastion.",
                badge_text="Veille de la forge",
                tone="neutral",
            )
            return

        ok, message = self._validate_selection(selected_players)
        if ok:
            update_badge(self.status_badge, "Formation equilibree", "success")
            self._set_info(message, badge_text="Etendards leves", tone="success")
        else:
            update_badge(self.status_badge, "Forge en cours", "warning")
            self._set_info(message, badge_text="Forge en cours", tone="warning")

    def refresh_players(self):
        rows = get_all_players()
        self.player_options = [row[1] for row in rows]
        player_count = len(rows)

        if not self.player_options:
            self.player_options = [""]

        for row in self.slot_rows:
            row.set_player_values(self.player_options)

        if rows:
            lines = [f"{idx + 1}. {row[1]}" for idx, row in enumerate(rows)]
            set_textbox_content(self.players_box, "\n".join(lines))
        else:
            set_textbox_content(
                self.players_box,
                "Aucun combattant n'est encore inscrit dans le registre.\n\nEnrole un premier nom pour reveiller la forge."
            )

        self._refresh_forge_state()

    def _handle_add_player(self):
        play_click()
        username = self.new_player_entry.get().strip()
        ok, message = create_player(username)

        if ok:
            self.new_player_entry.delete(0, "end")
            self.refresh_players()
            update_badge(self.status_badge, "Combattant enrôle", "success")
            self._set_info(message, badge_text="Combattant enrôle", tone="success")
        else:
            play_error()
            update_badge(self.status_badge, "Enrôlement refusé", "warning")
            self._set_info(message, badge_text="Enrôlement refusé", tone="warning")

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
            return False, "Active 2, 4 ou 6 combattants pour ouvrir une joute valable."

        names = [p["name"] for p in players_data]
        if any(not name for name in names):
            return False, "Un emplacement actif attend encore un combattant."

        if len(names) != len(set(names)):
            return False, "Un même combattant ne peut pas servir deux emplacements dans la même joute."

        team_a = [p for p in players_data if p["team"] == "A"]
        team_b = [p for p in players_data if p["team"] == "B"]

        expected_per_team = total // 2

        if len(team_a) != expected_per_team or len(team_b) != expected_per_team:
            return False, (
                f"Formation déséquilibrée : pour {total} combattants, il faut "
                f"{expected_per_team} combattant(s) dans chacun des deux bastions."
            )

        return True, "Formation validée. Les deux bastions sont prêts à entrer dans l'arène."

    def _handle_validate_and_launch(self):
        play_transition()
        players_data = self._collect_selected_players()
        ok, message = self._validate_selection(players_data)

        self._set_info(message, badge_text="Verdict de la forge" if ok else "Forge en cours", tone="success" if ok else "warning")

        if not ok:
            update_badge(self.status_badge, "Formation à reprendre", "warning")
            play_error()
            messagebox.showwarning("Formation à reprendre", message)
            return

        update_badge(self.status_badge, "Joute en préparation", "gold")
        self._set_info(
            "La forge scelle la formation. La joute va s'ouvrir avec les bastions choisis.",
            badge_text="Joute en préparation",
            tone="gold",
        )

        self.parent.withdraw()
        self.destroy()

        from game.game_window import run_game
        stop_music(fade_ms=180)
        result = run_game(players_data)

        self.parent.deiconify()
        start_menu_music()

        if result:
            ok, save_message = save_team_match(
                result["players_data"],
                result["team_a_score"],
                result["team_b_score"],
                result["duration_seconds"],
            )
            if not ok:
                play_error()
            messagebox.showinfo(
                "Verdict de la joute",
                f"{result['winner_text']}\n\n{save_message}"
           )

    def _open_history(self):
        play_transition()
        self._set_info(
            "Les chroniques locales s'ouvrent pour revoir les verdicts et la forme recente des bastions.",
            badge_text="Chroniques ouvertes",
            tone="gold",
        )
        HistoryView(self, source_label="Chroniques locales du bastion")

    def _handle_close(self):
        play_click()
        self.grab_release()
        self.destroy()