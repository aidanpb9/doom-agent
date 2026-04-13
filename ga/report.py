"""Post-run analysis for a completed or in-progress evolution run.

Usage:
    python ga/report.py output/evolve/YYYY-MM-DD_HHMM/

Reads evolution_history.json from the given run folder and produces:
    1. Fitness over generations   — elite + challenger on same plot
    2. Parameter evolution        — one line per evolvable parameter
    3. Win rate over generations  — challenger win rate by generation window
    4. Fitness stddev             — standard deviation of elite fitness across gens
    5. Per-episode fitness dist   — variance across EVAL_RUNS for a given genome
    6. Check if multiprocessing slowed down per gen
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) #ensure project root is on path

from ga.genetic_algo import PARAM_RANGES
import json
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from datetime import datetime as dt


def load_history(run_dir: Path) -> dict:
    """Load evolution_history.json from the run directory."""
    path = run_dir / "evolution_history.json"
    return json.loads(path.read_text())


def plot_fitness(history: dict, out_dir: Path) -> None:
    """1. Elite and challenger fitness over generations, one plot per level."""
    for level, gens in history.items():
        gen_nums = sorted(int(g) for g in gens if g != "timeout")
        elite_fit = [gens[str(g)]["elite_fitness"] for g in gen_nums]
        challenger_fit = [gens[str(g)]["challenger_fitness"] for g in gen_nums]

        fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="#1b1b1b")
        ax.set_facecolor("#1b1b1b")

        ax.plot(gen_nums, elite_fit, label="Elite", color="#0cd5d2", linewidth=1.7)
        ax.plot(gen_nums, challenger_fit, label="Challenger", color="#ffd700", linewidth=1.5, alpha=0.7)

        ax.set_title(f"{level} Fitness over Generations", fontsize=14, fontweight="bold", color="white")
        ax.set_xlabel("Generation", fontsize=12, color="white")
        ax.set_ylabel("Fitness", fontsize=12, color="white")
        ax.tick_params(colors="white")
        ax.grid(color="#3b3b3b", linestyle=":")
        ax.legend(facecolor="#2b2b2b", edgecolor="white", labelcolor="white")

        fig.savefig(out_dir / f"{level}_fitness.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def plot_parameters(history: dict, out_dir: Path) -> None:
    """2. Each evolvable parameter normalized to 0-1 across generations, one plot per level.
    Normalization uses PARAM_RANGES so all params are on the same scale.
    A flat line means the param converged; a varying line means it kept exploring."""
    colors = cm.viridis(np.linspace(0, 1, len(PARAM_RANGES)))

    for level, gens in history.items():
        gen_nums = sorted(int(g) for g in gens if g != "timeout")

        fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="#1b1b1b")
        ax.set_facecolor("#1b1b1b")

        for (param, (lo, hi)), color in zip(PARAM_RANGES.items(), colors):
            raw = [gens[str(g)]["elite_genome"][param] for g in gen_nums]
            normalized = [(v - lo) / (hi - lo) for v in raw]
            ax.plot(gen_nums, normalized, label=param, color=color, linewidth=1.5)

        ax.set_title(f"{level} Parameter Evolution (normalized)", fontsize=14, fontweight="bold", color="white")
        ax.set_xlabel("Generation", fontsize=12, color="white")
        ax.set_ylabel("Value (0 = min, 1 = max of range)", fontsize=12, color="white")
        ax.tick_params(colors="white")
        ax.grid(color="#3b3b3b", linestyle=":")
        ax.legend(facecolor="#2b2b2b", edgecolor="white", labelcolor="white",
                  loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

        fig.savefig(out_dir / f"{level}_parameters.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def plot_win_rate(history: dict, out_dir: Path) -> None:
    """3. Challenger win rate as a rolling average across generations, one plot per level.
    High win rate early = exploring. Low win rate late = elite has converged."""
    window = 10

    for level, gens in history.items():
        gen_nums = sorted(int(g) for g in gens if g != "timeout")
        challenger_won = [1 if gens[str(g)]["winner"] == "challenger" else 0 for g in gen_nums]

        #rolling average, skip gens before window fills
        rolling_rate = [
            sum(challenger_won[i:i + window]) / window
            for i in range(len(challenger_won) - window + 1)
        ]
        rolling_gens = gen_nums[window - 1:]

        fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="#1b1b1b")
        ax.set_facecolor("#1b1b1b")

        ax.plot(rolling_gens, rolling_rate, color="#ff4500", linewidth=1.7, label=f"Win rate ({window}-gen rolling avg)")
        ax.axhline(0.5, color="#3b3b3b", linestyle=":", linewidth=1)

        ax.set_title(f"{level} Challenger Win Rate", fontsize=14, fontweight="bold", color="white")
        ax.set_xlabel("Generation", fontsize=12, color="white")
        ax.set_ylabel("Challenger Win Rate", fontsize=12, color="white")
        ax.set_ylim(0, 1)
        ax.tick_params(colors="white")
        ax.grid(color="#3b3b3b", linestyle=":")
        ax.legend(facecolor="#2b2b2b", edgecolor="white", labelcolor="white")

        fig.savefig(out_dir / f"{level}_win_rate.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def plot_fitness_stddev(history: dict, out_dir: Path) -> None:
    """4. Rolling stddev of elite fitness across generations, one plot per level.
    High stddev = fitness is unstable. Flattening stddev = convergence."""
    window = 10

    for level, gens in history.items():
        gen_nums = sorted(int(g) for g in gens if g != "timeout")
        elite_fit = [gens[str(g)]["elite_fitness"] for g in gen_nums]

        overall_std = float(np.std(elite_fit)) or 1.0
        rolling_std = [
            float(np.std(elite_fit[i:i + window])) / overall_std
            for i in range(len(elite_fit) - window + 1)
        ]
        rolling_gens = gen_nums[window - 1:]

        fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="#1b1b1b")
        ax.set_facecolor("#1b1b1b")

        ax.plot(rolling_gens, rolling_std, color="#1e90ff", linewidth=1.7, label=f"Stddev ({window}-gen rolling)")

        ax.set_title(f"{level} Elite Fitness Stddev", fontsize=14, fontweight="bold", color="white")
        ax.set_xlabel("Generation", fontsize=12, color="white")
        ax.set_ylabel("Sigma (σ)", fontsize=12, color="white")
        ax.tick_params(colors="white")
        ax.grid(color="#3b3b3b", linestyle=":")
        ax.legend(facecolor="#2b2b2b", edgecolor="white", labelcolor="white")

        fig.savefig(out_dir / f"{level}_fitness_stddev.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def plot_episode_variance(run_dir: Path, history: dict, out_dir: Path) -> None:
    """5. Individual episode fitness dots overlaid on elite average line, one plot per level.
    Shows both the convergence trend and the run-to-run variance within each gen.
    Wide scatter = high Python RNG variance. Tight scatter = stable genome."""
    for level, gens in history.items():
        gen_nums = sorted(int(g) for g in gens if g != "timeout")
        elite_avg = [gens[str(g)]["elite_fitness"] for g in gen_nums]

        #collect individual episode fitnesses per gen from summary JSONs
        scatter_x, scatter_y = [], []
        for g in gen_nums:
            gen_dir = run_dir / level / f"gen_{g:04d}"
            for summary in gen_dir.glob("elite_ep_*_summary.json"):
                data = json.loads(summary.read_text())
                scatter_x.append(g)
                scatter_y.append(data["fitness"])

        fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="#1b1b1b")
        ax.set_facecolor("#1b1b1b")

        ax.scatter(scatter_x, scatter_y, color="#ffd700", s=12, alpha=0.3, label="Individual episodes")
        ax.plot(gen_nums, elite_avg, color="#0cd5d2", linewidth=1.7, label="Elite average")

        ax.set_title(f"{level} Episode Fitness Variance", fontsize=14, fontweight="bold", color="white")
        ax.set_xlabel("Generation", fontsize=12, color="white")
        ax.set_ylabel("Fitness", fontsize=12, color="white")
        ax.tick_params(colors="white")
        ax.grid(color="#3b3b3b", linestyle=":")
        ax.legend(facecolor="#2b2b2b", edgecolor="white", labelcolor="white")

        fig.savefig(out_dir / f"{level}_episode_variance.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def plot_gen_timing(history: dict, out_dir: Path) -> None:
    """6. Time per generation derived from timestamps, one plot per level.
    Flat line = consistent gen time. Rising line = multiprocessing slowing down over time.
    Also shows genome episode completion time."""
    for level, gens in history.items():
        gen_nums = sorted(int(g) for g in gens if g not in ("timeout",) and "timestamp" in gens[str(g)])
        if len(gen_nums) < 2:
            continue

        timestamps = [dt.fromisoformat(gens[str(g)]["timestamp"]) for g in gen_nums]
        durations = [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]
        duration_gens = gen_nums[1:]

        fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="#1b1b1b")
        ax.set_facecolor("#1b1b1b")

        ax.plot(duration_gens, durations, color="#32cd32", linewidth=1.5, alpha=0.7, label="Seconds per gen")
        ax.axhline(np.mean(durations), color="#ff4500", linewidth=1, linestyle="--",
                   label=f"Mean: {np.mean(durations):.1f}s")

        ax.set_title(f"{level} Generation Timing", fontsize=14, fontweight="bold", color="white")
        ax.set_xlabel("Generation", fontsize=12, color="white")
        ax.set_ylabel("Seconds", fontsize=12, color="white")
        ax.tick_params(colors="white")
        ax.grid(color="#3b3b3b", linestyle=":")
        ax.legend(facecolor="#2b2b2b", edgecolor="white", labelcolor="white")

        fig.savefig(out_dir / f"{level}_gen_timing.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def run(run_dir: Path) -> None:
    history = load_history(run_dir)
    for level, gens in history.items():
        out_dir = run_dir / level / "report"
        out_dir.mkdir(parents=True, exist_ok=True)
        level_history = {level: gens}
        plot_fitness(level_history, out_dir)
        plot_parameters(level_history, out_dir)
        plot_win_rate(level_history, out_dir)
        plot_fitness_stddev(level_history, out_dir)
        plot_episode_variance(run_dir, level_history, out_dir)
        plot_gen_timing(level_history, out_dir)
        print(f"Report saved to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 ga/report.py output/evolve/YYYY-MM-DD_HHMM/")
        sys.exit(1)
    run(Path(sys.argv[1]))