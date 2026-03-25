#Constants used by execution and genetic algo logic.

#Game Engine
DEFAULT_TICRATE = 35           #Doom's native ticrate (tics per second)
DEFAULT_MAP_NAME = "E1M1"
DEFAULT_WAD_PATH = "wads/doom.wad"
DEFAULT_EPISODE_TIMEOUT = 4200  #tics (120 seconds @ 35 tic/s)
DEFAULT_ACTION_FRAME_SKIP = 8   #frames skipped per action in fast mode
DEFAULT_LOG_INTERVAL = 20       #steps between log entries

#Action button indices (must match available_buttons order in vizdoom.cfg)
ACTION_FORWARD = 0
ACTION_BACKWARD = 1
ACTION_TURN_LEFT = 2
ACTION_TURN_RIGHT = 3
ACTION_ATTACK = 4
ACTION_USE = 5
ACTION_COUNT = 6 #for making arrays of the correct size
ACTION_NAMES = ["FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT", "ATTACK", "USE"]

#VizDoom keywords (matched against state.labels object_name)
ENEMY_KEYWORDS = (
    "zombie",
    "zombieman",
    "shotgunguy",
    "chaingunguy",
    "doomimp",
    "imp",
    "demon",
    "spectre",
    "cacodemon",
    "baronofhell",
    "hellknight",
    "lostsoul",
    "painelemental",
    "arachnotron",
    "revenant",
    "mancubus",
    "archvile",
    "spidermastermind",
    "cyberdemon",
    "trooper",
    "troop"
)

LOOT_KEYWORDS = (
    "shotgun",
    "chaingun",
    "stimpack",
    "medikit",
    "healthbonus",
    "armorbonus",
    "clip",
    "shell",
    "rocket",
    "cell",
    "backpack"
)

#WAD linedef specials that trigger doors
DOOR_SPECIALS = {
    1, 26, 27, 28, 31, 32, 33, 34, 35, 46,
    61, 62, 63, 90, 103, 105, 109, 111, 117, 118,
    133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
    143, 145, 146, 147, 148, 149, 150, 151, 152, 153,
    156, 157, 158, 159, 160, 162, 163, 166, 169, 170,
    171, 175, 176, 177, 179, 180, 181, 182, 183, 184,
    185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195,
}
DOOR_USE_COOLDOWN = 175  # 5 seconds @ 35 tics/s

#WAD linedef specials that end the level
EXIT_SPECIALS = {11, 51, 52, 124, 197}

#Aiming thresholds (fraction of screen width)
COMBAT_AIM_THRESHOLD_WIDE = 0.08       # turn to face enemy if offset exceeds this
COMBAT_AIM_THRESHOLD_NARROW = 0.12     # shoot if offset is within this
COMBAT_CONFIDENCE_THRESHOLD = 0.5      # minimum label confidence to shoot

#Wall detection (to avoid shooting walls instead of enemies)
COMBAT_WALL_BRIGHTNESS_THRESHOLD = 140
COMBAT_WALL_VARIANCE_THRESHOLD = 1500

#Frames to keep targeting an enemy after they leave FOV
COMBAT_SEEN_TICKS_DEFAULT = 10

# GA evolvable parameter bounds — populated in Phase 2
# strafe_switch_time, health_threshold, armor_threshold,
# ammo_threshold, scan_frequency, scan_cooldown, loot_node_distance
