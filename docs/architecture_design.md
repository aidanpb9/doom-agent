# DoomSat Runtime Architecture

## Overview

This doc explains the different runtime classes in core/ and the execution flow between classes. It does not include every method to be added, just mostly the high-level interfacing ones. These classes are responsible for perception, decision-making, navigation, and telemetry during a single playthrough of E1M1. It does not cover the genetic algorithm (which wraps the runtime via run_episode()), pre-processing tools like the navigation planner, or telemetry output schemas (see telemetry_tiers.md). 

The runtime is split into two sides with a clean boundary. The Agent side handles the episode lifecycle: initializing VizDoom, running the game loop, parsing raw game state into a GameState dataclass via Perception, and writing telemetry. Agent makes no decisions. The StateMachine side owns all decision-making: StateMachine reads GameState each tick and returns an action, delegating navigation to NavigationEngine (pure A* pathfinding and movement) and mission progress to PathTracker (node graph management, loot node placement, waypoint tracking). The boundary between the two sides is GameState flowing in and an action vector flowing out.

## Execution Flow

1. main.py calls agent.initialize(). Agent creates VizDoom game object, loads config, creates Graph (static nodes from JSON), creates NavigationEngine and PathTracker with Graph reference, creates StateMachine with PathTracker, creates Perception and ActionDecoder.
2. main.py calls agent.run_episode(). Agent calls game.new_episode(). Loop starts.
3. Game tick fires. Agent calls perception.parse(game.get_state()) -> GameState.
4. Agent calls state_machine.update(gamestate). StateMachine checks priority: stats above thresholds, no enemies, no damage taken -> stay in TRAVERSE state. 
5. StateMachine calls path_tracker.update(game_state). PathTracker checks loot_visible, runs duplicate check, places anchor + loot nodes if needed, advanced last_node and next_node if node reached.
6. StateMachine calls path_tracker.get_next_move(current_position). PathTracker calls NavigationEngine internally -> returns action.
7. StateMachine returns action to Agent. Agent calls action_decoder.decode(action) -> button presses. Agent calls game.make_action(button_presses). Agent calls telemetry_writer.record_step().Loop continues
8. game.is_episode_finished() -> True. Agent calls finalize_episode(), returns stats.


```mermaid
sequenceDiagram
    participant M as main.py
    participant A as Agent
    participant P as Perception
    participant AD as ActionDecoder
    participant SM as StateMachine
    participant PT as PathTracker
    participant NE as NavigationEngine
    participant TW as TelemetryWriter

    M->>A: initialize()
    A->>PT: (Graph with static nodes loaded)
    A->>TW: start_episode()

    M->>A: run_episode()
    A->>A: game.new_episode()

    loop each tick
        A->>P: parse(game.get_state())
        P-->>A: GameState

        A->>SM: update(gamestate)
        SM->>PT: update(gamestate)
        PT->>PT: check loot_visible, place_node() if needed
        PT->>PT: check has_reached_node(), advance last/next

        SM->>PT: get_next_move(current_pos)
        PT->>NE: step_toward(current_pos, next_node)
        NE-->>PT: action
        PT-->>SM: action

        SM-->>A: action
        A->>AD: decode(action)
        AD-->>A: button_presses
        A->>A: game.make_action(button_presses) 
        A->>TW: record_step()
    end

    A->>TW: finalize_episode()
    A-->>M: stats
```


## Classes
1. Graph
2. NavigationEngine
3. PathTracker
4. StateMachine
5. Agent
6. Perception
7. ActionDecoder
8. GameState
9. LootObject


## Class Graph:
**Overview:**
- represents the node graph 
- NodeTypes are WAYPOINT, ANCHOR, LOOT, DOOR, EXIT
- WAYPOINT is static node from JSON, DOOR and EXIT are not WAYPOINTs
- ANCHOR is dynamically placed to connect to loot
- LOOT uses the name field to specify loot type. 
- Special is a raw linedef number for key doors and exits, only used in DOOR and EXIT nodes

**Fields:**
- node objects (x, y, type: NodeType, name, special(int, optional))
- edge objects

**Methods:**
- add_node() 
- add_edge()


## Class NavigationEngine: 
**Overview:**
- pure pathfinding and movement
- given a graph and two points, find a path
- given a current position and a target point, produce an action
- knows nothing about mission state, node types, or progress

**Fields:**
- Graph object

**Methods:**
- make_path() (do A* here, return list of nodes to traverse)
- step_toward() (angle + action to reach next node, if next node is a door, emit USE action with cooldown)


## Class PathTracker: 
**Overview:**
- mission progress and graph state
- owns the node graph
- knows which node is current, which is next, which is the goal
- decides when a node is reached
- knows about NodeTypes

**Fields:**
- Graph object
- NavigationEngine
- current_path
- last_node
- next_node
- visited_waypoints
- door_use_timer

**Methods:**
- set_cur_path() (call make_path() from NavigationEngine to update cur_path)
- _get_next_node()
- _has_reached_node()
- place_node()
- load_static_nodes()
- update()


## Class StateMachine:
**Overview:** 
- manage what state the agent should be in, returns the agent's action

**Fields:**
- enum current_state
- PathTracker 

**Methods:** 
- update(gamestate) (a big if block for state switching, returns an action) 
- private methods for each state


## Class Agent:
**Overview:** 
- manages the episode details, like the interface between VizDoom and StateMachine 
- contains telemetry, perception, game initialization

**Fields:**
- VizDoom game object
- Perception 
- ActionDecoder
- StateMachine
- TelemetryWriter

**Methods:**
- initialize_game() (VizDoom setup, load config, create one Graph which passes to NavigationEngine and PathTracker)
- run_episode() (calls perception + state machine each tic, returns stats for GA)
- close()


## Class Perception:
**Overview:**
- parse raw VizDoom state into a useable GameState

**Fields:**
- enemy_names
- loot_names

**Methods:**
- parse()


## Class ActionDecoder:
**Overview:**
- provides utilities to construct action vectors and decode them
- all static methods, no fields

**Methods (only a few listed):**
- null_action()
- forward()
- attack()
- strafe_left()


## Class GameState:
**Overview:**
- dataclass holding game and agent information

**Fields (what StateMachine needs to make decisions):**
- health
- armor
- ammo, 
- enemies_visible: list[str]
- loots_visible: list[LootObject]
- position x
- position y
- angle 
- enemies_killed
- is_damage_taken_since_last_step


## Class LootObject:
**Overview:** 
- small dataclass for loot

**Fields:** 
- name
- x
- y


## References:
Identifying doors and exits: https://doomwiki.org/wiki/Linedef_type
VizDoom methods: https://vizdoom.farama.org/api/python/