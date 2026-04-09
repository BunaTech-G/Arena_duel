import customtkinter as ctk
import queue
import threading
import time
from tkinter import messagebox, TclError

from db.players import (
    create_player,
    get_player_registry_snapshot,
)
from db.matches import save_team_match
from game.audio import (
    play_click,
    play_error,
    play_transition,
    start_menu_music,
    stop_music,
)
from game.computer_opponent import (
    build_human_vs_ai_players,
    get_opposite_team,
)
from game.control_models import (
    AI_DIFFICULTY_CODE_BY_DISPLAY,
    AI_DIFFICULTY_DISPLAY_BY_CODE,
    HUMAN_CONTROL_MODE,
)
from game.match_text import get_team_label
from game.settings import (
    MATCH_DURATION_OPTIONS,
    MATCH_DURATION_SECONDS,
    format_match_duration_label,
)
from ui.history_view import HistoryView
from runtime_utils import resource_path
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    enable_large_window,
    style_window,
    style_frame,
    style_textbox,
    set_textbox_content,
    create_button,
    create_option_menu,
    create_badge,
    update_badge,
)


TEAM_DISPLAY_BY_CODE = {
    "A": get_team_label("A"),
    "B": get_team_label("B"),
}
TEAM_CODE_BY_DISPLAY = {
    label: code for code, label in TEAM_DISPLAY_BY_CODE.items()
}
MATCH_MODE_DISPLAY_BY_CODE = {
    "human": "Joute locale",
    "ai": "Contre l'ordinateur",
}
MATCH_MODE_CODE_BY_DISPLAY = {
    label: code for code, label in MATCH_MODE_DISPLAY_BY_CODE.items()
}
AI_SIDE_DISPLAY_BY_CODE = {
    code: TEAM_DISPLAY_BY_CODE[code]
    for code in TEAM_DISPLAY_BY_CODE
}
AI_SIDE_CODE_BY_DISPLAY = {
    label: code for code, label in AI_SIDE_DISPLAY_BY_CODE.items()
}

FORGE_RULES_TEXT_HUMAN = (
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
        self.team_locked = False
        self.default_team_label = TEAM_DISPLAY_BY_CODE[
            "A" if slot_number % 2 == 1 else "B"
        ]

        self.grid_columnconfigure(2, weight=1)

        self.slot_badge = create_badge(
            self,
            f"Poste {slot_number}",
            tone="neutral",
        )
        self.slot_badge.grid(
            row=0,
            column=0,
            padx=(14, 10),
            pady=12,
            sticky="w",
        )

        self.active_checkbox = ctk.CTkCheckBox(
            self,
            text="Activer",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            fg_color=PALETTE["gold"],
            hover_color=PALETTE["gold_hover"],
            border_color=PALETTE["border_strong"],
            command=self._toggle_active,
        )
        self.active_checkbox.grid(
            row=0,
            column=1,
            padx=(0, 10),
            pady=12,
            sticky="w",
        )

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
        self.team_combo.grid(
            row=0,
            column=3,
            padx=(10, 14),
            pady=12,
            sticky="e",
        )
        self._apply_slot_state(False)
        self.team_combo.set(self.default_team_label)

    def _apply_slot_state(self, is_active: bool):
        team_code = self._current_team_code()
        team_state = "disabled" if self.team_locked else "readonly"
        accent_color = PALETTE["gold"] if team_code == "A" else PALETTE["cyan"]
        accent_hover = (
            PALETTE["gold_hover"]
            if team_code == "A"
            else PALETTE["cyan_hover"]
        )
        accent_border = (
            PALETTE["gold_dim"]
            if team_code == "A"
            else PALETTE["cyan_dim"]
        )

        self.active_checkbox.configure(
            fg_color=accent_color,
            hover_color=accent_hover,
            border_color=accent_border,
        )

        if is_active:
            self.configure(
                fg_color=PALETTE["surface"],
                border_color=accent_border,
            )
            self.player_combo.configure(
                state="normal",
                text_color=PALETTE["text"],
            )
            self.team_combo.configure(
                state=team_state,
                text_color=PALETTE["text"],
            )
            update_badge(
                self.slot_badge,
                f"Poste {self.slot_number}",
                "gold" if team_code == "A" else "info",
            )
        else:
            self.configure(
                fg_color=PALETTE["panel_alt"],
                border_color=PALETTE["border"],
            )
            self.player_combo.configure(
                state="disabled",
                text_color=PALETTE["text_soft"],
            )
            self.team_combo.configure(
                state=team_state,
                text_color=PALETTE["text_soft"],
            )
            update_badge(
                self.slot_badge,
                f"Poste {self.slot_number}",
                "neutral",
            )

        self.player_combo.configure(
            border_color=accent_border,
            button_color=accent_border,
            button_hover_color=accent_color,
        )
        self.team_combo.configure(
            border_color=accent_border,
            button_color=accent_border,
            button_hover_color=accent_color,
        )

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
        self.on_change()

    def set_team_code(self, team_code: str):
        team_label = TEAM_DISPLAY_BY_CODE.get(
            team_code,
            TEAM_DISPLAY_BY_CODE["A"],
        )
        self.team_combo.set(team_label)
        self._apply_slot_state(self.active_checkbox.get() == 1)

    def lock_team(self, team_code: str):
        self.team_locked = True
        self.set_team_code(team_code)

    def unlock_team(self):
        self.team_locked = False
        self._apply_slot_state(self.active_checkbox.get() == 1)

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
            "team": TEAM_CODE_BY_DISPLAY.get(
                self.team_combo.get().strip(),
                "A",
            ),
        }


