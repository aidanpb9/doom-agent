# DoomSat

![CI](https://github.com/aidanpb9/DoomSat/actions/workflows/ci.yaml/badge.svg)

An autonomous agent plays DOOM 1993 for CubeSat payload simulation. The agent navigates and completes Doom levels using waypoint-graph pathfinding, a priority-based state machine, and a genetic algorithm that evolves behavioral parameters to simulate cosmic radiation resilience.

For a guided tour of the codebase read docs/HANDOFF.md


## How it works

The agent runs inside VizDoom, perceiving game state each tick and selecting actions through a hierarchical state machine (STUCK > COMBAT > SCAN > RECOVER > TRAVERSE). A micro-genetic algorithm evolves 7 behavioral parameters like health thresholds and scan frequency by running two genomes head-to-head each generation and keeping the better performer.


## Project structure

```
DoomSat/
├── main.py                      #entry point: run and evolve modes
├── pyproject.toml               #dependencies
├── Dockerfile
├── config/
│   ├── constants.py             #all tunable constants including GA param defaults
│   └── vizdoom.cfg              #VizDoom engine configuration
├── core/
│   ├── utils.py                 #shared geometry helpers (LOS, distance, intersections)
│   ├── execution/
│   │   ├── agent.py             #episode lifecycle, VizDoom I/O
│   │   ├── state_machine.py     #decision-making, state priority logic
│   │   ├── perception.py        #parses VizDoom state into GameState
│   │   ├── action_decoder.py    #builds action vectors
│   │   ├── game_state.py        #GameState, EnemyObject, LootObject dataclasses
│   │   └── telemetry_writer.py  #per-episode logging (3 tiers)
│   └── navigation/
│       ├── graph.py             #node graph (waypoints, loot, doors, exits)
│       ├── navigation_engine.py #A* pathfinding and movement
│       └── path_tracker.py      #dynamic node placement, mission progress
├── ga/
│   ├── genetic_algo.py          #GA evolution loop and fitness function
│   ├── report.py                #post-run analysis charts
│   └── test_genome.json         #edit this, for watching a specific genome in run mode
├── maps/
│   ├── images/                  #map screenshots used by navigation_planner
│   ├── json/                    #pre-processed map node data (one file per level)
│   ├── tools/                   #offline map processing scripts
│   └── wads/                    #doom.wad goes here (not committed)
├── docs/                        #design documents
├── tests/                       #pytest test suite
└── output/                      #generated at runtime, not committed
    ├── run/                     #single episode outputs (summary, CSV, SVG)
    └── evolve/                  #timestamped GA run folders
```


## Installation

Requires Python 3.10+ and a copy of `doom.wad` (not included).

```bash
git clone https://github.com/aidanpb9/DoomSat.git
cd DoomSat
pip install ".[dev]"
cp /path/to/doom.wad maps/wads/doom.wad (YOU NEED TO PUT THE WAD THERE)
```


## Usage

### Run the agent
```bash
python3 main.py run                   #single episode, windowed
python3 main.py run --headless        #single episode, headless (faster)
python3 main.py run --map E1M2        #specific map
python3 main.py evolve                #GA evolution
```

### Hand-crafted genome testing
Edit `ga/test_genome.json` to set custom parameter values, then run normally. If the file exists it overrides the defaults, letting you observe specific parameter combinations in windowed mode without touching evolved outputs.

### Tests
```bash
pytest tests/ -m "not local" -v      #unit tests (the CI runs these)
pytest tests/ -v                     #all tests including integration (requires VizDoom)
ruff check                           #checks style errors, enforced by CI
```

### Post-run analysis
```bash
python3 ga/report.py output/evolve/YYYY-MM-DD_HHMM/
```
Generates charts per level under `output/evolve/YYYY-MM-DD_HHMM/<level>/report/`.

### Docker
Notes:
Used for running the agent without setting up dependencies. Only supports headless run mode right now.
If you're a dev you probably won't use this.
The WAD file must be mounted at runtime and cannot be bundled in the image.
Docker Desktop must be running. Must be inside the DoomSat directory:

```bash
docker build -t doomsat .
docker run -v "$PWD/maps/wads/doom.wad:/app/maps/wads/doom.wad" doomsat
```


## Acknowledgments

- [VizDoom](https://github.com/Farama-Foundation/ViZDoom): Doom-based AI research platform
- [zdoom-navmesh-generator](https://github.com/pbr1111/zdoom-navmesh-generator): navmesh extraction
- [zdoom-pathfinding](https://github.com/dev-null-undefined/zdoom-pathfinding): A* and funnel algorithms

Doom and related trademarks are property of id Software. This project is for research and educational purposes.


## Authors

Aidan Brinkley

Thomas Brown