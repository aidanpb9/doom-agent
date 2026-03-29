#!/usr/bin/env python3
"""
DoomSat - Main entry point

Usage:
    python main.py run                        # single episode, window visible
    python main.py run --map E1M2             # run on a specific map
    python main.py run --headless             # run without window (high tickrate)
    python main.py run -v                     # verbose/debug logging
    python main.py evolve                     # GA evolution
"""

import sys
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime
from core.execution.agent import Agent
from ga.genetic_algo import compute_fitness
from config.constants import RUN_DIR, EVOLVE_DIR


#Ensure project root is on the path so imports work from any working directory
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def setup_logging(mode: str, verbose=False) -> logging.Logger:
    """Configure logging for the given run mode.

    Console: INFO (or DEBUG if --verbose) in all modes.
    File: ERROR only, evolve mode only — run mode is interactive so console is sufficient.
      evolve mode: logs/doomsat_evolve_TIMESTAMP.log (one file per GA run, kept for analysis)
    """
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_level = logging.DEBUG if verbose else logging.INFO

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(fmt)

    handlers = [console_handler]

    if mode == "evolve":
        #Errors to file — evolve runs unattended so console output may not be monitored
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_handler = logging.FileHandler(log_dir / f"doomsat_evolve_{timestamp}.log", mode="a")
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(fmt)
        handlers.append(file_handler)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for h in handlers:
        root.addHandler(h)

    return logging.getLogger(__name__)


def cmd_run(args):
    """Single episode with window visible."""
    logger = setup_logging("run", args.verbose)
    logger.info("DoomSat - Run Mode")

    #Wipe previous run output so output/run/ always reflects the latest run only
    if Path(RUN_DIR).exists():
        shutil.rmtree(RUN_DIR)

    agent = Agent()
    try:
        agent.initialize_game(headless=args.headless, map_name=args.map)
        stats = agent.run_episode()
        stats["fitness"] = compute_fitness(stats)
        agent.telemetry_writer.finalize_episode(stats)
        logger.info("Stats: %s", stats)
        return 0
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1
    finally:
        agent.close()  #always runs, even on exception


def cmd_evolve(args):
    """GA evolution, main delegates fully to GeneticAlgo."""
    logger = setup_logging("evolve", args.verbose)
    logger.info("DoomSat - Evolve Mode")

    #Wipe previous evolve output so output/evolve/ always reflects the latest run only
    if Path(EVOLVE_DIR).exists():
        shutil.rmtree(EVOLVE_DIR)

    from ga.genetic_algo import GeneticAlgo
    ga = GeneticAlgo()
    try:
        ga.evolve()
        return 0
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1


def main():
    parser = argparse.ArgumentParser(description='DoomSat - Doom AI Agent')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    run_parser = subparsers.add_parser('run', help='Run a single episode')
    run_parser.add_argument('-v', '--verbose', action='store_true', help='Debug logging')
    run_parser.add_argument('--headless', action='store_true', help='Headless mode, high tickrate')
    run_parser.add_argument('--map', default='E1M1', help='Map to load (default: E1M1)')
    run_parser.set_defaults(func=cmd_run)

    evolve_parser = subparsers.add_parser('evolve', help='Run GA evolution')
    evolve_parser.add_argument('-v', '--verbose', action='store_true', help='Debug logging')
    evolve_parser.set_defaults(func=cmd_evolve)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130


if __name__ == '__main__':
    sys.exit(main())
