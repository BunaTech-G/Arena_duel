import customtkinter as ctk
from ui.network_lobby import NetworkLobbyView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def run_main_lan():
    app = ctk.CTk()
    app.withdraw()

    window = NetworkLobbyView(app)

    def close_all():
        try:
            window.shutdown()
        except Exception:
            pass
        app.destroy()

    window.protocol("WM_DELETE_WINDOW", close_all)
    app.mainloop()


if __name__ == "__main__":
    run_main_lan()
