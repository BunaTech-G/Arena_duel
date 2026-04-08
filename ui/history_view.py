import customtkinter as ctk
from tkinter import TclError
from collections import Counter

from db.database import test_connection
from db.matches import get_match_history
from game.audio import play_alert, play_click
from game.match_text import DRAW_LABEL, format_compact_scoreline
from runtime_utils import resource_path
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    enable_large_window,
    style_window,
    style_frame,
    create_button,
    create_badge,
    load_ctk_image,
    update_badge,
)


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
        match_id, p1, p2, winner, s1, s2, duration, played_at = self.match_data
        winner_display = winner if winner else DRAW_LABEL
        duration_text = self._format_duration(duration)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)

        match_badge = create_badge(self, f"Joute #{match_id}", tone="gold")
        match_badge.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        title = ctk.CTkLabel(
            self,
            text="Chronique archivée",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
        )
        title.grid(row=0, column=1, padx=12, pady=(14, 8), sticky="w")

        date_label = ctk.CTkLabel(
            self,
            text=str(played_at),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
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
            text=(
                "Archive complète avec score, verdict et durée réelle de la "
                "joute."
            ),
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
        self.history_preview_image = load_ctk_image(
            "assets",
            "backgrounds",
            "launcher_sanctum_bg.png",
            size=(220, 108),
            fallback_label="sanctum",
        )
        self.history_portrait_image = load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(62, 62),
            fallback_label="mascot",
        )
        self.match_portrait_image = load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(42, 42),
            fallback_label="mascot",
        )

        self.title("Chroniques de l'arène")
        self.geometry("1320x860")
        enable_large_window(self, 1120, 760)
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except (OSError, TclError):
            pass

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
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, corner_radius=20)
        style_frame(header, tone="panel", border_color=PALETTE["gold_dim"])
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            header,
            text="Chroniques de l'arène",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        )
        title.grid(row=0, column=0, padx=20, pady=(16, 6), sticky="w")

        self.source_badge = create_badge(
            header,
            self.source_label,
            tone="gold",
        )
        self.source_badge.grid(
            row=0,
            column=0,
            padx=20,
            pady=(16, 6),
            sticky="e",
        )

        intro = ctk.CTkLabel(
            header,
            text=(
                "Lis les joutes déjà disputées, repère le bastion dominant et "
                "garde les chroniques utiles visibles sans perdre de hauteur "
                "en en-tête."
            ),
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=760,
            justify="left",
        )
        intro.grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        preview_card = ctk.CTkFrame(header, corner_radius=18)
        style_frame(
            preview_card,
            tone="panel_soft",
            border_color=PALETTE["gold_dim"],
        )
        preview_card.grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(10, 20),
            pady=16,
            sticky="nsew",
        )
        preview_card.grid_columnconfigure(1, weight=1)

        preview_image = ctk.CTkLabel(
            preview_card,
            text="",
            image=self.history_preview_image,
        )
        preview_image.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=12,
            pady=(12, 10),
            sticky="ew",
        )

        portrait = ctk.CTkLabel(
            preview_card,
            text="",
            image=self.history_portrait_image,
        )
        portrait.grid(row=1, column=0, padx=(12, 10), pady=(0, 12), sticky="w")

        preview_title = ctk.CTkLabel(
            preview_card,
            text="Archives du sanctum",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        preview_title.grid(
            row=1,
            column=1,
            padx=(0, 12),
            pady=(2, 0),
            sticky="sw",
        )

        preview_hint = ctk.CTkLabel(
            preview_card,
            text="Verdicts locaux\net joutes partagées",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
        )
        preview_hint.grid(
            row=1,
            column=1,
            padx=(0, 12),
            pady=(0, 12),
            sticky="nw",
        )

        self.summary_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(
            self.summary_frame,
            tone="panel_soft",
            border_color=PALETTE["border"],
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
            "Bastion dominant",
            "-",
        )
        self.draws_label = self._build_stat_card(3, "Equilibres parfaits", "0")

        action_frame = ctk.CTkFrame(self, corner_radius=16)
        style_frame(action_frame, tone="panel", border_color=PALETTE["border"])
        action_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=0)

        self.status_label = ctk.CTkLabel(
            action_frame,
            text="",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
        )
        self.status_label.grid(row=0, column=0, padx=18, pady=14, sticky="w")

        refresh_btn = create_button(
            action_frame,
            "Rafraîchir les chroniques",
            self._handle_refresh,
            variant="secondary",
            width=220,
            height=42,
            state="normal" if self.allow_refresh else "disabled",
        )
        refresh_btn.grid(row=0, column=1, padx=18, pady=12, sticky="e")

        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=14)
        self.scroll_frame.grid(
            row=3,
            column=0,
            padx=20,
            pady=(0, 20),
            sticky="nsew",
        )
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        self.scroll_frame.configure(fg_color=PALETTE["panel_soft"])

    def _render_scroll_message(
        self,
        title_text: str,
        detail_text: str,
        tone: str,
    ):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        card = ctk.CTkFrame(self.scroll_frame, corner_radius=18)
        style_frame(card, tone="panel", border_color=PALETTE["border"])
        card.grid(row=0, column=0, padx=12, pady=14, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        badge = create_badge(card, title_text, tone=tone)
        badge.grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")

        detail = ctk.CTkLabel(
            card,
            text=detail_text,
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=880,
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
            self.top_winner_label.configure(text="-")
            self.draws_label.configure(text="0")
            self.status_label.configure(
                text="Le sanctuaire des chroniques est indisponible."
            )
            update_badge(self.source_badge, self.source_label, "danger")
            self._render_scroll_message(
                "Chroniques voilees",
                (
                    "La base des chroniques ne répond pas. Rétablis le "
                    "sanctuaire avant de relire les verdicts archivés."
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
            self.top_winner_label.configure(text="-")
            self.draws_label.configure(text="0")
            self.status_label.configure(
                text="Aucune chronique archivée pour cette source."
            )
            update_badge(self.source_badge, self.source_label, "warning")
            self._render_scroll_message(
                "Aucune joute scellee",
                (
                    "Les prochaines joutes apparaitront ici avec leur "
                    "verdict, leur duree et le bastion qui a impose son "
                    "rythme."
                ),
                "warning",
            )
            return

        # Résumé
        unique_players = set()
        winners = []

        for row in rows:
            _, p1, p2, winner, *_ = row
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
            self.top_winner_label.configure(text="Aucun avantage net")

        draws_count = sum(1 for row in rows if not row[3])
        self.draws_label.configure(text=str(draws_count))

        self.status_label.configure(
            text=(
                f"{len(rows)} chronique(s) chargée(s) depuis "
                f"{self.source_label}."
            )
        )
        update_badge(self.source_badge, self.source_label, "success")

        # Cartes de matchs
        for index, row in enumerate(rows):
            card = MatchCard(
                self.scroll_frame,
                row,
                portrait_image=self.match_portrait_image,
            )
            card.grid(row=index, column=0, padx=8, pady=8, sticky="ew")
