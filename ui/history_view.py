import customtkinter as ctk
from tkinter import TclError
from collections import Counter

from db.database import test_connection
from db.matches import get_match_history
from game.audio import play_alert, play_click
from game.match_text import DRAW_LABEL, format_compact_scoreline
from runtime_utils import get_app_icon_ico_path
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    enable_large_window,
    present_window,
    style_window,
    style_frame,
    style_image_label,
    style_scrollable_frame,
    create_button,
    create_badge,
    load_ctk_image,
    load_launcher_background_image,
    resolve_widget_bg_color,
    update_badge,
)


def _coerce_history_row(row):
    if isinstance(row, dict):
        return {
            "match_id": row.get("match_id"),
            "team_a_players": row.get("team_a_players", "-"),
            "team_b_players": row.get("team_b_players", "-"),
            "winner_display": row.get("winner_display"),
            "team_a_score": row.get("team_a_score", 0),
            "team_b_score": row.get("team_b_score", 0),
            "duration_seconds": row.get("duration_seconds", 0),
            "played_at": row.get("played_at"),
            "mode_code": row.get("mode_code"),
            "source_code": row.get("source_code"),
            "arena_label": row.get("arena_label"),
            "ai_participants": row.get("ai_participants", 0),
        }

    row_data = list(row)
    return {
        "match_id": row_data[0] if len(row_data) > 0 else "?",
        "team_a_players": row_data[1] if len(row_data) > 1 else "-",
        "team_b_players": row_data[2] if len(row_data) > 2 else "-",
        "winner_display": row_data[3] if len(row_data) > 3 else None,
        "team_a_score": row_data[4] if len(row_data) > 4 else 0,
        "team_b_score": row_data[5] if len(row_data) > 5 else 0,
        "duration_seconds": row_data[6] if len(row_data) > 6 else 0,
        "played_at": row_data[7] if len(row_data) > 7 else None,
        "mode_code": "LEGACY",
        "source_code": "LEGACY",
        "arena_label": "Forgotten Sanctum",
        "ai_participants": 0,
    }


def _build_match_context(row_data: dict) -> str:
    mode_code = str(row_data.get("mode_code") or "").upper()
    source_code = str(row_data.get("source_code") or "").upper()
    ai_participants = int(row_data.get("ai_participants") or 0)
    arena_label = str(row_data.get("arena_label") or "").strip()

    if mode_code == "LAN" or source_code == "LAN":
        source_label = "Hall LAN"
    elif mode_code == "LOCAL_AI" or ai_participants > 0:
        source_label = "Forge vs IA"
    elif mode_code == "LEGACY" or source_code == "LEGACY":
        source_label = "Archives héritées"
    else:
        source_label = "Forge locale"

    if arena_label:
        return f"{source_label} · {arena_label}"
    return source_label


def _build_match_footer(row_data: dict) -> str:
    parts = []
    ai_participants = int(row_data.get("ai_participants") or 0)
    mode_code = str(row_data.get("mode_code") or "").upper()

    if mode_code:
        parts.append(_build_match_context(row_data))
    if ai_participants > 0:
        parts.append(f"{ai_participants} IA archivée(s)")

    if not parts:
        return "Archive complète avec score, verdict et durée réelle de la joute."

    return " · ".join(parts)


