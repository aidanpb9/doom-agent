"""Genome operations and GA evolution runner.

compute_fitness() is the single source of truth for fitness.
random_genome() and mutate() are pure genome operations.
GeneticAlgo owns the worker pool and drives the evolution loop.

See genetic_algo_design.md for algorithm details and parameter ranges.
"""
import json
import random
from pathlib import Path
from datetime import datetime
from core.execution.agent import Agent
from config.constants import EVOLVE_DIR
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
import glob


RADIATION_INTENSITY = 0.25  #per-param mutation probability
EVAL_RUNS = 5               #episodes averaged per genome evaluation
PLATEAU_GENS = 10           #generations without elite change before advancing
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

def eval_worker(genome: dict, level: str, gen: int, role: str, game_seed: int, run_dir: str) -> tuple[float, bool]:
    """Run EVAL_RUNS episodes for one genome. Return average fitness and if
    any run beat a level. Contained at the module level so it can be pickled and sent
    to a worker process by ProcessPoolExecutor."""
    #Initializations
    ep_offset = 0 if role == "elite" else 10000 #prevent filename collisions
    output_dir = str(Path(run_dir) / level / f"gen_{gen:04d}")
    agent = Agent()
    agent.episode_count = ep_offset
    fitnesses = []
    any_completed = False

    try:
        #Run EVAL_RUNS episodes and track fitness
        for _ in range(EVAL_RUNS):
            #Run a single episode. Re-initialize game to reset all state.
            agent.close()
            agent.initialize_game(headless=True, evolve=True, map_name=level, output_dir=output_dir, game_seed=game_seed)
            stats = agent.run_episode(genome=genome, full_telemetry=False, episode_prefix=role)
            stats["fitness"] = compute_fitness(stats)
            agent.telemetry_writer.finalize_episode(stats)
            fitnesses.append(stats["fitness"])
            if stats.get("finish_level"):
                any_completed = True
    finally:
        agent.close()

    #Close episode and return fitness info
    agent.close()
    avg_fitness = round(sum(fitnesses) / EVAL_RUNS, 2)
    return avg_fitness, any_completed

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

    def __init__(self) -> None:
        """Pool created once, persists across all generations and levels.
        Use fork so workers inherit the parent process state without re-importing modules."""
        self._pool = ProcessPoolExecutor(
            max_workers=2,
            mp_context=mp.get_context("fork"))
        
        for f in glob.glob("/dev/shm/ViZDoom*"):
            Path(f).unlink(missing_ok=True) #cleans up stale files, preserves RAM
        

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

            #Submit the two genomes to the workers and get returns
            #The purpose of wrapping this in attempt block is to handle crashes
            #that occur on the first generation, but we don't want to retry forver.
            game_seed = random.randint(0, 2**31) #same seed for both workers for fair comparison
            for attempt in range(2):
                f_a = self._pool.submit(eval_worker, elite, level, gen, "elite", game_seed, run_dir)
                f_b = self._pool.submit(eval_worker, challenger, level, gen, "challenger", game_seed, run_dir)
                try:
                    a_fit, a_beat = f_a.result(timeout=300)
                    b_fit, b_beat = f_b.result(timeout=300)
                    break  #success
                except (TimeoutError, BrokenProcessPool):
                    #BrokenProcessPool means the worker was killed at the OS level (VizDoom crash).
                    #The pool is dead and must be recreated before the next attempt can submit work.
                    self._pool = ProcessPoolExecutor(max_workers=2, mp_context=mp.get_context("fork"))
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
                
                #Submit the two genomes to the workers and get returns
                game_seed = random.randint(0, 2**31) #same seed for both workers for fair comparison
                f_a = self._pool.submit(eval_worker, elite, level, gen, "elite", game_seed, run_dir)
                f_b = self._pool.submit(eval_worker, challenger, level, gen, "challenger", game_seed, run_dir)
                #VizDoom can hang at the C++ level with no Python exception raised.
                #If a worker freezes past 5 minutes we skip the generation entirely.
                #The elite is unchanged, the plateau counter is not incremented,
                #and the next generation will retry with a fresh mutant.
                try:
                    a_fit, a_beat = f_a.result(timeout=300)
                    b_fit, b_beat = f_b.result(timeout=300)
                except (TimeoutError, BrokenProcessPool):
                    #BrokenProcessPool means the C++ VizDoom process was killed at the OS level.
                    #The pool is dead and must be recreated or all future submits will also raise.
                    self._pool = ProcessPoolExecutor(max_workers=2, mp_context=mp.get_context("fork"))
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