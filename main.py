#!/usr/bin/env python3
"""
DoomSat - Main entry point
Spacecraft flight software and Doom payload development

Usage:
    python main.py run --map E1M1 --timeout 60
    python main.py test --map E1M1 --episodes 10
    python main.py evolve --map E1M1 --generations 20
    python main.py validate --map E1M1 --episodes 5
    python main.py show-params
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import DEFAULT_WAD_PATH, DEFAULT_MAP_NAME


def setup_logging(verbose=False, log_file=None):
    """Configure logging for the application."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    if log_file is None:
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
    """Run a single agent episode."""
    from agent.agent import DoomAgent
    
    logger = setup_logging(args.verbose)
    logger.info("="*60)
    logger.info("DoomSat Agent - Run Mode")
    logger.info("="*60)
    logger.info(f"WAD: {args.wad}")
    logger.info(f"Map: {args.map}")
    logger.info(f"Timeout: {args.timeout}s")
    logger.info(f"Fast mode: {args.fast}")
    logger.info(f"No enemies: {args.no_enemies}")
    logger.info("="*60)
    
    agent = DoomAgent(
        wad_path=args.wad,
        episode_timeout=args.timeout,
        fast_mode=args.fast,
        map_name=args.map,
        save_debug=not args.no_debug,
        no_enemies=args.no_enemies,
    )
    
    try:
        agent.initialize_game()
        stats = agent.run_episode()
        
        logger.info("\n" + "="*60)
        logger.info("Episode Complete")
        logger.info("="*60)
        logger.info(f"End reason: {stats['end_reason']}")
        logger.info(f"Kills: {stats['kills']}")
        logger.info(f"Health lost: {stats.get('health_lost', 0):.0f}")
        logger.info(f"Reward: {stats['episode_reward']:.1f}")
        logger.info(f"Time: {stats['episode_time']:.1f}s")
        logger.info("="*60)
        
        return 0 if stats['end_reason'] == 'exit' else 1
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    finally:
        agent.close()


def cmd_test(args):
    """Run multiple test episodes."""
    from testing.test_framework import DoomTester
    
    logger = setup_logging(args.verbose)
    logger.info("="*60)
    logger.info("DoomSat Agent - Test Mode")
    logger.info("="*60)
    
    tester = DoomTester(wad_path=args.wad, map_name=args.map)
    tester.run_test_suite(
        num_episodes=args.episodes,
        episode_timeout=args.timeout,
        fast_mode=args.fast,
        no_enemies=args.no_enemies,
    )
    
    return 0


def cmd_evolve(args):
    """Run genetic algorithm evolution."""
    from evolution.genetic_algo import TwoAgentGA
    
    logger = setup_logging(args.verbose)
    logger.info("="*60)
    logger.info("DoomSat Agent - Evolution Mode")
    logger.info("="*60)
    
    ga = TwoAgentGA(
        wad_path=args.wad,
        map_name=args.map,
        episode_timeout=args.timeout,
        fast_mode=args.fast,
        no_enemies=args.no_enemies,
    )
    
    final_elite = ga.run(num_generations=args.generations)
    
    logger.info("\n" + "="*60)
    logger.info("Evolution Complete!")
    logger.info(f"Final elite parameters saved to logs/genetic_algo/")
    logger.info("="*60)
    
    return 0


def cmd_validate(args):
    """Validate baseline vs evolved parameters."""
    from testing.validate_params import main as validate_main
    
    logger = setup_logging(args.verbose)
    logger.info("="*60)
    logger.info("DoomSat Agent - Validation Mode")
    logger.info("="*60)
    
    # Override sys.argv for validate_params
    old_argv = sys.argv
    sys.argv = ['validate_params.py']
    
    try:
        validate_main()
        return 0
    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        return 1
    finally:
        sys.argv = old_argv


