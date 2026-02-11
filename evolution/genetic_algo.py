"""
2-Agent Micro Genetic Algorithm (µGA) for DoomSat
Implements head-to-head competition between elite and challenger agents.
Designed to match CubeSat mission architecture with radiation-style bit-flip mutations.
"""

import json
import random
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
from dataclasses import dataclass, asdict
from copy import deepcopy

from agent import DoomAgent

logger = logging.getLogger(__name__)


@dataclass
class AgentGenome:
    """
    Parameter set representing an agent's behavioral configuration.
    Simulates the linear policy controller that would be mutated by cosmic radiation.
    """
    
    # Combat parameters
    combat_burst: int = 8                    # Shots per burst (4-16)
    combat_cooldown_duration: int = 20       # Ticks between bursts (10-40)
    combat_strafe_switch: int = 8            # Ticks before changing strafe direction (4-16)
    combat_max_active: int = 120             # Max ticks in combat before disengaging (60-180)
    
    # Navigation parameters
    node_visit_radius: float = 64.0          # Distance to consider waypoint reached (32-128)
    stuck_radius: float = 96.0               # Movement threshold for stuck detection (48-192)
    stuck_time_s: float = 5.0                # Seconds before declaring stuck (2-10)
    end_subroute_block_dist: float = 1536.0  # Distance to end subroute (768-3072)
    
    # Agent metadata
    agent_id: str = "A"                      # "A" (elite) or "B" (challenger)
    generation: int = 0                      # Which generation this genome is from
    parent_id: str = None                    # ID of parent genome (for lineage tracking)
    
    def to_dict(self) -> Dict:
        """Convert genome to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentGenome':
        """Create genome from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
    
    @classmethod
    def random(cls, agent_id: str = "A", generation: int = 0) -> 'AgentGenome':
        """Generate random parameter set within valid ranges."""
        return cls(
            combat_burst=random.randint(4, 16),
            combat_cooldown_duration=random.randint(10, 40),
            combat_strafe_switch=random.randint(4, 16),
            combat_max_active=random.randint(60, 180),
            node_visit_radius=random.uniform(32.0, 128.0),
            stuck_radius=random.uniform(48.0, 192.0),
            stuck_time_s=random.uniform(2.0, 10.0),
            end_subroute_block_dist=random.uniform(768.0, 3072.0),
            agent_id=agent_id,
            generation=generation,
            parent_id=None,
        )
    
    def mutate(self, agent_id: str = "B", generation: int = 0) -> 'AgentGenome':
        """
        Create mutated copy simulating cosmic radiation bit flips.
        Each parameter has independent chance of mutation.
        
        Args:
            agent_id: ID for the mutated agent
            generation: Generation number
            
        Returns:
            New mutated genome
        """
        mutated = AgentGenome(**self.to_dict())
        mutated.agent_id = agent_id
        mutated.generation = generation
        mutated.parent_id = self.agent_id
        
        # Mutation probability per parameter (simulates radiation hit rate)
        mutation_rate = 0.25  # 25% chance each parameter gets hit
        
        # Integer parameters - bit flip simulation (add/subtract random delta)
        if random.random() < mutation_rate:
            delta = random.choice([-4, -3, -2, -1, 1, 2, 3, 4])
            mutated.combat_burst = max(4, min(16, self.combat_burst + delta))
        
        if random.random() < mutation_rate:
            delta = random.choice([-10, -8, -5, -3, 3, 5, 8, 10])
            mutated.combat_cooldown_duration = max(10, min(40, 
                self.combat_cooldown_duration + delta))
        
        if random.random() < mutation_rate:
            delta = random.choice([-4, -3, -2, -1, 1, 2, 3, 4])
            mutated.combat_strafe_switch = max(4, min(16, 
                self.combat_strafe_switch + delta))
        
        if random.random() < mutation_rate:
            delta = random.choice([-40, -30, -20, 20, 30, 40])
            mutated.combat_max_active = max(60, min(180, 
                self.combat_max_active + delta))
        
        # Float parameters - random perturbation (simulates floating point bit corruption)
        if random.random() < mutation_rate:
            perturbation = random.uniform(0.6, 1.4)  # ±40% change
            mutated.node_visit_radius = max(32.0, min(128.0,
                self.node_visit_radius * perturbation))
        
        if random.random() < mutation_rate:
            perturbation = random.uniform(0.6, 1.4)
            mutated.stuck_radius = max(48.0, min(192.0,
                self.stuck_radius * perturbation))
        
        if random.random() < mutation_rate:
            perturbation = random.uniform(0.6, 1.4)
            mutated.stuck_time_s = max(2.0, min(10.0,
                self.stuck_time_s * perturbation))
        
        if random.random() < mutation_rate:
            perturbation = random.uniform(0.6, 1.4)
            mutated.end_subroute_block_dist = max(768.0, min(3072.0,
                self.end_subroute_block_dist * perturbation))
        
        return mutated