class PlayerSelectView(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        style_window(self)

        self._forge_open_started_at = time.perf_counter()
        self._forge_first_paint_logged = False
        self._registry_loading = False
        self._registry_request_token = 0
        self._registry_result_queue = queue.SimpleQueue()
        self.parent = parent
        self.player_options = []
        self.registry_available = None
        self.duration_values = [
            str(duration) for duration in MATCH_DURATION_OPTIONS
        ]
        self.match_mode_var = ctk.StringVar(
            value=MATCH_MODE_DISPLAY_BY_CODE["human"]
        )
        self.human_team_var = ctk.StringVar(
            value=AI_SIDE_DISPLAY_BY_CODE["A"]
        )
        self.ai_difficulty_var = ctk.StringVar(
            value=AI_DIFFICULTY_DISPLAY_BY_CODE["standard"]
        )
        self.match_duration_var = ctk.StringVar(
            value=str(MATCH_DURATION_SECONDS)
        )
        self.title("Arena Duel - Forge locale")
        self.geometry("1380x900")
        enable_large_window(self, 1180, 820)
        _ico = resource_path("assets", "icons", "app.ico")
        self.after(200, lambda: self._apply_icon(_ico))

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.grab_set()
        self.after(100, lambda: self.attributes("-topmost", True))
        self.after(200, lambda: self.attributes("-topmost", False))

        self._build_ui()
        self._trace_perf("ui-shell-ready")
        self._set_registry_loading_state(
            "Ouverture de la forge et lecture du registre..."
        )
        self._refresh_forge_state()
        self.after_idle(self._handle_first_paint)
        # Ouvrir maximisé pour garantir que tout le contenu est visible
        self.after(60, lambda: self.state("zoomed"))

    def _apply_icon(self, path: str):
        try:
            self.iconbitmap(path)
        except (OSError, TclError):
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        header = ctk.CTkFrame(self, corner_radius=22)
        style_frame(header, tone="panel", border_color=PALETTE["gold_dim"])
        header.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=20,
            pady=(20, 10),
            sticky="ew",
        )
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            header,
            text="Forge de la joute",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        )
        title.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="w")

        self.status_badge = create_badge(
            header,
            "Forge en veille",
            tone="gold",
        )
        self.status_badge.grid(
            row=0,
            column=0,
            padx=20,
            pady=(18, 6),
            sticky="e",
        )

        subtitle = ctk.CTkLabel(
            header,
            text=(
                "Assemble deux bastions équilibrés, choisis les combattants "
                "et prépare une joute en 1v1, 2v2 ou 3v3."
            ),
            font=TYPOGRAPHY["subtitle"],
            text_color=PALETTE["text_muted"],
            wraplength=860,
            justify="left",
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        left_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(left_frame, tone="panel", border_color=PALETTE["border"])
        left_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
        left_frame.grid_rowconfigure(3, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        slots_title = ctk.CTkLabel(
            left_frame,
            text="Composition des bastions",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        slots_title.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="w")

        self.slots_hint = ctk.CTkLabel(
            left_frame,
            text=(
                "Active 2, 4 ou 6 postes. Chaque bastion doit garder le "
                "même nombre de combattants avant l'ouverture de la joute."
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            wraplength=760,
            justify="left",
        )
        self.slots_hint.grid(
            row=1,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="w",
        )

        formation_strip = ctk.CTkFrame(left_frame, corner_radius=16)
        style_frame(
            formation_strip,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        formation_strip.grid(
            row=2,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="ew",
        )
        formation_strip.grid_columnconfigure((0, 1, 2), weight=1)

        self.left_format_value = self._build_stat_card(
            formation_strip,
            0,
            0,
            "Cadence active",
            "Veille",
        )
        self.left_duration_value = self._build_stat_card(
            formation_strip,
            0,
            1,
            "Duree scellee",
            format_match_duration_label(self._get_selected_duration_seconds()),
        )
        self.left_mode_value = self._build_stat_card(
            formation_strip,
            0,
            2,
            "Adversaire",
            "Humains",
        )

        slots_shell = ctk.CTkFrame(left_frame, corner_radius=14)
        style_frame(
            slots_shell,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        slots_shell.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="nsew")
        slots_shell.grid_columnconfigure(0, weight=1)

        slots_columns = ctk.CTkFrame(slots_shell, fg_color="transparent")
        slots_columns.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        slots_columns.grid_columnconfigure(2, weight=1)

        column_specs = (
            ("Poste", 0, "w"),
            ("Etat", 1, "w"),
            ("Combattant", 2, "w"),
            ("Bastion", 3, "e"),
        )
        for label_text, column, anchor in column_specs:
            header_label = ctk.CTkLabel(
                slots_columns,
                text=label_text,
                font=TYPOGRAPHY["small_bold"],
                text_color=PALETTE["text_soft"],
                anchor=anchor,
                justify="left",
            )
            header_label.grid(row=0, column=column, padx=8, sticky="ew")

        self.slots_frame = ctk.CTkFrame(slots_shell, fg_color="transparent")
        self.slots_frame.grid(
            row=1,
            column=0,
            padx=0,
            pady=(0, 8),
            sticky="nsew",
        )
        self.slots_frame.grid_columnconfigure(0, weight=1)

        self.slot_rows = []
        for i in range(6):
            row = PlayerSlotRow(
                self.slots_frame,
                i + 1,
                [""],
                on_change=self._refresh_forge_state,
            )
            row.grid(
                row=i,
                column=0,
                padx=10,
                pady=(10 if i == 0 else 0, 10),
                sticky="ew",
            )
            self.slot_rows.append(row)

        right_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(right_frame, tone="panel", border_color=PALETTE["border"])
        right_frame.grid(
            row=2,
            column=1,
            padx=(10, 20),
            pady=10,
            sticky="nsew",
        )
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        setup_frame = ctk.CTkFrame(right_frame, corner_radius=16)
        style_frame(
            setup_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        setup_frame.grid(row=0, column=0, padx=18, pady=(18, 12), sticky="ew")
        setup_frame.grid_columnconfigure((0, 1), weight=1)

        setup_title = ctk.CTkLabel(
            setup_frame,
            text="Paramètres de joute",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        setup_title.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=18,
            pady=(16, 8),
            sticky="w",
        )

        mode_label = ctk.CTkLabel(
            setup_frame,
            text="Mode de joute",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        mode_label.grid(row=1, column=0, padx=18, pady=(0, 4), sticky="w")

        mode_hint = ctk.CTkLabel(
            setup_frame,
            text="Le mode IA complète automatiquement le bastion adverse.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
        )
        mode_hint.grid(row=1, column=1, padx=18, pady=(0, 4), sticky="e")

        self.mode_menu = create_option_menu(
            setup_frame,
            values=list(MATCH_MODE_DISPLAY_BY_CODE.values()),
            variable=self.match_mode_var,
            command=self._handle_match_mode_change,
            width=220,
            height=42,
        )
        self.mode_menu.grid(
            row=2,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="w",
        )

        self.mode_note = ctk.CTkLabel(
            setup_frame,
            text="Deux bastions humains contrôlés au clavier.",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            justify="right",
        )
        self.mode_note.grid(
            row=2,
            column=1,
            padx=18,
            pady=(0, 12),
            sticky="e",
        )

        self.ai_setup_frame = ctk.CTkFrame(
            setup_frame,
            corner_radius=14,
        )
        style_frame(
            self.ai_setup_frame,
            tone="panel",
            border_color=PALETTE["border"],
        )
        self.ai_setup_frame.grid(
            row=3,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 12),
            sticky="ew",
        )
        self.ai_setup_frame.grid_columnconfigure((0, 1), weight=1)

        human_team_label = ctk.CTkLabel(
            self.ai_setup_frame,
            text="Camp humain",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        human_team_label.grid(
            row=0,
            column=0,
            padx=14,
            pady=(12, 6),
            sticky="w",
        )

        ai_difficulty_label = ctk.CTkLabel(
            self.ai_setup_frame,
            text="Difficulté de l'IA",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        ai_difficulty_label.grid(
            row=0,
            column=1,
            padx=14,
            pady=(12, 6),
            sticky="w",
        )

        self.human_team_menu = create_option_menu(
            self.ai_setup_frame,
            values=list(AI_SIDE_DISPLAY_BY_CODE.values()),
            variable=self.human_team_var,
            command=self._handle_ai_setup_change,
            width=210,
            height=40,
        )
        self.human_team_menu.grid(
            row=1,
            column=0,
            padx=14,
            pady=(0, 12),
            sticky="w",
        )

        self.ai_difficulty_menu = create_option_menu(
            self.ai_setup_frame,
            values=list(AI_DIFFICULTY_DISPLAY_BY_CODE.values()),
            variable=self.ai_difficulty_var,
            command=self._handle_ai_setup_change,
            width=210,
            height=40,
        )
        self.ai_difficulty_menu.grid(
            row=1,
            column=1,
            padx=14,
            pady=(0, 12),
            sticky="w",
        )

        duration_label = ctk.CTkLabel(
            setup_frame,
            text="Durée de la partie",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        duration_label.grid(row=4, column=0, padx=18, pady=(0, 4), sticky="w")

        duration_hint = ctk.CTkLabel(
            setup_frame,
            text="Ce choix est réellement transmis au gameplay.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
        )
        duration_hint.grid(row=4, column=1, padx=18, pady=(0, 4), sticky="e")

        self.duration_menu = create_option_menu(
            setup_frame,
            values=self.duration_values,
            variable=self.match_duration_var,
            command=self._handle_duration_change,
            width=160,
            height=42,
        )
        self.duration_menu.grid(
            row=5,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="w",
        )

        selected_duration_label = format_match_duration_label(
            self._get_selected_duration_seconds()
        )
        self.duration_note = ctk.CTkLabel(
            setup_frame,
            text=f"Durée scellée : {selected_duration_label}",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        self.duration_note.grid(
            row=5,
            column=1,
            padx=18,
            pady=(0, 12),
            sticky="e",
        )

        self.rules_box = ctk.CTkTextbox(setup_frame, height=80)
        self.rules_box.grid(
            row=6,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 14),
            sticky="ew",
        )
        style_textbox(self.rules_box)
        set_textbox_content(self.rules_box, FORGE_RULES_TEXT_HUMAN)

        pulse_title = ctk.CTkLabel(
            setup_frame,
            text="Pouls de la forge",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        pulse_title.grid(
            row=7,
            column=0,
            columnspan=2,
            padx=18,
            pady=(4, 8),
            sticky="w",
        )

        self.selection_frame = ctk.CTkFrame(setup_frame, corner_radius=16)
        style_frame(
            self.selection_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        self.selection_frame.grid(
            row=8,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 16),
            sticky="ew",
        )
        self.selection_frame.grid_columnconfigure((0, 1), weight=1)

        self.active_slots_value = self._build_stat_card(
            self.selection_frame,
            0,
            0,
            "Etendards leves",
            "0",
        )
        self.format_value = self._build_stat_card(
            self.selection_frame,
            0,
            1,
            "Cadence",
            "Veille",
        )
        self.balance_value = self._build_stat_card(
            self.selection_frame,
            1,
            0,
            "Equilibre",
            "-",
        )
        self.registered_value = self._build_stat_card(
            self.selection_frame,
            1,
            1,
            "Registre",
            "0",
        )

        register_frame = ctk.CTkFrame(right_frame, corner_radius=16)
        style_frame(
            register_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        register_frame.grid(
            row=1,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="nsew",
        )
        register_frame.grid_columnconfigure((0, 1), weight=1)
        register_frame.grid_rowconfigure(3, weight=1)

        create_title = ctk.CTkLabel(
            register_frame,
            text="Enrôler un combattant",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        create_title.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self.register_count_badge = create_badge(
            register_frame,
            "0 inscrits",
            tone="neutral",
        )
        self.register_count_badge.grid(
            row=0,
            column=1,
            padx=18,
            pady=(16, 8),
            sticky="e",
        )

        self.new_player_entry = ctk.CTkEntry(
            register_frame,
            placeholder_text="Nom du combattant à inscrire",
            height=42,
            font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        self.new_player_entry.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 10),
            sticky="ew",
        )

        add_btn = create_button(
            register_frame,
            "Enrôler ce combattant",
            self._handle_add_player,
            variant="accent",
            height=42,
        )
        add_btn.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 16),
            sticky="ew",
        )

        self.players_list_frame = ctk.CTkScrollableFrame(
            register_frame,
            corner_radius=14,
            height=120,
            fg_color=PALETTE["panel"],
            border_width=1,
            border_color=PALETTE["border"],
        )
        self.players_list_frame.grid(
            row=3,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 18),
            sticky="nsew",
        )
        self.players_list_frame.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(self, corner_radius=16)
        style_frame(footer, tone="panel", border_color=PALETTE["border"])
        footer.grid(
            row=3,
            column=0,
            columnspan=2,
            padx=20,
            pady=(0, 20),
            sticky="ew",
        )
        footer.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.launch_button = create_button(
            footer,
            "Ouvrir la joute",
            self._handle_validate_and_launch,
            variant="primary",
            height=46,
        )
        self.launch_button.grid(
            row=0,
            column=0,
            padx=(16, 8),
            pady=16,
            sticky="ew",
        )

        history_btn = create_button(
            footer,
            "Lire les chroniques",
            self._open_history,
            variant="secondary",
            height=42,
        )
        history_btn.grid(row=0, column=1, padx=8, pady=16, sticky="ew")

        refresh_btn = create_button(
            footer,
            "Actualiser le registre",
            self.refresh_players,
            variant="ghost",
            height=42,
        )
        refresh_btn.grid(row=0, column=2, padx=8, pady=16, sticky="ew")
        self.refresh_button = refresh_btn

        close_btn = create_button(
            footer,
            "Retour au bastion",
            self._handle_close,
            variant="danger",
            height=42,
        )
        close_btn.grid(row=0, column=3, padx=(8, 16), pady=16, sticky="ew")

        self._sync_match_mode_ui()

    def _build_stat_card(
        self,
        master,
        row: int,
        column: int,
        label_text: str,
        value_text: str,
    ):
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

    def _render_registered_players(self, rows):
        for widget in self.players_list_frame.winfo_children():
            widget.destroy()

        if not rows:
            empty_state = ctk.CTkLabel(
                self.players_list_frame,
                text=(
                    "Aucun combattant n'est encore inscrit dans le "
                    "registre.\n\n"
                    "Enrole un premier nom pour reveiller la forge."
                ),
                font=TYPOGRAPHY["body"],
                text_color=PALETTE["text_soft"],
                justify="left",
                anchor="w",
            )
            empty_state.grid(row=0, column=0, padx=16, pady=18, sticky="ew")
            return

        for index, row in enumerate(rows):
            tone = "gold" if index % 2 == 0 else "info"
            border_color = (
                PALETTE["gold_dim"] if tone == "gold" else PALETTE["cyan_dim"]
            )

            player_card = ctk.CTkFrame(
                self.players_list_frame,
                corner_radius=14,
            )
            style_frame(
                player_card,
                tone="panel_soft",
                border_color=border_color,
            )
            player_card.grid(
                row=index,
                column=0,
                padx=12,
                pady=(12 if index == 0 else 0, 10),
                sticky="ew",
            )
            player_card.grid_columnconfigure(1, weight=1)

            position_badge = create_badge(
                player_card,
                f"#{index + 1:02d}",
                tone=tone,
            )
            position_badge.grid(
                row=0,
                column=0,
                padx=(14, 10),
                pady=(12, 4),
                sticky="w",
            )

            name_label = ctk.CTkLabel(
                player_card,
                text=row[1],
                font=TYPOGRAPHY["body_bold"],
                text_color=PALETTE["text"],
            )
            name_label.grid(
                row=0,
                column=1,
                padx=(0, 14),
                pady=(12, 4),
                sticky="w",
            )

            detail_label = ctk.CTkLabel(
                player_card,
                text=(
                    "Disponible pour la forge locale et les chroniques du "
                    "bastion."
                ),
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_soft"],
                justify="left",
            )
            detail_label.grid(
                row=1,
                column=1,
                padx=(0, 14),
                pady=(0, 12),
                sticky="w",
            )

    def _render_registry_loading_state(self, message: str):
        for widget in self.players_list_frame.winfo_children():
            widget.destroy()

        loading_state = ctk.CTkLabel(
            self.players_list_frame,
            text=message,
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            justify="left",
            anchor="w",
        )
        loading_state.grid(row=0, column=0, padx=16, pady=18, sticky="ew")

    def _trace_perf(self, stage: str, **metrics):
        elapsed_ms = (time.perf_counter() - self._forge_open_started_at) * 1000
        details = [f"open_ms={elapsed_ms:.1f}"]
        for key, value in metrics.items():
            details.append(f"{key}={value}")
        print(f"[forge-perf] {stage} | " + " | ".join(details))

    def _handle_first_paint(self):
        if self._forge_first_paint_logged or not self.winfo_exists():
            return

        self._forge_first_paint_logged = True
        self._trace_perf("first-paint")
        self.refresh_players(reason="initial")

    def _set_registry_loading_state(self, message: str):
        self._registry_loading = True
        update_badge(self.register_count_badge, "Lecture...", "neutral")
        if hasattr(self, "refresh_button"):
            self.refresh_button.configure(state="disabled")
        self._render_registry_loading_state(message)

    def _set_info(
        self,
        text: str,
        badge_text: str = "Veille de la forge",
        tone: str = "neutral",
    ):
        pass

    def _handle_duration_change(self, _choice=None):
        duration_text = format_match_duration_label(
            self._get_selected_duration_seconds()
        )
        self.duration_note.configure(text=f"Durée scellée : {duration_text}")
        self.left_duration_value.configure(text=duration_text)
        self._refresh_forge_state()

    def _get_selected_match_mode(self) -> str:
        return MATCH_MODE_CODE_BY_DISPLAY.get(
            self.match_mode_var.get().strip(),
            "human",
        )

    def _get_selected_human_team(self) -> str:
        return AI_SIDE_CODE_BY_DISPLAY.get(
            self.human_team_var.get().strip(),
            "A",
        )

    def _get_selected_ai_team(self) -> str:
        return get_opposite_team(self._get_selected_human_team())

    def _get_selected_ai_difficulty(self) -> str:
        return AI_DIFFICULTY_CODE_BY_DISPLAY.get(
            self.ai_difficulty_var.get().strip(),
            "standard",
        )

    def _handle_match_mode_change(self, _choice=None):
        self._sync_match_mode_ui()
        self._refresh_forge_state()

    def _handle_ai_setup_change(self, _choice=None):
        self._sync_match_mode_ui()
        self._refresh_forge_state()

    def _build_vs_ai_rules_text(self) -> str:
        human_team_label = TEAM_DISPLAY_BY_CODE[
            self._get_selected_human_team()
        ]
        ai_team_label = TEAM_DISPLAY_BY_CODE[self._get_selected_ai_team()]
        return (
            "Formats autorisés contre l'ordinateur :\n"
            "- Duel assisté : 1 combattant humain\n"
            "- Escarmouche assistée : 2 combattants humains\n"
            "- Mêlée assistée : 3 combattants humains\n\n"
            "Conditions de scellage :\n"
            "- tous les combattants humains restent dans "
            f"{human_team_label.lower()}\n"
            "- aucun doublon dans les noms\n"
            f"- l'ordinateur complète automatiquement {ai_team_label.lower()}"
        )

    def _sync_match_mode_ui(self):
        is_vs_ai = self._get_selected_match_mode() == "ai"
        human_team = self._get_selected_human_team()
        ai_team = self._get_selected_ai_team()
        ai_team_label = TEAM_DISPLAY_BY_CODE[ai_team]
        difficulty_label = AI_DIFFICULTY_DISPLAY_BY_CODE[
            self._get_selected_ai_difficulty()
        ]

        if is_vs_ai:
            self.slots_hint.configure(
                text=(
                    "Active 1, 2 ou 3 postes humains. L'ordinateur "
                    f"complète automatiquement {ai_team_label.lower()} avec "
                    "le même nombre de combattants."
                )
            )
            self.mode_note.configure(
                text=(
                    f"{ai_team_label} sera joué par l'ordinateur · "
                    "les flèches pilotent en priorité le premier humain."
                )
            )
            self.left_mode_value.configure(text=f"IA · {difficulty_label}")
            self.launch_button.configure(text="Lancer contre l'ordinateur")
            set_textbox_content(self.rules_box, self._build_vs_ai_rules_text())
            self.human_team_menu.configure(state="normal")
            self.ai_difficulty_menu.configure(state="normal")
            for row in self.slot_rows:
                row.lock_team(human_team)
        else:
            self.slots_hint.configure(
                text=(
                    "Active 2, 4 ou 6 postes. Chaque bastion doit garder le "
                    "même nombre de combattants avant l'ouverture de la joute."
                )
            )
            self.mode_note.configure(
                text="Deux bastions humains contrôlés au clavier."
            )
            self.left_mode_value.configure(text="Humains")
            self.launch_button.configure(text="Ouvrir la joute")
            set_textbox_content(self.rules_box, FORGE_RULES_TEXT_HUMAN)
            self.human_team_menu.configure(state="disabled")
            self.ai_difficulty_menu.configure(state="disabled")
            for row in self.slot_rows:
                row.unlock_team()

    def _get_selected_duration_seconds(self) -> int:
        try:
            return int(self.match_duration_var.get().strip())
        except ValueError:
            return MATCH_DURATION_SECONDS

    def _refresh_forge_state(self):
        selected_players = self._collect_selected_players()
        total = len(selected_players)
        match_mode = self._get_selected_match_mode()
        is_vs_ai = match_mode == "ai"
        team_a_count = sum(
            1 for player in selected_players if player["team"] == "A"
        )
        team_b_count = sum(
            1 for player in selected_players if player["team"] == "B"
        )
        registered_count = len(
            [name for name in self.player_options if name.strip()]
        )

        self.active_slots_value.configure(text=str(total))
        self.balance_value.configure(
            text=(
                f"{total} humain(s) / {total} IA"
                if total and is_vs_ai
                else (f"{team_a_count} / {team_b_count}" if total else "-")
            )
        )
        self.registered_value.configure(text=str(registered_count))

        if self._registry_loading:
            update_badge(self.status_badge, "Forge en ouverture", "neutral")
            return

        if self.registry_available is False:
            update_badge(self.status_badge, "Registre indisponible", "danger")
            self._set_info(
                (
                    "Le sanctuaire des chroniques ne repond pas. Tu peux "
                    "encore consulter la forge, mais l'enrolement et les "
                    "archives locales restent indisponibles tant que la base "
                    "ne revient pas."
                ),
                badge_text="Sanctuaire hors ligne",
                tone="danger",
            )
            return

        if is_vs_ai:
            format_label = {
                0: "Veille",
                1: "Duel IA",
                2: "Escarmouche IA",
                3: "Melee IA",
            }.get(total, "A completer")
        else:
            format_label = {
                0: "Veille",
                2: "Duel",
                4: "Escarmouche",
                6: "Melee",
            }.get(total, "A completer")
        self.format_value.configure(text=format_label)
        self.left_format_value.configure(text=format_label)
        duration_text = format_match_duration_label(
            self._get_selected_duration_seconds()
        )
        self.duration_note.configure(text=f"Durée scellée : {duration_text}")
        self.left_duration_value.configure(text=duration_text)

        if registered_count == 0:
            update_badge(self.status_badge, "Registre vide", "warning")
            self._set_info(
                (
                    "Le registre est vide. Enrole d'abord un combattant pour "
                    "commencer a forger une joute."
                ),
                badge_text="Registre a remplir",
                tone="warning",
            )
            return

        if total == 0:
            update_badge(self.status_badge, "Forge prete", "gold")
            if is_vs_ai:
                ai_team_label = TEAM_DISPLAY_BY_CODE[
                    self._get_selected_ai_team()
                ]
                self._set_info(
                    (
                        "Active 1, 2 ou 3 postes humains. La forge générera "
                        f"ensuite {ai_team_label.lower()} contrôlé par "
                        "l'ordinateur, "
                        "avec un nombre égal de combattants."
                    ),
                    badge_text="Veille de la forge",
                    tone="neutral",
                )
            else:
                self._set_info(
                    (
                        "Active 2, 4 ou 6 postes, choisis les combattants "
                        "puis garde le meme nombre de guerriers dans chaque "
                        "bastion."
                    ),
                    badge_text="Veille de la forge",
                    tone="neutral",
                )
            return

        ok, message = self._validate_selection(selected_players)
        if ok:
            update_badge(self.status_badge, "Formation equilibree", "success")
            self._set_info(
                message,
                badge_text="Etendards leves",
                tone="success",
            )
        else:
            update_badge(self.status_badge, "Forge en cours", "warning")
            self._set_info(
                message,
                badge_text="Forge en cours",
                tone="warning",
            )

    def refresh_players(self, reason: str = "manual"):
        if self._registry_loading:
            return

        self._registry_request_token += 1
        request_token = self._registry_request_token
        self._set_registry_loading_state("Lecture du registre en cours...")
        self._trace_perf("registry-load-start", reason=reason)

        worker = threading.Thread(
            target=self._load_registry_worker,
            args=(request_token, reason),
            daemon=True,
        )
        worker.start()
        self.after(25, self._drain_registry_results)

    def _load_registry_worker(self, request_token: int, reason: str):
        query_started_at = time.perf_counter()
        registry_available, rows = get_player_registry_snapshot()
        query_elapsed_ms = (time.perf_counter() - query_started_at) * 1000

        self._registry_result_queue.put(
            (
                request_token,
                registry_available,
                rows,
                reason,
                query_elapsed_ms,
            )
        )

    def _drain_registry_results(self):
        if not self.winfo_exists():
            return

        processed_result = False
        while True:
            try:
                payload = self._registry_result_queue.get_nowait()
            except queue.Empty:
                break

            processed_result = True
            self._apply_registry_snapshot(*payload)

        if self._registry_loading and not processed_result:
            self.after(25, self._drain_registry_results)

    def _apply_registry_snapshot(
        self,
        request_token: int,
        registry_available: bool,
        rows,
        reason: str,
        query_elapsed_ms: float,
    ):
        if (
            not self.winfo_exists()
            or request_token != self._registry_request_token
        ):
            return

        apply_started_at = time.perf_counter()
        self._registry_loading = False
        self.registry_available = registry_available
        self.player_options = [row[1] for row in rows]
        player_count = len(rows)

        if not self.player_options:
            self.player_options = [""]

        for row in self.slot_rows:
            row.set_player_values(self.player_options)

        if rows:
            update_badge(
                self.register_count_badge,
                f"{player_count} inscrit{'s' if player_count > 1 else ''}",
                "success",
            )
        else:
            update_badge(self.register_count_badge, "0 inscrit", "neutral")

        if hasattr(self, "refresh_button"):
            self.refresh_button.configure(state="normal")

        self._render_registered_players(rows)
        self._refresh_forge_state()

        apply_elapsed_ms = (time.perf_counter() - apply_started_at) * 1000
        self._trace_perf(
            "registry-load-done",
            reason=reason,
            db_ms=f"{query_elapsed_ms:.1f}",
            ui_ms=f"{apply_elapsed_ms:.1f}",
            rows=player_count,
            db_ok=registry_available,
        )

    def _handle_add_player(self):
        play_click()
        username = self.new_player_entry.get().strip()
        ok, message = create_player(username)

        if ok:
            self.new_player_entry.delete(0, "end")
            self.refresh_players(reason="post-add")
            update_badge(self.status_badge, "Combattant enrôle", "success")
            self._set_info(
                message,
                badge_text="Combattant enrôle",
                tone="success",
            )
        else:
            play_error()
            update_badge(self.status_badge, "Enrôlement refusé", "warning")
            self._set_info(
                message,
                badge_text="Enrôlement refusé",
                tone="warning",
            )

    def _collect_selected_players(self):
        selected = []
        for row in self.slot_rows:
            data = row.get_data()
            if data is not None:
                selected.append(data)
        return selected

    def _validate_selection(self, players_data):
        if self._get_selected_match_mode() == "ai":
            return self._validate_vs_ai_selection(players_data)

        total = len(players_data)

        if total not in (2, 4, 6):
            return (
                False,
                "Active 2, 4 ou 6 combattants pour ouvrir une joute valable.",
            )

        names = [p["name"] for p in players_data]
        if any(not name for name in names):
            return False, "Un emplacement actif attend encore un combattant."

        if len(names) != len(set(names)):
            return (
                False,
                "Un même combattant ne peut pas servir deux emplacements "
                "dans la même joute.",
            )

        team_a = [p for p in players_data if p["team"] == "A"]
        team_b = [p for p in players_data if p["team"] == "B"]

        expected_per_team = total // 2

        if (
            len(team_a) != expected_per_team
            or len(team_b) != expected_per_team
        ):
            return False, (
                f"Formation déséquilibrée : pour {total} combattants, il faut "
                f"{expected_per_team} combattant(s) dans chacun des deux "
                "bastions."
            )

        return (
            True,
            "Formation validée. Les deux bastions sont prêts à entrer dans "
            "l'arène.",
        )

    def _validate_vs_ai_selection(self, players_data):
        total = len(players_data)
        human_team = self._get_selected_human_team()
        human_team_label = TEAM_DISPLAY_BY_CODE[human_team]

        if total not in (1, 2, 3):
            return (
                False,
                "Active 1, 2 ou 3 combattants humains pour lancer une "
                "joute contre l'ordinateur.",
            )

        names = [p["name"] for p in players_data]
        if any(not name for name in names):
            return False, "Un emplacement actif attend encore un combattant."

        if len(names) != len(set(names)):
            return (
                False,
                "Un même combattant ne peut pas servir deux emplacements "
                "dans la même joute.",
            )

        invalid_teams = [
            player
            for player in players_data
            if player.get("team") != human_team
        ]
        if invalid_teams:
            return (
                False,
                "En mode contre l'ordinateur, les combattants humains "
                f"restent dans {human_team_label.lower()}."
            )

        return (
            True,
            f"Formation validée. {human_team_label} entrera dans l'arène "
            "avec un adversaire contrôlé par l'ordinateur de taille "
            "équivalente.",
        )

    def _build_launch_players(self, players_data):
        if self._get_selected_match_mode() == "ai":
            human_team = self._get_selected_human_team()
            return build_human_vs_ai_players(
                players_data,
                human_team=human_team,
                ai_team=self._get_selected_ai_team(),
                difficulty=self._get_selected_ai_difficulty(),
                prefer_arrow_controls=True,
            )

        return [
            {
                **player,
                "control_mode": HUMAN_CONTROL_MODE,
            }
            for player in players_data
        ]

    def _handle_validate_and_launch(self):
        play_transition()
        players_data = self._collect_selected_players()
        ok, message = self._validate_selection(players_data)
        is_vs_ai = self._get_selected_match_mode() == "ai"

        self._set_info(
            message,
            badge_text="Verdict de la forge" if ok else "Forge en cours",
            tone="success" if ok else "warning",
        )

        if not ok:
            update_badge(self.status_badge, "Formation à reprendre", "warning")
            play_error()
            messagebox.showwarning("Formation à reprendre", message)
            return

        update_badge(self.status_badge, "Joute en préparation", "gold")
        selected_duration = self._get_selected_duration_seconds()
        ai_difficulty_label = AI_DIFFICULTY_DISPLAY_BY_CODE[
            self._get_selected_ai_difficulty()
        ]
        ai_team_label = TEAM_DISPLAY_BY_CODE[self._get_selected_ai_team()]
        self._set_info(
            (
                "La forge scelle la formation. "
                + (
                    f"{ai_team_label} sera immédiatement confié à "
                    f"l'ordinateur ({ai_difficulty_label}). "
                    if is_vs_ai
                    else ""
                )
                + "La joute va s'ouvrir pour "
                + f"{format_match_duration_label(selected_duration)}."
            ),
            badge_text="Joute en préparation",
            tone="gold",
        )

        self.parent.withdraw()
        self.destroy()

        from game.game_window import run_game
        stop_music(fade_ms=180)
        launch_players = self._build_launch_players(players_data)
        result = run_game(
            launch_players,
            match_duration_seconds=selected_duration,
        )

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
                f"{result['winner_text']}\n\n{save_message}",
            )

    def _open_history(self):
        play_transition()
        self._set_info(
            (
                "Les chroniques locales s'ouvrent pour revoir les verdicts et "
                "la forme recente des bastions."
            ),
            badge_text="Chroniques ouvertes",
            tone="gold",
        )
        HistoryView(
            self,
            source_label="Chroniques locales du bastion",
        )

    def _handle_close(self):
        play_click()
        self.grab_release()
        self.destroy()
