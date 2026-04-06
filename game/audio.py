from pathlib import Path
import pygame

from runtime_utils import resource_path


SOUNDS_DIR = Path(resource_path("assets", "sounds"))

_audio_ready = False

pickup_sound = None
win_sound = None
draw_sound = None
click_sound = None

def _safe_load_sound(filename, volume=1.0):
    global _audio_ready

    if not _audio_ready:
        return None

    path = SOUNDS_DIR / filename
    if not path.exists():
        print(f"[audio] fichier introuvable : {path}")
        return None

    try:
        sound = pygame.mixer.Sound(str(path))
        sound.set_volume(volume)
        return sound
    except Exception as e:
        print(f"[audio] impossible de charger {filename} : {e}")
        return None


def init_audio():
    """
    Initialise l'audio sans faire planter le jeu si un fichier manque.
    """
    global _audio_ready, pickup_sound, win_sound, draw_sound, click_sound

    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        _audio_ready = True
    except Exception as e:
        print(f"[audio] initialisation audio échouée : {e}")
        _audio_ready = False
        return

    pickup_sound = _safe_load_sound("orb.mp3", volume=0.45)
    win_sound = _safe_load_sound("win.mp3", volume=0.65)
    draw_sound = _safe_load_sound("draw.mp3", volume=0.65)
    click_sound = _safe_load_sound("click.mp3", volume=0.35)

    print("[audio-debug] pickup_sound =", pickup_sound is not None)
    print("[audio-debug] win_sound =", win_sound is not None)
    print("[audio-debug] draw_sound =", draw_sound is not None)
    print("[audio-debug] click_sound =", click_sound is not None)

def play_pickup():
    if pickup_sound:
        try:
            pickup_sound.play()
        except Exception as e:
            print(f"[audio] lecture orb impossible : {e}")


def play_win():
    if win_sound:
        try:
            win_sound.play()
        except Exception as e:
            print(f"[audio] lecture victoire impossible : {e}")


def play_draw():
    if draw_sound:
        try:
            draw_sound.play()
        except Exception as e:
            print(f"[audio] lecture égalité impossible : {e}")


def play_click():
    if click_sound:
        try:
            click_sound.play()
        except Exception as e:
            print(f"[audio] lecture clic impossible : {e}")