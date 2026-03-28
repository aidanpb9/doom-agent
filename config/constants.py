"""Constants used by execution and genetic algo logic.
The GA will overwrite some of these constants."""


#GA Parameters — evolvable per genome, ranges defined in genetic_algo_design.md
LOOT_NODE_MAX_DISTANCE = 400     #units from agent that loot nodes can be placed
STUCK_RECOVERY_TICKS = 70        #ticks of turn+forward to dislodge from obstacles (~2 seconds)
HEALTH_THRESHOLD = 100           #enter RECOVER if health drops below this
ARMOR_THRESHOLD = 5              #enter RECOVER if armor drops below this
AMMO_THRESHOLD = 30              #enter RECOVER if ammo drops below this
SCAN_INTERVAL = 140              #1-in-N chance per tick of triggering a scan, also used as cooldown
COMBAT_HOLD_TICKS = 35           #ticks to keep targeting after enemy leaves FOV
VERTICAL_IGNORE_THRESHOLD = 0.15 #fraction of screen height, ignore enemies above/below this


#Game Engine
#Ticrate notes: Doom's native ticrate is 35 ticks/sec. In headed mode, VizDoom syncs to
#real-time so set_ticrate() has no effect on wall-clock speed.
#In headless mode, ticrate is uncapped — set HEADLESS_TICRATE high so
#CPU is the bottleneck, not the ticrate cap. Always use TICK in agent's make action
#for consistent decision making.
DEFAULT_TICKRATE = 35           #Doom's native ticks per second rate, used in window mode
HEADLESS_TICKRATE = 4000        #speeds up headless mode, used in headless(no window) mode
DEFAULT_MAP_NAME = "E1M1"
DEFAULT_WAD_PATH = "maps/wads/doom.wad"
DEFAULT_EPISODE_TIMEOUT = 12600 #ticks, covers longest expected level (12600ticks=360s @ 35 tic/s)
TICK = 1


#Action button indices (must match available_buttons order in vizdoom.cfg)
ACTION_FORWARD = 0
ACTION_BACKWARD = 1
ACTION_TURN_LEFT = 2
ACTION_TURN_RIGHT = 3
ACTION_ATTACK = 4
ACTION_USE = 5
ACTION_COUNT = 6                #for making arrays of the correct size


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

#Solid THING type IDs from WAD. Used to approximate obstacles as bounding boxes in blocking_segments.
OBSTACLE_KEYWORDS = {
    34,   #Candlestick
    35,   #Candelabra
    48,   #Tall techno column
    55,   #Short techno floor lamp
    85,   #Tall green firestick
    86,   #Short green firestick
    2028, #Floor lamp
}
OBSTACLE_RADIUS = 16            #units, approximate half-width of a solid decoration

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
DOOR_USE_COOLDOWN = 95          #ticks, ~3 seconds @ 35 ticks/sec


#Navigation thresholds. Don't tune with GA, only manually. These are geometry constants not behavior params
TURN_DEAD_ZONE = 10             #degrees, stop turning when this close to target angle
FORWARD_ANGLE_THRESHOLD = 10    #degrees, only move forward when aligned within this angle
NODE_PROXIMITY = 40             #units, distance to consider a node reached (tested: ~35-60 depending on angle)
DOOR_USE_DISTANCE = 30          #units, must be this close to fire USE on a door or exit
LOOT_PROXIMITY = 20             #units, loot within this distance of an existing node is already marked


#Stuck detection and loot node placement
ANCHOR_MIN_WALL_DISTANCE = 10   #units, min distance from wall to place an anchor node
STUCK_CHECK_INTERVAL = 175      #ticks between stuck checks (~5 seconds)
STUCK_DISTANCE_THRESHOLD = 50   #units, agent must move more than this per interval to avoid stuck trigger
LOOT_NODE_COOLDOWN = 210        #ticks before a removed loot node can be re-added (~6 seconds)


#Combat
COMBAT_AIM_THRESHOLD = 0.01     #fraction of screen width, fire when enemy center is within this of screen center