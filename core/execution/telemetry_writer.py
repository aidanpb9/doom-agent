"""Writes per-episode telemetry to output/run/ (run mode) or output/evolve/ (GA).

Three outputs per episode:
- Tier 0 (full_telemetry only): ep_NNNN_debug.jsonl: per-tick game state
- Tier 1 (always):              ep_NNNN_summary.json: episode summary + genome + fitness
- Tier 2 (always):              ep_NNNN_actions.csv: action stream for replay and map rendering
See docs/telemetry for more info.
"""
import csv
import json
import time
from pathlib import Path
from typing import Optional
from core.execution.game_state import GameState
from config.constants import RUN_DIR, EVOLVE_DIR


#Used for getting RAM in MB used by entire Python process including VizDoom.
#Useful for catching memory leaks (if it increases). View in output/_debug.jsonl.
try:
    import psutil
    _process = psutil.Process() 
except ImportError:
    _process = None


#Integer values match State enum in state_machine.py
_STATE_NAMES = {1: "STUCK", 2: "COMBAT", 3: "RECOVER", 4: "SCAN", 5: "TRAVERSE"}


def _encode_action(action: list[int]) -> int:
    """Encode action vector to bitmask. Index order matches ACTION_* constants."""
    mask = 0
    for i, v in enumerate(action):
        if v:
            mask |= (1 << i) #set bit i if this action is active
    return mask


