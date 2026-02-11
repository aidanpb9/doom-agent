"""
Navigation behavior configuration parameters.
Extracted from sector_navigator.py magic numbers.
"""

# Node visit radius (distance in game units to consider waypoint reached)
NAV_NODE_VISIT_RADIUS_MIN = 32.0
NAV_NODE_VISIT_RADIUS_MAX = 128.0
NAV_NODE_VISIT_RADIUS_DEFAULT = 64.0

# Stuck detection - position radius
NAV_STUCK_RADIUS_MIN = 48.0
NAV_STUCK_RADIUS_MAX = 192.0
NAV_STUCK_RADIUS_DEFAULT = 96.0

# Stuck detection - distance change threshold
NAV_STUCK_DIST_DELTA_DEFAULT = 16.0

# Stuck detection - minimum progress required
NAV_STUCK_MIN_PROGRESS_DEFAULT = 16.0

# Stuck detection - time thresholds
NAV_STUCK_TIME_MIN = 2.0
NAV_STUCK_TIME_MAX = 10.0
NAV_STUCK_TIME_DEFAULT = 5.0
NAV_STUCK_WINDOW_DEFAULT = 3.0

# Exit behavior - force distance to exit
NAV_EXIT_FORCE_DIST_DEFAULT = 512.0

# Subroute blocking distance (don't use subroutes when near end)
NAV_END_SUBROUTE_BLOCK_DIST_MIN = 768.0
NAV_END_SUBROUTE_BLOCK_DIST_MAX = 3072.0
NAV_END_SUBROUTE_BLOCK_DIST_DEFAULT = 1536.0

# Route trace maximum points to store
NAV_ROUTE_TRACE_MAX_DEFAULT = 6000

# Subroute pause duration (ticks to pause at start of subroute)
NAV_SUBROUTE_PAUSE_DURATION_DEFAULT = 10

# Subroute cooldown (ticks before allowing another subroute)
NAV_SUBROUTE_COOLDOWN_DEFAULT = 60

# Use action cooldown (ticks between use actions)
NAV_USE_COOLDOWN_DEFAULT = 35

# Path following - waypoint reach distance
NAV_PATH_WAYPOINT_RADIUS = 32.0

# Angle thresholds for movement decisions (degrees)
NAV_ANGLE_FORWARD_THRESHOLD = 10
NAV_ANGLE_SHARP_TURN_THRESHOLD = 60

# Explore mode cooldown
NAV_EXPLORE_COOLDOWN_DEFAULT = 60

# Exit behavior parameters
NAV_EXIT_USE_BURST_DURATION = 20
NAV_EXIT_SIDE_SWAP_COOLDOWN = 60

# Helper point generation parameters
NAV_HELPER_OFFSET_IN = 40.0
NAV_HELPER_BIAS = 40.0
NAV_HELPER_MAX_COUNT = 12
NAV_HELPER_MIN_SEP = 68.0

# Subroute helper requirements
NAV_SUBROUTE_MIN_HELPERS = 1

# Distance thresholds for various navigation decisions
NAV_SPECIAL_DIST_THRESHOLD = 48.0
NAV_DOOR_STUCK_THRESHOLD = 24.0
NAV_SPECIAL_STUCK_THRESHOLD = 12.0
NAV_EXIT_CLOSE_DIST = 192.0
NAV_EXIT_MEDIUM_DIST = 320.0
NAV_EXIT_NEAR_DIST = 256.0
NAV_EXIT_FAR_DIST = 200.0
NAV_EXIT_VERY_CLOSE = 64.0
NAV_EXIT_TOUCH_DIST = 48.0
NAV_EXIT_INSET_DIST = 24.0

# No progress counters
NAV_NO_PROGRESS_FLIP_THRESHOLD = 12
NAV_NO_PROGRESS_EXIT_THRESHOLD = 6
NAV_NO_PROGRESS_SUBROUTE_THRESHOLD = 20
NAV_NO_PROGRESS_CORNER_STUCK = 12
NAV_NO_PROGRESS_EXTREME = 40

# Movement monitoring
NAV_MOVEMENT_MIN_DIST = 16.0
NAV_MOVEMENT_CHECK_INTERVAL = 8.0

# Exit strafe timing
NAV_EXIT_STRAFE_SWITCH_TICKS = 10
NAV_EXIT_STRAFE_SWITCH_TICKS_ALT = 12

# Max steps calculation multiplier
NAV_MAX_STEPS_MULTIPLIER = 35
