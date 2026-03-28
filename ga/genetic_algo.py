"""GA evolution runner. Wraps Agent and controls the evolution loop.

main.py evolve delegates to this file. GeneticAlgo owns the Agent instance
and calls run_episode(), compute_fitness(), and finalize_episode() each evaluation.
See genetic_algo_design.md for algorithm details.
"""
from core.execution.agent import Agent
from ga.genome import compute_fitness


class GeneticAlgo:

    def __init__(self) -> None:
        self.agent = Agent()
        self.agent.initialize_game(headless=True, evolve=True)

    def _evaluate(self, params: dict) -> float:
        """Run one episode with the given genome params and return fitness."""
        stats = self.agent.run_episode(params=params)
        stats["fitness"] = compute_fitness(stats)
        self.agent.telemetry_writer.finalize_episode(stats)
        return stats["fitness"]

    def run(self) -> None:
        """Main evolution loop. Not yet implemented."""
        raise NotImplementedError("GA evolution not yet implemented")