def cmd_show_params(args):
    """Display current configuration parameters."""
    from config import combat, navigation, defaults
    
    print("\n" + "="*60)
    print("DoomSat Configuration Parameters")
    print("="*60)
    
    print("\n" + "-"*60)
    print("COMBAT PARAMETERS")
    print("-"*60)
    print(f"Combat burst:         {combat.COMBAT_BURST_DEFAULT} " +
          f"(range: {combat.COMBAT_BURST_MIN}-{combat.COMBAT_BURST_MAX})")
    print(f"Combat cooldown:      {combat.COMBAT_COOLDOWN_DEFAULT} ticks " +
          f"(range: {combat.COMBAT_COOLDOWN_MIN}-{combat.COMBAT_COOLDOWN_MAX})")
    print(f"Combat rearm:         {combat.COMBAT_REARM_DEFAULT} ticks")
    print(f"Strafe switch:        {combat.COMBAT_STRAFE_SWITCH_DEFAULT} ticks " +
          f"(range: {combat.COMBAT_STRAFE_SWITCH_MIN}-{combat.COMBAT_STRAFE_SWITCH_MAX})")
    print(f"Max active:           {combat.COMBAT_MAX_ACTIVE_DEFAULT} ticks " +
          f"(range: {combat.COMBAT_MAX_ACTIVE_MIN}-{combat.COMBAT_MAX_ACTIVE_MAX})")
    
    print("\n" + "-"*60)
    print("NAVIGATION PARAMETERS")
    print("-"*60)
    print(f"Node visit radius:    {navigation.NAV_NODE_VISIT_RADIUS_DEFAULT} " +
          f"(range: {navigation.NAV_NODE_VISIT_RADIUS_MIN}-{navigation.NAV_NODE_VISIT_RADIUS_MAX})")
    print(f"Stuck radius:         {navigation.NAV_STUCK_RADIUS_DEFAULT} " +
          f"(range: {navigation.NAV_STUCK_RADIUS_MIN}-{navigation.NAV_STUCK_RADIUS_MAX})")
    print(f"Stuck time:           {navigation.NAV_STUCK_TIME_DEFAULT}s " +
          f"(range: {navigation.NAV_STUCK_TIME_MIN}-{navigation.NAV_STUCK_TIME_MAX})")
    print(f"Subroute block dist:  {navigation.NAV_END_SUBROUTE_BLOCK_DIST_DEFAULT} " +
          f"(range: {navigation.NAV_END_SUBROUTE_BLOCK_DIST_MIN}-{navigation.NAV_END_SUBROUTE_BLOCK_DIST_MAX})")
    
    print("\n" + "-"*60)
    print("GAME DEFAULTS")
    print("-"*60)
    print(f"Default WAD:          {defaults.DEFAULT_WAD_PATH}")
    print(f"Default map:          {defaults.DEFAULT_MAP_NAME}")
    print(f"Episode timeout:      {defaults.DEFAULT_EPISODE_TIMEOUT}s")
    print(f"Ticrate:              {defaults.DEFAULT_TICRATE}")
    
    print("\n" + "="*60 + "\n")
    
    return 0


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='DoomSat - Doom AI Agent with Navigation and Combat',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a single episode on E1M1
  %(prog)s run --map E1M1 --timeout 60
  
  # Run in fast mode (headless)
  %(prog)s run --map E1M1 --fast
  
  # Test with 20 episodes
  %(prog)s test --map E1M1 --episodes 20
  
  # Evolve parameters for 50 generations
  %(prog)s evolve --map E1M1 --generations 50 --fast
  
  # Validate evolved vs baseline parameters
  %(prog)s validate --map E1M1 --episodes 10
  
  # Show current parameters
  %(prog)s show-params
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose debug logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a single episode')
    run_parser.add_argument('--wad', default=DEFAULT_WAD_PATH,
                           help=f'Path to WAD file (default: {DEFAULT_WAD_PATH})')
    run_parser.add_argument('--map', default=DEFAULT_MAP_NAME,
                           help=f'Map name (default: {DEFAULT_MAP_NAME})')
    run_parser.add_argument('--timeout', type=int, default=60,
                           help='Episode timeout in seconds (default: 60)')
    run_parser.add_argument('--fast', action='store_true',
                           help='Run in fast mode (headless, reduced logging)')
    run_parser.add_argument('--no-debug', action='store_true',
                           help='Disable debug output (no automap/nav images)')
    run_parser.add_argument('--no-enemies', action='store_true',
                           help='Disable monster spawning (-nomonsters)')
    run_parser.set_defaults(func=cmd_run)
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run multiple test episodes')
    test_parser.add_argument('--wad', default=DEFAULT_WAD_PATH,
                            help=f'Path to WAD file (default: {DEFAULT_WAD_PATH})')
    test_parser.add_argument('--map', default=DEFAULT_MAP_NAME,
                            help=f'Map name (default: {DEFAULT_MAP_NAME})')
    test_parser.add_argument('--episodes', type=int, default=10,
                            help='Number of episodes to run (default: 10)')
    test_parser.add_argument('--timeout', type=int, default=60,
                            help='Episode timeout in seconds (default: 60)')
    test_parser.add_argument('--fast', action='store_true',
                            help='Run in fast mode (headless)')
    test_parser.add_argument('--no-enemies', action='store_true',
                            help='Disable monster spawning (-nomonsters)')
    test_parser.set_defaults(func=cmd_test)
    
    # Evolve command
    evolve_parser = subparsers.add_parser('evolve', help='Run genetic algorithm')
    evolve_parser.add_argument('--wad', default=DEFAULT_WAD_PATH,
                              help=f'Path to WAD file (default: {DEFAULT_WAD_PATH})')
    evolve_parser.add_argument('--map', default=DEFAULT_MAP_NAME,
                              help=f'Map name (default: {DEFAULT_MAP_NAME})')
    evolve_parser.add_argument('--generations', type=int, default=20,
                              help='Number of generations (default: 20)')
    evolve_parser.add_argument('--timeout', type=int, default=120,
                              help='Episode timeout in seconds (default: 120)')
    evolve_parser.add_argument('--fast', action='store_true', default=True,
                              help='Run in fast mode (default: True)')
    evolve_parser.add_argument('--no-enemies', action='store_true',
                              help='Disable monster spawning (-nomonsters)')
    evolve_parser.set_defaults(func=cmd_evolve)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate',
                                           help='Validate baseline vs evolved parameters')
    validate_parser.add_argument('--wad', default=DEFAULT_WAD_PATH,
                                help=f'Path to WAD file (default: {DEFAULT_WAD_PATH})')
    validate_parser.add_argument('--map', default=DEFAULT_MAP_NAME,
                                help=f'Map name (default: {DEFAULT_MAP_NAME})')
    validate_parser.add_argument('--episodes', type=int, default=5,
                                help='Episodes per configuration (default: 5)')
    validate_parser.set_defaults(func=cmd_validate)
    
    # Show-params command
    show_parser = subparsers.add_parser('show-params',
                                       help='Display current configuration parameters')
    show_parser.set_defaults(func=cmd_show_params)
    
    # Parse and execute
    args = parser.parse_args()
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
