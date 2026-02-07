"""
Single entry point for running the Doom agent.
This script manages logging setup and runs the agent with specified parameters.
"""

import sys
import logging
import multiprocessing as mp
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


def _run_episode(
    wad_file: str,
    seconds: int,
    fast_mode: bool,
    step_delay: float,
    action_frame_skip: int,
):
    agent = DoomAgent(
        wad_file,
        episode_timeout=seconds,
        fast_mode=fast_mode,
        step_delay=step_delay,
        action_frame_skip=action_frame_skip,
    )
    try:
        agent.initialize_game()
        stats = agent.run_episode()
        results_file = Path("logs") / "last_run.json"
        with open(results_file, "w") as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Results saved to {results_file}")
    finally:
        agent.close()
        logger.info("Agent closed successfully")


def main():
    """Main entry point for the agent."""
    wad_file = "wads/doom1.wad"
    seconds = 30
    fast_mode = "--fast" in sys.argv
    slow_mode = "--slow" in sys.argv
    watchdog_enabled = "--no-watchdog" not in sys.argv
    if "--fast" in sys.argv:
        sys.argv.remove("--fast")
    if "--slow" in sys.argv:
        sys.argv.remove("--slow")
    if "--no-watchdog" in sys.argv:
        sys.argv.remove("--no-watchdog")

    # Visible + faster defaults
    # Small delay keeps the VizDoom window responsive on some Windows setups.
    step_delay = 0.01
    action_frame_skip = 6
    if slow_mode:
        step_delay = 0.05
        action_frame_skip = 4
        fast_mode = False

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
    
    if fast_mode:
        logger.info("Fast mode: headless render + reduced buffers")
    else:
        logger.info(
            f"Screen mode: frame_skip={action_frame_skip} step_delay={step_delay:.2f}s"
        )
    if not watchdog_enabled:
        _run_episode(wad_file, seconds, fast_mode, step_delay, action_frame_skip)
        return

    # Watchdog: run in a subprocess and hard-stop if the engine hangs.
    timeout = max(seconds + 5, 10)
    proc = mp.Process(
        target=_run_episode,
        args=(wad_file, seconds, fast_mode, step_delay, action_frame_skip),
        daemon=True,
    )
    proc.start()
    proc.join(timeout=timeout)
    if proc.is_alive():
        logger.error("Watchdog timeout after %ss; terminating VizDoom.", timeout)
        proc.terminate()
        proc.join(timeout=5)
        logger.error("Run terminated by watchdog. Try --no-watchdog to disable.")


if __name__ == "__main__":
    main()
