"""Genome representation and fitness function for the GA.

compute_fitness() is the single source of truth for fitness. It's used by
the GA runner (evolve mode) and main.py (run mode). See genetic_algo_design.md
for fitness function details.
"""


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