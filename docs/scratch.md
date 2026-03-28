# Session Notes — Telemetry, Combat Fixes, Output Structure

## What Changed

### Telemetry system (full rewrite)
`core/execution/telemetry_writer.py` was a stub (`class TelemetryWriter: pass`). It is now ~200 lines implementing three output tiers per episode:
- **Tier 0** (`ep_NNNN_debug.jsonl`): per-tick full game state, only when `full_telemetry=True`
- **Tier 1** (`ep_NNNN_summary.json`): episode summary + fitness + genome, always
- **Tier 2** (`ep_NNNN_actions.csv`): action stream `(tick, action_mask, sm_state, pos_x, pos_y)`, always

Fitness is computed inside `finalize_episode()` using the formula from `genetic_algo_design.md`.

### Visual map tool (`tools/replay_map.py`)
New post-processing script that reads Tier 2 + map JSON + WAD blocking segments and outputs an SVG showing the agent path colored by state, node markers, start/end markers, and a legend. Called automatically by `finalize_episode()` for every episode. Uses the same coordinate transform as `navigation_planner.py`.

### Agent wired to telemetry (`core/execution/agent.py`)
- `run_episode()` now calls `start_episode()`, `record_step()` per tick, `finalize_episode()` at end
- `run_episode(full_telemetry=True)` — run mode defaults to True (Tier 0 + map always); GA passes False
- `initialize_game(map_name=...)` — map is now a parameter, all internal calls use it (was hardcoded to DEFAULT_MAP_NAME)
- `episode_count` starts at 0, incremented before each episode
- Death now forces `gamestate.health = 0` so Tier 1 doesn't record a false non-zero health

### Output directory structure
- `output/run/` — run mode outputs, wiped at start of each run by `main.py`
- `output/evolve/` — GA outputs (not yet implemented, directory reserved)
- Old `output/telemetry/` and `output/ga_out/` removed

### Combat fixes (`core/execution/state_machine.py`)
- **Ammo-zero exit**: `(self.combat_hold or gamestate.enemies_visible) and gamestate.ammo > 0` — previously `combat_hold` could keep the agent in COMBAT with empty ammo indefinitely
- **Vertical ignore threshold removed**: was filtering enemies by screen Y position. Caused a valid enemy to be skipped. Fixed at the engine level with `+autoaim 35` in `vizdoom.cfg`, which enables ZDoom's native vertical autoaim (35° cone, matching original Doom). `VERTICAL_IGNORE_THRESHOLD` constant, import, field, and check all removed.

### VizDoom config (`config/vizdoom.cfg`)
Added `game_args = +autoaim 35`. This passes a ZDoom CVAR at launch. Without it, hitscan weapons fire perfectly horizontal and miss enemies on stairs or ledges even if they appear centered on screen.

### GA parameters updated (`docs/genetic_algo_design.md`)
`vertical_ignore_threshold` removed from evolvable parameters. Total genome size is now 7 parameters.

### Logging (`main.py`)
- Run mode: console only (INFO or DEBUG with `-v`), no file. You're watching the terminal — file adds nothing.
- Evolve mode: console + errors-only to `logs/doomsat_evolve_TIMESTAMP.log`.
- `--map`, `--headless`, `-v`/`--verbose` all on `run` subcommand (not parent parser).

### .gitignore cleanup
Removed stale entries: `telemetry/tier0/` etc., `wads/`, `!logs/last_run.json`. Added: `output/run/`, `output/evolve/`, corrected WAD path to `maps/wads/`.


## How It Works Now — Full Run Mode Flow

```
python main.py run [--map E1M2] [--headless] [-v]
```

1. `main.py` wipes `output/run/` (shutil.rmtree), sets up console logging
2. `Agent.__init__()` — nulls out all fields, `episode_count = 0`
3. `Agent.initialize_game(headless, map_name)`:
   - Loads `config/vizdoom.cfg` (includes `+autoaim 35`)
   - Applies native (640×480 windowed) or fast (320×240 headless) settings
   - Sets WAD path and map, calls `game.init()`
   - Loads blocking segments from WAD for this map
   - Creates `Graph → NavigationEngine → PathTracker → StateMachine → Perception → TelemetryWriter`
   - `PathTracker.load_static_nodes(map_name)` — loads waypoints/doors/exits from `maps/json/{map_name}.json`
