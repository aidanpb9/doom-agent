"""
Default game and system configuration parameters.
"""

# Episode settings
DEFAULT_EPISODE_TIMEOUT = 10  # seconds
DEFAULT_ACTION_FRAME_SKIP = 1
DEFAULT_STEP_DELAY = 0.0
DEFAULT_LOG_INTERVAL = 20  # steps between logs

# Hang detection
DEFAULT_HANG_TIMEOUT = 8.0  # seconds of no movement
DEFAULT_HANG_ACTION_TIMEOUT = 6.0  # seconds of no action completion

# Game engine settings
DEFAULT_TICRATE = 35  # Doom's native ticrate
DEFAULT_MAP_NAME = "E1M1"
DEFAULT_WAD_PATH = "wads/doom.wad"

# Enemy detection keywords
ENEMY_KEYWORDS = (
    "zombie",
    "zombieman",
    "shotgun",
    "chaingun",
    "imp",
    "demon",
    "caco",
    "baron",
    "lostsoul",
    "lost soul",
    "hellknight",
    "arachno",
    "revenant",
    "mancubus",
    "archvile",
    "pain",
    "spider",
    "cyber",
    "trooper",
    "troop",
    "spectre",
)

# Action button names
ACTION_NAMES = [
    "FORWARD",
    "BACKWARD",
    "LEFT_TURN",
    "RIGHT_TURN",
    "MOVE_LEFT",
    "MOVE_RIGHT",
    "ATTACK",
    "USE"
]

# Door special types (linedef specials that are doors)
DOOR_SPECIALS = {
    1, 26, 27, 28, 31, 32, 33, 34, 35, 46,
    61, 62, 63, 90, 103, 105, 109, 111, 117, 118,
    133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
    143, 145, 146, 147, 148, 149, 150, 151, 152, 153,
    156, 157, 158, 159, 160, 162, 163, 166, 169, 170,
    171, 175, 176, 177, 179, 180, 181, 182, 183, 184,
    185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195,
}

# Exit special types (linedef specials that end the level)
EXIT_SPECIALS = {11, 51, 52, 124, 197}


# Action indices
ACTION_FORWARD = 0
ACTION_BACKWARD = 1
ACTION_LEFT_TURN = 2
ACTION_RIGHT_TURN = 3
ACTION_MOVE_LEFT = 4
ACTION_MOVE_RIGHT = 5
ACTION_ATTACK = 6
ACTION_USE = 7
ACTION_COUNT = 8

# Action names
ACTION_NAMES = ["FORWARD", "BACKWARD", "LEFT_TURN", "RIGHT_TURN", "MOVE_LEFT", "MOVE_RIGHT", "ATTACK", "USE"]
