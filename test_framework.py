import vizdoom as vzd #type: ignore
import matplotlib.pyplot as plt
import json
from datetime import datetime
import os

class DoomTester:
    def __init__(self, agent_module):
        """
        agent_module: the execution algorithm (teammate's code)
        Should have a get_action(state) method that returns action array
        """
        self.agent = agent_module
        self.results = []
    
    def run_episode(self, scenario, episode_num):
        """Run single episode and collect metrics"""
        game = vzd.DoomGame()
        game.load_config(os.path.join(vzd.scenarios_path, f"{scenario}.cfg"))
        game.set_window_visible(False)
        game.init()
        
        game.new_episode()
        start_time = game.get_episode_time()
        total_reward = 0
        kills = 0
        completed = False
        
        while not game.is_episode_finished():
            state = game.get_state()
            action = self.agent.get_action(state)  # teammate's agent
            reward = game.make_action(action)
            total_reward += reward
            
            # Track kills if available
            if len(state.game_variables) > 2:
                kills = state.game_variables[2]
        
        # Check completion before closing
        if not game.is_episode_finished():
            completed = True
        
        end_time = game.get_episode_time()
        survival_time = max(0, end_time - start_time)
        
        game.close()
        
        return {
            'episode': episode_num,
            'scenario': scenario,
            'score': total_reward,
            'survival_time': survival_time,
            'kills': kills,
            'completed': completed
        }
    
    def run_test_suite(self, scenario, num_episodes=20):
        """Run multiple episodes and collect results"""
        print(f"Testing {scenario} for {num_episodes} episodes...")
        
        for i in range(num_episodes):
            result = self.run_episode(scenario, i+1)
            self.results.append(result)
            print(f"Episode {i+1}: Score={result['score']:.0f}, Time={result['survival_time']}, Kills={result['kills']}")
        
        self.save_results()
        self.generate_graphs()
        self.print_summary()
    
    def save_results(self):
        """Save results to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to {filename}")
    
    def generate_graphs(self):
        """Generate performance visualization"""
        episodes = [r['episode'] for r in self.results]
        scores = [r['score'] for r in self.results]
        times = [r['survival_time'] for r in self.results]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # Score over time
        ax1.plot(episodes, scores, marker='o')
        ax1.axhline(y=0, color='r', linestyle='--', alpha=0.3)
        ax1.set_xlabel('Episode')
        ax1.set_ylabel('Score')
        ax1.set_title('Agent Score Over Time')
        ax1.grid(True, alpha=0.3)
        
        # Survival time
        ax2.plot(episodes, times, marker='o', color='green')
        ax2.set_xlabel('Episode')
        ax2.set_ylabel('Survival Time (tics)')
        ax2.set_title('Agent Survival Time')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'performance_{timestamp}.png'
        plt.savefig(filename, dpi=150)
        print(f"Graph saved to {filename}")
        plt.close()
    
    def print_summary(self):
        """Print summary statistics"""
        if not self.results:
            return
        
        scores = [r['score'] for r in self.results]
        times = [r['survival_time'] for r in self.results]
        kills = [r['kills'] for r in self.results]
        
        print("\n" + "="*50)
        print("PERFORMANCE SUMMARY")
        print("="*50)
        print(f"Episodes run: {len(self.results)}")
        print(f"Average score: {sum(scores)/len(scores):.1f}")
        print(f"Best score: {max(scores):.1f}")
        print(f"Worst score: {min(scores):.1f}")
        print(f"Average survival time: {sum(times)/len(times):.1f} tics")
        print(f"Total kills: {sum(kills)}")
        print("="*50 + "\n")

# Example usage (update this after Thursday meeting):
if __name__ == "__main__":
    # Placeholder agent for testing
    class DummyAgent:
        def get_action(self, state):
            import random
            # Random action for basic scenario (turn left, turn right, shoot)
            return [0, 0, random.choice([0,1]), random.choice([0,1]), 0, 0, random.choice([0,1])]
    
    # Test the framework
    tester = DoomTester(DummyAgent())
    tester.run_test_suite('basic', num_episodes=5)