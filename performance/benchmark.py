import random
import time
import os
import tempfile
import hashlib
import shutil
import statistics
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.execution.agent import Agent
from ga.genetic_algo import compute_fitness

EPISODES_TO_RUN = 15
WARMUP_EPISODES = 3 # Use this many less time values, removing from the beginning
OUTLIER_FROM_MEDIAN_PERCENT = 0.05
ACTION_FILE = "benchmark_ep_0001_actions.csv"
OUTPUT_PATH = "performance/output/tests/"

GENOME = {
  "loot_node_max_distance": 500,
  "stuck_recovery_ticks": 70,
  "combat_hold_ticks": 35,
  "health_threshold": 80,
  "armor_threshold": 5,
  "ammo_threshold": 25,
  "scan_interval": 140
}


def run_benchmark_loop():
    """Runs several episodes and reports the performance."""
    times = []
    for i in range(EPISODES_TO_RUN):
        with tempfile.TemporaryDirectory() as d:
            start_time = time.perf_counter()
            print(i, _run_one_episode(d))
            end_time = time.perf_counter()
            times.append(end_time - start_time)

            # Save files to compare against golden
            from_path: str = os.path.join(d, ACTION_FILE)
            to_path = f"{OUTPUT_PATH}test_{i}"
            os.makedirs(to_path, exist_ok=True)
            shutil.copy(from_path, to_path)

    # Time benchmarks.
    print(f"Time minimum: {min(times)}") # maybe the min was in a warmup
    times = times[WARMUP_EPISODES:] # cut the warmups

    print(f"\nTimes: {times}")
    print(f"Time stddev: {statistics.stdev(times)}")

    median = statistics.median(times)
    print(f"Time median: {median}")
    for i, ep_time in enumerate(times, start=WARMUP_EPISODES):
        if abs(ep_time - median) / median > OUTLIER_FROM_MEDIAN_PERCENT:
            print(f"Episode {i} with time {ep_time} is an outlier")


def check_result_hashes():
    """
    Checks that episodes deterministic using saved results.
    Catches regression in episode results and if the episodes
    become non-deterministic.
    """
    # Get the golden's hash.
    with open(f"performance/output/golden/{ACTION_FILE}", "rb") as f:
        golden_hash = hashlib.file_digest(f, "sha256").hexdigest()

    # Get the hashes from the benchmark.
    action_hashes = set()
    for i in range(EPISODES_TO_RUN):
        action_file = f"{OUTPUT_PATH}test_{i}/{ACTION_FILE}"
        with open(action_file, "rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        action_hashes.add(digest)

    # Hash validation messages.
    error_msg: str = ""
    if len(action_hashes) > 1:
        error_msg += "New result hashes differ from each other, no determinism. "
    if golden_hash not in action_hashes:
        error_msg += "No result hash matched the golden hash. "
    if error_msg:
        raise ValueError(error_msg)
    print("All hashes valid")


def delete_test_folder():
    shutil.rmtree(OUTPUT_PATH, ignore_errors=True)


def _run_one_episode(out_dir: str, game_seed: int = 123, py_seed: int = 1) -> dict:
    """TODO"""
    agent = Agent()
    try:
        random.seed(py_seed)
        
        agent.initialize_game(
            headless=True,
            evolve=True,
            map_name="E1M1",
            output_dir=out_dir,
            game_seed=game_seed
        )
        
        stats = agent.run_episode(genome=GENOME, full_telemetry=False, episode_prefix="benchmark")
        stats["fitness"] = compute_fitness(stats)
        agent.telemetry_writer.finalize_episode(stats)
        return stats
    finally:
        agent.close() #always release the engine


if __name__ == "__main__":
    delete_test_folder()
    run_benchmark_loop()
    check_result_hashes()
