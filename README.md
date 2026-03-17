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

## License

[Add license information]

## Acknowledgments

- **VizDoom**: The Doom-based RL research platform
- **zdoom-navmesh-generator**: Navmesh extraction tools
- **zdoom-pathfinding**: A* and funnel algorithms

## Contact

[Add contact information]

---

**Note**: This project is for research and educational purposes. Doom and related trademarks are property of id Software.
