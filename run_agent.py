"""
Single entry point for running the Doom agent.
This script manages logging setup and runs the agent with specified parameters.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
import json

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"doom_agent_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Import agent
from agent.agent import DoomAgent


def main():
    """Main entry point for the agent."""
    wad_file = "wads/doom1.wad"
    seconds = 10

    if len(sys.argv) > 1:
        wad_file = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            seconds = int(sys.argv[2])
        except ValueError:
            seconds = 10
    
    if not Path(wad_file).exists():
        logger.error(f"WAD file not found: {wad_file}")
        sys.exit(1)
    
    logger.info(f"Starting Doom Agent with WAD: {wad_file}")
    logger.info(f"Episode timeout: {seconds} seconds")
    
    agent = DoomAgent(wad_file, episode_timeout=seconds)
    
    try:
        agent.initialize_game()
        stats = agent.run_episode()
        
        # Save results
        results_file = log_dir / "last_run.json"
        with open(results_file, "w") as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        
    finally:
        agent.close()
        logger.info("Agent closed successfully")


if __name__ == "__main__":
    main()
