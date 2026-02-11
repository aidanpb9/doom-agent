"""
Validation script to compare baseline vs evolved parameters.
Loads GA output and runs head-to-head comparison.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

from agent import DoomAgent
from evolution.genetic_algo import AgentGenome

logger = logging.getLogger(__name__)


def apply_genome_to_agent(agent: DoomAgent, genome: AgentGenome):
    """Apply genome parameters to agent's behavior systems."""
    behavior = agent.behavior_selector
    behavior.combat_burst = genome.combat_burst
    behavior.combat_cooldown_duration = genome.combat_cooldown_duration
    behavior.combat_strafe_switch = genome.combat_strafe_switch
    behavior.combat_max_active = genome.combat_max_active
    
    nav = behavior.sector_navigator
    nav.node_visit_radius = genome.node_visit_radius
    nav.stuck_radius = genome.stuck_radius
    nav.stuck_time_s = genome.stuck_time_s
    nav.end_subroute_block_dist = genome.end_subroute_block_dist


def run_agent_with_genome(
    genome: AgentGenome,
    wad_path: str,
    map_name: str,
    num_episodes: int = 5,
    episode_timeout: int = 60
):
    """
    Run multiple episodes with a specific genome configuration.
    
    Returns:
        List of episode stats
    """
    results = []
    
    for episode in range(num_episodes):
        logger.info(f"Running episode {episode + 1}/{num_episodes} with {genome.agent_id} params...")
        
        agent = DoomAgent(
            wad_path=wad_path,
            episode_timeout=episode_timeout,
            fast_mode=True,
            map_name=map_name,
            save_debug=False,
        )
        
        # Apply genome parameters
        apply_genome_to_agent(agent, genome)
        
        try:
            agent.initialize_game()
            stats = agent.run_episode()
            stats['genome_id'] = genome.agent_id
            results.append(stats)
            
            logger.info(f"  Result: {stats['end_reason']}, "
                       f"kills={stats['kills']}, "
                       f"health_lost={stats.get('health_lost', 0):.0f}")
        except Exception as e:
            logger.error(f"Episode failed: {e}")
            results.append({
                'end_reason': 'error',
                'kills': 0,
                'health_lost': 100,
                'episode_time': 0,
                'genome_id': genome.agent_id
            })
        finally:
            agent.close()
    
    return results


def calculate_metrics(results):
    """Calculate aggregate metrics from episode results."""
    total = len(results)
    
    # Count outcomes
    exits = sum(1 for r in results if r['end_reason'] == 'exit')
    deaths = sum(1 for r in results if r['end_reason'] == 'player_dead')
    timeouts = sum(1 for r in results if r['end_reason'] in ['timeout', 'max_steps'])
    
    # Average stats
    avg_kills = sum(r.get('kills', 0) for r in results) / total
    avg_health_lost = sum(r.get('health_lost', 0) for r in results) / total
    avg_time = sum(r.get('episode_time', 0) for r in results) / total
    
    return {
        'total_episodes': total,
        'exits': exits,
        'deaths': deaths,
        'timeouts': timeouts,
        'success_rate': exits / total * 100,
        'death_rate': deaths / total * 100,
        'timeout_rate': timeouts / total * 100,
        'avg_kills': avg_kills,
        'avg_health_lost': avg_health_lost,
        'avg_time': avg_time,
    }


def print_comparison(baseline_metrics, evolved_metrics):
    """Print side-by-side comparison."""
    print("\n" + "="*70)
    print("BASELINE vs EVOLVED PARAMETERS COMPARISON")
    print("="*70)
    
    print(f"\n{'Metric':<25} {'Baseline':<20} {'Evolved':<20} {'Change':<15}")
    print("-"*70)
    
    # Success rate
    b_success = baseline_metrics['success_rate']
    e_success = evolved_metrics['success_rate']
    delta_success = e_success - b_success
    print(f"{'Success Rate':<25} {b_success:>6.1f}% {'':<13} {e_success:>6.1f}% {'':<13} {delta_success:+.1f}%")
    
    # Death rate
    b_death = baseline_metrics['death_rate']
    e_death = evolved_metrics['death_rate']
    delta_death = e_death - b_death
    print(f"{'Death Rate':<25} {b_death:>6.1f}% {'':<13} {e_death:>6.1f}% {'':<13} {delta_death:+.1f}%")
    
    # Timeout rate
    b_timeout = baseline_metrics['timeout_rate']
    e_timeout = evolved_metrics['timeout_rate']
    delta_timeout = e_timeout - b_timeout
    print(f"{'Timeout Rate':<25} {b_timeout:>6.1f}% {'':<13} {e_timeout:>6.1f}% {'':<13} {delta_timeout:+.1f}%")
    
    print("-"*70)
    
    # Average kills
    b_kills = baseline_metrics['avg_kills']
    e_kills = evolved_metrics['avg_kills']
    delta_kills = e_kills - b_kills
    print(f"{'Avg Kills':<25} {b_kills:>6.1f} {'':<14} {e_kills:>6.1f} {'':<14} {delta_kills:+.1f}")
    
    # Health lost
    b_health = baseline_metrics['avg_health_lost']
    e_health = evolved_metrics['avg_health_lost']
    delta_health = e_health - b_health
    print(f"{'Avg Health Lost':<25} {b_health:>6.1f} {'':<14} {e_health:>6.1f} {'':<14} {delta_health:+.1f}")
    
    # Survival time
    b_time = baseline_metrics['avg_time']
    e_time = evolved_metrics['avg_time']
    delta_time = e_time - b_time
    print(f"{'Avg Survival Time (s)':<25} {b_time:>6.1f} {'':<14} {e_time:>6.1f} {'':<14} {delta_time:+.1f}")
    
    print("="*70)
    
    # Overall verdict
    print("\nVERDICT:")
    improvements = 0
    degradations = 0
    
    if delta_success > 0:
        print(f"  ✓ Success rate improved by {delta_success:.1f}%")
        improvements += 1
    elif delta_success < 0:
        print(f"  ✗ Success rate decreased by {abs(delta_success):.1f}%")
        degradations += 1
    
    if delta_death < 0:
        print(f"  ✓ Death rate reduced by {abs(delta_death):.1f}%")
        improvements += 1
    elif delta_death > 0:
        print(f"  ✗ Death rate increased by {delta_death:.1f}%")
        degradations += 1
    
    if delta_kills > 0:
        print(f"  ✓ Kills increased by {delta_kills:.1f}")
        improvements += 1
    elif delta_kills < 0:
        print(f"  ✗ Kills decreased by {abs(delta_kills):.1f}")
        degradations += 1
    
    if delta_health < 0:
        print(f"  ✓ Health preservation improved (lost {abs(delta_health):.1f} less)")
        improvements += 1
    elif delta_health > 0:
        print(f"  ✗ Health preservation worse (lost {delta_health:.1f} more)")
        degradations += 1
    
    print(f"\nScore: {improvements} improvements, {degradations} degradations")
    
    if improvements > degradations:
        print("🎉 EVOLVED PARAMETERS ARE BETTER!")
    elif improvements < degradations:
        print("⚠️  Baseline parameters performed better")
    else:
        print("→ Results are mixed/inconclusive")
    
    print("="*70 + "\n")


