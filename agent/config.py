"""
Global configuration and constants for the Doom agent.
"""

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

# Item priority for targeting (higher = more important)
PRIORITY_LABELS = {
    "exit": 10,
    "switch": 9,
    "door": 8,
    "key": 7,
    "clip": 6,
    "ammo": 6,
    "stimpack": 5,
    "health": 5,
    "armor": 4,
    "soul": 3,
}

# Action button indices
ACTION_NAMES = ["FORWARD", "LEFT_TURN", "RIGHT_TURN", "MOVE_LEFT", "MOVE_RIGHT", "ATTACK", "USE"]

# Action indices for clarity
ACTION_FORWARD = 0
ACTION_LEFT_TURN = 1
ACTION_RIGHT_TURN = 2
ACTION_MOVE_LEFT = 3
ACTION_MOVE_RIGHT = 4
ACTION_ATTACK = 5
ACTION_USE = 6
ACTION_COUNT = 7
