# State Machine Design


## Overview
This doc details how StateMachine works. The state machine is hierarchical with tunable params that control agent behavior. States have a natural hierarchy defined by their entry/exit conditions.


## Navigation
The state machine delegates all movement to PathTracker and NavigationEngine. States that navigate (TRAVERSE, RECOVER) set a goal node. PathTracker manages the node graph, tracks mission progress, and detects stuck conditions. NavigationEngine handles A* pathfinding and movement. The state machine only decides what to target; the navigation stack handles how to get there. See architecture_design.md for class-level details.


## State Machine & Priority
- High to low priority, these are like goals
- The hierarchy must be adhered to quite strictly or cycles will occur
- STUCK is highest priority so stuck recovery always completes before other states can interrupt it
- COMBAT is above SCAN/RECOVER. Agent finishes the fight first, then heals. Running for loot past enemies is often more dangerous than standing and fighting.
- SCAN is above RECOVER. A scan may reveal closer loot than the currently known node, so scanning before committing to a RECOVER path is usually worth the brief delay.

1. STUCK
2. COMBAT
3. SCAN (360)
4. RECOVER
5. TRAVERSE

**State Machine Diagram (Mermaid):**
```mermaid
stateDiagram-v2
    [*] --> TRAVERSE

    TRAVERSE --> STUCK : stuck
    TRAVERSE --> SCAN : damage taken or freq trigger
    TRAVERSE --> COMBAT : enemy visible & ammo > 0
    TRAVERSE --> RECOVER : stats low & loot known

    SCAN --> STUCK : stuck
    SCAN --> COMBAT : enemy visible
    SCAN --> TRAVERSE : spin complete

    COMBAT --> STUCK : stuck
    COMBAT --> RECOVER : no enemies & stats low & loot known
    COMBAT --> TRAVERSE : no enemies & stats ok

    RECOVER --> STUCK : stuck
    RECOVER --> SCAN : damage taken or freq trigger
    RECOVER --> TRAVERSE : stats ok

    STUCK --> TRAVERSE : recovery complete

    classDef traverse fill:#1e3a5f,stroke:#4a7ab5,color:#fff
    classDef combat fill:#6b1e1e,stroke:#b54a4a,color:#fff
    classDef recover fill:#1e4d2e,stroke:#4a9a5d,color:#fff
    classDef scan fill:#4d3d1e,stroke:#9a7a4a,color:#fff
    classDef stuck fill:#3d1e4d,stroke:#7a4a9a,color:#fff

    class TRAVERSE traverse
    class COMBAT combat
    class RECOVER recover
    class SCAN scan
    class STUCK stuck
```


## STUCK
**Notes:**
- Highest priority state — interrupts everything including RECOVER and COMBAT
- Always exits to TRAVERSE regardless of prior state to avoid cycles (TRAVERSE re-evaluates and enters RECOVER if needed)
- Agent can't navigate to loot while physically stuck anyway, so interrupting RECOVER costs nothing

**Entry:**
- From any state when PathTracker stuck detection fires (agent moved < 50 units in 175 ticks)

**Behavior:**
- Randomly picks left or right turn direction once on entry, holds that direction for full duration
- Combines turn + forward every tick to physically arc around the obstacle
- Runs for STUCK_RECOVERY_TICKS (70 ticks, ~2 seconds)

**Exit:**
- Go to TRAVERSE when recovery ticks complete


## COMBAT
**Notes:**
- Higher priority than RECOVER — agent finishes the fight before seeking loot
- Vertical aiming is handled by the engine (`+autoaim 35` in vizdoom.cfg), no screen-space filtering needed

**Entry:**
- From TRAVERSE, SCAN, or RECOVER
- If enemy is detected and ammo > 0

**Behavior:**
- Aims and fires at enemy

**Exit:**
- Go to RECOVER if no enemies and stats < thresholds and loot known
- Go to TRAVERSE if no enemies and stats above thresholds


## RECOVER
**Notes:**
- Like TRAVERSE but the goal node is loot rather than exit
- Loot is health pack, armor, ammo (high to low priority)
- Parameters determine which other states can be accessed from here

