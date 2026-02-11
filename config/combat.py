"""
Combat behavior configuration parameters.
Extracted from behavior_selector.py magic numbers.
"""

# Combat burst parameters (shots per engagement)
COMBAT_BURST_MIN = 4
COMBAT_BURST_MAX = 16
COMBAT_BURST_DEFAULT = 8

# Combat cooldown duration (ticks between bursts)
COMBAT_COOLDOWN_MIN = 10
COMBAT_COOLDOWN_MAX = 40
COMBAT_COOLDOWN_DEFAULT = 20

# Combat rearm duration (ticks to wait after cooldown before engaging again)
COMBAT_REARM_DEFAULT = 8

# Combat strafe switch (ticks before changing strafe direction)
COMBAT_STRAFE_SWITCH_MIN = 4
COMBAT_STRAFE_SWITCH_MAX = 16
COMBAT_STRAFE_SWITCH_DEFAULT = 8

# Combat max active (maximum ticks in combat before forcing disengage)
COMBAT_MAX_ACTIVE_MIN = 60
COMBAT_MAX_ACTIVE_MAX = 180
COMBAT_MAX_ACTIVE_DEFAULT = 120

# Combat seen ticks (frames to remember enemy after losing sight)
COMBAT_SEEN_TICKS_DEFAULT = 10

# Wall detection thresholds (to avoid shooting walls)
COMBAT_WALL_BRIGHTNESS_THRESHOLD = 140
COMBAT_WALL_VARIANCE_THRESHOLD = 1500

# Aiming thresholds (percentage of screen width for target alignment)
COMBAT_AIM_THRESHOLD_WIDE = 0.08
COMBAT_AIM_THRESHOLD_NARROW = 0.12

# Enemy confidence threshold for shooting
COMBAT_CONFIDENCE_THRESHOLD = 0.5
