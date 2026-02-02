#!/usr/bin/env python
"""
Parallel batch testing system for Doom agent.
Runs multiple tests simultaneously and finds best performers.
"""

import subprocess
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def extract_kills_from_last_run():
    """Extract kills from last_run.json"""
    try:
        with open("logs/last_run.json", "r") as f:
            data = json.load(f)
            return {
                "kills": data.get("kills", 0),
                "health_lost": data.get("health_lost", 0),
                "reward": data.get("episode_reward", 0.0),
                "ammo_used": data.get("ammo_used", 0),
                "actions": data.get("actions_taken", 0)
            }
    except:
        return {"kills": 0, "health_lost": 0, "reward": 0.0, "ammo_used": 0, "actions": 0}

def run_single_test(test_id, wad="DOOM/wads/doom2.wad", seconds=12):
    """Run a single test and return results."""
    sys.stdout.write(f"[Test {test_id}] Starting...\n")
    sys.stdout.flush()
    
    try:
        result = subprocess.run(
            [sys.executable, "doom_agent.py", wad, str(seconds)],
            capture_output=True,
            text=True,
            timeout=seconds + 10
        )
        
        stats = extract_kills_from_last_run()
        sys.stdout.write(
            f"[Test {test_id}] Kills: {stats['kills']:2d} | "
            f"Health Lost: {stats['health_lost']:6.1f} | "
            f"Ammo Used: {stats['ammo_used']:3.0f}\n"
        )
        sys.stdout.flush()
        
        return {
            "test_id": test_id,
            "success": True,
            **stats
        }
    except Exception as e:
        sys.stdout.write(f"[Test {test_id}] ERROR: {e}\n")
        sys.stdout.flush()
        return {"test_id": test_id, "success": False, "error": str(e)}

def run_parallel_batch(num_tests, wad="DOOM/wads/doom2.wad", seconds=12, max_workers=4):
    """Run tests in parallel."""
    print(f"\n{'='*60}")
    print(f"Running {num_tests} tests in parallel (max {max_workers} workers)")
    print(f"WAD: {wad} | Duration: {seconds}s")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_single_test, i+1, wad, seconds)
            for i in range(num_tests)
        ]
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    elapsed = time.time() - start_time
    
    return results, elapsed

def print_batch_summary(results, elapsed):
    """Print summary of batch results."""
    successful = [r for r in results if r.get("success", False)]
    
    if not successful:
        print("\nNo successful tests!")
        return
    
    kills_list = [r["kills"] for r in successful]
    health_list = [r["health_lost"] for r in successful]
    ammo_list = [r["ammo_used"] for r in successful]
    
    best_kills_idx = kills_list.index(max(kills_list))
    best_test = successful[best_kills_idx]
    
    print(f"\n{'='*60}")
    print(f"BATCH SUMMARY ({len(successful)}/{len(results)} successful)")
    print(f"{'='*60}")
    print(f"Time elapsed: {elapsed:.1f}s")
    print(f"\nKills:")
    print(f"  Average: {sum(kills_list) / len(kills_list):.2f}")
    print(f"  Max: {max(kills_list)} (Test {best_test['test_id']})")
    print(f"  Min: {min(kills_list)}")
    print(f"\nHealth Lost:")
    print(f"  Average: {sum(health_list) / len(health_list):.2f}")
    print(f"  Min (best): {min(health_list):.1f}")
    print(f"  Max (worst): {max(health_list):.1f}")
    print(f"\nEfficiency (Kills per Health Lost):")
    efficiencies = [
        k / max(h, 1) for k, h in zip(kills_list, health_list)
    ]
    best_eff_idx = efficiencies.index(max(efficiencies))
    print(f"  Best: {efficiencies[best_eff_idx]:.3f} (Test {successful[best_eff_idx]['test_id']})")
    print(f"  Average: {sum(efficiencies) / len(efficiencies):.3f}")
    print(f"{'='*60}\n")
    
    return successful

def main():
    num_tests = 8
    num_batches = 3
    wad = "DOOM/wads/doom2.wad"
    seconds = 12
    max_workers = 4
    
    if len(sys.argv) > 1:
        num_tests = int(sys.argv[1])
    if len(sys.argv) > 2:
        num_batches = int(sys.argv[2])
    if len(sys.argv) > 3:
        seconds = int(sys.argv[3])
    if len(sys.argv) > 4:
        max_workers = int(sys.argv[4])
    
    all_results = []
    
    for batch_num in range(1, num_batches + 1):
        print(f"\n\n{'#'*60}")
        print(f"# BATCH {batch_num}/{num_batches}")
        print(f"{'#'*60}")
        
        batch_results, elapsed = run_parallel_batch(num_tests, wad, seconds, max_workers)
        all_results.extend(batch_results)
        
        summary = print_batch_summary(batch_results, elapsed)
        
        if batch_num < num_batches:
            print("Waiting before next batch...\n")
            time.sleep(2)
    
    # Overall summary
    successful = [r for r in all_results if r.get("success", False)]
    
    print(f"\n{'='*60}")
    print(f"OVERALL SUMMARY ({len(successful)}/{len(all_results)} tests)")
    print(f"{'='*60}")
    
    if successful:
        kills_list = [r["kills"] for r in successful]
        print(f"Average kills across all tests: {sum(kills_list) / len(kills_list):.2f}")
        print(f"Best kills: {max(kills_list)}")
        print(f"Worst kills: {min(kills_list)}")
        
        # Save results
        with open("logs/batch_testing_results.json", "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nDetailed results saved to: logs/batch_testing_results.json")

if __name__ == "__main__":
    main()