class TelemetryWriter:

    def __init__(self, evolve: bool = False, output_dir: str | None = None) -> None:
        #Output config: where files go and what to write.
        self._dir: Path = Path(output_dir) if output_dir else Path(EVOLVE_DIR if evolve else RUN_DIR)
        self._full_telemetry: bool = False
        self._prefix: str = "ep_0000"

        #Episode metatada: written into Tier 1 summary.
        self._episode_id: int = 0
        self._seed: int = 0
        self._genome: Optional[dict] = None
        
        #Open file handles: set by start_episode(), closed by close()
        self._tier0_file = None
        self._tier2_file = None
        self._tier2_writer = None

        #Per-episode accumulators: reset each start_episode()
        self._last_health: float = 100.0
        self._ammo_start: Optional[float] = None
        self._damage_taken_total: float = 0.0
        self._tick_count: int = 0
        self._stuck_events: int = 0
        self._last_sm_state: int = 5 #TRAVERSE

    def start_episode(
        self,
        level_id: str,
        episode_id: int,
        seed: int = 0,
        genome: Optional[dict] = None,
        full_telemetry: bool = False,
        episode_prefix: str = "",
    ) -> None:
        """Close any open files from previous episode and open new ones for this episode.
        This seems like the same as the init. The init creates the fields, this resets them."""
        self.close()

        #Episode metadata
        self._episode_id = episode_id
        self._seed = seed
        self._map_name = level_id.upper()
        self._genome = genome
        self._full_telemetry = full_telemetry

        #Reset per-episode accumulators
        self._last_health = 100.0
        self._ammo_start = None
        self._damage_taken_total = 0.0
        self._tick_count = 0
        self._stuck_events = 0
        self._last_sm_state = 5 #Traverse

        #Build output filename prefix like "elite_ep__0042"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._prefix = f"{episode_prefix}_ep_{episode_id:04d}" if episode_prefix else f"ep_{episode_id:04d}"
        prefix = self._prefix

        #Open Tier 0 debug log only in full_telemtry mode. It's too big to do for every GA episode.
        if full_telemetry:
            self._tier0_file = (self._dir / f"{prefix}_debug.jsonl").open("w", encoding="utf-8")

        #Open Tier 2 action CSV and write the header. This is always written (run or evolve mode).
        self._tier2_file = (self._dir / f"{prefix}_actions.csv").open("w", encoding="utf-8", newline="")
        self._tier2_writer = csv.writer(self._tier2_file)
        self._tier2_writer.writerow(["tick", "action", "sm_state", "pos_x", "pos_y"])

    def record_step(self, gamestate: GameState, action: list[int], sm_state: int) -> None:
        """Record one tick. Called every tick by Agent."""
        #--- Tier 1 accumulators (feed into summary at episode end). ---
        self._tick_count += 1

        #Detect transitions into STUCK state
        if sm_state == 1 and self._last_sm_state != 1:
            self._stuck_events += 1
        self._last_sm_state = sm_state

        #Compute damage taken this tick. Clamp to 0 so healing doesn't produce negative damage.
        damage = max(0.0, self._last_health - gamestate.health)
        self._damage_taken_total += damage
        self._last_health = gamestate.health

        #Capture starting ammo on tick 1 so ammo_used can be computed at episode end.
        if self._ammo_start is None:
            self._ammo_start = gamestate.ammo

        action_mask = _encode_action(action)

        #--- Tier 2 always. Action and position trace. ---
        if self._tier2_writer:
            self._tier2_writer.writerow([
                self._tick_count, action_mask, _STATE_NAMES.get(sm_state, str(sm_state)),
                f"{gamestate.pos_x:.1f}", f"{gamestate.pos_y:.1f}",
            ])
            self._tier2_file.flush()

        #--- Tier 0. Per-tick debug log. full_telemetry mode only. ---
        if self._tier0_file:
            rss_mb = 0.0
            if _process:
                try:
                    rss_mb = round(_process.memory_info().rss / (1024 * 1024), 1) #bytes to MB
                except Exception:
                    pass

            self._tier0_file.write(json.dumps({
                "tick": self._tick_count,
                "unix_ms": int(time.time() * 1000),
                "health": gamestate.health,
                "armor": gamestate.armor,
                "ammo": gamestate.ammo,
                "pos_x": round(gamestate.pos_x, 1),
                "pos_y": round(gamestate.pos_y, 1),
                "angle": round(gamestate.angle, 1),
                "enemies_killed": gamestate.enemies_killed,
                "enemies_visible": len(gamestate.enemies_visible),
                "sm_state": _STATE_NAMES.get(sm_state, str(sm_state)),
                "action": action_mask,
                "damage_taken": round(damage, 1),
                "rss_mb": rss_mb,
            }) + "\n")
            self._tier0_file.flush()

    def finalize_episode(self, stats: dict) -> dict:
        """Write Tier 1 summary and generate map SVG. Return output file paths."""
        #Build output paths from prefix
        prefix = self._prefix
        tier1_path = self._dir / f"{prefix}_summary.json"
        tier2_path = self._dir / f"{prefix}_actions.csv"
        map_path = self._dir / f"{prefix}_map.svg"

        #Compute derived stats that aren't directly tracked by agent
        ammo_used = max(0.0, (self._ammo_start or 0.0) - stats.get("ammo", 0.0))
        fitness = stats.get("fitness", 0.0)

        #Build and write Tier 1 summary. A mix of agent stats and telem accumulators.
        summary = {
            "episode_id": self._episode_id,
            "level_id": self._map_name,
            "seed": self._seed,
            "end_reason": stats.get("end_reason", "unknown"),
            "ticks": stats.get("ticks", self._tick_count),
            "health": stats.get("health", 0),
            "armor": stats.get("armor", 0),
            "ammo": stats.get("ammo", 0),
            "enemies_killed": stats.get("enemies_killed", 0),
            "waypoints_reached": stats.get("waypoints_reached", 0),
            "stuck_events": self._stuck_events,
            "damage_taken_total": round(self._damage_taken_total),
            "ammo_used": round(ammo_used),
            "fitness": fitness,
        }
        if self._genome:
            summary["genome"] = self._genome #only exists in evolve mode

        tier1_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        #Capture map_name before close() clears state
        map_name = self._map_name
        self.close()

        #Generate SVG map from Tier 2 positions. Not fatal if fails.
        try:
            from tools.replay_map import render
            render(
                tier2_path=tier2_path,
                map_json_path=Path(f"maps/json/{map_name}.json"),
                output_path=map_path,
                map_name=map_name,
                end_reason=stats.get("end_reason", "unknown"),
            )
        except Exception as e:
            print(f"telemetry_writer: map render failed: {e}")

        return {
            "tier1": str(tier1_path),
            "tier2": str(tier2_path),
            "tier0": str(self._dir / f"{prefix}_debug.jsonl") if self._full_telemetry else "",
            "map": str(map_path),
        }

    def close(self) -> None:
        """Close any open file handles. Safe to call multiple times."""
        for f in (self._tier0_file, self._tier2_file):
            if f:
                try:
                    f.close()
                except Exception:
                    pass
        self._tier0_file = None
        self._tier2_file = None
        self._tier2_writer = None