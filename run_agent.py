"""
Main script to run the Doom agent iteratively.
This script runs the agent, analyzes logs, and suggests improvements.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def analyze_logs(log_dir):
    """Analyze logs from previous runs and suggest improvements."""
    log_dir = Path(log_dir)
    
    if not log_dir.exists():
        print("No logs found. Running initial test...")
        return None
    
    # Find latest log files
    log_files = sorted(log_dir.glob("doom_agent_*.log"))
    summary_file = log_dir / "summary.json"
    
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        
        print("\n" + "="*60)
        print("ANALYSIS OF PREVIOUS RUNS")
        print("="*60)
        print(f"Total iterations: {summary['iterations']}")
        print(f"Average kills: {summary['average_kills']:.2f}")
        print(f"Average reward: {summary['average_reward']:.2f}")
        print(f"Average health lost: {summary['average_health_lost']:.2f}")
        print(f"Best iteration: {summary['best_iteration']} (Kills: {summary['best_kills']})")
        
        # Suggest improvements
        print("\n" + "="*60)
        print("SUGGESTIONS FOR IMPROVEMENT")
        print("="*60)
        
        if summary['average_kills'] < 1:
            print("- Agent is not killing enemies effectively")
            print("  -> Improve enemy detection algorithm")
            print("  -> Increase attack frequency when enemies detected")
        
        if summary['average_health_lost'] > 50:
            print("- Agent is taking too much damage")
            print("  -> Add defensive behaviors (backing away when low health)")
            print("  -> Improve movement patterns to avoid enemy fire")
        
        if summary['average_reward'] < -50:
            print("- Agent is performing poorly overall")
            print("  -> Review action selection logic")
            print("  -> Improve exploration vs exploitation balance")
        
        return summary
    
    return None

def run_agent(wad_file, num_iterations=5, seconds=15):
    """Run the agent and return results."""
    print(f"\nRunning agent with {num_iterations} iterations...")
    print(f"WAD file: {wad_file}\n")
    
    result = subprocess.run(
        [sys.executable, "doom_agent.py", wad_file, str(seconds)],
        capture_output=False,
        text=True
    )
    
    return result.returncode == 0

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Doom agent iteratively")
    parser.add_argument("--wad", default="DOOM/wads/doom2.wad", help="Path to WAD file")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations")
    parser.add_argument("--auto-improve", action="store_true", help="Automatically run multiple improvement cycles")
    parser.add_argument("--seconds", type=int, default=15, help="Episode duration in seconds")
    args = parser.parse_args()
    
    wad_file = Path(args.wad)
    if not wad_file.exists():
        print(f"Error: WAD file not found: {wad_file}")
        sys.exit(1)
    
    log_dir = Path("logs")
    
    if args.auto_improve:
        # Run multiple cycles of improvement
        max_cycles = 3
        for cycle in range(max_cycles):
            print(f"\n{'='*60}")
            print(f"IMPROVEMENT CYCLE {cycle + 1}/{max_cycles}")
            print(f"{'='*60}\n")
            
            # Analyze previous results
            if cycle > 0:
                analyze_logs(log_dir)
                print("\nRunning next iteration cycle...\n")
            
            # Run agent
            success = run_agent(str(wad_file), args.iterations, args.seconds)
            
            if not success:
                print("Error running agent. Check logs for details.")
                break
            
            # Brief pause between cycles
            if cycle < max_cycles - 1:
                print("\nWaiting before next cycle...")
                import time
                time.sleep(5)
        
        # Final analysis
        print("\n" + "="*60)
        print("FINAL ANALYSIS")
        print("="*60)
        analyze_logs(log_dir)
    else:
        # Single run
        analyze_logs(log_dir)
        run_agent(str(wad_file), args.iterations, args.seconds)
        analyze_logs(log_dir)

if __name__ == "__main__":
    main()
