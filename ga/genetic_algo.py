"""Genome operations and GA evolution runner.

compute_fitness() is the single source of truth for fitness.
random_genome() and mutate() are pure genome operations.
GeneticAlgo owns the worker pool and drives the evolution loop.

See genetic_algo_design.md for algorithm details and parameter ranges.
"""
import json
import math
import random
from pathlib import Path
from datetime import datetime
from core.execution.agent import Agent
from config.constants import EVOLVE_DIR
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, TimeoutError, wait
from concurrent.futures.process import BrokenProcessPool
import glob


RADIATION_INTENSITY = 0.25  #per-param mutation probability
EVAL_RUNS = 5               #episodes averaged per genome evaluation
PLATEAU_GENS = 10           #generations without elite change before advancing
DEFAULT_WORKERS = 2         #matches the 2-core flight hardware, change only for ground runs
EPISODE_TIMEOUT = 60        #seconds allowed per episode task, VizDoom can hang with no Python exception
LEVELS = ["E1M1", "E1M2"]

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

def eval_episode(genome: dict, level: str, gen: int, role: str, game_seed: int, run_dir: str,
                 run_idx: int, py_seed: int | None = None) -> tuple[float, bool]:
    """Run one episode for one genome. Return its fitness and whether it beat the level.
    Contained at the module level so it can be pickled and sent to a worker process
    by ProcessPoolExecutor. run_idx makes the output files of the EVAL_RUNS episodes distinct.
    py_seed fixes the Python RNG so the episode is reproducible, None keeps it random."""
    output_dir = str(Path(run_dir) / level / f"gen_{gen:04d}")
    agent = Agent()
    try:
        if py_seed is not None:
            random.seed(py_seed) #run_episode draws its own seed from this RNG
        agent.initialize_game(headless=True, evolve=True, map_name=level, output_dir=output_dir, game_seed=game_seed)
        agent.episode_count = run_idx #deterministic id per run, run_episode adds 1
        stats = agent.run_episode(genome=genome, full_telemetry=False, episode_prefix=role)
        stats["fitness"] = compute_fitness(stats)
        agent.telemetry_writer.finalize_episode(stats)
        return stats["fitness"], bool(stats.get("finish_level"))
    finally:
        agent.close()

def compute_fitness(stats: dict) -> float:
    """Compute fitness from episode stats. See genetic_algo_design.md."""
    if stats.get("finish_level"):
        ticks = stats.get("ticks", 12600)
        raw = (5000
               + 500 * (1 - ticks / 4200)
               + 2 * stats.get("health", 0)
               + 1 * stats.get("armor", 0)
               + 0.5 * stats.get("ammo", 0))
    else:
        raw = (5 * stats.get("enemies_killed", 0)
               + 10 * stats.get("waypoints_reached", 0))
    return round(raw, 2)

def random_genome() -> dict:
    """Generate a genome with all 7 params randomly sampled from within their valid ranges."""
    genome = {}
    for param, (lo, hi) in PARAM_RANGES.items():
        genome[param] = random.randint(lo, hi) #pick a random int between min and max for this param
    return genome

def mutate(genome: dict) -> dict:
    """Return a new genome derived from the parent, with random params re-sampled.
    Each param has a RADIATION_INTENSITY chance of being re-rolled independently.
    Models cosmic ray bit-flips, most params stay the same, a few change randomly."""
    child = dict(genome) #copy the parent so we don't modify the original
    for param, (lo, hi) in PARAM_RANGES.items():
        if random.random() < RADIATION_INTENSITY: #25% chance per param
            child[param] = random.randint(lo, hi) #re-roll within valid range
    return child