4. `Agent.run_episode(full_telemetry=True)`:
   - `episode_count += 1`
   - `TelemetryWriter.start_episode(map_name, episode_id, full_telemetry=True)`:
     - Opens `output/run/ep_0001_actions.csv` and `ep_0001_debug.jsonl`
   - `game.new_episode()`, parse initial state, set path goal to EXIT
   - **Game loop** (each tick):
     - `Perception.parse(state)` → `GameState`
     - `StateMachine.update(gamestate)` → `action` (list of button booleans)
     - Priority order: STUCK → COMBAT → RECOVER → SCAN → TRAVERSE
     - COMBAT only entered if `ammo > 0`; exits immediately if ammo hits 0
     - `game.make_action(action, TICK=1)` — one decision per tick always
     - `TelemetryWriter.record_step(gamestate, action, sm_state)`
   - End detection: `is_player_dead()`, `tick_count >= DEFAULT_EPISODE_TIMEOUT`, or episode finished
   - If dead: force `gamestate.health = 0`
   - `TelemetryWriter.finalize_episode(stats)`:
     - Computes fitness
     - Writes `ep_0001_summary.json` (Tier 1)
     - Calls `tools/replay_map.render(...)` → `ep_0001_map.svg`
5. Stats dict returned and printed to console


## Where to Document Better

- **`core/execution/state_machine.py`**: The state priority order (STUCK > COMBAT > RECOVER > SCAN > TRAVERSE) is only implicit in `update()`. A short block comment above the priority checks explaining the hierarchy and why that order would help readability. Also worth noting that COMBAT requires `ammo > 0` and why.

- **`core/execution/agent.py`**: `run_episode()` has no comment on the end-detection logic. The three conditions and why `tick_count >= DEFAULT_EPISODE_TIMEOUT` is used instead of `game.get_episode_time()` (which returns 0 after episode ends) is non-obvious and worth a comment.

- **`config/vizdoom.cfg`**: The autoaim comment is there, but it would be worth referencing in `docs/execution_algo_design.md` under the combat section — the design doc should explain why vertical filtering is not needed and how aiming works.

- **`docs/telemetry.md`**: Good shape. Could add an explicit "Run Mode vs Evolve Mode" section contrasting the two output directories, file retention, and when `full_telemetry` is used — currently spread across the doc.

- **`tools/replay_map.py`**: The usage docstring covers CLI use but not the automatic invocation from `TelemetryWriter.finalize_episode()`. Worth a sentence at the top.


## Commit Message

```
Add telemetry system, visual map tool, and combat fixes

Implement TelemetryWriter (three-tier output: per-tick debug,
episode summary, action stream CSV). Wire telemetry into Agent's
run loop. Add tools/replay_map.py for SVG path visualization,
called automatically at episode end for all end reasons.

Fix two combat bugs: agent now exits COMBAT immediately when ammo
reaches zero (previously combat_hold kept it in COMBAT indefinitely
with empty ammo), and remove the vertical enemy filter that was
causing a valid enemy to be skipped. Vertical aiming is now handled
at the engine level with +autoaim 35 in vizdoom.cfg, matching
Doom's original 35-degree autoaim cone.

Restructure output directory: output/run/ for run mode (wiped each
run), output/evolve/ reserved for GA. Run mode logging is
console-only; no log file created when there are no errors.

Expand multi-map support: --map arg on run subcommand, all internal
references to DEFAULT_MAP_NAME replaced with the selected map name,
blocking segments and static nodes loaded per-map. Update
.gitignore to reflect new paths and remove stale entries.

Remove vertical_ignore_threshold from GA genome (7 params total).
```
