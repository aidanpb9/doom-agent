"""Writes per-episode telemetry to output/run/ (run mode) or output/evolve/ (GA).

Three outputs per episode:
- Tier 0 (full_telemetry only): ep_NNNN_debug.jsonl  — per-tick game state
- Tier 1 (always):              ep_NNNN_summary.json  — episode summary + genome + fitness
- Tier 2 (always):              ep_NNNN_actions.csv   — action stream for replay and map rendering
"""
import csv
import json
import time
from pathlib import Path
from typing import Optional
from core.execution.game_state import GameState
from config.constants import RUN_DIR, EVOLVE_DIR

try:
    import psutil
    _process = psutil.Process()
except ImportError:
    _process = None

#Integer values match State enum in state_machine.py
_STATE_NAMES = {1: "STUCK", 2: "COMBAT", 3: "RECOVER", 4: "SCAN", 5: "TRAVERSE"}


def _encode_action(action: list[int]) -> int:
    """Encode action vector to bitmask. Index order matches ACTION_* constants."""
    return sum(v << i for i, v in enumerate(action) if v)


class TelemetryWriter:

    def __init__(self, evolve: bool = False) -> None:
        self._dir: Path = Path(EVOLVE_DIR if evolve else RUN_DIR)
        self._episode_id: int = 0
        self._seed: int = 0
        self._genome: Optional[dict] = None
        self._full_telemetry: bool = False

        self._tier0_file = None
        self._tier2_file = None
        self._tier2_writer = None

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
        full_telemetry: bool = False
    ) -> None:
        """Open output files for a new episode."""
        self.close()
        self._episode_id = episode_id
        self._seed = seed
        self._map_name = level_id.upper()
        self._genome = genome
        self._full_telemetry = full_telemetry

        self._last_health = 100.0
        self._ammo_start = None
        self._damage_taken_total = 0.0
        self._tick_count = 0
        self._stuck_events = 0
        self._last_sm_state = 5

        self._dir.mkdir(parents=True, exist_ok=True)
        prefix = f"ep_{episode_id:04d}"

        if full_telemetry:
            self._tier0_file = (self._dir / f"{prefix}_debug.jsonl").open("w", encoding="utf-8")

        self._tier2_file = (self._dir / f"{prefix}_actions.csv").open("w", encoding="utf-8", newline="")
        self._tier2_writer = csv.writer(self._tier2_file)
        self._tier2_writer.writerow(["tick", "action", "sm_state", "pos_x", "pos_y"])

    def record_step(self, gamestate: GameState, action: list[int], sm_state: int) -> None:
        """Record one tick. Called every tick by Agent."""
        self._tick_count += 1

        #Detect transitions into STUCK state
        if sm_state == 1 and self._last_sm_state != 1:
            self._stuck_events += 1
        self._last_sm_state = sm_state

        damage = max(0.0, self._last_health - gamestate.health)
        self._damage_taken_total += damage
        self._last_health = gamestate.health

        if self._ammo_start is None:
            self._ammo_start = gamestate.ammo

        action_mask = _encode_action(action)

        #Tier 2, always
        if self._tier2_writer:
            self._tier2_writer.writerow([
                self._tick_count, action_mask, _STATE_NAMES.get(sm_state, str(sm_state)),
                f"{gamestate.pos_x:.1f}", f"{gamestate.pos_y:.1f}",
            ])
            self._tier2_file.flush()

        #Tier 0, full_telemetry only
        if self._tier0_file:
            rss_mb = 0.0
            if _process:
                try:
                    rss_mb = round(_process.memory_info().rss / (1024 * 1024), 1)
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
        """Write Tier 1 summary, generate map if applicable. Returns output file paths."""
        prefix = f"ep_{self._episode_id:04d}"
        tier1_path = self._dir / f"{prefix}_summary.json"
        tier2_path = self._dir / f"{prefix}_actions.csv"
        map_path = self._dir / f"{prefix}_map.svg"

        ammo_used = max(0.0, (self._ammo_start or 0.0) - stats.get("ammo", 0.0))
        fitness = stats.get("fitness", 0.0)

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
            "fitness": round(fitness, 2),
        }
        if self._genome:
            summary["genome"] = self._genome

        tier1_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        #Capture map_name before close() clears state
        map_name = self._map_name
        self.close()

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
        for f in (self._tier0_file, self._tier2_file):
            if f:
                try:
                    f.close()
                except Exception:
                    pass
        self._tier0_file = None
        self._tier2_file = None
        self._tier2_writer = None