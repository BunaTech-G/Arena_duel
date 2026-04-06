import customtkinter as ctk
import pygame

from game.audio import init_audio, start_menu_music, stop_music
from ui.network_lobby import NetworkLobbyView
from ui.theme import apply_theme_settings

apply_theme_settings()


def run_main_lan():
    # Initialisation audio
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

    app = ctk.CTk()
    app.withdraw()

    window = NetworkLobbyView(app)

    def close_all():
        try:
            window.shutdown()
        except Exception:
            pass
        try:
            stop_music(fade_ms=150)
        except Exception:
            pass
        app.destroy()

    window.protocol("WM_DELETE_WINDOW", close_all)
    app.mainloop()


if __name__ == "__main__":
    run_main_lan()