from pathlib import Path
import pygame

from runtime_utils import (
    is_runtime_flag_enabled,
    resource_path,
    runtime_file_path,
)


SOUNDS_DIR = Path(resource_path("assets", "sounds"))

SOUND_CONFIG = {
    "pickup": {
        "files": ["pickup-impact.mp3", "impact.mp3", "orb.mp3"],
        "volume": 0.34,
    },
    "bonus_spawn": {
        "files": ["bonus_jetons.mp3"],
        "volume": 0.38,
        "maxtime_ms": 900,
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
        "files": [
            "confirm-sting.mp3",
            "humordome-magic-button-click-453255.mp3",
            "click.mp3",
        ],
        "volume": 0.17,
        "maxtime_ms": 420,
    },
    "transition": {
        "files": [
            "menu-open-sting.mp3",
            "voicebosch-menu-select-button-182476.mp3",
            "confirm-sting.mp3",
        ],
        "volume": 0.14,
        "maxtime_ms": 650,
    },
    "lose": {
        "files": [
            "game_over.mp3",
            "lose-sting.mp3",
            "floraphonic-violin-lose-1-175615.mp3",
            "draw.mp3",
        ],
        "volume": 0.52,
    },
    "lose_alt": {
        "files": ["gameover2.mp3", "game_over2.mp3"],
        "volume": 0.54,
    },
    "trap_a": {
        "files": ["piege1.mp3"],
        "volume": 0.34,
        "maxtime_ms": 700,
    },
    "trap_b": {
        "files": ["piege2.mp3"],
        "volume": 0.34,
        "maxtime_ms": 700,
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
        "files": [
            "match-theme.mp3",
            "drummusiclooper5000-lose-sfx-365579.mp3",
        ],
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
bonus_spawn_sound = None
lose_alt_sound = None
trap_a_sound = None
trap_b_sound = None
_trap_sound_index = 0


def _log_audio(message):
    if is_runtime_flag_enabled("debug_console_logs", default=False):
        print(f"[audio] {message}")


def _resolve_audio_path(candidates):
    for filename in candidates:
        candidate_paths = [
            SOUNDS_DIR / filename,
            Path(runtime_file_path(filename)),
        ]

        seen_paths = set()
        for path in candidate_paths:
            normalized = str(path)
            if normalized in seen_paths:
                continue
            seen_paths.add(normalized)

            if path.exists():
                return path

    _log_audio(f"aucun fichier trouve parmi : {', '.join(candidates)}")
    return None


def _safe_load_sound(candidates, volume=1.0, label="son"):
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
        _log_audio(f"impossible de charger {label} depuis {path.name} : {e}")
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
        _log_audio(f"lecture {label} impossible : {e}")


def _load_role_sound(role_name):
    config = SOUND_CONFIG[role_name]
    return _safe_load_sound(
        config["files"],
        volume=config.get("volume", 1.0),
        label=role_name,
    )


def _role_maxtime(role_name):
    return SOUND_CONFIG.get(role_name, {}).get("maxtime_ms")


def init_audio():
    """
    Initialise l'audio sans faire planter le jeu si un fichier manque.
    """
    global _audio_ready
    global _trap_sound_index
    global pickup_sound, win_sound, draw_sound, click_sound
    global select_sound, transition_sound, lose_sound, error_sound, alert_sound
    global bonus_spawn_sound, lose_alt_sound, trap_a_sound, trap_b_sound

    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        _audio_ready = True
    except Exception as e:
        _log_audio(f"initialisation audio echouee : {e}")
        _audio_ready = False
        return

    pickup_sound = _load_role_sound("pickup")
    bonus_spawn_sound = _load_role_sound("bonus_spawn")
    win_sound = _load_role_sound("win")
    draw_sound = _load_role_sound("draw")
    click_sound = _load_role_sound("click")
    select_sound = _load_role_sound("select")
    transition_sound = _load_role_sound("transition")
    lose_sound = _load_role_sound("lose")
    lose_alt_sound = _load_role_sound("lose_alt")
    trap_a_sound = _load_role_sound("trap_a")
    trap_b_sound = _load_role_sound("trap_b")
    error_sound = _load_role_sound("error")
    alert_sound = _load_role_sound("alert")
    _trap_sound_index = 0


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
        if (
            not restart
            and _active_music_track == track_name
            and pygame.mixer.music.get_busy()
        ):
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
        _log_audio(f"lecture musique {track_name} impossible : {e}")
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
        _log_audio(f"arret musique impossible : {e}")
    finally:
        _active_music_track = None


def play_pickup():
    _safe_play(pickup_sound, "pickup", _role_maxtime("pickup"))


def play_bonus_spawn():
    _safe_play(
        bonus_spawn_sound,
        "bonus_spawn",
        _role_maxtime("bonus_spawn"),
    )


def play_win():
    _safe_play(win_sound, "victoire", _role_maxtime("win"))


def play_draw():
    _safe_play(draw_sound, "egalite", _role_maxtime("draw"))


def play_click():
    _safe_play(click_sound, "clic", _role_maxtime("click"))


def play_select():
    _safe_play(
        select_sound or click_sound,
        "selection",
        _role_maxtime("select"),
    )


def play_transition():
    _safe_play(
        transition_sound or select_sound or click_sound,
        "transition",
        _role_maxtime("transition"),
    )


def play_lose(consecutive_rematch_loss: bool = False):
    if consecutive_rematch_loss and lose_alt_sound:
        _safe_play(
            lose_alt_sound,
            "defaite_rematch",
            _role_maxtime("lose_alt"),
        )
        return

    _safe_play(lose_sound or draw_sound, "defaite", _role_maxtime("lose"))


def play_trap():
    global _trap_sound_index

    trap_sounds = [sound for sound in (trap_a_sound, trap_b_sound) if sound]
    if not trap_sounds:
        return

    selected_index = _trap_sound_index % len(trap_sounds)
    selected_sound = trap_sounds[selected_index]
    selected_label = "trap_a" if selected_index == 0 else "trap_b"
    _trap_sound_index = (_trap_sound_index + 1) % len(trap_sounds)
    _safe_play(
        selected_sound,
        selected_label,
        _role_maxtime(selected_label),
    )


def play_error():
    _safe_play(error_sound or alert_sound, "erreur", _role_maxtime("error"))


def play_alert():
    _safe_play(alert_sound or error_sound, "alerte", _role_maxtime("alert"))
