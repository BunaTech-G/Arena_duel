import customtkinter as ctk
import pygame
from tkinter import messagebox

from db.database import test_connection
from game.audio import (
    init_audio,
    play_alert,
    play_click,
    play_error,
    play_transition,
    start_menu_music,
    stop_music,
)
from network.server import start_server_in_background
from ui.player_select import PlayerSelectView
from ui.history_view import HistoryView
from ui.network_lobby import NetworkLobbyView
from runtime_utils import resource_path, set_runtime_override, load_runtime_config
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    apply_theme_settings,
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


apply_theme_settings()


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        style_window(self)

        self.title("Arena Duel - Bastion central")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except Exception:
            pass
        self.geometry("1360x860")
        enable_large_window(self, 1240, 780)

        self.embedded_server = None
        self.embedded_server_thread = None
        self.embedded_server_ip = None
        self.current_db_mode = "local"
        self.tcp_port = int(load_runtime_config().get("tcp_port", 5000))
        self._set_db_mode_local()
        self.launcher_background_image = load_ctk_image(
            "assets",
            "backgrounds",
            "launcher_twilight_bastion_bg.png",
            size=(740, 708),
            fallback_label="twilight bastion",
        )
        self.launcher_portrait_image = load_ctk_image(
            "assets",
            "portraits",
            "skeleton_mascot_portrait.png",
            size=(88, 88),
            fallback_label="mascot",
        )

        # audio
        pygame.mixer.pre_init(44100, -16, 2, 512)
        try:
            pygame.init()
        except Exception:
            pass

        try:
            init_audio()
        except Exception:
            pass
        try:
            start_menu_music()
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._handle_close_app)

        self._build_ui()
        self._set_info(self._default_journal_text(), badge_text="Voie de demo", tone="gold")
        self._set_db_status("Chroniques en veille", "neutral")
        self._set_server_status("Hall au repos", "neutral")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        viewport = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        viewport.grid(row=0, column=0, sticky="nsew")
        viewport.grid_columnconfigure(0, weight=1)

        shell = ctk.CTkFrame(viewport, corner_radius=32)
        style_frame(shell, tone="bg_alt", border_color=PALETTE["border_strong"])
        shell.grid(row=0, column=0, padx=24, pady=24, sticky="ew")
        shell.grid_columnconfigure(0, weight=7)
        shell.grid_columnconfigure(1, weight=4)
        shell.grid_rowconfigure(0, weight=1)

        hero_panel = ctk.CTkFrame(shell, corner_radius=30, width=740, height=708)
        style_frame(hero_panel, tone="panel_soft", border_color=PALETTE["border_strong"])
        hero_panel.grid(row=0, column=0, padx=(22, 12), pady=22, sticky="nsew")
        hero_panel.grid_propagate(False)

        hero_backdrop = ctk.CTkLabel(hero_panel, text="", image=self.launcher_background_image)
        hero_backdrop.place(relx=0.5, rely=0.5, anchor="center")

        scene_tag = ctk.CTkLabel(
            hero_panel,
            text="Sanctum oublié",
            fg_color=PALETTE["bg_alt"],
            text_color=PALETTE["text"],
            font=TYPOGRAPHY["small_bold"],
            corner_radius=999,
            padx=14,
            pady=8,
        )
        scene_tag.place(x=560, y=26)

        hero_intro = ctk.CTkFrame(hero_panel, corner_radius=24, width=440, height=274)
        style_frame(hero_intro, tone="bg_alt", border_color=PALETTE["gold_dim"])
        hero_intro.place(x=28, y=28)
        hero_intro.grid_columnconfigure(0, weight=1)

        crest = create_badge(hero_intro, "Bastion central · joutes et chroniques", tone="gold")
        crest.grid(row=0, column=0, padx=22, pady=(18, 8), sticky="w")

        title = ctk.CTkLabel(
            hero_intro,
            text="Arena Duel",
            font=(TYPOGRAPHY["display"][0], 48, "bold"),
            text_color=PALETTE["text"],
        )
        title.grid(row=1, column=0, padx=22, pady=(0, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            hero_intro,
            text="Un accueil plus net, centré sur l'arène, le rythme et l'envie d'entrer tout de suite en joute.",
            font=TYPOGRAPHY["subtitle"],
            text_color=PALETTE["text_muted"],
            wraplength=410,
            justify="left",
        )
        subtitle.grid(row=2, column=0, padx=22, pady=(0, 10), sticky="w")

        overview = ctk.CTkLabel(
            hero_intro,
            text="Choisis une voie claire, garde l'appel du hall lisible, puis replonge dans le sanctum sans te battre contre l'interface.",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            wraplength=410,
            justify="left",
        )
        overview.grid(row=3, column=0, padx=22, pady=(0, 16), sticky="w")

        chips = ctk.CTkFrame(hero_intro, fg_color="transparent")
        chips.grid(row=4, column=0, padx=22, pady=(0, 20), sticky="w")
        for index, text in enumerate(("Joutes locales", "Hall des bastions", "Chroniques du bastion")):
            chip = ctk.CTkLabel(
                chips,
                text=text,
                font=TYPOGRAPHY["small_bold"],
                text_color=PALETTE["text"],
                fg_color=PALETTE["panel_soft"],
                corner_radius=999,
                padx=12,
                pady=7,
            )
            chip.grid(row=0, column=index, padx=(0, 8 if index < 2 else 0), sticky="w")

        route_card = ctk.CTkFrame(hero_panel, corner_radius=24, width=440, height=146)
        style_frame(route_card, tone="panel", border_color=PALETTE["border"])
        route_card.place(x=28, y=534)
        route_card.grid_columnconfigure(0, weight=1)

        route_title = ctk.CTkLabel(
            route_card,
            text="Itineraire rapide",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        route_title.grid(row=0, column=0, padx=20, pady=(16, 6), sticky="w")

        for row, line in enumerate((
            "1. Ouvre la forge locale pour sentir la map.",
            "2. Ouvre le hall si tu joues a plusieurs sur le poste gardien.",
            "3. Fais entrer un compagnon puis lis la chronique finale.",
        ), start=1):
            item = ctk.CTkLabel(
                route_card,
                text=line,
                font=TYPOGRAPHY["body"],
                text_color=PALETTE["text_muted"],
                justify="left",
                anchor="w",
            )
            item.grid(row=row, column=0, padx=20, pady=(0, 5), sticky="ew")

        mascot_card = ctk.CTkFrame(hero_panel, corner_radius=22, width=214, height=132)
        style_frame(mascot_card, tone="panel", border_color=PALETTE["cyan_dim"])
        mascot_card.place(x=500, y=548)
        mascot_card.grid_columnconfigure(1, weight=1)

        portrait = ctk.CTkLabel(mascot_card, text="", image=self.launcher_portrait_image)
        portrait.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=18, sticky="w")

        hero_title = ctk.CTkLabel(
            mascot_card,
            text="Heraut du sanctum",
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        hero_title.grid(row=0, column=1, padx=(0, 14), pady=(22, 2), sticky="sw")

        hero_hint = ctk.CTkLabel(
            mascot_card,
            text="La map et les mascottes gardent la vedette.\nL'accueil sert l'entree en joute.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="left",
        )
        hero_hint.grid(row=1, column=1, padx=(0, 14), pady=(0, 18), sticky="nw")

        rail = ctk.CTkFrame(shell, corner_radius=30)
        style_frame(rail, tone="panel", border_color=PALETTE["border"])
        rail.grid(row=0, column=1, padx=(12, 22), pady=22, sticky="nsew")
        rail.grid_columnconfigure(0, weight=1)
        rail.grid_rowconfigure(6, weight=1)

        rail_badge = create_badge(rail, "Bastion central", tone="info")
        rail_badge.grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

        rail_title = ctk.CTkLabel(
            rail,
            text="Choisir une voie",
            font=TYPOGRAPHY["title"],
            text_color=PALETTE["text"],
        )
        rail_title.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="w")

        rail_intro = ctk.CTkLabel(
            rail,
            text="Trois entrees claires pour jouer. Le bastion garde le mecanisme hors scene pour laisser la joute respirer.",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_soft"],
            wraplength=340,
            justify="left",
        )
        rail_intro.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="w")

        status_panel = ctk.CTkFrame(rail, corner_radius=22)
        style_frame(status_panel, tone="panel_soft", border_color=PALETTE["border"])
        status_panel.grid(row=3, column=0, padx=18, pady=(0, 12), sticky="ew")
        status_panel.grid_columnconfigure(0, weight=1)

        self.db_badge = self._build_status_card(
            status_panel,
            0,
            "Chroniques du bastion",
            "Les verdicts et les combattants du bastion se conservent ici.",
            "Chroniques en veille",
        )

        self.server_badge = self._build_status_card(
            status_panel,
            1,
            "Hall des bastions",
            "Le hall s'ouvre ici quand le bastion accueille une joute partagee.",
            "Hall au repos",
        )

        self._build_action_card(
            rail,
            4,
            "Forge locale",
            "Compose deux bastions sur ce poste et replonge instantanement dans la map.",
            "Entrer dans la forge locale",
            self._handle_new_game,
            variant="primary",
        )

        self._build_action_card(
            rail,
            5,
            "Ouvrir le hall",
            "Ce poste garde le hall et conserve les chroniques de la joute partagee.",
            "Ouvrir le hall",
            self._handle_host_lan,
            variant="accent",
        )

        self._build_action_card(
            rail,
            6,
            "Rejoindre le hall",
            "Entre dans un hall deja ouvert et bascule vers la joute partagee sans friction.",
            "Rejoindre le hall",
            self._handle_join_lan,
            variant="secondary",
        )

        utility_panel = ctk.CTkFrame(rail, corner_radius=22)
        style_frame(utility_panel, tone="panel_soft", border_color=PALETTE["border"])
        utility_panel.grid(row=7, column=0, padx=18, pady=(12, 12), sticky="ew")
        utility_panel.grid_columnconfigure((0, 1), weight=1)

        utility_title = ctk.CTkLabel(
            utility_panel,
            text="Chroniques et veille",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        utility_title.grid(row=0, column=0, columnspan=2, padx=18, pady=(16, 6), sticky="w")

        utility_hint = ctk.CTkLabel(
            utility_panel,
            text="Relis les verdicts, verifie que le sanctuaire repond et ferme proprement le bastion.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            wraplength=330,
            justify="left",
        )
        utility_hint.grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 12), sticky="w")

        history_btn = create_button(utility_panel, "Lire les chroniques", self._handle_history, variant="secondary", height=42)
        history_btn.grid(row=2, column=0, padx=(18, 8), pady=(0, 10), sticky="ew")

        test_db_btn = create_button(utility_panel, "Verifier le sanctuaire", self._handle_test_db, variant="ghost", height=42)
        test_db_btn.grid(row=2, column=1, padx=(8, 18), pady=(0, 10), sticky="ew")

        quit_btn = create_button(utility_panel, "Fermer le bastion", self._handle_close_app, variant="danger", height=42)
        quit_btn.grid(row=3, column=0, columnspan=2, padx=18, pady=(0, 18), sticky="ew")

        info_panel = ctk.CTkFrame(rail, corner_radius=22)
        style_frame(info_panel, tone="bg_alt", border_color=PALETTE["border"])
        info_panel.grid(row=8, column=0, padx=18, pady=(0, 18), sticky="nsew")
        info_panel.grid_columnconfigure(0, weight=1)
        info_panel.grid_columnconfigure(1, weight=0)
        info_panel.grid_rowconfigure(2, weight=1)

        info_title = ctk.CTkLabel(
            info_panel,
            text="Journal vivant",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        info_title.grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")

        self.info_badge = create_badge(info_panel, "Veille du bastion", tone="neutral")
        self.info_badge.grid(row=0, column=1, padx=18, pady=(16, 4), sticky="e")

        info_hint = ctk.CTkLabel(
            info_panel,
            text="Les etapes de demo, l'etat du hall et les nouvelles du sanctuaire remontent ici.",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            wraplength=330,
            justify="left",
        )
        info_hint.grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="w")

        self.info_box = ctk.CTkTextbox(info_panel, height=148)
        self.info_box.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 18), sticky="nsew")
        style_textbox(self.info_box, tone="panel_soft")

    def _build_status_card(self, master, row, title, description, badge_text):
        card = ctk.CTkFrame(master, corner_radius=18)
        style_frame(card, tone="panel", border_color=PALETTE["border"])
        card.grid(row=row, column=0, padx=12, pady=(12 if row == 0 else 0, 12), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        )
        title_label.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        desc_label = ctk.CTkLabel(
            card,
            text=description,
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            wraplength=320,
            justify="left",
        )
        desc_label.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        badge = create_badge(card, badge_text, tone="neutral")
        badge.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")
        return badge

    def _build_action_card(self, master, row, title, description, button_text, command, variant="primary"):
        border_map = {
            "primary": PALETTE["gold_dim"],
            "accent": PALETTE["cyan_dim"],
            "secondary": PALETTE["border_strong"],
        }

        card = ctk.CTkFrame(master, corner_radius=22)
        style_frame(card, tone="panel_soft", border_color=border_map.get(variant, PALETTE["border"]))
        card.grid(row=row, column=0, padx=18, pady=(0, 12), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        )
        title_label.grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")

        desc_label = ctk.CTkLabel(
            card,
            text=description,
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            wraplength=330,
            justify="left",
        )
        desc_label.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        action_btn = create_button(card, button_text, command, variant=variant, height=46)
        action_btn.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="ew")
        return action_btn

    def _default_journal_text(self):
        return (
            "Le bastion est pret.\n\n"
            "Voie de demo :\n"
            "1. Forge locale pour sentir la map\n"
            "2. Hall partage sur le poste gardien\n"
            "3. Compagnon dans le hall puis joute\n"
            "4. Lecture de la chronique finale"
        )

    def _db_ready_journal_text(self):
        return (
            "Le sanctuaire des chroniques repond.\n\n"
            "Le bastion peut enregistrer les combattants, conserver les verdicts et relire les chroniques locales comme partagees."
        )

    def _db_error_journal_text(self):
        return (
            "Le sanctuaire des chroniques ne repond pas.\n\n"
            "L'archive est indisponible pour le moment. Verifie le bastion gardien avant de reprendre la joute."
        )

    def _relay_opened_journal_text(self, local_ip: str):
        return (
            "Hall ouvert.\n\n"
            f"Invitation du bastion a transmettre : {local_ip}\n\n"
            "Ouvre le hall, inscris les combattants puis lance la joute quand tous les etendards sont leves."
        )

    def _relay_join_journal_text(self):
        return (
            "Le hall s'ouvre.\n\n"
            "Prepare l'invitation du bastion et le nom du combattant avant d'entrer dans l'arene partagee."
        )

    def _set_info(self, text, badge_text="Veille du bastion", tone="neutral"):
        update_badge(self.info_badge, badge_text, tone)
        set_textbox_content(self.info_box, text)

    def _set_db_status(self, text: str, tone: str):
        update_badge(self.db_badge, text, tone)

    def _set_server_status(self, text: str, tone: str):
        update_badge(self.server_badge, text, tone)

    def _set_db_mode_local(self):
        set_runtime_override("db_host", "localhost")
        self.current_db_mode = "local"

    def _set_db_mode_remote(self, server_ip: str):
        set_runtime_override("db_host", server_ip)
        self.current_db_mode = f"remote:{server_ip}"    

    def _handle_test_db(self):
        try:
            play_click()
        except Exception:
            pass

        ok = test_connection()
        if ok:
            self._set_db_status("Chroniques pretes", "success")
            self._set_info(self._db_ready_journal_text(), badge_text="Chroniques pretes", tone="success")
        else:
            play_error()
            self._set_db_status("Sanctuaire indisponible", "danger")
            self._set_info(self._db_error_journal_text(), badge_text="Alerte du sanctuaire", tone="danger")

    def _handle_new_game(self):
        try:
            play_transition()
        except Exception:
            pass

        self._set_db_mode_local()
        self._set_info(
            "La forge locale s'ouvre.\n\n"
            "Prepare deux bastions equilibres avant de sceller la prochaine joute.",
            badge_text="Forge ouverte",
            tone="gold",
        )

        window = PlayerSelectView(self)
        window.lift()
        window.focus_force()

    def _handle_history(self):
        try:
            play_transition()
        except Exception:
            pass

        self._set_db_mode_local()
        self._set_info(
            "Ouverture des chroniques locales.\n\n"
            "Relis les verdicts recents et la tendance dominante des bastions.",
            badge_text="Chroniques ouvertes",
            tone="gold",
        )

        window = HistoryView(self, source_label="Chroniques locales du bastion")
        window.lift()
        window.focus_force()

    def _handle_host_lan(self):
        try:
            play_transition()
        except Exception:
            pass
            
        # si le serveur est déjà démarré, on réutilise l'IP
        if self.embedded_server is None:
            try:
                server, thread, local_ip = start_server_in_background("0.0.0.0", self.tcp_port)
                self.embedded_server = server
                self.embedded_server_thread = thread
                self.embedded_server_ip = local_ip

                self._set_server_status(
                    "Hall ouvert · invitation prete",
                    "info",
                )

                self._set_info(self._relay_opened_journal_text(local_ip), badge_text="Invitation prete", tone="info")

            except Exception as e:
                play_alert()
                self._set_info(
                    "Le hall n'a pas pu s'ouvrir.\n\n"
                    "Le bastion n'a pas reussi a preparer une invitation stable pour la joute.",
                    badge_text="Hall indisponible",
                    tone="danger",
                )
                messagebox.showerror("Hall indisponible", f"Impossible d'ouvrir le hall : {e}")
                return
        else:
            self._set_server_status(
                "Hall deja ouvert · invitation prete",
                "info",
            )
            self._set_info(self._relay_opened_journal_text(self.embedded_server_ip), badge_text="Invitation prete", tone="info")
            
        self._set_db_mode_local()

        window = NetworkLobbyView(
            self,
            default_server_ip="127.0.0.1",
            server_port=self.tcp_port,
            host_mode=True
        )
        window.lift()
        window.focus_force()

    def _handle_join_lan(self):
        try:
            play_transition()
        except Exception:
            pass

        self._set_db_mode_local()
        self._set_info(self._relay_join_journal_text(), badge_text="Hall en approche", tone="info")

        window = NetworkLobbyView(self, server_port=self.tcp_port)
        window.lift()
        window.focus_force()

    def _handle_close_app(self):
        # arrêt propre du serveur embarqué si actif
        try:
            if self.embedded_server is not None:
                self.embedded_server.shutdown()
                self.embedded_server.server_close()
        except Exception:
            pass

        try:
            stop_music(fade_ms=150)
        except Exception:
            pass

        self.destroy()


def run_launcher():
    app = LauncherApp()
    app.mainloop()
