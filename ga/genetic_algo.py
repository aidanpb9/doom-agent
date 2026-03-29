"""Genome operations and GA evolution runner.

compute_fitness() is the single source of truth for fitness.
random_genome() and mutate() are pure genome operations.
GeneticAlgo owns the Agent and drives the evolution loop.

See genetic_algo_design.md for algorithm details and parameter ranges.
"""
import json
import random
from pathlib import Path
from core.execution.agent import Agent
from config.constants import EVOLVE_DIR

#Evolvable parameter ranges, must match genetic_algo_design.md
PARAM_RANGES = {
    "loot_node_max_distance": (200, 1000),
    "stuck_recovery_ticks":   (35,  140),
    "combat_hold_ticks":      (5,   50),
    "health_threshold":       (0,   100),
    "armor_threshold":        (0,   100),
    "ammo_threshold":         (0,   200),
    "scan_interval":          (70,  420),
}

RADIATION_INTENSITY = 0.25  #per-param mutation probability
EVAL_RUNS = 3               #episodes averaged per genome evaluation
PLATEAU_GENS = 10           #generations without elite change before advancing
LEVELS = ["E1M1", "E1M2"]


def compute_fitness(stats: dict) -> float:
    """Compute fitness from episode stats. See genetic_algo_design.md."""
    if stats.get("finish_level"):
        ticks = stats.get("ticks", 12600)
        raw = (1000
               + 500 * (1 - ticks / 4200)
               + 2 * stats.get("health", 0)
               + 1 * stats.get("armor", 0)
               + 0.5 * stats.get("ammo", 0))
    else:
        raw = (5 * stats.get("enemies_killed", 0)
               + 10 * stats.get("waypoints_reached", 0))
    return round(raw, 2)


def random_genome() -> dict:
    """Generate a random genome with all params sampled uniformly within valid ranges."""
    return {k: random.randint(lo, hi) for k, (lo, hi) in PARAM_RANGES.items()}


def mutate(genome: dict) -> dict:
    """Return a new genome with each param independently re-sampled at RADIATION_INTENSITY rate."""
    child = dict(genome)
    for k, (lo, hi) in PARAM_RANGES.items():
        if random.random() < RADIATION_INTENSITY:
            child[k] = random.randint(lo, hi)
    return child


class GeneticAlgo:

    def __init__(self) -> None:
        self.agent = Agent()

    def evolve(self) -> None:
        """Main evolution loop. Iterates levels, evolves until plateau, writes history."""
        evolve_dir = Path(EVOLVE_DIR)
        evolve_dir.mkdir(parents=True, exist_ok=True)

        history = {}
        level_elites = {}
        elite = None

        for level in LEVELS:
            history[level] = {}
            gens_no_change = 0
            level_beaten = False

            #Gen 0: seed initial population
            if elite is None:
                elite = random_genome()
            challenger = mutate(elite)

            a_fit, a_beat = self._evaluate(elite, level, 0, "elite")
            b_fit, b_beat = self._evaluate(challenger, level, 0, "challenger")
            level_beaten = a_beat or b_beat
            winner = "challenger" if b_fit > a_fit else "elite"
            if winner == "challenger":
                elite = challenger

            print(f"[{level}] gen=0  elite={a_fit}  challenger={b_fit}  winner={winner}")
            history[level][0] = {
                "elite_fitness": a_fit, "challenger_fitness": b_fit,
                "winner": winner, "elite_genome": dict(elite),
            }
            (evolve_dir / "evolution_history.json").write_text(json.dumps(history, indent=2))

            gen = 0
            while True:
                gen += 1
                challenger = mutate(elite)

                a_fit, a_beat = self._evaluate(elite, level, gen, "elite")
                b_fit, b_beat = self._evaluate(challenger, level, gen, "challenger")

                if a_beat or b_beat:
                    level_beaten = True

                winner = "challenger" if b_fit > a_fit else "elite"
                if winner == "challenger":
                    elite = challenger
                    gens_no_change = 0
                else:
                    gens_no_change += 1

                print(f"[{level}] gen={gen}  elite={a_fit}  challenger={b_fit}"
                      f"  winner={winner}  plateau={gens_no_change}/{PLATEAU_GENS}")

                history[level][gen] = {
                    "elite_fitness": a_fit, "challenger_fitness": b_fit,
                    "winner": winner, "elite_genome": dict(elite),
                }
                (evolve_dir / "evolution_history.json").write_text(json.dumps(history, indent=2))

                if level_beaten and gens_no_change >= PLATEAU_GENS:
                    level_elites[level] = dict(elite)
                    genome_str = "  ".join(f"{k}={v}" for k, v in elite.items())
                    print(f"[{level}] plateau after gen {gen}  elite genome: {genome_str}")
                    break

        (evolve_dir / "final_elite.json").write_text(json.dumps(level_elites, indent=2))
        print(f"Evolution complete. Level elites: {level_elites}")

    def _evaluate(self, genome: dict, level: str, gen: int, role: str) -> tuple[float, bool]:
        """Run EVAL_RUNS episodes and return (avg_fitness, any_completed)."""
        results = [self._run_once(genome, level, gen, role) for _ in range(EVAL_RUNS)]
        avg = round(sum(r["fitness"] for r in results) / EVAL_RUNS, 2)
        any_completed = any(r.get("finish_level") for r in results)
        return avg, any_completed

    def _run_once(self, genome: dict, level: str, gen: int, role: str) -> dict:
        """Run a single episode. Re-initializes game to reset all state."""
        self.agent.close()
        output_dir = str(Path(EVOLVE_DIR) / f"gen_{gen:04d}")
        self.agent.initialize_game(headless=True, evolve=True, map_name=level, output_dir=output_dir)
        stats = self.agent.run_episode(genome=genome, full_telemetry=False, episode_prefix=role)
        stats["fitness"] = compute_fitness(stats)
        self.agent.telemetry_writer.finalize_episode(stats)
        return stats