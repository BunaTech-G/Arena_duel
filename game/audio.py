from pathlib import Path
import pygame

from runtime_utils import resource_path


SOUNDS_DIR = Path(resource_path("assets", "sounds"))

SOUND_CONFIG = {
    "pickup": {
        "files": ["pickup-impact.mp3", "impact.mp3", "orb.mp3"],
        "volume": 0.34,
    },
    "win": {
        "files": ["win.mp3"],
        "volume": 0.58,
    },
    "draw": {
        "files": ["draw.mp3"],
        "volume": 0.5,
    },
    "click": {
        "files": ["click.mp3"],
        "volume": 0.2,
        "maxtime_ms": 220,
    },
    "select": {
        "files": ["confirm-sting.mp3", "humordome-magic-button-click-453255.mp3", "click.mp3"],
        "volume": 0.17,
        "maxtime_ms": 420,
    },
    "transition": {
        "files": ["menu-open-sting.mp3", "voicebosch-menu-select-button-182476.mp3", "confirm-sting.mp3"],
        "volume": 0.14,
        "maxtime_ms": 650,
    },
    "lose": {
        "files": ["lose-sting.mp3", "floraphonic-violin-lose-1-175615.mp3", "draw.mp3"],
        "volume": 0.52,
    },
    "error": {
        "files": ["error-sting.mp3", "erreur.mp3", "draw.mp3"],
        "volume": 0.24,
        "maxtime_ms": 420,
    },
    "alert": {
        "files": ["error-sting.mp3", "erreur.mp3"],
        "volume": 0.28,
        "maxtime_ms": 700,
    },
}

MUSIC_CONFIG = {
    "menu": {
        "files": ["menu-theme.mp3", "menu-song.mp3"],
        "volume": 0.18,
    },
    "match": {
        "files": ["match-theme.mp3", "drummusiclooper5000-lose-sfx-365579.mp3"],
        "volume": 0.14,
    },
}

_audio_ready = False
_active_music_track = None

pickup_sound = None
win_sound = None
draw_sound = None
click_sound = None
select_sound = None
transition_sound = None
lose_sound = None
error_sound = None
alert_sound = None

def _resolve_audio_path(candidates):
    for filename in candidates:
        path = SOUNDS_DIR / filename
        if path.exists():
            return path

    print(f"[audio] aucun fichier trouvé parmi : {', '.join(candidates)}")
    return None


def _safe_load_sound(candidates, volume=1.0, label="son"):
    global _audio_ready

    if not _audio_ready:
        return None

    path = _resolve_audio_path(candidates)
    if path is None:
        return None

    try:
        sound = pygame.mixer.Sound(str(path))
        sound.set_volume(volume)
        return sound
    except Exception as e:
        print(f"[audio] impossible de charger {label} depuis {path.name} : {e}")
        return None


def _safe_play(sound, label, maxtime_ms=None):
    if not sound:
        return

    try:
        if maxtime_ms:
            sound.play(maxtime=maxtime_ms)
        else:
            sound.play()
    except Exception as e:
        print(f"[audio] lecture {label} impossible : {e}")


def _load_role_sound(role_name):
    config = SOUND_CONFIG[role_name]
    return _safe_load_sound(config["files"], volume=config.get("volume", 1.0), label=role_name)


def _role_maxtime(role_name):
    return SOUND_CONFIG.get(role_name, {}).get("maxtime_ms")


def init_audio():
    """
    Initialise l'audio sans faire planter le jeu si un fichier manque.
    """
    global _audio_ready
    global pickup_sound, win_sound, draw_sound, click_sound
    global select_sound, transition_sound, lose_sound, error_sound, alert_sound

    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        _audio_ready = True
    except Exception as e:
        print(f"[audio] initialisation audio échouée : {e}")
        _audio_ready = False
        return

    pickup_sound = _load_role_sound("pickup")
    win_sound = _load_role_sound("win")
    draw_sound = _load_role_sound("draw")
    click_sound = _load_role_sound("click")
    select_sound = _load_role_sound("select")
    transition_sound = _load_role_sound("transition")
    lose_sound = _load_role_sound("lose")
    error_sound = _load_role_sound("error")
    alert_sound = _load_role_sound("alert")


def play_music(track_name="menu", loops=-1, restart=False):
    global _active_music_track

    if not _audio_ready:
        init_audio()

    if not _audio_ready:
        return False

    track_config = MUSIC_CONFIG.get(track_name)
    if not track_config:
        return False

    try:
        if not restart and _active_music_track == track_name and pygame.mixer.music.get_busy():
            return True
    except Exception:
        pass

    path = _resolve_audio_path(track_config["files"])
    if path is None:
        return False

    try:
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(track_config.get("volume", 0.25))
        pygame.mixer.music.play(loops=loops, fade_ms=300)
        _active_music_track = track_name
        return True
    except Exception as e:
        print(f"[audio] lecture musique {track_name} impossible : {e}")
        return False


def start_menu_music(restart=False):
    return play_music("menu", loops=-1, restart=restart)


def start_match_music(restart=False):
    return play_music("match", loops=-1, restart=restart)


def stop_music(fade_ms=250):
    global _active_music_track

    if not _audio_ready:
        return

    try:
        if fade_ms > 0 and pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
    except Exception as e:
        print(f"[audio] arret musique impossible : {e}")
    finally:
        _active_music_track = None

def play_pickup():
    _safe_play(pickup_sound, "pickup", _role_maxtime("pickup"))


def play_win():
    _safe_play(win_sound, "victoire", _role_maxtime("win"))


def play_draw():
    _safe_play(draw_sound, "egalite", _role_maxtime("draw"))


def play_click():
    _safe_play(click_sound, "clic", _role_maxtime("click"))


def play_select():
    _safe_play(select_sound or click_sound, "selection", _role_maxtime("select"))


def play_transition():
    _safe_play(transition_sound or select_sound or click_sound, "transition", _role_maxtime("transition"))


def play_lose():
    _safe_play(lose_sound or draw_sound, "defaite", _role_maxtime("lose"))


def play_error():
    _safe_play(error_sound or alert_sound, "erreur", _role_maxtime("error"))


def play_alert():
    _safe_play(alert_sound or error_sound, "alerte", _role_maxtime("alert"))