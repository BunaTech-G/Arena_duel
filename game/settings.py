WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 980
FPS = 60

BACKGROUND_COLOR = (18, 20, 24)
ARENA_BG_COLOR = (38, 42, 50)
WALL_COLOR = (95, 105, 125)
GRID_COLOR = (52, 58, 70)

ARENA_MARGIN = 60

PLAYER_RADIUS = 20
PLAYER_SPEED = 5

# Couleurs équipe A
TEAM_A_COLORS = [
    (231, 76, 60),
    (255, 120, 90),
    (255, 170, 140),
]

# Couleurs équipe B
TEAM_B_COLORS = [
    (52, 152, 219),
    (100, 190, 255),
    (160, 220, 255),
]

# Contrôles par slot
# Slot 1 : ZQSD
# Slot 2 : Flèches
# Slot 3 : TFGH
# Slot 4 : IJKL
# Slot 5 : WAXC
# Slot 6 : Pavé numérique 8456
PLAYER_SLOT_CONTROLS = [
    {"up": "z", "down": "s", "left": "q", "right": "d"},
    {"up": "up", "down": "down", "left": "left", "right": "right"},
    {"up": "t", "down": "g", "left": "f", "right": "h"},
    {"up": "i", "down": "k", "left": "j", "right": "l"},
    {"up": "w", "down": "x", "left": "a", "right": "c"},
    {"up": "kp8", "down": "kp5", "left": "kp4", "right": "kp6"},
]

ORB_RADIUS = 12
ORB_COLOR = (241, 196, 15)
ORB_SPAWN_COUNT = 10
ORB_SCORE_VALUE = 1

MATCH_DURATION_SECONDS = 60
MATCH_DURATION_OPTIONS = (30, 60, 90, 120)


def coerce_match_duration(value, default: int = MATCH_DURATION_SECONDS) -> int:
    try:
        duration_seconds = int(value)
    except (TypeError, ValueError):
        duration_seconds = default

    if duration_seconds in MATCH_DURATION_OPTIONS:
        return duration_seconds
    return default


def format_match_duration_label(duration_seconds: int) -> str:
    duration_seconds = coerce_match_duration(duration_seconds)
    if duration_seconds < 60:
        return f"{duration_seconds} s"

    minutes, seconds = divmod(duration_seconds, 60)
    if seconds == 0:
        return f"{minutes} min"
    return f"{minutes} min {seconds:02d}s"


HUD_TEXT_COLOR = (240, 240, 240)
HUD_ACCENT_COLOR = (130, 220, 255)
HUD_PANEL_COLOR = (30, 34, 42)
HUD_BORDER_COLOR = (90, 110, 150)

OBSTACLE_COLOR = (75, 83, 98)
OBSTACLE_BORDER_COLOR = (130, 145, 175)
