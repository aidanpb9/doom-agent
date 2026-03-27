#!/usr/bin/env python3
"""
DoomSat - Main entry point

Usage:
    python main.py run      # single episode, window visible
    python main.py evolve   # headless GA evolution (not yet implemented)
"""

import sys
import argparse
import logging
import vizdoom as vzd
from pathlib import Path
from datetime import datetime
from core.execution.agent import Agent


#Ensure project root is on the path so imports work from any working directory
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def setup_logging(verbose=False):
    """Configure logging to both file (logs/) and console.
    Uses DEBUG level if verbose, INFO otherwise."""

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
    logger = setup_logging(args.verbose)
    logger.info("DoomSat - Run Mode")

    #Create VizDoom game object and Agent, then run one episode
    game = vzd.DoomGame()
    agent = Agent(game)

    try:
        agent.initialize_game(headless=args.hl)
        stats = agent.run_episode(params={})
        logger.info("Stats: %s", stats)
        return 0
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1
    finally:
        agent.close()  #always runs, even on exception


def main():
    parser = argparse.ArgumentParser(description='DoomSat - Doom AI Agent')
    parser.add_argument('-v', '--verbose', action='store_true', help='Debug logging')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    run_parser = subparsers.add_parser('run', help='Run a single episode')
    run_parser.add_argument('-hl', action='store_true', help='Headless mode, high tickrate')
    run_parser.set_defaults(func=cmd_run)
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130


if __name__ == '__main__':
    sys.exit(main())