class MatchCard(ctk.CTkFrame):
    def __init__(self, master, match_data, portrait_image=None):
        super().__init__(master, corner_radius=14)
        style_frame(self, tone="panel", border_color=PALETTE["border"])

        self.match_data = match_data
        self.portrait_image = portrait_image or load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(42, 42),
            fallback_label="mascot",
        )
        self._build_ui()

    def _build_ui(self):
        row_data = _coerce_history_row(self.match_data)
        match_id = row_data["match_id"]
        p1 = row_data["team_a_players"]
        p2 = row_data["team_b_players"]
        winner = row_data["winner_display"]
        s1 = row_data["team_a_score"]
        s2 = row_data["team_b_score"]
        duration = row_data["duration_seconds"]
        played_at = row_data["played_at"]

        winner_display = winner if winner else DRAW_LABEL
        duration_text = self._format_duration(duration)
        context_text = _build_match_context(row_data)
        footer_text = _build_match_footer(row_data)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)

        match_badge = create_badge(self, f"Joute #{match_id}", tone="gold")
        match_badge.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        title = ctk.CTkLabel(
            self,
            text=context_text,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        title.grid(row=0, column=1, padx=12, pady=(14, 8), sticky="w")

        date_label = ctk.CTkLabel(
            self,
            text=str(played_at),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            bg_color=PALETTE["panel"],
            fg_color=PALETTE["panel_soft"],
            corner_radius=999,
            padx=12,
            pady=6,
        )
        date_label.grid(row=0, column=2, padx=16, pady=(14, 8), sticky="e")

        duel_row = ctk.CTkFrame(self, fg_color="transparent")
        duel_row.grid(
            row=1,
            column=0,
            columnspan=3,
            padx=16,
            pady=4,
            sticky="ew",
        )
        duel_row.grid_columnconfigure(0, weight=1)
        duel_row.grid_columnconfigure(1, weight=1)
        duel_row.grid_columnconfigure(2, weight=1)

        left_card = ctk.CTkFrame(duel_row, corner_radius=16)
        style_frame(
            left_card,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        left_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        left_card.grid_columnconfigure(1, weight=1)

        left_portrait = ctk.CTkLabel(
            left_card,
            text="",
            image=self.portrait_image,
        )
        style_image_label(left_portrait)
        left_portrait.grid(
            row=0,
            column=0,
            rowspan=2,
            padx=(12, 10),
            pady=12,
            sticky="w",
        )

        left_title = ctk.CTkLabel(
            left_card,
            text="Bastion braise",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        left_title.grid(
            row=0,
            column=1,
            padx=(0, 12),
            pady=(12, 2),
            sticky="sw",
        )

        duel_label = ctk.CTkLabel(
            left_card,
            text=str(p1),
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            bg_color=resolve_widget_bg_color(self),
            wraplength=240,
            justify="left",
        )
        duel_label.grid(
            row=1,
            column=1,
            padx=(0, 12),
            pady=(0, 12),
            sticky="w",
        )

        center_card = ctk.CTkFrame(duel_row, corner_radius=16)
        style_frame(
            center_card,
            tone="panel",
            border_color=PALETTE["gold_dim"],
        )
        center_card.grid(row=0, column=1, padx=6, sticky="nsew")
        center_card.grid_columnconfigure(0, weight=1)

        score_label = ctk.CTkLabel(
            center_card,
            text=format_compact_scoreline(s1, s2),
            font=TYPOGRAPHY["stat"],
            text_color=PALETTE["text"],
        )
        score_label.grid(row=0, column=0, padx=18, pady=(16, 4))

        winner_tone = "gold" if winner else "warning"
        winner_badge = create_badge(
            center_card,
            f"Verdict : {winner_display}",
            tone=winner_tone,
        )
        winner_badge.grid(row=1, column=0, padx=18, pady=(0, 10))

        duration_label = ctk.CTkLabel(
            center_card,
            text=f"Sablier : {duration_text}",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
        )
        duration_label.grid(row=2, column=0, padx=18, pady=(0, 16))

        right_card = ctk.CTkFrame(duel_row, corner_radius=16)
        style_frame(
            right_card,
            tone="panel_soft",
            border_color=PALETTE["border"],
        )
        right_card.grid(row=0, column=2, padx=(10, 0), sticky="nsew")
        right_card.grid_columnconfigure(0, weight=1)

        right_portrait = ctk.CTkLabel(
            right_card,
            text="",
            image=self.portrait_image,
        )
        style_image_label(right_portrait)
        right_portrait.grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(10, 12),
            pady=12,
            sticky="e",
        )

        right_title = ctk.CTkLabel(
            right_card,
            text="Bastion azur",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        right_title.grid(
            row=0,
            column=0,
            padx=(12, 0),
            pady=(12, 2),
            sticky="se",
        )

        right_names = ctk.CTkLabel(
            right_card,
            text=str(p2),
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            wraplength=240,
            justify="right",
        )
        right_names.grid(
            row=1,
            column=0,
            padx=(12, 0),
            pady=(0, 12),
            sticky="e",
        )

        footer = ctk.CTkLabel(
            self,
            text=footer_text,
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
        )
        footer.grid(
            row=2,
            column=0,
            columnspan=3,
            padx=16,
            pady=(8, 12),
            sticky="w",
        )

    @staticmethod
    def _format_duration(duration) -> str:
        try:
            total_seconds = max(0, int(duration))
        except (TypeError, ValueError):
            total_seconds = 0

        minutes, seconds = divmod(total_seconds, 60)
        if minutes:
            return f"{minutes} min {seconds:02d}s"
        return f"{seconds}s"


class HistoryView(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        history_rows=None,
        source_label="Chroniques locales",
        allow_refresh=True,
    ):
        super().__init__(parent)
        style_window(self)

        self.history_rows = history_rows
        self.source_label = source_label
        self.allow_refresh = allow_refresh
        screen_width = max(1320, self.winfo_screenwidth())
        screen_height = max(860, self.winfo_screenheight())
        self.background_image = load_launcher_background_image(
            "assets",
            "backgrounds",
            "launcher_twilight_bastion_bg.png",
            size=(screen_width, screen_height),
            fallback_label="chroniques bastion",
        )
        self.match_portrait_image = load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(42, 42),
            fallback_label="mascot",
        )

        self.title("Arena Duel - Chroniques")
        self.geometry("1320x860")
        enable_large_window(self, 1120, 760)
        self.configure(fg_color=PALETTE["launcher_blend"])
        _ico = get_app_icon_ico_path()
        self.after(200, lambda: self._apply_icon(_ico))

        self.lift()
        self.focus_force()

        self._build_ui()
        present_window(self)
        self.refresh_history()

    def _apply_icon(self, path: str):
        try:
            self.iconbitmap(path)
        except (OSError, TclError):
            pass

    def _build_ui(self):
        backdrop = ctk.CTkLabel(self, text="", image=self.background_image)
        style_image_label(backdrop)
        backdrop.place(x=0, y=0, relwidth=1, relheight=1)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, corner_radius=22)
        style_frame(
            header,
            tone="panel_deep",
            border_color=PALETTE["gold_dim"],
            border_width=0,
        )
        header.configure(bg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        create_badge(header, "Historique", tone="gold").grid(
            row=0,
            column=0,
            padx=22,
            pady=(22, 12),
            sticky="w",
        )

        self.source_badge = create_badge(
            header,
            self.source_label,
            tone="neutral",
        )
        self.source_badge.grid(
            row=0,
            column=1,
            padx=22,
            pady=(22, 12),
            sticky="e",
        )

        title = ctk.CTkLabel(
            header,
            text="Historique des matchs",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
            justify="left",
            wraplength=720,
        )
        title.grid(row=1, column=0, columnspan=2, padx=22, sticky="w")

        signal_row = ctk.CTkFrame(header, fg_color="transparent")
        signal_row.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=22,
            pady=(14, 22),
            sticky="ew",
        )
        for column in range(4):
            signal_row.grid_columnconfigure(column, weight=1)

        create_badge(signal_row, "Vainqueurs", tone="gold").grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="w",
        )
        create_badge(signal_row, "Scores", tone="info").grid(
            row=0,
            column=1,
            padx=8,
            sticky="w",
        )
        create_badge(signal_row, "Durées", tone="warning").grid(
            row=0,
            column=2,
            padx=8,
            sticky="w",
        )
        create_badge(signal_row, "Sources", tone="neutral").grid(
            row=0,
            column=3,
            padx=8,
            sticky="w",
        )

        self.summary_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(
            self.summary_frame,
            tone="panel_deep",
            border_color=PALETTE["border"],
            border_width=0,
        )
        self.summary_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.total_matches_label = self._build_stat_card(
            0,
            "Joutes archivées",
            "0",
        )
        self.players_label = self._build_stat_card(1, "Combattants vus", "0")
        self.top_winner_label = self._build_stat_card(
            2,
            "Équipe dominante",
            "-",
        )
        self.draws_label = self._build_stat_card(3, "Matchs nuls", "0")

        action_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(
            action_frame,
            tone="panel_deep",
            border_color=PALETTE["border"],
            border_width=0,
        )
        action_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=0)

        self.status_label = ctk.CTkLabel(
            action_frame,
            text="Aucune chronique chargée.",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=860,
            justify="left",
        )
        self.status_label.grid(
            row=0,
            column=0,
            padx=18,
            pady=14,
            sticky="w",
        )

        refresh_btn = create_button(
            action_frame,
            "Actualiser",
            self._handle_refresh,
            variant="ghost",
            width=220,
            height=42,
            state="normal" if self.allow_refresh else "disabled",
        )
        refresh_btn.grid(row=0, column=1, padx=18, pady=12, sticky="e")

        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=18)
        self.scroll_frame.grid(
            row=3,
            column=0,
            padx=20,
            pady=(0, 20),
            sticky="nsew",
        )
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        style_scrollable_frame(self.scroll_frame, tone="panel_deep")

        self.after(0, backdrop.lower)

    def _render_scroll_message(
        self,
        title_text: str,
        detail_text: str,
        tone: str,
    ):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        card = ctk.CTkFrame(self.scroll_frame, corner_radius=20)
        style_frame(card, tone="panel_deep", border_color=PALETTE["border"])
        card.grid(row=0, column=0, padx=12, pady=14, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        badge = create_badge(card, title_text, tone=tone)
        badge.grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")

        detail = ctk.CTkLabel(
            card,
            text=detail_text,
            font=TYPOGRAPHY["body"],
            wraplength=980,
            text_color=PALETTE["text_muted"],
            justify="left",
        )
        detail.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="w")

    def _build_stat_card(self, column: int, label_text: str, value_text: str):
        card = ctk.CTkFrame(self.summary_frame, corner_radius=16)
        style_frame(card, tone="panel", border_color=PALETTE["border"])
        card.grid(row=0, column=column, padx=10, pady=14, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            card,
            text=label_text,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        label.grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")

        value = ctk.CTkLabel(
            card,
            text=value_text,
            font=TYPOGRAPHY["stat"],
            text_color=PALETTE["text"],
        )
        value.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        return value

    def _handle_refresh(self):
        play_click()
        self.refresh_history()

    def refresh_history(self):
        if self.history_rows is not None:
            rows = self.history_rows
        elif not test_connection():
            play_alert()
            self.total_matches_label.configure(text="0")
            self.players_label.configure(text="0")
            self.top_winner_label.configure(text="Indisponible")
            self.draws_label.configure(text="0")
            self.status_label.configure(
                text="Chroniques indisponibles : base locale hors ligne."
            )
            update_badge(self.source_badge, self.source_label, "danger")
            self._render_scroll_message(
                "Chroniques indisponibles",
                (
                    "La base locale ne répond pas. Relance MariaDB puis "
                    "rouvre cette vue."
                ),
                "danger",
            )
            return
        else:
            rows = get_match_history()

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not rows:
            self.total_matches_label.configure(text="0")
            self.players_label.configure(text="0")
            self.top_winner_label.configure(text="Aucune")
            self.draws_label.configure(text="0")
            self.status_label.configure(text="Aucun match dans cette source.")
            update_badge(self.source_badge, self.source_label, "warning")
            self._render_scroll_message(
                "Aucun match archivé",
                "Joue une partie locale ou LAN pour remplir l'historique.",
                "warning",
            )
            return

        # Résumé
        unique_players = set()
        winners = []

        for row in rows:
            row_data = _coerce_history_row(row)
            p1 = row_data["team_a_players"]
            p2 = row_data["team_b_players"]
            winner = row_data["winner_display"]
            for group in (p1, p2):
                for player_name in str(group).split(","):
                    clean_name = player_name.strip()
                    if clean_name:
                        unique_players.add(clean_name)
            if winner:
                winners.append(winner)

        self.total_matches_label.configure(text=str(len(rows)))
        self.players_label.configure(text=str(len(unique_players)))

        if winners:
            winner_counter = Counter(winners)
            top_name, top_count = winner_counter.most_common(1)[0]
            self.top_winner_label.configure(text=f"{top_name} ({top_count})")
        else:
            self.top_winner_label.configure(text="Équilibre")

        draws_count = sum(
            1 for row in rows if not _coerce_history_row(row)["winner_display"]
        )
        self.draws_label.configure(text=str(draws_count))

        self.status_label.configure(text=f"{len(rows)} match(s) chargé(s).")
        update_badge(self.source_badge, self.source_label, "success")

        # Cartes de matchs
        for index, row in enumerate(rows):
            card = MatchCard(
                self.scroll_frame,
                row,
                portrait_image=self.match_portrait_image,
            )
            card.grid(row=index, column=0, padx=8, pady=8, sticky="ew")
