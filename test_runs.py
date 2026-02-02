#!/usr/bin/env python
"""Run multiple agent tests and aggregate results."""

import subprocess
import sys
import json
from pathlib import Path

def extract_kills_from_last_run():
    """Extract kills from last_run.json"""
    try:
        with open("logs/last_run.json", "r") as f:
            data = json.load(f)
            return data.get("kills", 0), data.get("health_lost", 0), data.get("episode_reward", 0.0)
    except:
        return 0, 0, 0.0

def run_test(iteration, wad="DOOM/wads/doom2.wad", seconds=12):
    """Run a single test."""
    print(f"\n{'='*60}")
    print(f"Test {iteration}: Running {seconds}s episode...")
    print(f"{'='*60}")
    
    result = subprocess.run(
        [sys.executable, "doom_agent.py", wad, str(seconds)],
        capture_output=True,
        text=True
    )
    
    kills, health_lost, reward = extract_kills_from_last_run()
    print(f"Kills: {kills:2d} | Health Lost: {health_lost:6.1f} | Reward: {reward:7.2f}")
    
    return kills, health_lost, reward

def main():
    num_tests = 10
    wad = "DOOM/wads/doom2.wad"
    seconds = 12
    
    if len(sys.argv) > 1:
        num_tests = int(sys.argv[1])
    if len(sys.argv) > 2:
        wad = sys.argv[2]
    if len(sys.argv) > 3:
        seconds = int(sys.argv[3])
    
    results = []
    for i in range(1, num_tests + 1):
        kills, health_lost, reward = run_test(i, wad, seconds)
        results.append({
            "iteration": i,
            "kills": kills,
            "health_lost": health_lost,
            "reward": reward
        })
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    kills_list = [r["kills"] for r in results]
    health_list = [r["health_lost"] for r in results]
    
    print(f"Tests run: {num_tests}")
    print(f"Average kills: {sum(kills_list) / len(kills_list):.2f}")
    print(f"Max kills: {max(kills_list)}")
    print(f"Min kills: {min(kills_list)}")
    print(f"Average health lost: {sum(health_list) / len(health_list):.2f}")
    print(f"Max health lost: {max(health_list):.1f}")
    
    # Save results
    with open("logs/batch_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to logs/batch_test_results.json")

if __name__ == "__main__":
    main()
