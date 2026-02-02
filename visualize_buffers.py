#!/usr/bin/env python3
"""
Buffer Visualization Tool for DOOM Agent
=========================================

Displays all active DOOM game buffers in real-time while running the agent:
- Screen Buffer: RGB game view with agent actions
- Depth Buffer: Depth map visualization
- Automap Buffer: Top-down map view
- Labels Buffer: Objects with bounding boxes and names

This tool runs the actual agent decision logic while visualizing what the agent
is seeing and doing, making it easy to debug navigation and targeting issues.

Usage:
    python visualize_buffers.py [wad] [timeout]
    
    wad: Path to WAD file (default: DOOM/wads/doom2.wad)
    timeout: Episode timeout in seconds (default: 10)

Controls:
    ESC             - Quit visualization

Examples:
    python visualize_buffers.py
    python visualize_buffers.py DOOM/wads/doom1.wad 20
"""

import sys
from pathlib import Path

# Add DOOM directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
DOOM_DIR = SCRIPT_DIR / "DOOM"
if str(DOOM_DIR) not in sys.path:
    sys.path.insert(0, str(DOOM_DIR))

from visualize_buffers import visualize_buffers

if __name__ == "__main__":
    wad_file = str(DOOM_DIR / "wads" / "doom2.wad")
    episode_timeout = 10
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        wad_file = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            episode_timeout = int(sys.argv[2])
        except:
            episode_timeout = 10
    
    print(__doc__)
    print(f"WAD: {wad_file}")
    print(f"Timeout: {episode_timeout}s\n")
    
    visualize_buffers(wad_path=wad_file, episode_timeout=episode_timeout)
