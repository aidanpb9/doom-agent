# Execution Algorithm Design

## Overview
The execution algorithm is a hierarchal state machine with tunable params that control agent behavior. This doc defines the architecture needed to beat E1M1 and its mechanics only. States have a natural hierarchy defined by their entry/exit conditions.

## Hyperparameters
- Level timeout: should scale by level, E1M1 = 4200 tics (120 seconds @ 35 tic/s)
- Hang detector: level ends if position changes < 200 units in 1050 tics (30 seconds)
- Minimum combat ammo: 0, ammo_threshold param controls when we look for ammo, but we don't want it to dictate when we run from a fight.


## Layer 1: Navigation Engine
- Use A* or Djistrika's to just go from points A to B
- Input: start position, goal node, graph of all nodes
- If door detected in path, execute USE action (doors defined with WADlinedef data)


## Layer 2: PathTracker
- Manages the node graph and mission progress
- Static nodes define the mininal path for level completion created by navmesh
- Dynamic nodes get created in SCAN state, these are reset each time a level is started
- Nodes also get type labels such as if a node marks a health pack or level exit


## Layer 3: States
- High to low priority, these are like goals
- The hierarchy must be adhered to quite strictly or cycles will occur
- RECOVER is 1st and COMBAT is 2nd to prioritize survival over fighting 

1. RECOVER
2. COMBAT
3. TRAVERSE
4. SCAN (360)

## RECOVER
**Notes:**
- Like a higher priority TRAVERSE where the goal node is loot rather than exit
- Loot is health pack, armor, ammo (high to low priority)
- Parameters determine which other states can be accessed from here 

**Entry:**
- From COMBAT or TRAVERSE or SCAN 
- if health/armor/ammo below thresholds AND respective loot nodes are known

**Behavior:**
- Every frame we evaluate priority based on agent stats (health, armor, ammo)
- Set goal node to highest priority item node
- Navigate to goal node

**Exit:**
- If seeking health: no exit, highest priority
- Then if seeking armor OR ammo, can go to COMBAT if enemy detected AND ammo > 0
- Then if all stats above threshold, go to TRAVERSE


## COMBAT
**Notes:**
- Only overriden by RECOVER if health or armor stats drop below threshold

**Entry:**
- From RECOVER or TRAVERSE or SCAN
- If enemy is detected and ammo > 0

**Behavior:**
- Place a dynamic node at current position to help return to main path if we strafe too far
- Mechanics are aim, fire, and strafe

**Exit:**
- Go to RECOVER if health < health_threshold OR ammo = 0
- Go to TRAVERSE if no more enemies detected


## TRAVERSE:
**Notes:**:
- The default state, goal is level exit node

**Entry**:
- Default state at level start
- From RECOVER if stats above thresholds
- From COMBAT if no enemies
- From SCAN after completing a scan with no interruptions

**Behavior:**
- Set goal node to the level exit
- Navigate to the goal node

**Exit:**
- Go to RECOVER if stats drop below thresholds
- Go to COMBAT if enemy visible
- Go to SCAN (if not on cooldown) if damage taken or SCAN chance activated


## SCAN:
**Notes:**
- Only available from TRAVERSE since we want to be on the main path and not actively looking for loot
- Helps us find loot to pick up and turn towards enemies that shoot us in the back

**Entry:**
- From TRAVERSE
- IF SCAN not on cooldown AND (damage taken OR scan_frequency param triggered)

**Behavior:**
- Place a dynamic node at current position since it should be on the main path
- Perform a 360 degree spin in-place and place dynamic nodes at observed loot positions

**Exit:**
- Go to RECOVER if states drop below thresholds
- Go to COMBAT if enemy visible
- Go to TRAVERSE if 360 spin completes


## Design Decisions
**Automap Not Used:**
VizDoom provides an automap buffer showing entire level layout and object positions. We chose not to use this feature because:
- We want the agent to explore some and not have perfect map info going into the level
- Maintains realistic perception constraints
- Pre-placed waypoints + dynamic item nodes provide sufficient navigation guidance
- Don't want to write image processing code

**FOV information:**
VizDoom provides "state.objects" which gives the agent all enemy/item positions in the entire map. We chose not to use this to prioritize learning by giving the agent minimal help. This creates more interesting evolutionary pressure (exploration vs exploitation). Testing on E1M1 showed state.objects returns 84 objects (entire level) while state.labels, which is FOV limited, returns 7 labels, confirming state.objects provides complete map knowledge. We will use state.labels to only use information available in the agent's FOV.


## Needs Testing:
How fast does agent move roughly?
Does current implementation use A* or Dijkstra?
How is aim affected by movement in VizDoom?
How does agent handle sprinting on tight or zigzag paths?
How far can agent see labels?
How close does agent need to be to pick up loot?
Can agent create nodes for loot it sees accurately?
Confirm label.object_name provides item type granularity?
What movement actually helps get unstuck?
What is frame rate in normal vs fast mode?
Does action_frame_skip affect stuck detection timing?
How long does it take to run one level in fast mode (update genetic algo doc)?


## Testing Results
**Movement Speed:**
- Walking: 6.11 units/tic (214 units/sec)
- Sprinting: 12.28 units/tic (430 units/sec)
- Sprint multiplier: 2.01x


## Future Work
- Stuck state, how it could work:
    Notes: The idea is to help TRAVERSE or RECOVER pathfinding get back to the main path. Even though we might want to shoot enemies while stuck, that would introduce cycles without state tracking (this architecture does not have). Returns to TRAVERSE even if previously in RECOVER to avoid using state history, TRAVERSE will take it to RECOVER anyways if needed
    Entry: From TRAVERSE or RECOVER when stuck detection triggered (see Hyperparameters)
    Behavior undefined currently. Exit: Go to TRAVERSE when agent returned to main path
- Detour state and Breadcrumb pathfinding will allow more exploration