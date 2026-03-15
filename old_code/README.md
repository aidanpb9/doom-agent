## Project Overview
Spacecraft flight software and Doom payload development using VizDoom. This project implements an AI agent that autonomously navigates and completes Doom levels using navmesh-based pathfinding, combat behaviors, and genetic algorithm parameter optimization.

DoomSat autonomously plays and completes Doom levels using navmesh pathfinding and genetic algorithm parameter optimization. The agent uses:


## Project Structure

```
DoomSat/
├── main.py                          # Single CLI entry point
├── README.md                        # This file
├── requirements.txt                 # Python dependencies
├── config/
│   ├── __init__.py
│   ├── combat.py                    # Combat behavior parameters
│   ├── navigation.py                # Navigation parameters
│   └── defaults.py                  # Default game settings
├── agent/
│   ├── __init__.py
│   ├── agent.py                     # Main DoomAgent orchestrator
│   ├── behavior/
│   │   ├── __init__.py
│   │   └── behavior_selector.py    # State machine for behavior selection
│   ├── navigation/
│   │   ├── __init__.py
│   │   ├── sector_navigator.py     # Main navigation controller
│   │   └── navmesh.py              # Navmesh data structures
│   ├── perception/
│   │   ├── __init__.py
│   │   └── perception.py           # Game state parsing, enemy detection
│   └── utils/
│       ├── __init__.py
│       ├── action_decoder.py       # Action encoding utilities
│       └── video_recorder.py       # Episode recording
├── evolution/
│   ├── __init__.py
│   └── genetic_algo.py             # 2-agent genetic algorithm
├── testing/
│   ├── __init__.py
│   ├── test_framework.py           # Multi-episode performance testing
│   └── validate_params.py          # A/B comparison tool
├── tools/
│   └── build_navmesh.py            # Navmesh generation tool
├── models/
│   └── nav/                        # Pre-built navmeshes (E1M1, E1M2)
├── logs/                           # Generated at runtime
└── wads/                           # Doom WAD files (not in repo)
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
