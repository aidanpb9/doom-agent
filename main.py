#!/usr/bin/env python3
"""
DoomSat - Main entry point

Usage:
    python main.py run                        # single episode, window visible
    python main.py run --map E1M2             # run on a specific map
    python main.py run --headless             # run without window (high tickrate)
    python main.py evolve                     # GA evolution

Hand-crafted genome testing:
    Edit ga/test_genome.json with custom param values, then run main.py run.
    If the file exists it is loaded and passed to run_episode(genome=...).
    If it does not exist, the agent runs with hardcoded constant defaults.
    Lets you observe specific parameter combinations in windowed mode without
    touching evolved outputs in output/evolve/.
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from core.execution.agent import Agent
from ga.genetic_algo import compute_fitness
from config.constants import RUN_DIR


#Ensure project root is on the path so imports work from any working directory
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def cmd_run(args):
    """Single episode with window visible."""
    print("DoomSat - Run Mode")

    #Wipe previous run output so output/run/ always reflects the latest run only
    if Path(RUN_DIR).exists():
        shutil.rmtree(RUN_DIR)

    #Load hand-crafted genome if present, otherwise run with constant defaults
    genome = None
    test_genome_path = ROOT_DIR / "ga" / "test_genome.json"
    if test_genome_path.exists():
        genome = json.loads(test_genome_path.read_text())
        print(f"Loaded test genome: {genome}")
    else:
        print("No ga/test_genome.json found, running with defaults")

    agent = Agent()
    try:
        agent.initialize_game(headless=args.headless, map_name=args.map)
        stats = agent.run_episode(genome=genome)
        stats["fitness"] = compute_fitness(stats)
        agent.telemetry_writer.finalize_episode(stats)
        print("Stats:", stats)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        agent.close()  #always runs, even on exception


def cmd_evolve(args):
    """GA evolution, main delegates fully to GeneticAlgo."""
    print("DoomSat - Evolve Mode")

    from ga.genetic_algo import GeneticAlgo
    ga = GeneticAlgo()
    try:
        ga.evolve()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='DoomSat - Doom AI Agent')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    run_parser = subparsers.add_parser('run', help='Run a single episode')
    run_parser.add_argument('--headless', action='store_true', help='Headless mode, high tickrate')
    run_parser.add_argument('--map', default='E1M1', help='Map to load (default: E1M1)')
    run_parser.set_defaults(func=cmd_run)

    evolve_parser = subparsers.add_parser('evolve', help='Run GA evolution')
    evolve_parser.set_defaults(func=cmd_evolve)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130


if __name__ == '__main__':
    sys.exit(main())