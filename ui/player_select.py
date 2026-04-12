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
    init_audio,
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
from runtime_utils import is_runtime_flag_enabled, resource_path
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
    load_ctk_image,
    load_launcher_background_image,
    present_window,
    update_badge,
)


TEAM_DISPLAY_BY_CODE = {
    "A": get_team_label("A"),
    "B": get_team_label("B"),
}
TEAM_CODE_BY_DISPLAY = {label: code for code, label in TEAM_DISPLAY_BY_CODE.items()}
MATCH_MODE_DISPLAY_BY_CODE = {
    "human": "Joute locale",
    "ai": "Contre l'ordinateur",
}
MATCH_MODE_CODE_BY_DISPLAY = {
    label: code for code, label in MATCH_MODE_DISPLAY_BY_CODE.items()
}
AI_SIDE_DISPLAY_BY_CODE = {
    code: TEAM_DISPLAY_BY_CODE[code] for code in TEAM_DISPLAY_BY_CODE
}
AI_SIDE_CODE_BY_DISPLAY = {
    label: code for code, label in AI_SIDE_DISPLAY_BY_CODE.items()
}
FIGHTER_DISPLAY_BY_SPRITE_ID = {
    "skeleton_fighter_ember": "Ember · dueliste",
    "skeleton_fighter_aether": "Aether · gardien",
}
FIGHTER_SPRITE_ID_BY_DISPLAY = {
    label: sprite_id for sprite_id, label in FIGHTER_DISPLAY_BY_SPRITE_ID.items()
}
DEFAULT_FIGHTER_BY_TEAM = {
    "A": "skeleton_fighter_ember",
    "B": "skeleton_fighter_aether",
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


def get_default_fighter_id(team_code: str) -> str:
    return DEFAULT_FIGHTER_BY_TEAM.get(
        str(team_code or "A").upper(),
        DEFAULT_FIGHTER_BY_TEAM["A"],
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
        self.default_fighter_id = get_default_fighter_id(
            "A" if slot_number % 2 == 1 else "B"
        )

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

        self.fighter_combo = ctk.CTkComboBox(
            self,
            values=list(FIGHTER_SPRITE_ID_BY_DISPLAY.keys()),
            width=190,
            state="disabled",
            font=TYPOGRAPHY["body_bold"],
            dropdown_font=TYPOGRAPHY["body"],
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            button_color=PALETTE["surface"],
            button_hover_color=PALETTE["border_strong"],
            text_color=PALETTE["text_muted"],
            command=self._handle_fighter_change,
        )
        self.fighter_combo.grid(
            row=0,
            column=3,
            padx=10,
            pady=12,
            sticky="ew",
        )

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
            column=4,
            padx=(10, 14),
            pady=12,
            sticky="e",
        )
        self._apply_slot_state(False)
        self.team_combo.set(self.default_team_label)
        self.set_fighter_id(self.default_fighter_id)

    def _apply_slot_state(self, is_active: bool):
        team_code = self._current_team_code()
        team_state = "disabled" if self.team_locked else "readonly"
        accent_color = PALETTE["gold"] if team_code == "A" else PALETTE["cyan"]
        accent_hover = (
            PALETTE["gold_hover"] if team_code == "A" else PALETTE["cyan_hover"]
        )
        accent_border = PALETTE["gold_dim"] if team_code == "A" else PALETTE["cyan_dim"]

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
            self.fighter_combo.configure(
                state="readonly",
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
            self.fighter_combo.configure(
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
        self.fighter_combo.configure(
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
        if not self.fighter_combo.get().strip():
            self.set_fighter_id(self._default_fighter_id_for_current_team())
        self._notify_change()

    def _current_team_code(self) -> str:
        return TEAM_CODE_BY_DISPLAY.get(self.team_combo.get().strip(), "A")

    def _default_fighter_id_for_current_team(self) -> str:
        return get_default_fighter_id(self._current_team_code())

    def _current_fighter_id(self) -> str:
        return FIGHTER_SPRITE_ID_BY_DISPLAY.get(
            self.fighter_combo.get().strip(),
            self._default_fighter_id_for_current_team(),
        )

    def _handle_team_change(self, _choice=None):
        if self.active_checkbox.get() != 1:
            self.set_fighter_id(self._default_fighter_id_for_current_team())
        self._apply_slot_state(self.active_checkbox.get() == 1)
        self._notify_change()

    def _handle_fighter_change(self, _choice=None):
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

    def set_fighter_id(self, sprite_id: str):
        fighter_label = FIGHTER_DISPLAY_BY_SPRITE_ID.get(
            sprite_id,
            FIGHTER_DISPLAY_BY_SPRITE_ID[self.default_fighter_id],
        )
        self.fighter_combo.set(fighter_label)

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
            "sprite_id": self._current_fighter_id(),
        }


class PlayerSelectView(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        style_window(self)

        self._forge_open_started_at = time.perf_counter()
        self._forge_first_paint_logged = False
        self._registry_loading = False
        self._add_player_in_progress = False
        self._launch_in_progress = False
        self._registry_request_token = 0
        self._registry_result_queue = queue.SimpleQueue()
        self.parent = parent
        self.history_window = None
        self.player_options = []
        self.registry_available = None
        self.duration_values = [str(duration) for duration in MATCH_DURATION_OPTIONS]
        self.match_mode_var = ctk.StringVar(value=MATCH_MODE_DISPLAY_BY_CODE["human"])
        self.human_team_var = ctk.StringVar(value=AI_SIDE_DISPLAY_BY_CODE["A"])
        self.ai_difficulty_var = ctk.StringVar(
            value=AI_DIFFICULTY_DISPLAY_BY_CODE["standard"]
        )
        self.match_duration_var = ctk.StringVar(value=str(MATCH_DURATION_SECONDS))
        screen_width = max(1360, self.winfo_screenwidth())
        screen_height = max(860, self.winfo_screenheight())
        self.background_image = load_launcher_background_image(
            "assets",
            "backgrounds",
            "launcher_twilight_bastion_bg.png",
            size=(screen_width, screen_height),
            fallback_label="forge locale",
        )
        self.logo_image = load_ctk_image(
            "assets",
            "icons",
            "icon_preview_256.png",
            size=(104, 104),
            fallback_label="arena duel",
            remove_edge_dark_regions=True,
            crop_to_visible_bounds=True,
        )
        self.title("Arena Duel - Forge locale")
        self.geometry("1380x900")
        enable_large_window(self, 1180, 820)
        _ico = resource_path("assets", "icons", "app.ico")
        self.after(200, lambda: self._apply_icon(_ico))

        self.lift()
        self.focus_force()

        self._build_ui()
        self._set_info(
            "Ouverture de la forge et lecture du registre...",
            badge_text="Forge en ouverture",
            tone="info",
        )
        present_window(self)
        self._trace_perf("ui-shell-ready")
        self._render_registry_loading_state(
            "Ouverture de la forge et lecture du registre..."
        )
        self._refresh_forge_state()
        self.after(40, lambda: self.refresh_players(reason="initial"))
        self.after(80, self._handle_first_paint)
        # Ouvrir maximisé pour garantir que tout le contenu est visible
        self.after(60, lambda: self.state("zoomed"))
        self.after(120, lambda: present_window(self))

    def _apply_icon(self, path: str):
        try:
            self.iconbitmap(path)
        except (OSError, TclError):
            pass

    def _get_idle_launch_button_text(self) -> str:
        if self._get_selected_match_mode() == "ai":
            return "Lancer contre l'ordinateur"
        return "Ouvrir la joute"

    def _get_live_window(self, window):
        if window is None:
            return None

        try:
            return window if window.winfo_exists() else None
        except TclError:
            return None

    def _focus_or_open_window(self, attr_name, factory):
        existing_window = self._get_live_window(getattr(self, attr_name))
        if existing_window is not None:
            present_window(existing_window)
            return existing_window

        window = factory()
        setattr(self, attr_name, window)
        present_window(window)
        return window

    def _sync_action_controls(self):
        registry_busy = self._registry_loading
        add_busy = self._add_player_in_progress
        launch_busy = self._launch_in_progress
        entry_enabled = not registry_busy and not add_busy and not launch_busy

        self.new_player_entry.configure(state="normal" if entry_enabled else "disabled")

        self.add_button.configure(
            text=("Enrôlement..." if add_busy else "Enrôler ce nouveau combattant"),
            state="normal" if entry_enabled else "disabled",
        )
        self.refresh_button.configure(
            text=(
                "Lecture du registre..." if registry_busy else "Actualiser le registre"
            ),
            state=(
                "disabled" if registry_busy or add_busy or launch_busy else "normal"
            ),
        )
        self.launch_button.configure(
            text=(
                "Ouverture en cours..."
                if launch_busy
                else self._get_idle_launch_button_text()
            ),
            state=(
                "disabled" if registry_busy or add_busy or launch_busy else "normal"
            ),
        )
        self.history_button.configure(state="disabled" if launch_busy else "normal")
        self.close_button.configure(state="disabled" if launch_busy else "normal")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        backdrop = ctk.CTkLabel(
            self,
            text="",
            image=self.background_image,
            fg_color="transparent",
        )
        backdrop.place(x=0, y=0, relwidth=1, relheight=1)

        header = ctk.CTkFrame(self, corner_radius=22)
        style_frame(
            header,
            tone="panel_deep",
            border_color=PALETTE["gold_dim"],
        )
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

        hero_panel = ctk.CTkFrame(header, fg_color="transparent")
        hero_panel.grid(row=0, column=0, padx=20, pady=18, sticky="ew")
        hero_panel.grid_columnconfigure(0, weight=1)
        hero_panel.grid_columnconfigure(1, weight=0)

        create_badge(hero_panel, "Forge locale", tone="gold").grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.status_badge = create_badge(
            hero_panel,
            "Forge en veille",
            tone="gold",
        )
        self.status_badge.grid(
            row=0,
            column=1,
            padx=(14, 0),
            sticky="e",
        )

        title = ctk.CTkLabel(
            hero_panel,
            text="Forge de la joute",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        )
        title.grid(
            row=1,
            column=0,
            columnspan=2,
            pady=(10, 6),
            sticky="w",
        )

        subtitle = ctk.CTkLabel(
            hero_panel,
            text=(
                "Assemble deux bastions equilibres, choisis les combattants "
                "et prepare une joute en 1v1, 2v2 ou 3v3."
            ),
            font=TYPOGRAPHY["subtitle"],
            text_color=PALETTE["text_muted"],
            wraplength=860,
            justify="left",
        )
        subtitle.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
        )

        ctk.CTkLabel(
            header,
            text="",
            image=self.logo_image,
            fg_color="transparent",
        ).grid(
            row=0,
            column=1,
            padx=(0, 22),
            pady=16,
            sticky="e",
        )

        self.info_frame = ctk.CTkFrame(self, corner_radius=18)
        style_frame(
            self.info_frame,
            tone="panel_deep",
            border_color=PALETTE["divider"],
        )
        self.info_frame.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=20,
            pady=(0, 10),
            sticky="ew",
        )
        self.info_frame.grid_columnconfigure(0, weight=0)
        self.info_frame.grid_columnconfigure(1, weight=1)

        self.info_badge = create_badge(
            self.info_frame,
            "Veille de la forge",
            tone="neutral",
        )
        self.info_badge.grid(
            row=0,
            column=0,
            padx=(16, 12),
            pady=14,
            sticky="w",
        )

        self.info_label = ctk.CTkLabel(
            self.info_frame,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=1080,
        )
        self.info_label.grid(
            row=0,
            column=1,
            padx=(0, 16),
            pady=14,
            sticky="ew",
        )

        left_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(
            left_frame,
            tone="panel_deep",
            border_color=PALETTE["divider"],
        )
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
            ("Profil", 3, "w"),
            ("Bastion", 4, "e"),
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
        style_frame(
            right_frame,
            tone="panel_deep",
            border_color=PALETTE["divider"],
        )
        right_frame.grid(
            row=2,
            column=1,
            padx=(10, 20),
            pady=10,
            sticky="nsew",
        )
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        self.right_scroll_frame = ctk.CTkScrollableFrame(
            right_frame,
            corner_radius=12,
            fg_color="transparent",
            scrollbar_button_color=PALETTE["surface"],
            scrollbar_button_hover_color=PALETTE["border_strong"],
        )
        self.right_scroll_frame.grid(
            row=0,
            column=0,
            padx=8,
            pady=8,
            sticky="nsew",
        )
        self.right_scroll_frame.grid_columnconfigure(0, weight=1)

        setup_frame = ctk.CTkFrame(self.right_scroll_frame, corner_radius=16)
        style_frame(
            setup_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        setup_frame.grid(
            row=0,
            column=0,
            padx=10,
            pady=(10, 12),
            sticky="ew",
        )
        setup_frame.grid_columnconfigure(0, weight=0, minsize=176)
        setup_frame.grid_columnconfigure(1, weight=1)

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
            wraplength=190,
            justify="left",
        )
        mode_hint.grid(row=1, column=1, padx=18, pady=(0, 4), sticky="w")

        self.mode_menu = create_option_menu(
            setup_frame,
            values=list(MATCH_MODE_DISPLAY_BY_CODE.values()),
            variable=self.match_mode_var,
            command=self._handle_match_mode_change,
            width=170,
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
            wraplength=190,
            justify="left",
        )
        self.mode_note.grid(
            row=2,
            column=1,
            padx=18,
            pady=(0, 12),
            sticky="w",
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
            width=170,
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
            width=170,
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
            wraplength=190,
            justify="left",
        )
        duration_hint.grid(
            row=4,
            column=1,
            padx=18,
            pady=(0, 4),
            sticky="w",
        )

        self.duration_menu = create_option_menu(
            setup_frame,
            values=self.duration_values,
            variable=self.match_duration_var,
            command=self._handle_duration_change,
            width=120,
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
            wraplength=190,
            justify="left",
        )
        self.duration_note.grid(
            row=5,
            column=1,
            padx=18,
            pady=(0, 12),
            sticky="w",
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

        register_frame = ctk.CTkFrame(
            self.right_scroll_frame,
            corner_radius=16,
        )
        style_frame(
            register_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        register_frame.grid(
            row=1,
            column=0,
            padx=10,
            pady=(0, 12),
            sticky="ew",
        )
        register_frame.grid_columnconfigure(0, weight=1)
        register_frame.grid_columnconfigure(1, weight=0)

        create_title = ctk.CTkLabel(
            register_frame,
            text="Enrôler un nouveau combattant",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
            wraplength=240,
            justify="left",
        )
        create_title.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="ew")

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
            placeholder_text="Nom du nouveau combattant",
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
        self.new_player_entry.bind(
            "<Return>",
            lambda _event: self._handle_add_player(),
        )

        self.add_button = create_button(
            register_frame,
            "Enrôler ce nouveau combattant",
            self._handle_add_player,
            variant="accent",
            height=42,
        )
        self.add_button.grid(
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
        style_frame(
            footer,
            tone="panel_deep",
            border_color=PALETTE["divider"],
        )
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

        self.history_button = create_button(
            footer,
            "Lire les chroniques",
            self._open_history,
            variant="secondary",
            height=42,
        )
        self.history_button.grid(
            row=0,
            column=1,
            padx=8,
            pady=16,
            sticky="ew",
        )

        refresh_btn = create_button(
            footer,
            "Actualiser le registre",
            self.refresh_players,
            variant="ghost",
            height=42,
        )
        refresh_btn.grid(row=0, column=2, padx=8, pady=16, sticky="ew")
        self.refresh_button = refresh_btn

        self.close_button = create_button(
            footer,
            "Retour au bastion",
            self._handle_close,
            variant="danger",
            height=42,
        )
        self.close_button.grid(
            row=0,
            column=3,
            padx=(8, 16),
            pady=16,
            sticky="ew",
        )

        self._sync_match_mode_ui()
        self._sync_action_controls()
        self.after(0, backdrop.lower)

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
                    "Enrôle un nouveau combattant pour réveiller la forge."
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
                text=("Disponible pour la forge locale et les chroniques du bastion."),
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
        if not is_runtime_flag_enabled("debug_console_logs"):
            return

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

    def _set_registry_loading_state(self, message: str):
        self._registry_loading = True
        update_badge(self.register_count_badge, "Lecture...", "neutral")
        self._sync_action_controls()
        self._render_registry_loading_state(message)

    def _set_info(
        self,
        text: str,
        badge_text: str = "Veille de la forge",
        tone: str = "neutral",
    ):
        badge_tone_map = {
            "neutral": "neutral",
            "info": "info",
            "success": "success",
            "warning": "warning",
            "danger": "danger",
            "gold": "gold",
        }
        text_color_map = {
            "neutral": PALETTE["text_soft"],
            "info": PALETTE["cyan"],
            "success": PALETTE["success"],
            "warning": PALETTE["warning"],
            "danger": PALETTE["danger"],
            "gold": PALETTE["gold"],
        }
        border_color_map = {
            "neutral": PALETTE["divider"],
            "info": PALETTE["cyan_dim"],
            "success": PALETTE["success_dim"],
            "warning": PALETTE["warning_dim"],
            "danger": PALETTE["danger_dim"],
            "gold": PALETTE["gold_dim"],
        }

        update_badge(
            self.info_badge,
            badge_text,
            badge_tone_map.get(tone, "neutral"),
        )
        self.info_label.configure(
            text=text,
            text_color=text_color_map.get(tone, PALETTE["text_soft"]),
        )
        self.info_frame.configure(
            border_color=border_color_map.get(tone, PALETTE["divider"])
        )

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
        human_team_label = TEAM_DISPLAY_BY_CODE[self._get_selected_human_team()]
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
            self.launch_button.configure(text=self._get_idle_launch_button_text())
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
            self.mode_note.configure(text="Deux bastions humains contrôlés au clavier.")
            self.left_mode_value.configure(text="Humains")
            self.launch_button.configure(text=self._get_idle_launch_button_text())
            set_textbox_content(self.rules_box, FORGE_RULES_TEXT_HUMAN)
            self.human_team_menu.configure(state="disabled")
            self.ai_difficulty_menu.configure(state="disabled")
            for row in self.slot_rows:
                row.unlock_team()

        self._sync_action_controls()

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
        team_a_count = sum(1 for player in selected_players if player["team"] == "A")
        team_b_count = sum(1 for player in selected_players if player["team"] == "B")
        registered_count = len([name for name in self.player_options if name.strip()])

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
                ai_team_label = TEAM_DISPLAY_BY_CODE[self._get_selected_ai_team()]
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
        if not self.winfo_exists() or request_token != self._registry_request_token:
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
            self._sync_action_controls()

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
        if self._registry_loading or self._add_player_in_progress:
            return

        play_click()
        self._add_player_in_progress = True
        update_badge(self.status_badge, "Enrôlement en cours", "info")
        self._set_info(
            "La forge inscrit le combattant dans le registre...",
            badge_text="Enrôlement en cours",
            tone="info",
        )
        self._sync_action_controls()
        self.update_idletasks()

        username = self.new_player_entry.get().strip()
        ok, message = create_player(username)
        self._add_player_in_progress = False

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
            self._sync_action_controls()

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

        if len(team_a) != expected_per_team or len(team_b) != expected_per_team:
            return False, (
                f"Formation déséquilibrée : pour {total} combattants, il faut "
                f"{expected_per_team} combattant(s) dans chacun des deux "
                "bastions."
            )

        return (
            True,
            "Formation validée. Les deux bastions sont prêts à entrer dans l'arène.",
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
            player for player in players_data if player.get("team") != human_team
        ]
        if invalid_teams:
            return (
                False,
                "En mode contre l'ordinateur, les combattants humains "
                f"restent dans {human_team_label.lower()}.",
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
        if (
            self._registry_loading
            or self._add_player_in_progress
            or self._launch_in_progress
        ):
            return

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

        self._launch_in_progress = True
        update_badge(self.status_badge, "Joute en préparation", "gold")
        selected_duration = self._get_selected_duration_seconds()
        ai_difficulty_label = AI_DIFFICULTY_DISPLAY_BY_CODE[
            self._get_selected_ai_difficulty()
        ]
        ai_team_label = TEAM_DISPLAY_BY_CODE[self._get_selected_ai_team()]
        from game.runtime_backend import (
            get_local_game_backend_status,
            run_local_game,
        )

        backend_status = get_local_game_backend_status()
        backend_message = (
            f"La joute locale utilisera {backend_status['effective_label']}."
        )
        if backend_status["fallback_reason"] == "arcade_unavailable":
            backend_message = (
                "Arcade est indisponible dans cet environnement, "
                "bascule automatique vers Pygame."
            )

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
                + f"{format_match_duration_label(selected_duration)}. "
                + backend_message
            ),
            badge_text="Joute en préparation",
            tone="gold",
        )
        self._sync_action_controls()
        self.update_idletasks()

        self.parent.withdraw()
        self.destroy()

        stop_music(fade_ms=180)
        launch_players = self._build_launch_players(players_data)
        result = run_local_game(
            launch_players,
            match_duration_seconds=selected_duration,
        )

        self.parent.deiconify()
        init_audio()
        start_menu_music(restart=True)
        present_window(self.parent)

        if result:
            ok, save_message = save_team_match(
                result["players_data"],
                result["team_a_score"],
                result["team_b_score"],
                result["duration_seconds"],
            )
            if not ok:
                play_error()
            dialog_title = "Verdict de la joute" if ok else "Archive indisponible"
            dialog_handler = messagebox.showinfo if ok else messagebox.showwarning
            dialog_handler(
                dialog_title,
                f"{result['winner_text']}\n\n{save_message}",
                parent=self.parent,
            )

    def _open_history(self):
        if self._launch_in_progress:
            return

        play_transition()
        self._set_info(
            (
                "Les chroniques locales s'ouvrent pour revoir les verdicts et "
                "la forme recente des bastions."
            ),
            badge_text="Chroniques ouvertes",
            tone="gold",
        )
        self._focus_or_open_window(
            "history_window",
            lambda: HistoryView(
                self,
                source_label="Chroniques locales du bastion",
            ),
        )

    def _handle_close(self):
        play_click()
        self.destroy()