@dataclass
class CompetitionResult:
    """Results from a head-to-head competition between two agents."""
    
    generation: int
    agent_a_stats: Dict
    agent_b_stats: Dict
    winner_id: str
    reason: str  # Why this agent won
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TwoAgentGA:
    """
    Two-Agent Micro Genetic Algorithm for parameter evolution.
    Implements elite vs challenger head-to-head competition.
    """
    
    def __init__(
        self,
        wad_path: str = "wads/doom1.wad",
        map_name: str = "E1M1",
        episode_timeout: int = 120,
        fast_mode: bool = True,
    ):
        """
        Initialize the 2-agent GA.
        
        Args:
            wad_path: Path to Doom WAD file
            map_name: Map to evolve on (e.g., "E1M1")
            episode_timeout: Timeout per episode in seconds
            fast_mode: Run headless for speed
        """
        self.wad_path = wad_path
        self.map_name = map_name
        self.episode_timeout = episode_timeout
        self.fast_mode = fast_mode
        
        # Agent population (exactly 2)
        self.agent_a: AgentGenome = None  # Elite
        self.agent_b: AgentGenome = None  # Challenger
        
        self.generation = 0
        self.elite_lineage = []  # Track elite genome history
        
        # Competition history
        self.competition_history = []
        
        # Create results directory
        self.results_dir = Path("logs/genetic_algo")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"2-Agent GA initialized for {map_name}")
        logger.info("Population: Elite (A) vs Challenger (B)")
    
    def initialize(self):
        """Initialize both agents with random parameters."""
        logger.info("\n" + "="*60)
        logger.info("Initializing random agent population")
        logger.info("="*60)
        
        # Both agents start random for generation 0
        self.agent_a = AgentGenome.random(agent_id="A", generation=0)
        self.agent_b = AgentGenome.random(agent_id="B", generation=0)
        
        logger.info("Agent A (Elite) initialized with random parameters:")
        self._log_genome(self.agent_a)
        
        logger.info("\nAgent B (Challenger) initialized with random parameters:")
        self._log_genome(self.agent_b)
        
        logger.info("="*60 + "\n")
    
    def _log_genome(self, genome: AgentGenome):
        """Log genome parameters."""
        logger.info(f"  Agent ID: {genome.agent_id}")
        logger.info(f"  Generation: {genome.generation}")
        logger.info(f"  Combat: burst={genome.combat_burst}, "
                   f"cooldown={genome.combat_cooldown_duration}, "
                   f"strafe={genome.combat_strafe_switch}, "
                   f"max_active={genome.combat_max_active}")
        logger.info(f"  Navigation: visit_radius={genome.node_visit_radius:.1f}, "
                   f"stuck_radius={genome.stuck_radius:.1f}, "
                   f"stuck_time={genome.stuck_time_s:.1f}s, "
                   f"subroute_dist={genome.end_subroute_block_dist:.1f}")
    
    def evaluate_agent(self, genome: AgentGenome) -> Dict:
        """
        Evaluate an agent by running one episode.
        
        Args:
            genome: Parameter set to evaluate
            
        Returns:
            Episode statistics
        """
        logger.info(f"Evaluating Agent {genome.agent_id}...")
        
        # Create agent with these parameters
        agent = DoomAgent(
            wad_path=self.wad_path,
            episode_timeout=self.episode_timeout,
            fast_mode=self.fast_mode,
            map_name=self.map_name,
            save_debug=False,
        )
        
        # Apply genome parameters
        self._apply_genome_to_agent(agent, genome)
        
        try:
            agent.initialize_game()
            stats = agent.run_episode()
            
            logger.info(f"  Agent {genome.agent_id} results: "
                       f"end_reason={stats['end_reason']}, "
                       f"kills={stats['kills']}, "
                       f"health_lost={stats.get('health_lost', 0):.0f}, "
                       f"time={stats['episode_time']:.1f}s")
            
            return stats
            
        except Exception as e:
            logger.error(f"Agent {genome.agent_id} evaluation error: {e}")
            return {
                'end_reason': 'error',
                'kills': 0,
                'health_lost': 100,
                'episode_time': 0,
                'episode_reward': -10000,
            }
        finally:
            agent.close()
    
    def _apply_genome_to_agent(self, agent: DoomAgent, genome: AgentGenome):
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
    
    def determine_winner(
        self, 
        stats_a: Dict, 
        stats_b: Dict
    ) -> Tuple[str, str]:
        """
        Determine winner using mission-defined fitness criteria.
        
        Priority (lexicographic):
        1. Level completion (exit > anything else)
        2. Ending health (higher = better)
        3. Kills (higher = better)
        4. Survival time (longer = better)
        
        Args:
            stats_a: Agent A statistics
            stats_b: Agent B statistics
            
        Returns:
            Tuple of (winner_id, reason)
        """
        end_a = stats_a.get('end_reason', 'unknown')
        end_b = stats_b.get('end_reason', 'unknown')
        
        # Primary: Level completion
        exit_a = (end_a == 'exit')
        exit_b = (end_b == 'exit')
        
        if exit_a and not exit_b:
            return ("A", "Agent A completed level, B did not")
        if exit_b and not exit_a:
            return ("B", "Agent B completed level, A did not")
        
        # Secondary: Ending health (lower health_lost = better)
        health_lost_a = stats_a.get('health_lost', 100)
        health_lost_b = stats_b.get('health_lost', 100)
        
        health_diff = abs(health_lost_a - health_lost_b)
        if health_diff > 5:  # Significant difference
            if health_lost_a < health_lost_b:
                return ("A", f"Agent A preserved health better ({health_lost_a:.0f} vs {health_lost_b:.0f} lost)")
            else:
                return ("B", f"Agent B preserved health better ({health_lost_b:.0f} vs {health_lost_a:.0f} lost)")
        
        # Tertiary: Kills
        kills_a = stats_a.get('kills', 0)
        kills_b = stats_b.get('kills', 0)
        
        if kills_a != kills_b:
            if kills_a > kills_b:
                return ("A", f"Agent A got more kills ({kills_a} vs {kills_b})")
            else:
                return ("B", f"Agent B got more kills ({kills_b} vs {kills_a})")
        
        # Quaternary: Survival time
        time_a = stats_a.get('episode_time', 0)
        time_b = stats_b.get('episode_time', 0)
        
        if abs(time_a - time_b) > 1.0:  # Significant difference
            if time_a > time_b:
                return ("A", f"Agent A survived longer ({time_a:.1f}s vs {time_b:.1f}s)")
            else:
                return ("B", f"Agent B survived longer ({time_b:.1f}s vs {time_a:.1f}s)")
        
        # Tie - keep elite
        return ("A", "Tie - elite retained")
    
    def compete_generation(self) -> CompetitionResult:
        """
        Run one generation: both agents compete head-to-head.
        
        Returns:
            Competition result with winner
        """
        self.generation += 1
        
        logger.info("\n" + "="*60)
        logger.info(f"Generation {self.generation} - HEAD TO HEAD COMPETITION")
        logger.info("="*60)
        
        logger.info("\nAgent A (Elite) parameters:")
        self._log_genome(self.agent_a)
        
        logger.info("\nAgent B (Challenger) parameters:")
        self._log_genome(self.agent_b)
        
        logger.info("\n" + "-"*60)
        logger.info("Running competitions...")
        logger.info("-"*60)
        
        # Evaluate both agents
        stats_a = self.evaluate_agent(self.agent_a)
        stats_b = self.evaluate_agent(self.agent_b)
        
        # Determine winner
        winner_id, reason = self.determine_winner(stats_a, stats_b)
        
        logger.info("\n" + "="*60)
        logger.info(f"🏆 WINNER: Agent {winner_id}")
        logger.info(f"Reason: {reason}")
        logger.info("="*60 + "\n")
        
        # Create result record
        result = CompetitionResult(
            generation=self.generation,
            agent_a_stats=stats_a,
            agent_b_stats=stats_b,
            winner_id=winner_id,
            reason=reason
        )
        
        self.competition_history.append(result)
        
        # Update population based on winner
        if winner_id == "B":
            logger.info("🔄 Agent B defeated Elite! B becomes new Elite.")
            self.agent_a = deepcopy(self.agent_b)
            self.agent_a.agent_id = "A"
        else:
            logger.info("✓ Elite (Agent A) retained.")
        
        # Track elite lineage
        self.elite_lineage.append(deepcopy(self.agent_a))
        
        # Generate new challenger for next generation
        self.agent_b = self.agent_a.mutate(
            agent_id="B",
            generation=self.generation + 1
        )
        
        logger.info(f"\nNew challenger (Agent B) generated for generation {self.generation + 1}")
        
        # Save generation results
        self.save_generation(result)
        
        return result
    
    def save_generation(self, result: CompetitionResult):
        """Save generation results to disk."""
        # Save competition result
        gen_file = self.results_dir / f"generation_{self.generation:03d}.json"
        with open(gen_file, 'w') as f:
            json.dump({
                'generation': self.generation,
                'competition': result.to_dict(),
                'elite_genome': self.agent_a.to_dict(),
                'challenger_genome': self.agent_b.to_dict(),
            }, f, indent=2)
        
        # Save cumulative history
        history_file = self.results_dir / "evolution_history.json"
        with open(history_file, 'w') as f:
            json.dump({
                'current_generation': self.generation,
                'map': self.map_name,
                'elite_genome': self.agent_a.to_dict(),
                'competitions': [c.to_dict() for c in self.competition_history],
                'elite_lineage': [e.to_dict() for e in self.elite_lineage],
            }, f, indent=2)
        
        logger.info(f"Saved generation {self.generation} to {gen_file}")
    
    def run(self, num_generations: int = 20):
        """
        Run the 2-agent GA for specified generations.
        
        Args:
            num_generations: Number of generations to evolve
        """
        logger.info("\n" + "="*60)
        logger.info("Starting 2-Agent Genetic Algorithm")
        logger.info(f"Map: {self.map_name}")
        logger.info(f"Generations: {num_generations}")
        logger.info("Strategy: Elite vs Challenger head-to-head")
        logger.info("="*60 + "\n")
        
        # Initialize if needed
        if self.agent_a is None:
            self.initialize()
        
        # Run generations
        wins_a = 0
        wins_b = 0
        
        for gen in range(num_generations):
            result = self.compete_generation()
            
            if result.winner_id == "A":
                wins_a += 1
            else:
                wins_b += 1
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("Evolution Complete!")
        logger.info("="*60)
        logger.info(f"Total generations: {self.generation}")
        logger.info(f"Elite retained: {wins_a} times ({100*wins_a/num_generations:.1f}%)")
        logger.info(f"Challenger won: {wins_b} times ({100*wins_b/num_generations:.1f}%)")
        logger.info(f"\nFinal Elite (Agent A) parameters:")
        self._log_genome(self.agent_a)
        logger.info("="*60 + "\n")
        
        return self.agent_a


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"logs/genetic_algo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ]
    )
    
    # Run 2-agent GA
    ga = TwoAgentGA(
        wad_path="wads/doom1.wad",
        map_name="E1M1",
        episode_timeout=60,
        fast_mode=True,
    )
    
    # Evolve for 20 generations
    final_elite = ga.run(num_generations=20)
    
    print(f"\n🏆 Final Elite Parameters:")
    print(json.dumps(final_elite.to_dict(), indent=2))
