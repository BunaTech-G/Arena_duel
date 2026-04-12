from __future__ import annotations

import ipaddress
from tkinter import TclError, messagebox

import customtkinter as ctk
import pygame

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
from game.runtime_backend import (
    BACKEND_ARCADE,
    BACKEND_LABELS,
    BACKEND_PYGAME,
    get_local_game_backend_status,
    normalize_gameplay_backend,
)
from hardware.arduino import list_available_serial_ports
from hardware.bridge import load_hardware_runtime_config
from hardware.service import describe_hardware_runtime_status
from network.net_utils import (
    format_endpoint,
    get_lan_address_info,
    load_lan_runtime_config,
)
from network.server import start_server_in_background
from runtime_utils import (
    clear_runtime_override,
    clear_runtime_user_overrides,
    load_persisted_runtime_config,
    resource_path,
    runtime_user_config_path,
    save_runtime_user_overrides,
)
from ui.history_view import HistoryView
from ui.network_lobby import NetworkLobbyView
from ui.player_select import PlayerSelectView
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    apply_theme_settings,
    create_badge,
    create_button,
    create_option_menu,
    enable_large_window,
    load_launcher_background_image,
    load_ctk_image,
    present_window,
    style_window,
)


apply_theme_settings()


GAMEPLAY_BACKEND_LABEL_BY_CODE = {
    BACKEND_ARCADE: BACKEND_LABELS[BACKEND_ARCADE],
    BACKEND_PYGAME: BACKEND_LABELS[BACKEND_PYGAME],
}
GAMEPLAY_BACKEND_CODE_BY_LABEL = {
    label: code for code, label in GAMEPLAY_BACKEND_LABEL_BY_CODE.items()
}


def _get_gameplay_backend_label(raw_backend) -> str:
    backend_code = normalize_gameplay_backend(raw_backend)
    return GAMEPLAY_BACKEND_LABEL_BY_CODE[backend_code]


def _get_gameplay_backend_code(raw_label: str) -> str:
    clean_label = str(raw_label or "").strip()
    return GAMEPLAY_BACKEND_CODE_BY_LABEL.get(clean_label, BACKEND_PYGAME)


