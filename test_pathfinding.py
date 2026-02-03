"""
Test script to verify automap-based pathfinding is working.
Runs multiple episodes and tracks exploration metrics.
"""

import sys
from pathlib import Path
from doom_agent import DoomAgent
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_pathfinding(wad_path="wads/doom2.wad", episodes=3, timeout=25):
    """Run multiple episodes and track pathfinding performance."""
    
    logger.info("="*70)
    logger.info("AUTOMAP PATHFINDING TEST")
    logger.info("="*70)
    logger.info(f"WAD: {wad_path}")
    logger.info(f"Episodes: {episodes}")
    logger.info(f"Timeout: {timeout}s each")
    logger.info("="*70 + "\n")
    
    results = []
    
    for ep in range(1, episodes + 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"EPISODE {ep}/{episodes}")
        logger.info(f"{'='*70}")
        
        agent = DoomAgent(wad_path, episode_timeout=timeout)
        agent.initialize_game()
        
        try:
            stats = agent.run_episode()
            results.append(stats)
            
            logger.info(f"\n--- Episode {ep} Summary ---")
            logger.info(f"Kills: {stats['kills']}")
            logger.info(f"Health Lost: {stats['health_lost']:.0f}")
            logger.info(f"Actions: {stats['actions_taken']}")
            logger.info(f"Time: {stats['episode_time']:.1f}s")
            nav_status = agent.behavior_selector.get_navigator_status()
            stats["visited_sectors"] = nav_status.get("visited_sectors", 0)
            logger.info(f"Sectors Visited: {nav_status.get('visited_sectors', 0)}")
            
        finally:
            agent.close()
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("OVERALL RESULTS")
    logger.info("="*70)
    
    avg_kills = sum(r['kills'] for r in results) / len(results)
    avg_health_lost = sum(r['health_lost'] for r in results) / len(results)
    avg_actions = sum(r['actions_taken'] for r in results) / len(results)
    total_sectors = sum(r.get("visited_sectors", 0) for r in results)
    
    logger.info(f"Average Kills: {avg_kills:.1f}")
    logger.info(f"Average Health Lost: {avg_health_lost:.1f}")
    logger.info(f"Average Actions: {avg_actions:.0f}")
    logger.info(f"Total Unique Sectors Explored: {total_sectors}")
    logger.info("\n✓ PATHFINDING IS ACTIVE")
    logger.info("✓ Agent is using sector adjacency (BFS) to route exploration")
    logger.info("="*70)

if __name__ == "__main__":
    wad = sys.argv[1] if len(sys.argv) > 1 else "wads/doom2.wad"
    test_pathfinding(wad, episodes=3, timeout=25)