class GeneticAlgo:

    def __init__(self, workers: int = DEFAULT_WORKERS, py_seed_base: int | None = None) -> None:
        """Pool created once, persists across all generations and levels.
        workers is the number of episodes that run at once. Each generation has 2 * EVAL_RUNS
        episode tasks (elite and challenger), so more workers than that sit idle.
        py_seed_base makes every episode reproducible (for benchmarks and tests), None keeps it random."""
        if workers < 1:
            raise ValueError(f"workers must be at least 1, got {workers}")
        self._workers = workers
        self._py_seed_base = py_seed_base
        self._pool = self._make_pool()

        for f in glob.glob("/dev/shm/ViZDoom*"):
            Path(f).unlink(missing_ok=True) #cleans up stale files, preserves RAM

    def _make_pool(self) -> ProcessPoolExecutor:
        """Use fork so workers inherit the parent process state without re-importing modules."""
        return ProcessPoolExecutor(max_workers=self._workers, mp_context=mp.get_context("fork"))

    def evaluate_genomes(self, elite: dict, challenger: dict, level: str, gen: int,
                         game_seed: int, run_dir: str) -> tuple[float, bool, float, bool]:
        """Run EVAL_RUNS episodes for each genome across the worker pool. Return
        (elite_fitness, elite_beat, challenger_fitness, challenger_beat), where fitness is
        the average over the episodes and beat is True if any episode beat the level.
        Raises TimeoutError if the episodes don't all finish in time, and
        BrokenProcessPool if a worker is killed. The caller recreates the pool."""
        futures: dict[str, list] = {"elite": [], "challenger": []}
        for role, genome in (("elite", elite), ("challenger", challenger)):
            for run_idx in range(EVAL_RUNS):
                py_seed = None if self._py_seed_base is None else self._py_seed_base + gen * EVAL_RUNS + run_idx
                futures[role].append(self._pool.submit(
                    eval_episode, genome, level, gen, role, game_seed, run_dir, run_idx, py_seed))

        #Tasks beyond the worker count queue up, so the deadline covers every round of work.
        rounds = math.ceil(2 * EVAL_RUNS / self._workers)
        _, not_done = wait(futures["elite"] + futures["challenger"], timeout=rounds * EPISODE_TIMEOUT)
        if not_done:
            for future in not_done:
                future.cancel() #only cancels tasks that haven't started
            raise TimeoutError(f"{len(not_done)} episode tasks did not finish")

        #Collect in run_idx order so the float sum doesn't depend on which finished first.
        results = {}
        for role, role_futures in futures.items():
            episodes = [future.result() for future in role_futures]
            avg_fitness = round(sum(fitness for fitness, _ in episodes) / EVAL_RUNS, 2)
            results[role] = (avg_fitness, any(beat for _, beat in episodes))
        return results["elite"] + results["challenger"]

    def evolve(self) -> None:
        """Main evolution loop. Iterates levels, evolves until plateau, writes history."""
        #Each run gets a timestamped subfolder so previous runs are never overwritten
        run_dir = str(Path(EVOLVE_DIR) / datetime.now().strftime("%Y-%m-%d_%H%M"))
        evolve_dir = Path(run_dir)
        evolve_dir.mkdir(parents=True, exist_ok=True)
        
        #Initialize genome dicts
        history = {}
        level_elites = {}
        elite = None

        #Loop over every level 
        for level in LEVELS:
            #The outer loop that starts here is just for run 0 for each level. 
            #Then genomes compete in the loop below until plateau. 
            #Then return here to start next level, but use old elite as starting.
            history[level] = {}
            gens_no_change = 0
            level_beaten = False
            gen = 0

            #Gen 0: seed initial population
            if elite is None:
                elite = random_genome()
            challenger = mutate(elite)

            #Evaluate the two genomes across the workers and get returns
            #The purpose of wrapping this in attempt block is to handle crashes
            #that occur on the first generation, but we don't want to retry forver.
            game_seed = random.randint(0, 2**31) #same seed for both genomes for fair comparison
            for attempt in range(2):
                try:
                    a_fit, a_beat, b_fit, b_beat = self.evaluate_genomes(elite, challenger, level, gen, game_seed, run_dir)
                    break  #success
                except (TimeoutError, BrokenProcessPool):
                    #BrokenProcessPool means the worker was killed at the OS level (VizDoom crash).
                    #The pool is dead and must be recreated before the next attempt can submit work.
                    self._pool = self._make_pool()
                    print(f"[{level}] gen={gen} timed out (attempt {attempt + 1}/2), retrying...")
            else:
                #Both attempts timed out which means VizDoom is likely stuck.
                #Record the failure in history so it's visible in the output and try next level.
                print(f"[{level}] gen={gen} failed both attempts, skipping level")
                history[level]["timeout"] = True
                (evolve_dir / "evolution_history.json").write_text(json.dumps(history, indent=2))
                continue

            #Update the elite genome by comparing results
            level_beaten = a_beat or b_beat
            winner = "challenger" if b_fit > a_fit else "elite"
            if winner == "challenger":
                elite = challenger

            #Print and initialize telemetry output.
            print(f"[{level}] gen=0  elite={a_fit}  challenger={b_fit}  winner={winner}")
            history[level][0] = {
                "elite_fitness": a_fit, "challenger_fitness": b_fit,
                "winner": winner, "game_seed": game_seed,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "elite_genome": dict(elite),
            }
            (evolve_dir / "evolution_history.json").write_text(json.dumps(history, indent=2))

            while True: #Until plateau, then move onto next level
                gen += 1
                challenger = mutate(elite)
                
                #Evaluate the two genomes across the workers and get returns
                game_seed = random.randint(0, 2**31) #same seed for both genomes for fair comparison
                #VizDoom can hang at the C++ level with no Python exception raised.
                #If the episodes don't finish within their time budget we skip the generation entirely.
                #The elite is unchanged, the plateau counter is not incremented,
                #and the next generation will retry with a fresh mutant.
                try:
                    a_fit, a_beat, b_fit, b_beat = self.evaluate_genomes(elite, challenger, level, gen, game_seed, run_dir)
                except (TimeoutError, BrokenProcessPool):
                    #BrokenProcessPool means the C++ VizDoom process was killed at the OS level.
                    #The pool is dead and must be recreated or all future submits will also raise.
                    self._pool = self._make_pool()
                    print(f"[{level}] gen={gen} worker crashed or timed out, skipping generation")
                    continue

                #Compare results and update genome
                if a_beat or b_beat:
                    level_beaten = True
                winner = "challenger" if b_fit > a_fit else "elite"
                if winner == "challenger":
                    elite = challenger
                    gens_no_change = 0
                else:
                    gens_no_change += 1

                #Print and write to telemetry
                print(f"[{level}] gen={gen}  elite={a_fit}  challenger={b_fit}"
                      f"  winner={winner}  plateau={gens_no_change}/{PLATEAU_GENS}")
                history[level][gen] = {
                    "elite_fitness": a_fit, "challenger_fitness": b_fit,
                    "winner": winner, "game_seed": game_seed,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "elite_genome": dict(elite),
                }
                (evolve_dir / "evolution_history.json").write_text(json.dumps(history, indent=2))

                if level_beaten and gens_no_change >= PLATEAU_GENS:
                    level_elites[level] = dict(elite)
                    genome_str = "  ".join(f"{k}={v}" for k, v in elite.items())
                    print(f"[{level}] plateau after gen {gen}  elite genome: {genome_str}")
                    break
        
        #When plateau, update the final_elites doc.
        (evolve_dir / "final_elite.json").write_text(json.dumps(level_elites, indent=2))
        print(f"Evolution complete. Level elites: {level_elites}")