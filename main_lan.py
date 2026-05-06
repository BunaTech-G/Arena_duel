from typing import Callable, cast

import customtkinter as ctk
import pygame

from game.audio import init_audio, start_menu_music, stop_music
from ui.shutdown import (
    build_graceful_shutdown,
    close_window_gracefully,
    install_signal_shutdown,
)
from ui.network_lobby import NetworkLobbyView
from ui.theme import apply_theme_settings

apply_theme_settings()


def run_main_lan():
    # Initialisation audio
    pygame.mixer.pre_init(44100, -16, 2, 512)
    init_pygame = getattr(pygame, "init", None)
    if init_pygame is not None:
        try:
            cast(Callable[[], object], init_pygame)()
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            pass

    try:
        init_audio()
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        start_menu_music()
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass

    app = ctk.CTk()
    app.withdraw()

    window = NetworkLobbyView(app)

    close_all = build_graceful_shutdown(
        app,
        steps=(
            lambda: close_window_gracefully(window, user_initiated=True),
            lambda: stop_music(fade_ms=150),
        ),
    )
    restore_signal_handlers = install_signal_shutdown(app, close_all)

    window.protocol("WM_DELETE_WINDOW", close_all)
    try:
        app.mainloop()
    finally:
        restore_signal_handlers()


if __name__ == "__main__":
    run_main_lan()