**Entry:**
- From COMBAT, TRAVERSE, or SCAN
- if health/armor/ammo below thresholds AND respective loot nodes are known

**Behavior:**
- Every frame we evaluate priority based on agent stats (health, armor, ammo)
- Set goal node to highest priority item node
- Navigate to goal node

**Exit:**
- Go to STUCK if stuck detection fires
- Go to SCAN if not on cooldown and damage taken or freq trigger (may find closer loot)
- Go to TRAVERSE when all stats above thresholds


## TRAVERSE:
**Notes:**:
- The default state, goal is level exit node

**Entry**:
- Default state at level start
- From RECOVER if stats above thresholds
- From COMBAT if no enemies
- From SCAN after completing a scan with no interruptions
- From STUCK when recovery ticks complete

**Behavior:**
- Set goal node to the level exit
- Navigate to the goal node

**Exit:**
- Go to STUCK if stuck detection fires
- Go to RECOVER if stats drop below thresholds
- Go to COMBAT if enemy visible
- Go to SCAN (if not on cooldown) if damage taken or SCAN chance activated


## SCAN:
**Notes:**
- Available from TRAVERSE or RECOVER, scanning while stats are low may reveal closer loot
- Helps mark loot nodes we missed and helps turn towards enemies that shoot us in the back
- Once a scan starts it runs to completion, RECOVER cannot interrupt it, only STUCK or COMBAT can

**Entry:**
- From SCAN (continuing), TRAVERSE, or RECOVER
- If SCAN not on cooldown AND (damage taken OR scan_frequency param triggered)

**Behavior:**
- Perform a 360 degree spin in-place

**Exit:**
- Go to STUCK if stuck detection fires
- Go to COMBAT if enemy visible
- Go to TRAVERSE if 360 spin completes (RECOVER will fire next tick if stats still low)


## Design Decisions
**Automap Not Used:**
VizDoom provides an automap buffer showing entire level layout and object positions. We chose not to use this feature because:
- We want the agent to explore some and not have perfect map info going into the level
- Maintains realistic perception constraints
- Pre-placed waypoints + dynamic item nodes provide sufficient navigation guidance
- Don't want to write image processing code

**FOV Information:**
VizDoom provides "state.objects" which gives the agent all enemy/item positions in the entire map. We chose not to use this to prioritize learning by giving the agent minimal help. This creates more interesting evolutionary pressure (exploration vs exploitation). Testing on E1M1 showed state.objects returns 84 objects (entire level) while state.labels, which is FOV limited, returns 7 labels, confirming state.objects provides complete map knowledge. We will use state.labels to only use information available in the agent's FOV.

**Sprint Not Used:**
Sprint is a valid action. However, we are omitting it for simplicity. The main benefit of using sprint would be to complete levels faster, but it only takes 2 seconds per level currently, so this isn't a huge time-saver. The main concern is that because sprinting exaggerates the effects of the sliding mechanic, the agent would lose some control over its pathfinding and get stuck or fall more often. This needs to be tested more.


## Testing Results
**Units, Speed, Visibility, Labels:**
- Walking speed: 6.11 units/tick (214 units/sec)
- Sprinting speed: 12.28 units/tick (430 units/sec)
- Visibility range: at least 700 units
- FOV-limited: state.labels only shows objects in current view
- Objects behind agent or passed by disappear from labels
- Loot pickup range: ~60 units from item
- game.get_state.screen_buffer.shape gives (height, width) for GRAY8 or (height, width, channels) for RGB24, VizDoom uses channels-last, so shape[1] is always width
- can damage enemies if horizontally aligned even if not vertically aligned
- VizDoom angles: 0=East, 90=North, 180=West, 270=South (tested with temporary script)


## References
- Unit size reference: https://doomwiki.org/wiki/Map_unit
- Linedef types (doors, exits) https://doomwiki.org/wiki/Linedef_type#Door_linedef_types
- Weapons and items: https://gamefaqs.gamespot.com/ps4/270132-doom-1993/faqs/80222/weapons-and-items
- For more specific item names: https://zdoom.org/w/index.php?title=Main_Page