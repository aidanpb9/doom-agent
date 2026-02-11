"""
Updated testing framework that integrates directly with DoomAgent.
Runs multiple episodes and collects performance metrics.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt

# Import the actual agent
from agent import DoomAgent

logger = logging.getLogger(__name__)


class DoomTester:
    """Testing framework for evaluating DoomAgent performance across multiple episodes."""
    
    def __init__(self, wad_path="wads/doom1.wad", map_name="E1M1"):
        """
        Initialize the tester.
        
        Args:
            wad_path: Path to the Doom WAD file
            map_name: Map to test on (e.g., "E1M1", "E1M2")
        """
        self.wad_path = wad_path
        self.map_name = map_name
        self.results = []
        
        # Create logs directory if it doesn't exist
        Path("logs").mkdir(exist_ok=True)
    
    def run_episode(self, episode_num, episode_timeout=60, fast_mode=True):
        """
        Run a single episode and collect metrics.
        
        Args:
            episode_num: Episode number for tracking
            episode_timeout: Time limit in seconds
            fast_mode: Run headless for speed
            
        Returns:
            dict: Episode statistics
        """
        logger.info(f"Starting episode {episode_num} on {self.map_name}")
        
        # Create agent for this episode
        agent = DoomAgent(
            wad_path=self.wad_path,
            config_path="vizdoom_config.cfg",
            episode_timeout=episode_timeout,
            fast_mode=fast_mode,
            map_name=self.map_name,
            save_debug=False,  # Disable debug saves during testing
        )
        
        try:
            agent.initialize_game()
            stats = agent.run_episode()
            
            # Add episode number to stats
            stats['episode'] = episode_num
            stats['map'] = self.map_name
            
            return stats
            
        except Exception as e:
            logger.error(f"Episode {episode_num} failed: {e}")
            return {
                'episode': episode_num,
                'map': self.map_name,
                'kills': 0,
                'episode_reward': 0,
                'actions_taken': 0,
                'episode_time': 0,
                'end_reason': f'error:{str(e)}',
                'health_lost': 0,
                'ammo_used': 0,
            }
        finally:
            agent.close()
    
    def run_test_suite(self, num_episodes=20, episode_timeout=60, fast_mode=True):
        """
        Run multiple episodes and collect results.
        
        Args:
            num_episodes: Number of episodes to run
            episode_timeout: Time limit per episode in seconds
            fast_mode: Run headless for speed
        """
        print(f"\n{'='*60}")
        print(f"Testing {self.map_name} for {num_episodes} episodes")
        print(f"Episode timeout: {episode_timeout}s, Fast mode: {fast_mode}")
        print(f"{'='*60}\n")
        
        for i in range(num_episodes):
            result = self.run_episode(i+1, episode_timeout, fast_mode)
            self.results.append(result)
            
            # Print progress
            print(f"Episode {i+1}/{num_episodes}: "
                  f"Reward={result['episode_reward']:.0f}, "
                  f"Kills={result['kills']}, "
                  f"Time={result['episode_time']:.1f}s, "
                  f"End={result['end_reason']}")
        
        print(f"\n{'='*60}")
        print("Test suite complete!")
        print(f"{'='*60}\n")
        
        # Save and analyze results
        self.save_results()
        self.generate_graphs()
        self.print_summary()
    
    def save_results(self):
        """Save test results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Path("logs") / f"test_results_{self.map_name}_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'map': self.map_name,
                'wad_path': self.wad_path,
                'num_episodes': len(self.results),
                'timestamp': timestamp,
                'results': self.results
            }, f, indent=2)
        
        print(f"Results saved to {filename}")
    
    def generate_graphs(self):
        """Generate performance visualization."""
        if not self.results:
            print("No results to graph")
            return
        
        episodes = [r['episode'] for r in self.results]
        rewards = [r['episode_reward'] for r in self.results]
        kills = [r['kills'] for r in self.results]
        times = [r['episode_time'] for r in self.results]
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Agent Performance on {self.map_name}', fontsize=16)
        
        # Reward over episodes
        ax1.plot(episodes, rewards, marker='o', color='blue', alpha=0.7)
        ax1.axhline(y=0, color='r', linestyle='--', alpha=0.3)
        ax1.set_xlabel('Episode')
        ax1.set_ylabel('Episode Reward')
        ax1.set_title('Reward Over Time')
        ax1.grid(True, alpha=0.3)
        
        # Kills over episodes
        ax2.plot(episodes, kills, marker='o', color='green', alpha=0.7)
        ax2.set_xlabel('Episode')
        ax2.set_ylabel('Kills')
        ax2.set_title('Kills Over Time')
        ax2.grid(True, alpha=0.3)
        
        # Survival time
        ax3.plot(episodes, times, marker='o', color='orange', alpha=0.7)
        ax3.set_xlabel('Episode')
        ax3.set_ylabel('Survival Time (seconds)')
        ax3.set_title('Survival Time')
        ax3.grid(True, alpha=0.3)
        
        # End reasons pie chart
        end_reasons = {}
        for r in self.results:
            reason = r.get('end_reason', 'unknown')
            end_reasons[reason] = end_reasons.get(reason, 0) + 1
        
        ax4.pie(end_reasons.values(), labels=end_reasons.keys(), autopct='%1.1f%%')
        ax4.set_title('Episode End Reasons')
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Path("logs") / f'performance_{self.map_name}_{timestamp}.png'
        plt.savefig(filename, dpi=150)
        print(f"Graph saved to {filename}")
        plt.close()
    
    def print_summary(self):
        """Print summary statistics."""
        if not self.results:
            print("No results to summarize")
            return
        
        rewards = [r['episode_reward'] for r in self.results]
        kills = [r['kills'] for r in self.results]
        times = [r['episode_time'] for r in self.results]
        health_lost = [r.get('health_lost', 0) for r in self.results]
        ammo_used = [r.get('ammo_used', 0) for r in self.results]
        
        # Count end reasons
        end_reasons = {}
        for r in self.results:
            reason = r.get('end_reason', 'unknown')
            end_reasons[reason] = end_reasons.get(reason, 0) + 1
        
        # Count exits (successful completions)
        exits = end_reasons.get('exit', 0)
        
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        print(f"Map: {self.map_name}")
        print(f"Episodes run: {len(self.results)}")
        print(f"\nCompletion:")
        print(f"  Successful exits: {exits} ({100*exits/len(self.results):.1f}%)")
        print(f"\nReward:")
        print(f"  Average: {sum(rewards)/len(rewards):.1f}")
        print(f"  Best: {max(rewards):.1f}")
        print(f"  Worst: {min(rewards):.1f}")
        print(f"\nCombat:")
        print(f"  Total kills: {sum(kills)}")
        print(f"  Average kills/episode: {sum(kills)/len(kills):.1f}")
        print(f"  Best kills: {max(kills)}")
        print(f"\nSurvival:")
        print(f"  Average time: {sum(times)/len(times):.1f}s")
        print(f"  Longest: {max(times):.1f}s")
        print(f"\nResources:")
        print(f"  Average health lost: {sum(health_lost)/len(health_lost):.1f}")
        print(f"  Average ammo used: {sum(ammo_used)/len(ammo_used):.1f}")
        print(f"\nEnd Reasons:")
        for reason, count in sorted(end_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count} ({100*count/len(self.results):.1f}%)")
        print("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Test on E1M1
    print("\nRunning test suite on E1M1...")
    tester = DoomTester(wad_path="wads/doom1.wad", map_name="E1M1")
    tester.run_test_suite(num_episodes=5, episode_timeout=60, fast_mode=True)
    
    # Optionally test on E1M2
    # print("\nRunning test suite on E1M2...")
    # tester2 = DoomTester(wad_path="wads/doom1.wad", map_name="E1M2")
    # tester2.run_test_suite(num_episodes=5, episode_timeout=60, fast_mode=True)
