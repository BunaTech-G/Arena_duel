import socket


def get_local_lan_ip() -> str:
    """
    Tente de récupérer l'IP LAN locale de la machine.
    Fallback : 127.0.0.1
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # astuce classique : pas besoin d'avoir Internet réellement actif,
        # on force juste le système à choisir l'interface réseau utilisée
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]

        if not ip or ip.startswith("127."):
            return "127.0.0.1"

        return ip

    except Exception:
        return "127.0.0.1"

    finally:
        try:
            if sock:
                sock.close()
        except Exception:
            pass