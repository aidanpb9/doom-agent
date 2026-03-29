"""Integration tests. These require VizDoom, doom.wad, and map JSON files.
These tests boot a real game instance and run a full episode so they cannot
run in CI. Skip them with: pytest -m "not local"

To run locally:
    pytest tests/test_integration.py -v


Design notes
------------
Fixture scope: scope="module" boots VizDoom once for all four tests. Booting
takes a few seconds; doing it per-test would be wasteful for tests that are
otherwise independent. Episode count increments across tests (ep_0001, ep_0002,
etc.) so filename assertions use agent.episode_count rather than hardcoding.

Output directory: tests write to the real output/run/ like a normal run would.

SVG test: if maps/json/E1M1.json is missing, finalize_episode() silently skips
the render (try/except). The SVG test asserting the file exists will then fail
and surface the missing dependency explicitly rather than passing silently.
"""
import pytest
from pathlib import Path
from core.execution.agent import Agent
from ga.genetic_algo import compute_fitness


pytestmark = pytest.mark.local

STATS_REQUIRED_KEYS = {
    "finish_level", "ticks", "health", "armor", "ammo",
    "enemies_killed", "waypoints_reached", "end_reason",
}


@pytest.fixture(scope="module")
def agent():
    """Single Agent instance reused across all integration tests.
    Boots VizDoom once in headless mode on E1M1 and closes it after the module."""
    a = Agent()
    a.initialize_game(headless=True, map_name="E1M1")
    yield a
    a.game.close()


def test_full_episode_runs_without_crashing(agent):
    #if VizDoom hangs or the agent loop throws, this is the test that catches it
    agent.run_episode()


def test_run_episode_returns_stats_with_all_required_keys(agent):
    stats = agent.run_episode()
    assert STATS_REQUIRED_KEYS.issubset(stats.keys())


def test_tier1_and_tier2_files_created_on_disk(agent):
    #episode_count increments each run_episode() call, so we capture it after
    #the call to know which episode number was just written.
    #finalize_episode() must be called explicitly, run_episode() only returns stats.
    stats = agent.run_episode()
    stats["fitness"] = compute_fitness(stats)
    agent.telemetry_writer.finalize_episode(stats)
    ep = agent.episode_count
    out = Path("output/run")
    assert (out / f"ep_{ep:04d}_summary.json").exists()
    assert (out / f"ep_{ep:04d}_actions.csv").exists()


def test_map_svg_is_generated(agent):
    #requires maps/json/E1M1.json to exist — if missing, render silently fails
    #and this assertion surfaces the gap rather than passing silently.
    #finalize_episode() triggers the map render.
    stats = agent.run_episode()
    stats["fitness"] = compute_fitness(stats)
    agent.telemetry_writer.finalize_episode(stats)
    ep = agent.episode_count
    assert (Path("output/run") / f"ep_{ep:04d}_map.svg").exists()