def main():
    """Run validation comparison."""
    
    # Configuration
    wad_path = "wads/doom1.wad"
    map_name = "E1M1"
    num_episodes = 5
    episode_timeout = 120
    
    print("\n" + "="*70)
    print("PARAMETER VALIDATION TEST")
    print("="*70)
    print(f"Map: {map_name}")
    print(f"Episodes per config: {num_episodes}")
    print("="*70 + "\n")
    
    # Load evolved parameters from GA output
    ga_history_file = Path("logs/genetic_algo/evolution_history.json")
    
    if not ga_history_file.exists():
        print(f"ERROR: GA results not found at {ga_history_file}")
        print("Run genetic_algo.py first to generate evolved parameters")
        return
    
    with open(ga_history_file, 'r') as f:
        ga_data = json.load(f)
    
    evolved_genome = AgentGenome.from_dict(ga_data['elite_genome'])
    
    print("Evolved parameters loaded:")
    print(f"  Combat: burst={evolved_genome.combat_burst}, "
          f"cooldown={evolved_genome.combat_cooldown_duration}, "
          f"strafe={evolved_genome.combat_strafe_switch}")
    print(f"  Navigation: visit_radius={evolved_genome.node_visit_radius:.1f}, "
          f"stuck_time={evolved_genome.stuck_time_s:.1f}s\n")
    
    # Create baseline genome (default parameters)
    baseline_genome = AgentGenome(
        combat_burst=8,
        combat_cooldown_duration=20,
        combat_strafe_switch=8,
        combat_max_active=120,
        node_visit_radius=64.0,
        stuck_radius=96.0,
        stuck_time_s=5.0,
        end_subroute_block_dist=1536.0,
        agent_id="Baseline",
        generation=0
    )
    
    print("Baseline parameters (defaults):")
    print(f"  Combat: burst={baseline_genome.combat_burst}, "
          f"cooldown={baseline_genome.combat_cooldown_duration}, "
          f"strafe={baseline_genome.combat_strafe_switch}")
    print(f"  Navigation: visit_radius={baseline_genome.node_visit_radius:.1f}, "
          f"stuck_time={baseline_genome.stuck_time_s:.1f}s\n")
    
    # Run baseline
    print("-"*70)
    print("TESTING BASELINE PARAMETERS")
    print("-"*70)
    baseline_results = run_agent_with_genome(
        baseline_genome, wad_path, map_name, num_episodes, episode_timeout
    )
    
    # Run evolved
    print("\n" + "-"*70)
    print("TESTING EVOLVED PARAMETERS")
    print("-"*70)
    evolved_results = run_agent_with_genome(
        evolved_genome, wad_path, map_name, num_episodes
    )
    
    # Calculate metrics
    baseline_metrics = calculate_metrics(baseline_results)
    evolved_metrics = calculate_metrics(evolved_results)
    
    # Print comparison
    print_comparison(baseline_metrics, evolved_metrics)
    
    # Save results
    results_file = Path("logs") / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'map': map_name,
            'episodes_per_config': num_episodes,
            'baseline_genome': baseline_genome.to_dict(),
            'evolved_genome': evolved_genome.to_dict(),
            'baseline_results': baseline_results,
            'evolved_results': evolved_results,
            'baseline_metrics': baseline_metrics,
            'evolved_metrics': evolved_metrics,
        }, f, indent=2)
    
    print(f"Detailed results saved to {results_file}")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    main()
