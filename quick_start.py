"""
Quick start script to run the Doom agent with default settings.
"""

import sys
from pathlib import Path
from doom_agent import run_iterative_tests

def main():
    # Check for WAD files
    wad_dir = Path("wads")
    if not wad_dir.exists():
        print("Error: 'wads' directory not found!")
        sys.exit(1)
    
    # Find available WAD files
    wad_files = list(wad_dir.glob("*.wad"))
    if not wad_files:
        print("Error: No WAD files found in 'wads' directory!")
        sys.exit(1)
    
    # Use first available WAD file
    wad_file = wad_files[0]
    print(f"Using WAD file: {wad_file}")
    print("Starting Doom Agent...")
    print("="*60)
    
    # Run tests
    run_iterative_tests(str(wad_file), num_iterations=2, episode_timeout=2)
    
    print("\n" + "="*60)
    print("Test completed! Check the 'logs' directory for results.")
    print("Use 'python visualize_gameplay.py --mode analyze' to view performance.")
    print("="*60)

if __name__ == "__main__":
    main()
