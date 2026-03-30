# Telemetry Design

## Overview
TelemetryWriter produces per-episode outputs for debugging, replay, and GA fitness tracking. There are three outputs: Tier 0 (per-tick game state), Tier 1 (episode summary), and Tier 2 (action stream). Run mode writes to `output/run/`; evolve mode writes to a timestamped subfolder under `output/evolve/`. Files are named by sequential episode index so GA runs don't overwrite each other.

Files are opened by `start_episode()` and finalized by `finalize_episode()`. The GA runner embeds Tier 1 summaries into `evolution_history.json` and links them by `episode_id`.


## Output Files
```
output/run/ep_NNNN_summary.json            <- Tier 1
output/run/ep_NNNN_actions.csv             <- Tier 2
output/run/ep_NNNN_map.svg                 <- visual map
output/run/ep_NNNN_debug.jsonl             <- Tier 0 (full_telemetry mode only)

output/evolve/YYYY-MM-DD_HHMM/               <- one folder per run, never overwritten
    evolution_history.json                   <- per-generation results
    final_elite.json                         <- best genome per level
    E1M1/gen_NNNN/
        elite_ep_NNNN_{summary,actions,map}  <- Tier 1/2, elite runs
        challenger_ep_NNNN_{summary,actions,map}  <- Tier 1/2, challenger runs
```
Episode index is sequential across an entire evolution run and does not reset between maps or generations. Each run gets a timestamped folder so previous runs are never overwritten. The GA doc defines evolve mode outputs.


## Tier 0: Per-Tick Debug Log
**File:** `ep_NNNN_debug.jsonl`: one JSON object per tick

**Written:** full_telemetry mode only. Too large to write for every GA episode.

**Use for:** debugging specific runs, checking perception, understanding why the agent died.

**Fields per tick:**
- `tick`: game tick
- `unix_ms`: wall clock timestamp
- `health`, `armor`, `ammo`: current player stats
- `pos_x`, `pos_y`, `angle`: player position and facing
- `enemies_killed`: cumulative kill count
- `enemies_visible`: count of enemies in FOV this tick
- `sm_state`: state machine state (`TRAVERSE`, `COMBAT`, `RECOVER`, `SCAN`, `STUCK`)
- `action`: action taken this tick (integer bitmask)
- `damage_taken`: health lost since last tick
- `rss_mb`: process memory in MB


## Tier 1: Episode Summary
**File:** `ep_NNNN_summary.json`: written once at episode end

**Written:** always, including all 5 evaluation runs per genome in evolve mode.

**Use for:** GA fitness tracking, comparing genomes, post-run plots.

**Fields:**
- `episode_id`: sequential episode index
- `level_id`: map name (e.g. `"E1M1"`)
- `seed`: Python RNG seed for this episode, controls SCAN timing and STUCK turn direction. VizDoom's world state RNG is controlled per generation and recorded in `evolution_history.json` as `game_seed`.
- `end_reason`: `"completion"`, `"death"`, or `"timeout"`
- `ticks`: total ticks elapsed
- `health`, `armor`, `ammo`: final player stats
- `enemies_killed`: total kills
- `waypoints_reached`: static waypoints visited (GA fitness input)
- `stuck_events`: number of times STUCK state triggered
- `damage_taken_total`: cumulative damage received
- `ammo_used`: ammo at start minus ammo at end
- `fitness`: computed fitness score (see genetic_algo_design.md)
- `genome`: genome params for this episode (all 7 evolvable parameters), omitted in run mode


## Tier 2: Action and Position Trace
**File:** `ep_NNNN_actions.csv`: one row per tick

**Written:** always.

**Use for:** action replay and SVG map generation. `action` is sufficient to replay the episode into VizDoom  because positions are recomputed by the game. `pos_x/pos_y` and `sm_state` are included for the map renderer: `replay_map.py` reads them to draw the agent path on the SVG, with path color driven by `sm_state`. Without position there is no path to render; without state the path has no color.

**CSV columns:**
`tick, action, sm_state, pos_x, pos_y`

- `tick`: game tick
- `action`: integer bitmask of buttons pressed this tick
  - bit 0: FORWARD, bit 1: BACKWARD, bit 2: TURN_LEFT, bit 3: TURN_RIGHT, bit 4: ATTACK, bit 5: USE
- `sm_state`: state machine state name string (`"STUCK"`, `"COMBAT"`, `"RECOVER"`, `"SCAN"`, `"TRAVERSE"`)
- `pos_x`, `pos_y`: player position in Doom map units


## Visual Map (Tier 2 also)
**File:** `ep_NNNN_map.svg`: generated at end of episode

**Written:** always generate a map since all end reasons (completion, death, timeout) give useful info.

**Use for:** visually inspecting agent behavior like where it went, what state it was in, where it got stuck.

**Contents:**
- Map walls from WAD blocking segments (gray)
- Agent path from Tier 2 positions, colored by sm_state
- Static node positions from map JSON

**Generation:** post-process script `tools/replay_map.py` reads Tier 2 + map JSON + WAD segments and outputs SVG. Called automatically by `finalize_episode()`. Uses the same SVG coordinate transform as `tools/navigation_planner.py`.


## TelemetryWriter Interface
```python
writer.start_episode(level_id, episode_id, genome=None, full_telemetry=False, episode_prefix="")
writer.record_step(gamestate, action, sm_state)
writer.finalize_episode(stats)
```
- `full_telemetry=True` enables Tier 0 (run mode), map SVG is always generated
- `genome` dict is embedded in Tier 1 when provided (evolve mode)
- `episode_prefix` prepends a label to all output filenames (e.g. `"elite"` -> `elite_ep_NNNN_*`)
- `record_step` is called every tick (frameskip = 1 always)


## Run Mode vs Evolve Mode
Run mode (`python main.py run`) is ground testing only. It writes to `output/run/`,
which is wiped at the start of each run so you always have one clean set of outputs.
`full_telemetry=True` by default. Tier 0 and map SVG always generated.

Evolve mode writes to a timestamped subfolder `output/evolve/YYYY-MM-DD_HHMM/` created at the start of each run. Previous runs are never overwritten. Episodes are organized into `LEVEL/gen_NNNN/` subdirectories with `elite_` and `challenger_` filename prefixes.
`full_telemetry=False` excludes Tier 0, but map SVG still generated. The satellite is meant to run evolve mode only.


## Design Decisions
**No TLP or spacecraft fields:** Removed from original reference implementation. DoomSat payload telemetry covers only game state, not satellite health.

**Sequential episode IDs:** Episodes are numbered globally across an entire evolution run so telemetry files can be cross-referenced by ID across generation folders.

**Tier 2 sufficient for replay:** Because record_step is called every tick, the action stream is complete. Replaying it into VizDoom reproduces the episode without re-evaluating any decisions, bypassing RNG entirely.

**Run mode is ground testing only:** The satellite runs evolve mode exclusively. Run mode (windowed, full rendering) is a developer tool for ground debugging. Pass `full_telemetry=True` to enable Tier 0 and continuous map SVG output during ground testing.

**Tier 0 full_telemetry only:** At ~12600 ticks per episode and potentially thousands of GA episodes, writing full per-tick JSON for every run would generate gigabytes of data. Use full_telemetry mode to investigate a specific genome, or downlink Tier 0 from orbit for a specific episode of interest.