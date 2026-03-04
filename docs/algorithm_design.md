# Overview

The execution algorithm is a state machine with tunable params that control agent behavior. The default state is Navigation, other states are like interrupts for allowing the agent to deal with the game which temporarily changes behavior and the goal node. This doc defines the architecture needed to beat E1M1 and its mechanics only. States have a natural hierarchy defined by their entry/exit conditions.

Genetic algorithm compares baseline A param set (genome) with mutated B genome and saves the higher scorer as the new baseline.

# Execution Algorithm

## Hyperparameters
- Level timeout: scales by level, E1M1 = 120 seconds
- Hang detector: level ends if STUCK state active > 30 seconds
- Stuck detection: if agent's moves < 100 units in the last 3 seconds (while walking forward, agent moves 3.3 units per frame * 25 fps = 80 units per second)
- Minimum combat ammo: 0, if there's an enemy use every last bullet


## Layer 1: navigation engine
- Use A* or Djistrika's to just go from points A to B
- Input: start position, goal node, graph of all nodes
- If door detected in path, execute USE action (doors defined with WADlinedef data)


## Layer 2: PathTracker
- Manages the node graph and mission progress
- Static nodes define the mininal path for level completion created by navmesh
- Dynamic nodes get created in SCAN state, these are reset each time a level is started
- Nodes also get type labels such as if a node marks a health pack or level exit


## Layer 3: States
- See [State Machine Diagram](state_machine_diagram.md) for visual overview
- High to low priority, these are like goals
- The hierarchy must be adhered to quite strictly or cycles will occur
- STUCK is highest because it fixes underlying navigation problems
- RECOVER is 2nd and COMBAT is 3rd to prioritize survival over fighting 

1. STUCK 
2. RECOVER
3. COMBAT
4. TRAVERSE
5. SCAN (360)


## STUCK:
**Notes:**
- The idea is to help TRAVERSE or RECOVER pathfinding get back to the main path
- Even though we might want to shoot enemies while stuck, that would introduce cycles without state tracking (this architecture does not have) 
- Returns to TRAVERSE even if previously in RECOVER to avoid using state history, TRAVERSE will take it to RECOVER anyways if needed

**Entry:**
- From TRAVERSE or RECOVER when stuck detection triggered (see Hyperparameters)

**Behavior:**
**Exit:**
- Go to TRAVERSE when agent returned to main path


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
- Go to STUCK if needed, stats don't matter
- If seeking health: no exit besides STUCK
- Then if seeking armor OR ammo, can go to COMBAT if enemy AND ammo > 0
- Then if all stats above threshold, go to TRAVERSE


## COMBAT
**Notes:**
- Only overriden by RECOVER if health or armor stats drop below threshold

**Entry:**
- From RECOVER or TRAVERSE or SCAN
- If enemy is detected and ammo > 0

**Behavior:**
- Mechanics are aim, fire, and strafe

**Exit:**
- Go to RECOVER if health < health_threshold OR ammo = 0
- Go to TRAVERSE if no more enemies detected


## TRAVERSE:
**Notes:**:
- The default state, goal is level exit node

**Entry**:
- Default state at level start
- From STUCK if agent gets unstuck
- From RECOVER if stats above thresholds
- From COMBAT if no enemies
- From SCAN after completing a scan with no interruptions

**Behavior:**
- Set goal node to the level exit
- Navigate to the goal node

**Exit:**
- Go to STUCK if stuck detected
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


## Testing:
How is aim affected by movement in VizDoom?
Can agent create nodes for loot it sees accurately?
How far can agent see labels?
How close does agent need to be to pick up loot?
Confirm label.object_name provides item type granularity?
What movement actually helps get unstuck?
What is frame rate in normal vs fast mode?
Does action_frame_skip affect stuck detection timing?



## Future Work
- Detour state and Breadcrumb pathfinding will allow more exploration