def _parse_int_value(
    label: str,
    raw_value: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed_value = int(str(raw_value or "").strip())
    except ValueError as error:
        raise ValueError(f"Le champ {label} doit etre un entier.") from error

    if parsed_value < minimum or parsed_value > maximum:
        raise ValueError(f"Le champ {label} doit rester entre {minimum} et {maximum}.")
    return parsed_value


def _parse_float_value(
    label: str,
    raw_value: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed_value = float(str(raw_value or "").strip())
    except ValueError as error:
        raise ValueError(f"Le champ {label} doit etre un nombre valide.") from error

    if parsed_value < minimum or parsed_value > maximum:
        raise ValueError(f"Le champ {label} doit rester entre {minimum} et {maximum}.")
    return parsed_value


def _validate_bind_host(raw_value: str) -> str:
    bind_host = str(raw_value or "").strip() or "0.0.0.0"
    normalized = bind_host.casefold()
    if normalized in {"0.0.0.0", "localhost"}:
        return bind_host

    try:
        ipaddress.ip_address(bind_host)
    except ValueError as error:
        raise ValueError(
            "Le bind host LAN doit etre une IPv4 valide ou localhost."
        ) from error
    return bind_host


def _parse_seed_players(raw_value: str) -> list[str]:
    seen_names = set()
    player_names = []
    for token in str(raw_value or "").replace("\n", ",").split(","):
        clean_name = token.strip()
        if not clean_name:
            continue
        normalized = clean_name.casefold()
        if normalized in seen_names:
            continue
        seen_names.add(normalized)
        player_names.append(clean_name)
    return player_names


class LauncherSettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent: "LauncherApp"):
        super().__init__(parent)
        self.parent_launcher = parent
        style_window(self)

        self.title("Arena Duel - Parametres")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except (OSError, TclError):
            pass

        self.geometry("860x640")
        enable_large_window(self, 760, 520, start_zoomed=False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.runtime_snapshot = load_persisted_runtime_config()
        self.serial_ports = list_available_serial_ports()
        self.vars = self._build_vars(self.runtime_snapshot)
        self.serial_ports_label: ctk.CTkLabel
        self.notice_label: ctk.CTkLabel
        self.gameplay_backend_notice_label: ctk.CTkLabel | None = None

        self._build_ui()
        present_window(self)

    def _build_vars(self, config: dict) -> dict[str, ctk.Variable]:
        return {
            "db_host": ctk.StringVar(value=str(config.get("db_host") or "localhost")),
            "db_port": ctk.StringVar(value=str(config.get("db_port") or 3306)),
            "db_user": ctk.StringVar(value=str(config.get("db_user") or "root")),
            "db_password": ctk.StringVar(value=str(config.get("db_password") or "")),
            "db_name": ctk.StringVar(
                value=str(config.get("db_name") or "arena_duel_v2_db")
            ),
            "db_connect_timeout": ctk.StringVar(
                value=str(config.get("db_connect_timeout") or 3)
            ),
            "gameplay_backend": ctk.StringVar(
                value=_get_gameplay_backend_label(config.get("gameplay_backend"))
            ),
            "lan_bind_host": ctk.StringVar(
                value=str(config.get("lan_bind_host") or "0.0.0.0")
            ),
            "tcp_port": ctk.StringVar(value=str(config.get("tcp_port") or 5000)),
            "lan_connect_timeout_seconds": ctk.StringVar(
                value=str(config.get("lan_connect_timeout_seconds") or 4)
            ),
            "debug_console_logs": ctk.BooleanVar(
                value=bool(config.get("debug_console_logs", False))
            ),
            "demo_local_storage_enabled": ctk.BooleanVar(
                value=bool(config.get("demo_local_storage_enabled", False))
            ),
            "demo_local_storage_force": ctk.BooleanVar(
                value=bool(config.get("demo_local_storage_force", False))
            ),
            "demo_seed_players": ctk.StringVar(
                value=", ".join(config.get("demo_seed_players") or [])
            ),
            "hardware_bridge_enabled": ctk.BooleanVar(
                value=bool(config.get("hardware_bridge_enabled", False))
            ),
            "hardware_serial_port": ctk.StringVar(
                value=str(config.get("hardware_serial_port") or "")
            ),
            "hardware_serial_auto_detect": ctk.BooleanVar(
                value=bool(config.get("hardware_serial_auto_detect", True))
            ),
            "hardware_serial_baudrate": ctk.StringVar(
                value=str(config.get("hardware_serial_baudrate") or 115200)
            ),
            "hardware_serial_timeout_seconds": ctk.StringVar(
                value=str(config.get("hardware_serial_timeout_seconds") or 0.2)
            ),
            "hardware_serial_write_timeout_seconds": ctk.StringVar(
                value=str(config.get("hardware_serial_write_timeout_seconds") or 0.2)
            ),
        }

    def _apply_snapshot(self, config: dict):
        self.vars["db_host"].set(str(config.get("db_host") or "localhost"))
        self.vars["db_port"].set(str(config.get("db_port") or 3306))
        self.vars["db_user"].set(str(config.get("db_user") or "root"))
        self.vars["db_password"].set(str(config.get("db_password") or ""))
        self.vars["db_name"].set(str(config.get("db_name") or "arena_duel_v2_db"))
        self.vars["db_connect_timeout"].set(str(config.get("db_connect_timeout") or 3))
        self.vars["gameplay_backend"].set(
            _get_gameplay_backend_label(config.get("gameplay_backend"))
        )
        self.vars["lan_bind_host"].set(str(config.get("lan_bind_host") or "0.0.0.0"))
        self.vars["tcp_port"].set(str(config.get("tcp_port") or 5000))
        self.vars["lan_connect_timeout_seconds"].set(
            str(config.get("lan_connect_timeout_seconds") or 4)
        )
        self.vars["debug_console_logs"].set(
            bool(config.get("debug_console_logs", False))
        )
        self.vars["demo_local_storage_enabled"].set(
            bool(config.get("demo_local_storage_enabled", False))
        )
        self.vars["demo_local_storage_force"].set(
            bool(config.get("demo_local_storage_force", False))
        )
        self.vars["demo_seed_players"].set(
            ", ".join(config.get("demo_seed_players") or [])
        )
        self.vars["hardware_bridge_enabled"].set(
            bool(config.get("hardware_bridge_enabled", False))
        )
        self.vars["hardware_serial_port"].set(
            str(config.get("hardware_serial_port") or "")
        )
        self.vars["hardware_serial_auto_detect"].set(
            bool(config.get("hardware_serial_auto_detect", True))
        )
        self.vars["hardware_serial_baudrate"].set(
            str(config.get("hardware_serial_baudrate") or 115200)
        )
        self.vars["hardware_serial_timeout_seconds"].set(
            str(config.get("hardware_serial_timeout_seconds") or 0.2)
        )
        self.vars["hardware_serial_write_timeout_seconds"].set(
            str(config.get("hardware_serial_write_timeout_seconds") or 0.2)
        )
        self._refresh_gameplay_backend_notice()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(
            self,
            corner_radius=22,
            fg_color=PALETTE["panel_deep"],
            border_width=1,
            border_color=PALETTE["divider"],
        )
        header.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        create_badge(header, "Parametres du bastion", tone="gold").grid(
            row=0,
            column=0,
            padx=16,
            pady=(16, 10),
            sticky="w",
        )
        ctk.CTkLabel(
            header,
            text="Configuration compacte et persistante",
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, padx=16, sticky="w")
        ctk.CTkLabel(
            header,
            text=(
                "Les reglages sont stockes dans un override utilisateur, "
                "hors du build distribue."
            ),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=760,
        ).grid(row=2, column=0, padx=16, pady=(8, 16), sticky="w")

        scroll = ctk.CTkScrollableFrame(
            self,
            corner_radius=22,
            fg_color=PALETTE["panel_soft"],
            border_width=1,
            border_color=PALETTE["divider"],
        )
        scroll.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        network_content = self._create_section(
            scroll,
            0,
            0,
            "Hall LAN",
            "Port, bind host et timeout du hall principal.",
        )
        self._add_entry_field(
            network_content,
            "Bind host",
            self.vars["lan_bind_host"],
            note="0.0.0.0 ecoute partout. localhost reste local au poste.",
        )
        self._add_entry_field(
            network_content,
            "Port TCP",
            self.vars["tcp_port"],
        )
        self._add_entry_field(
            network_content,
            "Timeout client",
            self.vars["lan_connect_timeout_seconds"],
            note="En secondes. Les changements impactent les prochains halls.",
        )

        db_content = self._create_section(
            scroll,
            0,
            1,
            "Sanctuaire",
            "Connexion MariaDB du registre et des chroniques.",
        )
        self._add_entry_field(db_content, "Hote", self.vars["db_host"])
        self._add_entry_field(db_content, "Port", self.vars["db_port"])
        self._add_entry_field(db_content, "Utilisateur", self.vars["db_user"])
        self._add_entry_field(
            db_content,
            "Mot de passe",
            self.vars["db_password"],
            show="*",
        )
        self._add_entry_field(db_content, "Base", self.vars["db_name"])
        self._add_entry_field(
            db_content,
            "Timeout DB",
            self.vars["db_connect_timeout"],
        )

        demo_content = self._create_section(
            scroll,
            1,
            0,
            "Demo, logs et forge locale",
            "Options utiles pour la presentation et le backend local.",
        )
        self._add_option_field(
            demo_content,
            "Backend local",
            self.vars["gameplay_backend"],
            values=list(GAMEPLAY_BACKEND_CODE_BY_LABEL.keys()),
            note=("Forge locale uniquement. Le hall LAN conserve son flux actuel."),
            command=self._handle_gameplay_backend_change,
        )
        self.gameplay_backend_notice_label = ctk.CTkLabel(
            demo_content,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_faint"],
            justify="left",
            wraplength=320,
        )
        self.gameplay_backend_notice_label.pack(fill="x", pady=(0, 8))
        self._refresh_gameplay_backend_notice()
        self._add_checkbox_field(
            demo_content,
            "Activer le stockage demo",
            self.vars["demo_local_storage_enabled"],
        )
        self._add_checkbox_field(
            demo_content,
            "Forcer le stockage demo",
            self.vars["demo_local_storage_force"],
        )
        self._add_checkbox_field(
            demo_content,
            "Activer les logs console",
            self.vars["debug_console_logs"],
        )
        self._add_entry_field(
            demo_content,
            "Liste seed demo",
            self.vars["demo_seed_players"],
            note="Noms separes par des virgules.",
        )

        hardware_content = self._create_section(
            scroll,
            1,
            1,
            "Bonus Arduino",
            "Le menu principal reste simple, le diagnostic reste ici.",
        )
        self._add_checkbox_field(
            hardware_content,
            "Activer le bridge",
            self.vars["hardware_bridge_enabled"],
        )
        self._add_checkbox_field(
            hardware_content,
            "Auto-detection des ports",
            self.vars["hardware_serial_auto_detect"],
        )
        self._add_entry_field(
            hardware_content,
            "Port serie",
            self.vars["hardware_serial_port"],
        )
        self._add_entry_field(
            hardware_content,
            "Baudrate",
            self.vars["hardware_serial_baudrate"],
        )
        self._add_entry_field(
            hardware_content,
            "Timeout lecture",
            self.vars["hardware_serial_timeout_seconds"],
        )
        self._add_entry_field(
            hardware_content,
            "Timeout ecriture",
            self.vars["hardware_serial_write_timeout_seconds"],
        )

        self.serial_ports_label = ctk.CTkLabel(
            hardware_content,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_faint"],
            justify="left",
            wraplength=320,
        )
        self.serial_ports_label.pack(fill="x", pady=(0, 2))
        self._refresh_serial_ports_label()

        footer = ctk.CTkFrame(
            self,
            corner_radius=22,
            fg_color=PALETTE["panel_deep"],
            border_width=1,
            border_color=PALETTE["divider"],
        )
        footer.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)

        self.notice_label = ctk.CTkLabel(
            footer,
            text=runtime_user_config_path(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=420,
        )
        self.notice_label.grid(
            row=0,
            column=0,
            padx=16,
            pady=16,
            sticky="w",
        )

        buttons = ctk.CTkFrame(footer, fg_color="transparent")
        buttons.grid(row=0, column=1, padx=16, pady=12, sticky="e")

        create_button(
            buttons,
            "Enregistrer",
            self._save_settings,
            variant="primary",
            width=150,
            height=42,
        ).grid(row=0, column=0, padx=(0, 8))
        create_button(
            buttons,
            "Recharger",
            self._reload_settings,
            variant="secondary",
            width=140,
            height=42,
        ).grid(row=0, column=1, padx=(0, 8))
        create_button(
            buttons,
            "Defaut",
            self._restore_defaults,
            variant="subtle",
            width=120,
            height=42,
        ).grid(row=0, column=2, padx=(0, 8))
        create_button(
            buttons,
            "Fermer",
            self.destroy,
            variant="ghost",
            width=120,
            height=42,
        ).grid(row=0, column=3)

    def _create_section(
        self,
        parent,
        row: int,
        column: int,
        title: str,
        description: str,
    ):
        section = ctk.CTkFrame(
            parent,
            corner_radius=20,
            fg_color=PALETTE["panel"],
            border_width=1,
            border_color=PALETTE["divider"],
        )
        section.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(
            section,
            text=title,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
        ).pack(anchor="w", padx=14, pady=(14, 4))
        ctk.CTkLabel(
            section,
            text=description,
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=320,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        content = ctk.CTkFrame(section, fg_color="transparent")
        content.pack(fill="x", padx=14, pady=(0, 14))
        return content

    def _add_entry_field(
        self,
        parent,
        label: str,
        variable,
        *,
        note: str | None = None,
        show: str | None = None,
    ):
        field = ctk.CTkFrame(parent, fg_color="transparent")
        field.pack(fill="x", pady=(0, 8))
        field.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            field,
            text=label,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(row=0, column=0, sticky="w")

        entry = ctk.CTkEntry(
            field,
            textvariable=variable,
            height=36,
            fg_color=PALETTE["panel_soft"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
            font=TYPOGRAPHY["small"],
            show=show,
        )
        entry.grid(row=0, column=1, padx=(12, 0), sticky="ew")

        if note:
            ctk.CTkLabel(
                field,
                text=note,
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_faint"],
                justify="left",
                wraplength=320,
            ).grid(
                row=1,
                column=0,
                columnspan=2,
                pady=(4, 0),
                sticky="w",
            )

    def _add_checkbox_field(self, parent, label: str, variable):
        checkbox = ctk.CTkCheckBox(
            parent,
            text=label,
            variable=variable,
            onvalue=True,
            offvalue=False,
            fg_color=PALETTE["gold"],
            hover_color=PALETTE["gold_hover"],
            border_color=PALETTE["border_strong"],
            text_color=PALETTE["text"],
            font=TYPOGRAPHY["small_bold"],
        )
        checkbox.pack(anchor="w", pady=(0, 8))

    def _add_option_field(
        self,
        parent,
        label: str,
        variable,
        *,
        values: list[str],
        note: str | None = None,
        command=None,
    ):
        field = ctk.CTkFrame(parent, fg_color="transparent")
        field.pack(fill="x", pady=(0, 8))
        field.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            field,
            text=label,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_muted"],
        ).grid(row=0, column=0, sticky="w")

        option_menu = create_option_menu(
            field,
            values=values,
            variable=variable,
            command=command,
            width=220,
            height=36,
            font=TYPOGRAPHY["small_bold"],
            dropdown_font=TYPOGRAPHY["small"],
        )
        option_menu.grid(row=0, column=1, padx=(12, 0), sticky="ew")

        if note:
            ctk.CTkLabel(
                field,
                text=note,
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_faint"],
                justify="left",
                wraplength=320,
            ).grid(
                row=1,
                column=0,
                columnspan=2,
                pady=(4, 0),
                sticky="w",
            )

        return option_menu

    def _handle_gameplay_backend_change(self, _choice=None):
        self._refresh_gameplay_backend_notice()

    def _refresh_gameplay_backend_notice(self):
        if self.gameplay_backend_notice_label is None:
            return

        backend_code = _get_gameplay_backend_code(self.vars["gameplay_backend"].get())
        backend_status = get_local_game_backend_status(
            {"gameplay_backend": backend_code}
        )

        if backend_status["fallback_reason"] == "arcade_unavailable":
            notice_text = (
                "Arcade est demande pour la forge locale, mais le prochain "
                "match restera sur Pygame tant que la dependance n'est pas "
                "disponible."
            )
            notice_color = PALETTE["warning"]
        elif backend_status["effective"] == BACKEND_ARCADE:
            notice_text = (
                "La forge locale utilisera Arcade. Le hall LAN reste inchange."
            )
            notice_color = PALETTE["cyan"]
        else:
            notice_text = (
                "La forge locale utilisera Pygame. Le hall LAN reste inchange."
            )
            notice_color = PALETTE["text_faint"]

        self.gameplay_backend_notice_label.configure(
            text=notice_text,
            text_color=notice_color,
        )

    def _refresh_serial_ports_label(self):
        ports_text = ", ".join(self.serial_ports)
        if not ports_text:
            ports_text = "aucun port compatible visible"
        self.serial_ports_label.configure(text=f"Ports detectes : {ports_text}")

    def _set_notice(self, text: str, tone: str):
        color_map = {
            "success": PALETTE["success"],
            "info": PALETTE["cyan"],
            "gold": PALETTE["gold"],
            "danger": PALETTE["danger"],
        }
        self.notice_label.configure(
            text=text,
            text_color=color_map.get(tone, PALETTE["text_soft"]),
        )

    def _collect_payload(self) -> dict:
        db_host = str(self.vars["db_host"].get() or "").strip()
        if not db_host:
            raise ValueError("Renseigne un hote de base valide.")

        demo_force = bool(self.vars["demo_local_storage_force"].get())
        demo_enabled = bool(self.vars["demo_local_storage_enabled"].get())
        if demo_force:
            demo_enabled = True

        return {
            "db_host": db_host,
            "db_port": _parse_int_value(
                "Port DB",
                self.vars["db_port"].get(),
                minimum=1,
                maximum=65535,
            ),
            "db_user": (str(self.vars["db_user"].get() or "root").strip() or "root"),
            "db_password": str(self.vars["db_password"].get() or ""),
            "db_name": (
                str(self.vars["db_name"].get() or "arena_duel_v2_db").strip()
                or "arena_duel_v2_db"
            ),
            "db_connect_timeout": _parse_int_value(
                "Timeout DB",
                self.vars["db_connect_timeout"].get(),
                minimum=1,
                maximum=30,
            ),
            "gameplay_backend": _get_gameplay_backend_code(
                self.vars["gameplay_backend"].get()
            ),
            "lan_bind_host": _validate_bind_host(self.vars["lan_bind_host"].get()),
            "tcp_port": _parse_int_value(
                "Port TCP",
                self.vars["tcp_port"].get(),
                minimum=1,
                maximum=65535,
            ),
            "lan_connect_timeout_seconds": _parse_float_value(
                "Timeout client",
                self.vars["lan_connect_timeout_seconds"].get(),
                minimum=0.5,
                maximum=30.0,
            ),
            "debug_console_logs": bool(self.vars["debug_console_logs"].get()),
            "demo_local_storage_enabled": demo_enabled,
            "demo_local_storage_force": demo_force,
            "demo_seed_players": _parse_seed_players(
                self.vars["demo_seed_players"].get()
            ),
            "hardware_bridge_enabled": bool(self.vars["hardware_bridge_enabled"].get()),
            "hardware_bridge_backend": "arduino",
            "hardware_serial_port": str(
                self.vars["hardware_serial_port"].get() or ""
            ).strip(),
            "hardware_serial_auto_detect": bool(
                self.vars["hardware_serial_auto_detect"].get()
            ),
            "hardware_serial_baudrate": _parse_int_value(
                "Baudrate",
                self.vars["hardware_serial_baudrate"].get(),
                minimum=1200,
                maximum=1000000,
            ),
            "hardware_serial_timeout_seconds": _parse_float_value(
                "Timeout lecture",
                self.vars["hardware_serial_timeout_seconds"].get(),
                minimum=0.05,
                maximum=10.0,
            ),
            "hardware_serial_write_timeout_seconds": _parse_float_value(
                "Timeout ecriture",
                self.vars["hardware_serial_write_timeout_seconds"].get(),
                minimum=0.05,
                maximum=10.0,
            ),
        }

    def _save_settings(self):
        play_click()
        try:
            previous_config = load_persisted_runtime_config()
            payload = self._collect_payload()
        except ValueError as error:
            play_error()
            self._set_notice(str(error), "danger")
            return

        save_runtime_user_overrides(payload)
        self.runtime_snapshot = dict(payload)

        restart_note = ""
        backend_note = ""
        hall_host = self.parent_launcher.get_active_hall_host()
        hall_port = self.parent_launcher.get_active_hall_port()
        backend_status = get_local_game_backend_status(payload)
        if previous_config.get("gameplay_backend") != payload["gameplay_backend"]:
            if backend_status["fallback_reason"] == "arcade_unavailable":
                backend_note = (
                    " La forge locale demandera Arcade, mais retombera sur "
                    "Pygame "
                    "tant qu'Arcade restera indisponible."
                )
            else:
                backend_note = (
                    f" La forge locale utilisera {backend_status['effective_label']}."
                )
        if hall_host is not None and hall_port is not None:
            if (
                previous_config.get("tcp_port") != payload["tcp_port"]
                or previous_config.get("lan_bind_host") != payload["lan_bind_host"]
            ):
                restart_note = (
                    " Hall deja ouvert sur "
                    f"{format_endpoint(hall_host, hall_port)} : "
                    "redemarrage requis pour appliquer le nouveau port."
                )

        self._set_notice("Reglages enregistres.", "success")
        self.parent_launcher.handle_settings_saved(
            "Reglages enregistres." + backend_note + restart_note,
            tone="success",
        )

    def _reload_settings(self):
        play_click()
        self.runtime_snapshot = load_persisted_runtime_config()
        self._apply_snapshot(self.runtime_snapshot)
        self.serial_ports = list_available_serial_ports()
        self._refresh_serial_ports_label()
        self._set_notice(
            "Reglages relus depuis le fichier utilisateur.",
            "info",
        )
        self.parent_launcher.handle_settings_saved(
            "Reglages relus.",
            tone="info",
        )

    def _restore_defaults(self):
        play_click()
        clear_runtime_user_overrides()
        self.runtime_snapshot = load_persisted_runtime_config()
        self._apply_snapshot(self.runtime_snapshot)
        self.serial_ports = list_available_serial_ports()
        self._refresh_serial_ports_label()
        self._set_notice(
            ("Override utilisateur retire. Les valeurs du projet reprennent la main."),
            "gold",
        )
        self.parent_launcher.handle_settings_saved(
            "Parametres revenus aux valeurs du projet.",
            tone="gold",
        )


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        style_window(self)

        self.title("Arena Duel - Bastion central")
        try:
            self.iconbitmap(resource_path("assets", "icons", "app.ico"))
        except (OSError, TclError):
            pass

        self.geometry("1024x640")
        enable_large_window(self, 920, 540, start_zoomed=False)

        self.embedded_server = None
        self.embedded_server_thread = None
        self.embedded_server_address_info = None
        self.active_server_port: int | None = None
        self.player_select_window = None
        self.history_window = None
        self.host_lobby_window = None
        self.join_lobby_window = None
        self.settings_window = None

        self.db_status_text = "a verifier"
        self.hall_status_text = "au repos"
        self.hardware_status_text = "en veille"
        self.gameplay_backend_text = BACKEND_LABELS[BACKEND_PYGAME]

        self.persisted_runtime_config = load_persisted_runtime_config()
        self.network_config = load_lan_runtime_config()
        self.hardware_runtime_config = load_hardware_runtime_config()
        self.tcp_port = self.network_config.port
        self.lan_address_info = get_lan_address_info()

        screen_width = max(1024, self.winfo_screenwidth())
        screen_height = max(640, self.winfo_screenheight())
        self.background_image = load_launcher_background_image(
            "assets",
            "backgrounds",
            "launcher_twilight_bastion_bg.png",
            size=(screen_width, screen_height),
            fallback_label="twilight bastion",
        )
        self.logo_image = load_ctk_image(
            "assets",
            "icons",
            "icon_preview_256.png",
            size=(138, 138),
            fallback_label="arena duel",
            brightness=1.0,
            remove_edge_dark_regions=True,
            crop_to_visible_bounds=True,
        )

        pygame.mixer.pre_init(44100, -16, 2, 512)
        init_audio()
        start_menu_music()

        self.protocol("WM_DELETE_WINDOW", self._handle_close_app)
        self.bind("<FocusIn>", self._handle_focus_in)

        self._build_ui()
        self._refresh_runtime_state(probe_db=True)
        self._set_info("Le bastion attend la prochaine joute.", tone="gold")

    def _build_ui(self):
        backdrop = ctk.CTkLabel(
            self,
            text="",
            image=self.background_image,
            fg_color="transparent",
            bg_color="transparent",
        )
        backdrop.place(x=0, y=0, relwidth=1, relheight=1)

        logo_label = ctk.CTkLabel(
            self,
            text="",
            image=self.logo_image,
            fg_color="transparent",
            bg_color="transparent",
        )
        logo_label.place(relx=0.5, rely=0.09, anchor="n")

        menu_badge = create_badge(self, "Menu principal", tone="gold")
        menu_badge.configure(bg_color="transparent")
        menu_badge.place(relx=0.5, rely=0.255, anchor="n")

        title_label = ctk.CTkLabel(
            self,
            text="Arena Duel",
            font=(TYPOGRAPHY["display"][0], 56, "bold"),
            text_color=PALETTE["text"],
            fg_color="transparent",
            bg_color="transparent",
        )
        title_label.place(relx=0.5, rely=0.315, anchor="n")

        subtitle_label = ctk.CTkLabel(
            self,
            text="Forgotten Bastion - Entrez dans l'arene",
            font=TYPOGRAPHY["body"],
            text_color=PALETTE["text_muted"],
            fg_color="transparent",
            bg_color="transparent",
        )
        subtitle_label.place(relx=0.5, rely=0.405, anchor="n")

        forge_button = create_button(
            self,
            "Forge locale",
            self._handle_new_game,
            variant="primary",
            width=360,
            height=52,
            bg_color="transparent",
        )
        forge_button.place(relx=0.5, rely=0.455, anchor="n")

        hall_button = create_button(
            self,
            "Hall LAN",
            self._handle_host_lan,
            variant="accent",
            width=360,
            height=52,
            bg_color="transparent",
        )
        hall_button.place(relx=0.5, rely=0.535, anchor="n")

        join_button = create_button(
            self,
            "Rejoindre un hall",
            self._handle_join_lan,
            variant="secondary",
            width=360,
            height=52,
            bg_color="transparent",
        )
        join_button.place(relx=0.5, rely=0.615, anchor="n")

        history_button = create_button(
            self,
            "Chroniques",
            self._handle_history,
            variant="secondary",
            width=360,
            height=50,
            bg_color="transparent",
        )
        history_button.place(relx=0.5, rely=0.695, anchor="n")

        settings_button = create_button(
            self,
            "Parametres",
            self._handle_settings,
            variant="subtle",
            width=170,
            height=40,
            bg_color="transparent",
        )
        settings_button.place(relx=0.5, x=-93, rely=0.785, anchor="n")

        quit_button = create_button(
            self,
            "Quitter",
            self._handle_close_app,
            variant="danger",
            width=170,
            height=40,
            bg_color="transparent",
        )
        quit_button.place(relx=0.5, x=93, rely=0.785, anchor="n")

        self.info_label = ctk.CTkLabel(
            self,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="center",
            wraplength=420,
            fg_color="transparent",
            bg_color="transparent",
        )
        self.info_label.place(relx=0.5, rely=0.858, anchor="n")

        author_label = ctk.CTkLabel(
            self,
            text="Ousmane et Gabriel",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
            fg_color="transparent",
            bg_color="transparent",
        )
        author_label.place(x=22, rely=1.0, y=-18, anchor="sw")

        self.footer_status_label = ctk.CTkLabel(
            self,
            text="",
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_muted"],
            justify="right",
            wraplength=720,
            fg_color="transparent",
            bg_color="transparent",
        )
        self.footer_status_label.place(relx=1.0, x=-22, rely=1.0, y=-18, anchor="se")

        self.after(0, backdrop.lower)

    def _load_runtime_state(self):
        self.persisted_runtime_config = load_persisted_runtime_config()
        self.network_config = load_lan_runtime_config()
        self.hardware_runtime_config = load_hardware_runtime_config()
        self.tcp_port = self.network_config.port
        self.lan_address_info = get_lan_address_info()

    def get_active_hall_port(self) -> int | None:
        if self.embedded_server is None:
            return None
        return self.active_server_port

    def get_active_hall_host(self) -> str | None:
        if self.embedded_server is None:
            return None
        if (
            self.embedded_server_address_info is not None
            and self.embedded_server_address_info.primary_ip
        ):
            return self.embedded_server_address_info.primary_ip
        if self.lan_address_info.primary_ip:
            return self.lan_address_info.primary_ip
        return "127.0.0.1"

    def _refresh_runtime_state(self, *, probe_db: bool = False):
        self._load_runtime_state()

        if probe_db:
            self.db_status_text = "pret" if test_connection() else "indisponible"

        hardware_status = describe_hardware_runtime_status(self.hardware_runtime_config)
        self.hardware_status_text = hardware_status.badge_text
        backend_status = get_local_game_backend_status(self.persisted_runtime_config)
        self.gameplay_backend_text = str(backend_status["effective_label"])
        if backend_status["fallback_reason"] == "arcade_unavailable":
            self.gameplay_backend_text += " (repli)"
        if self.embedded_server is None:
            self.hall_status_text = "au repos"
        else:
            self.hall_status_text = self._current_invitation_text()
        self._update_footer_status()

    def _update_footer_status(self):
        summary = (
            f"Sanctuaire: {self.db_status_text}   •   "
            f"Hall: {self.hall_status_text}   •   "
            f"Forge: {self.gameplay_backend_text}   •   "
            f"Arduino: {self.hardware_status_text}"
        )
        self.footer_status_label.configure(text=summary)

    def _set_info(self, text: str, *, tone: str = "neutral"):
        color_map = {
            "gold": PALETTE["gold"],
            "info": PALETTE["cyan"],
            "success": PALETTE["success"],
            "danger": PALETTE["danger"],
            "neutral": PALETTE["text_soft"],
        }
        self.info_label.configure(
            text=text,
            text_color=color_map.get(tone, PALETTE["text_soft"]),
        )

    def _handle_focus_in(self, _event=None):
        self._refresh_runtime_state(probe_db=False)

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

    def _set_db_mode_local(self):
        clear_runtime_override("db_host")

    def handle_settings_saved(self, message: str, *, tone: str = "success"):
        self._set_db_mode_local()
        self._refresh_runtime_state(probe_db=True)
        self._set_info(message, tone=tone)

    def _handle_settings(self):
        play_click()
        self._focus_or_open_window(
            "settings_window",
            lambda: LauncherSettingsWindow(self),
        )

    def _handle_new_game(self):
        play_transition()
        self._set_db_mode_local()
        backend_status = get_local_game_backend_status(self.persisted_runtime_config)
        if backend_status["fallback_reason"] == "arcade_unavailable":
            info_text = (
                "La forge locale s'ouvre avec repli vers Pygame, car Arcade "
                "reste indisponible dans cet environnement."
            )
        else:
            info_text = (
                f"La forge locale s'ouvre avec {backend_status['effective_label']}."
            )
        self._set_info(info_text, tone="gold")
        self._focus_or_open_window(
            "player_select_window",
            lambda: PlayerSelectView(self),
        )

    def _handle_history(self):
        play_transition()
        self._set_db_mode_local()
        self._set_info("Ouverture des chroniques.", tone="gold")
        self._focus_or_open_window(
            "history_window",
            lambda: HistoryView(
                self,
                source_label="Chroniques locales du bastion",
            ),
        )

    def _handle_host_lan(self):
        play_transition()

        if self.embedded_server is None:
            try:
                server, thread, address_info = start_server_in_background(
                    self.network_config.bind_host,
                    self.tcp_port,
                )
            except (OSError, RuntimeError) as error:
                play_alert()
                self._set_info(
                    "Le hall LAN n'a pas pu s'ouvrir.",
                    tone="danger",
                )
                messagebox.showerror(
                    "Hall indisponible",
                    f"Impossible d'ouvrir le hall : {error}",
                )
                return

            self.embedded_server = server
            self.embedded_server_thread = thread
            self.embedded_server_address_info = address_info
            self.active_server_port = self.tcp_port
        else:
            self.embedded_server_address_info = get_lan_address_info()

        self._set_db_mode_local()
        self._refresh_runtime_state(probe_db=False)
        self._set_info(
            f"Hall pret : {self._current_invitation_text()}",
            tone="info",
        )
        self._focus_or_open_window(
            "host_lobby_window",
            lambda: NetworkLobbyView(
                self,
                default_server_invitation=self._current_invitation_text(),
                server_port=self.get_active_hall_port() or self.tcp_port,
                host_mode=True,
            ),
        )

    def _handle_join_lan(self):
        play_transition()
        self._set_db_mode_local()
        self._set_info(
            "Prepare l'invitation du bastion hote puis entre dans le hall.",
            tone="info",
        )
        self._focus_or_open_window(
            "join_lobby_window",
            lambda: NetworkLobbyView(self, server_port=self.tcp_port),
        )

    def _current_invitation_text(self) -> str:
        host = self.get_active_hall_host()
        port = self.get_active_hall_port()
        if host is not None and port is not None:
            return format_endpoint(host, port)

        if self.lan_address_info.primary_ip:
            return format_endpoint(
                self.lan_address_info.primary_ip,
                self.tcp_port,
            )

        return f"127.0.0.1:{self.tcp_port}"

    def _handle_close_app(self):
        if self.embedded_server is not None:
            try:
                self.embedded_server.shutdown()
                self.embedded_server.server_close()
            except (OSError, RuntimeError):
                pass

        self.active_server_port = None
        stop_music(fade_ms=150)
        self.destroy()


def run_launcher():
    app = LauncherApp()
    app.mainloop()
