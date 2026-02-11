# DoomSat 

Spacecraft flight software and Doom payload development using VizDoom. This project implements an AI agent that autonomously navigates and completes Doom levels using navmesh-based pathfinding, combat behaviors, and genetic algorithm parameter optimization.

## Project Overview

DoomSat is a research platform for developing autonomous navigation and decision-making systems in complex 3D environments. The agent uses:

- **Navmesh-based pathfinding**: A* algorithm with funnel algorithm for smooth paths
- **Sector-aware navigation**: Leverages Doom's sector geometry for spatial reasoning
- **Adaptive combat system**: Dynamic enemy engagement with strategic positioning
- **Stuck detection & recovery**: Subroute planning to escape local minima
- **Genetic algorithm evolution**: 2-agent µGA for parameter optimization

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

## Quick Start

### Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Add your Doom WAD** to the `wads/` directory:
```bash
# For shareware Doom
cp /path/to/doom1.wad wads/

# Or for full Doom
cp /path/to/doom.wad wads/
```

### Basic Usage

**Run a single episode**:
```bash
python main.py run --map E1M1 --timeout 60
```

**Run with visualization (slower)**:
```bash
python main.py run --map E1M1 --timeout 60
```

**Run in fast mode (headless)**:
```bash
python main.py run --map E1M1 --timeout 60 --fast
```

## Available Commands

### 1. Run Mode
Execute a single agent episode:
```bash
python main.py run [options]

Options:
  --map MAP         Map name (default: E1M1)
  --wad WAD         Path to WAD file (default: wads/doom1.wad)
  --timeout SEC     Episode timeout in seconds (default: 60)
  --fast            Run in fast mode (headless, reduced logging)
  --no-debug        Disable debug output (no automap/nav images)
```

**Example**:
```bash
python main.py run --map E1M2 --timeout 120 --fast
```

### 2. Test Mode
Run multiple episodes and generate performance reports:
```bash
python main.py test [options]

Options:
  --map MAP         Map to test (default: E1M1)
  --episodes N      Number of episodes (default: 10)
  --timeout SEC     Timeout per episode (default: 60)
  --fast            Run in fast mode
```

**Example**:
```bash
python main.py test --map E1M1 --episodes 20 --fast
```

**Outputs**:
- `logs/test_results_E1M1_*.json` - Raw episode data
- `logs/performance_E1M1_*.png` - Performance graphs
- Console summary with success rates and statistics

### 3. Evolve Mode
Run genetic algorithm to evolve optimal parameters:
```bash
python main.py evolve [options]

Options:
  --map MAP         Map to evolve on (default: E1M1)
  --generations N   Number of generations (default: 20)
  --timeout SEC     Timeout per episode (default: 120)
  --fast            Run in fast mode (default: True)
```

**Example**:
```bash
python main.py evolve --map E1M1 --generations 50 --fast
```

**Outputs**:
- `logs/genetic_algo/generation_NNN.json` - Per-generation results
- `logs/genetic_algo/evolution_history.json` - Full evolution history
- Elite parameters saved automatically

### 4. Validate Mode
Compare baseline vs evolved parameters:
```bash
python main.py validate [options]

Options:
  --map MAP         Map to validate on (default: E1M1)
  --episodes N      Episodes per configuration (default: 5)
```

**Example**:
```bash
python main.py validate --map E1M1 --episodes 10
```

**Requires**: Prior run of `evolve` command to generate parameters

### 5. Show Parameters
Display current configuration values:
```bash
python main.py show-params
```

Shows all combat, navigation, and default parameters with their valid ranges.

## Genetic Algorithm

The 2-agent micro genetic algorithm (µGA) evolves optimal behavior parameters:

**Architecture**:
- **Elite agent (A)**: Current best performer
- **Challenger agent (B)**: Mutated version of elite
- Head-to-head competition each generation
- Winner becomes new elite, loser discarded
- Cosmic radiation-style bit-flip mutations

**Evolved Parameters**:
- `combat_burst`: Shots per engagement (4-16)
- `combat_cooldown_duration`: Ticks between bursts (10-40)
- `combat_strafe_switch`: Strafe direction change timing (4-16)
- `combat_max_active`: Max combat duration (60-180 ticks)
- `node_visit_radius`: Waypoint reach distance (32-128 units)
- `stuck_radius`: Movement threshold for stuck detection (48-192 units)
- `stuck_time_s`: Time before declaring stuck (2-10 seconds)
- `end_subroute_block_dist`: Distance to disable subroutes (768-3072 units)

**Fitness Criteria** (lexicographic priority):
1. Level completion (exit > all else)
2. Health preservation (lower damage taken)
3. Combat effectiveness (higher kill count)
4. Survival time (longer duration)

## Performance Baseline (E1M1)

**Sprint 1 Results** (20 episodes, 60s timeout):
- **Success rate**: 20% (4/20 exits)
- **Average kills**: 3.2 per episode
- **Common failure**: Navigation bottlenecks, stuck in starting room
- **Best run**: 8 kills, 87% health remaining

**Known Issues**:
- Subroute planning can be computationally expensive
- Exit switch detection requires precise positioning
- Some door types not properly handled

## Configuration

All tunable parameters are centralized in `config/`:

**Combat Parameters** (`config/combat.py`):
- Burst firing patterns
- Cooldown durations
- Strafe behavior timing
- Enemy confidence thresholds

**Navigation Parameters** (`config/navigation.py`):
- Waypoint visit radii
- Stuck detection thresholds
- Subroute planning constraints
- Exit behavior parameters

**Default Settings** (`config/defaults.py`):
- Episode timeouts
- Frame skip rates
- Enemy detection keywords
- Special linedef types

## Development

### Project Philosophy
- **Clean architecture**: Modular design, separation of concerns
- **No magic numbers**: All parameters in config files
- **Extensive logging**: Debug info at every decision point
- **Test-driven**: Comprehensive test framework included

### Key Modules

**`agent/agent.py`**: Main orchestrator
- Initializes VizDoom environment
- Manages episode lifecycle
- Coordinates behavior selection
- Handles hang detection and timeouts

**`agent/navigation/sector_navigator.py`**: Navigation controller
- Loads navmesh data
- Plans routes using A* pathfinding
- Detects and recovers from stuck states
- Handles special linedefs (doors, exits)

**`agent/behavior/behavior_selector.py`**: Decision-making
- Prioritizes navigation vs combat
- Manages combat engagement timing
- Coordinates with navigation system

### Adding New Maps

1. **Generate navmesh**:
```bash
python tools/build_navmesh.py --wad wads/doom1.wad --map E1M3
```

2. **Navmesh will be saved** to `models/nav/E1M3.json`

3. **Test the agent**:
```bash
python main.py run --map E1M3 --timeout 120
```

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
