# DoomSat

![CI](https://github.com/aidanpb9/DoomSat/actions/workflows/ci.yaml/badge.svg)


## Project Overview

Spacecraft flight software and Doom payload development using VizDoom. This project implements an AI agent that autonomously navigates and completes Doom levels using navmesh-based pathfinding, combat behaviors, and genetic algorithm parameter optimization.

DoomSat autonomously plays and completes Doom levels using navmesh pathfinding and genetic algorithm parameter optimization. The agent uses:



## Project Structure

```
DoomSat/
├── README.md                        
├── .gitignore                         
├── requirements.txt                 
├── main.py 
├── wads/
├── maps/
├── logs/
├── docs/
├── config/
│   ├── constants.py
│   └── vizdoom.cfg
├── tools/
│   └── TBD...(navigation_planner.py)
├── ga/
│   ├── genetic_algorithm.py
│   └── agent_genome.py
├── core/
│   ├── execution/
│   │   ├── agent.py
│   │   ├── state_machine.py
│   │   ├── perception.py
│   │   ├── action_decoder.py
│   │   ├── game_state.py
│   │   └── telemetry_writer.py
│   └── navigation/
│       ├── graph.py
│       ├── navigation_engine.py
│       └── path_tracker.py


            
```

# #Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Add your Doom WAD** to the `wads/` directory:
```bash
# For shareware Doom
cp /path/to/doom.wad wads/

# Or for full Doom
cp /path/to/doom.wad wads/
```
RENAME the wad file to: doom.wad

## Usage

Run tests with: python3 -m pytest tests/
Run ga report with: python3 ga/report.py output/evolve/YYYY-MM-DD_HHMM/

## License

[Add license information]

## Potential Future Work
- If node finding becomes a problem, can add blocking segments in _nearest_node()
- Combat blackist (if needed): if we don't kill any enemies after being in combat for a while, it means the enemy is behind some geometry and we need to stop shooting or all ammo will get wasted. Can work similarly to loot node blacklist in path_tracker.
- Move backwards during combat. A few ways to do this. Could make it a GA param. Helpful when there's an enemy with a lot of health and we need more time to kill it.
- A way to allow for more exploration. A detour state or some type of breadcrumb pathfinding could help.
- Port to C++ to improve runtime or some other reason (good luck :)

## Acknowledgments

- **VizDoom**: The Doom-based RL research platform
- **zdoom-navmesh-generator**: Navmesh extraction tools
- **zdoom-pathfinding**: A* and funnel algorithms

## Authors

[Add contact information]

---

**Note**: This project is for research and educational purposes. Doom and related trademarks are property of id Software.
