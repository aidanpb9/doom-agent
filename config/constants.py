"""Constants used by execution and genetic algo logic.
The GA will overwrite some of these constants."""

#Game Engine
#Ticrate notes: Doom's native ticrate is 35 ticks/sec. In headed mode, VizDoom syncs to
#real-time so set_ticrate() has no effect on wall-clock speed.
#In headless mode, ticrate is uncapped — set HEADLESS_TICRATE high so
#CPU is the bottleneck, not the ticrate cap. ACTION_FRAME_SKIP should
#stay at 1 so agent behavior is identical between headed and headless.
#Basically agent will act similarly whether head or headless mode as long as
#you use TICK=1 in agents run loop: self.game.make_action(action, TICK)
DEFAULT_TICKRATE = 35 #Doom's native ticks per second rate, used in window mode
HEADLESS_TICKRATE = 2000 #speeds up headless mode, used in headless(no window) mode
DEFAULT_MAP_NAME = "E1M1"
DEFAULT_WAD_PATH = "maps/wads/doom.wad"
DEFAULT_EPISODE_TIMEOUT = 4200  #ticks (120 seconds @ 35 tic/s)
DEFAULT_LOG_INTERVAL = 20 #steps between log entries
TICK = 1    

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

HEALTH_KEYWORDS = {"stimpack", "medikit", "healthbonus"}
ARMOR_KEYWORDS = {"armorbonus", "greenarmor", "bluearmor"}
AMMO_KEYWORDS = {"clip", "backpack"}  #pistol only for now
WEAPON_KEYWORDS = {"shotgun", "chaingun"}
LOOT_KEYWORDS = HEALTH_KEYWORDS | ARMOR_KEYWORDS | AMMO_KEYWORDS | WEAPON_KEYWORDS

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
#WAD linedef specials that end the level
EXIT_SPECIALS = {11, 51, 52, 124, 197}
DOOR_USE_COOLDOWN = 95 # 3 seconds @ 35 ticks/sec

#Navigation thresholds
#Don't tune these. They work and we don't want GA messing with them.
TURN_DEAD_ZONE = 10 #degrees, angle threshold for not turning towards a target node
FORWARD_ANGLE_THRESHOLD = 20 #degrees, don't go forwards unless we're aligned with next node
NODE_PROXIMITY = 60 #how many units away from a node to be on it (tested with loot pickup range)
DOOR_USE_DISTANCE = 30 #need to be more precise about when to USE on doors so we don't waste it
LOOT_PROXIMITY = 20 #how far loot is away from an existing node, so we know if loot is already marked
#Tune this
LOOT_NODE_MAX_DISTANCE = 400 #GA param, units from loot that we can mark it as a node

#Agent thresholds 
HEALTH_THRESHOLD = 50
ARMOR_THRESHOLD = 0
AMMO_THRESHOLD = 20

#SCAN thresholds
SCAN_FREQUENCY = 0.5 #odds of triggering a scan (0=never, 1=every 95 ticks=3seconds)
SCAN_FREQUENCY_MAX = 95 #represents the hardcoded upper range of the GA param
SCAN_COOLDOWN = 175 #minimum ticks between scans 

#Aiming thresholds (fraction of screen width)
COMBAT_HOLD_TICKS = 10 #ticks to keep targeting an enemy after they leave FOV or die
#based on offset which ranges from -0.5 to 0.5 (left to right edge, center=0).
#0.05 means fire if enemy center is within 5% of screen width from center.
COMBAT_AIM_THRESHOLD = 0.05 