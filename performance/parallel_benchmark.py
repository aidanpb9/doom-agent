import hashlib
import heapq
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import psutil

from ga.genetic_algo import GeneticAlgo, EVAL_RUNS

# Normalization
WORKER_COUNTS = [1, 2, 4, 6, 8, 10, 12] # 12 is above the 10 tasks per generation, so it should not beat 10.
WARMUP_GENERATIONS = 1 # Starts the worker processes. Not timed, not sampled.
GENERATIONS_PER_COUNT = 3
SAMPLE_SECONDS = 0.5 # How often CPU and memory are sampled during a timed generation.

# Seeds. Every run uses the same ones, so every run plays the same 10 episodes.
FAST_SEED = 123 # 5 seconds per episode.
SLOW_SEED = 42  # 12 seconds per episode.
GAME_SEED = FAST_SEED
PY_SEED_BASE = 7
GEN = 0
LEVEL = "E1M1"

# Files
CHART_PATH = "performance/output/parallel_scaling.png"

MB = 1024 * 1024
TASKS_PER_GENERATION = 2 * EVAL_RUNS # Elite and challenger, one task per episode.

ELITE = {
  "loot_node_max_distance": 500,
  "stuck_recovery_ticks": 70,
  "combat_hold_ticks": 35,
  "health_threshold": 80,
  "armor_threshold": 5,
  "ammo_threshold": 25,
  "scan_interval": 140
}
CHALLENGER = dict(ELITE, health_threshold=60, scan_interval=200)

# Chart colors. Blue and orange are categorical slots 1 and 2, validated together.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
MEASURED_COLOR = "#2a78d6"
BOUND_COLOR = "#eb6834"


def benchmark_workers() -> None:
    """Times one GA generation (elite and challenger, EVAL_RUNS episodes each) at every
    worker count, checks that every worker count gave identical results, then reports
    and plots how the speedup scales."""
    runs = {}
    for workers in WORKER_COUNTS:
        runs[workers] = _run_worker_count(workers)
    _check_results_match(runs)
    summary = _analyze(runs)
    _plot(summary)


def _run_worker_count(workers: int) -> list:
    """Run several generations with a pool of this many workers.
    The warmup generations are not returned."""
    ga = GeneticAlgo(workers=workers, py_seed_base=PY_SEED_BASE)
    runs = []
    try:
        for i in range(WARMUP_GENERATIONS + GENERATIONS_PER_COUNT):
            # Sampling starts a thread, and the workers fork on the first generation.
            # Forking with another thread running can deadlock, so warmups are not sampled.
            run = _run_one_generation(ga, sample=i >= WARMUP_GENERATIONS)
            print(f"workers={workers} generation={i} time={run['time']:.2f}s fitness={run['fitness']}")
            runs.append(run)
    finally:
        ga._pool.shutdown() # Release the workers before the next pool is created.
    return runs[WARMUP_GENERATIONS:]


def _run_one_generation(ga: GeneticAlgo, sample: bool) -> dict:
    """Run one generation in a temporary directory. Returns the time, the results,
    the ticks and file hash of every episode, and the CPU and memory samples."""
    samples = []
    stop = threading.Event()
    sampler = threading.Thread(target=_sample_resources, args=(stop, samples))
    with tempfile.TemporaryDirectory() as d:
        if sample:
            sampler.start()
        start_time = time.perf_counter()
        fitness = ga.evaluate_genomes(ELITE, CHALLENGER, LEVEL, GEN, GAME_SEED, d)
        end_time = time.perf_counter()
        if sample:
            stop.set()
            sampler.join()
        ticks, hashes = _read_episode_files(d)
    return {
        "time": end_time - start_time,
        "fitness": fitness,
        "ticks": ticks,
        "hashes": hashes,
        "samples": samples,
    }


def _sample_resources(stop: threading.Event, samples: list) -> None:
    """Every SAMPLE_SECONDS, record system CPU use, memory used by this process and all
    its children (the workers and the VizDoom engines), and memory still available."""
    parent = psutil.Process()
    psutil.cpu_percent() # The first call only sets the reference point.
    while not stop.wait(SAMPLE_SECONDS):
        rss = 0
        try:
            processes = [parent] + parent.children(recursive=True)
        except psutil.Error:
            continue
        for process in processes:
            try:
                rss += process.memory_info().rss
            except psutil.Error:
                pass # The process exited between listing and reading.
        samples.append({
            "cpu_percent": psutil.cpu_percent(), # Across all logical CPUs, 100 is every thread busy.
            "rss_mb": rss / MB,
            "available_mb": psutil.virtual_memory().available / MB,
        })


def _read_episode_files(out_dir: str) -> tuple[dict, dict]:
    """Ticks and file hash of every episode's action file, by file name."""
    ticks = {}
    hashes = {}
    for path in sorted(Path(out_dir).rglob("*_actions.csv")):
        data = path.read_bytes()
        hashes[path.name] = hashlib.sha256(data).hexdigest()
        ticks[path.name] = data.count(b"\n") - 1 # One row per tick, minus the header.
    return ticks, hashes


def _check_results_match(runs: dict) -> None:
    """
    Checks that every run, at every worker count, gave the same fitness and
    the same action files as the first run. Catches results that depend on the
    number of workers.
    """
    first = runs[WORKER_COUNTS[0]][0]
    error_msg: str = ""
    for workers, worker_runs in runs.items():
        for run in worker_runs:
            if run["fitness"] != first["fitness"]:
                error_msg += f"Fitness with {workers} workers differs from {WORKER_COUNTS[0]} worker. "
            if run["hashes"] != first["hashes"]:
                error_msg += f"Action files with {workers} workers differ from {WORKER_COUNTS[0]} worker. "
    if error_msg:
        raise ValueError(error_msg)
    print("All results match across worker counts")


