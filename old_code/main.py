#!/usr/bin/env python3
"""
DoomSat - Main entry point

Usage:
    python main.py run      # single episode, window visible
    python main.py evolve   # headless GA evolution
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.constants import DEFAULT_WAD_PATH, DEFAULT_MAP_NAME, DEFAULT_EPISODE_TIMEOUT


def setup_logging(verbose=False):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"doomsat_{timestamp}.log"
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def cmd_run(args):
    """Single episode with window visible."""
    from agent.agent import DoomAgent

    logger = setup_logging(args.verbose)
    logger.info("DoomSat - Run Mode")

    agent = DoomAgent(
        wad_path=DEFAULT_WAD_PATH,
        map_name=DEFAULT_MAP_NAME,
        episode_timeout=DEFAULT_EPISODE_TIMEOUT,
        fast_mode=False,
    )

    try:
        agent.initialize_game()
        stats = agent.run_episode()
        logger.info("End reason: %s | Kills: %s | Time: %.1fs",
                    stats['end_reason'], stats['kills'], stats['episode_time'])
        return 0 if stats['end_reason'] == 'exit' else 1
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1
    finally:
        agent.close()


def cmd_evolve(args):
    """Headless GA evolution."""
    from evolution.genetic_algo import TwoAgentGA

    logger = setup_logging(args.verbose)
    logger.info("DoomSat - Evolve Mode")

    ga = TwoAgentGA(
        wad_path=DEFAULT_WAD_PATH,
        map_name=DEFAULT_MAP_NAME,
        episode_timeout=DEFAULT_EPISODE_TIMEOUT,
        fast_mode=True,
    )

    ga.run(num_generations=args.generations)
    return 0


def main():
    parser = argparse.ArgumentParser(description='DoomSat - Doom AI Agent')
    parser.add_argument('-v', '--verbose', action='store_true', help='Debug logging')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    subparsers.add_parser('run', help='Run a single episode').set_defaults(func=cmd_run)

    evolve_parser = subparsers.add_parser('evolve', help='Run genetic algorithm')
    evolve_parser.add_argument('--generations', type=int, default=20,
                               help='Number of generations (default: 20)')
    evolve_parser.set_defaults(func=cmd_evolve)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130


if __name__ == '__main__':
    sys.exit(main())
