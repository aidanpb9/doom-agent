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

Not yet implemented.
"""