def _analyze(runs: dict) -> list:
    """
    Report time performance and the numbers that explain it. Returns one summary per worker count.

    How to read the table:
      speedup     one worker's median time divided by this row's median time.
      bound       the best speedup the episodes' lengths allow. Episodes run in the order
                  they are submitted, each on the first free worker, and take time in
                  proportion to their ticks. Once the longest episode is running alone,
                  more workers cannot help.
      measured below bound  means the workers slowed each other down. Look at the CPU
                  columns for shared cores or hyperthreads, and at the memory columns.
      avg busy    logical CPUs in use on average. Compare with the physical core count.
      peak RSS    memory of the main process, workers and VizDoom engines together.
      min free    the lowest memory left on the whole machine during a generation.
    """
    one_worker_time = statistics.median(run["time"] for run in runs[1])
    ticks = runs[1][0]["ticks"]
    names = sorted(ticks, key=lambda name: (not name.startswith("elite"), name)) # Submission order.
    seconds_per_tick = one_worker_time / sum(ticks.values())
    durations = [ticks[name] * seconds_per_tick for name in names]

    physical = psutil.cpu_count(logical=False)
    logical = psutil.cpu_count()
    print("\n")
    print(f"Machine: {physical} physical cores, {logical} logical CPUs, {psutil.virtual_memory().total / MB:.0f} MB memory")
    print(f"Tasks per generation: {TASKS_PER_GENERATION}")
    print(f"Episode ticks: {sorted(ticks.values())}")
    print(f"Longest episode is {max(ticks.values()) / sum(ticks.values()):.1%} of all ticks,"
          f" so no worker count can give more than {sum(ticks.values()) / max(ticks.values()):.2f}x")

    print("\n")
    print(f"{'workers':>7} {'median s':>9} {'stddev':>7} {'speedup':>8} {'effic':>6} {'bound':>6}"
          f" {'avg CPU%':>9} {'avg busy':>9} {'peak RSS MB':>12} {'min free MB':>12}")
    summary = []
    for workers in WORKER_COUNTS:
        times = [run["time"] for run in runs[workers]]
        samples = [sample for run in runs[workers] for sample in run["samples"]]
        median = statistics.median(times)
        speedup = one_worker_time / median
        avg_cpu = statistics.mean(sample["cpu_percent"] for sample in samples)
        row = {
            "workers": workers,
            "median": median,
            "speedup": speedup,
            "speedup_low": one_worker_time / max(times),
            "speedup_high": one_worker_time / min(times),
            "bound": one_worker_time / _makespan(durations, workers),
        }
        summary.append(row)
        print(f"{workers:>7} {median:>9.2f} {statistics.stdev(times):>7.2f} {speedup:>7.2f}x {speedup / workers:>6.0%}"
              f" {row['bound']:>5.2f}x {avg_cpu:>9.0f} {avg_cpu / 100 * logical:>9.1f}"
              f" {max(sample['rss_mb'] for sample in samples):>12.0f}"
              f" {min(sample['available_mb'] for sample in samples):>12.0f}")
    return summary


def _makespan(durations: list, workers: int) -> float:
    """Time for this many workers to finish the tasks. Each task, in order, starts on the first free worker."""
    free_at = [0.0] * workers
    for duration in durations:
        earliest = heapq.heappop(free_at)
        heapq.heappush(free_at, earliest + duration)
    return max(free_at)


def _plot(summary: list) -> None:
    """Chart of speedup by worker count. Saved to CHART_PATH and shown."""
    workers = [row["workers"] for row in summary]
    measured = [row["speedup"] for row in summary]
    error = [
        [row["speedup"] - row["speedup_low"] for row in summary],
        [row["speedup_high"] - row["speedup"] for row in summary],
    ]
    physical = psutil.cpu_count(logical=False)

    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.plot([0, max(workers)], [0, max(workers)], color=INK_SECONDARY, linestyle="--", linewidth=1.5,
            label="Ideal (speedup = workers)")
    ax.plot(workers, [row["bound"] for row in summary], color=BOUND_COLOR, linewidth=2, marker="o",
            markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, label="Bound from episode lengths")
    ax.errorbar(workers, measured, yerr=error, color=MEASURED_COLOR, linewidth=2, marker="o",
                markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, capsize=4, label="Measured")

    for x, label in ((physical, f"{physical} cores"), (TASKS_PER_GENERATION, f"{TASKS_PER_GENERATION} tasks")):
        ax.axvline(x, color=GRID, linewidth=1.5, zorder=0)
        ax.text(x + 0.1, 0.3, label, rotation=90, color=INK_SECONDARY, fontsize=9, va="bottom")

    ax.set_xlim(0, max(workers) + 0.5)
    ax.set_ylim(0, max(workers) + 0.5)
    ax.set_xticks(workers)
    ax.set_xlabel("Workers", color=INK)
    ax.set_ylabel("Speedup over 1 worker", color=INK)
    ax.set_title("GA generation speedup by worker count", color=INK, loc="left", fontsize=13)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_SECONDARY)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.legend(loc="upper left", frameon=False, labelcolor=INK)
    fig.text(0.01, 0.01,
             f"{physical} physical cores / {psutil.cpu_count()} threads, {TASKS_PER_GENERATION} tasks = episodes per generation, "
             f"seed {GAME_SEED}, median of {GENERATIONS_PER_COUNT} generations, bars show fastest to slowest",
             color=INK_SECONDARY, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    Path(CHART_PATH).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=150, facecolor=SURFACE)
    print(f"Chart saved to {CHART_PATH}")
    plt.show()


if __name__ == "__main__":
    benchmark_workers()
