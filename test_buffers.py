#!/usr/bin/env python3
"""Quick test of buffer visualization"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DOOM_DIR = SCRIPT_DIR / "DOOM"
if str(DOOM_DIR) not in sys.path:
    sys.path.insert(0, str(DOOM_DIR))

from visualize_buffers import visualize_buffers

print("Testing buffer visualization initialization...")
print("This will run for 10 ticks then exit automatically.\n")

try:
    from vizdoom import DoomGame
    
    game = DoomGame()
    game.load_config(str(DOOM_DIR / "doom.cfg"))
    
    # Enable all buffers
    game.set_depth_buffer_enabled(True)
    game.set_automap_buffer_enabled(True)
    game.set_labels_buffer_enabled(True)
    
    game.init()
    game.new_episode()
    
    print(f"✓ Game initialized successfully")
    print(f"✓ Screen buffer available: {game.get_state().screen_buffer is not None}")
    print(f"✓ Depth buffer available: {game.get_state().depth_buffer is not None}")
    print(f"✓ Automap buffer available: {game.get_state().automap_buffer is not None}")
    print(f"✓ Labels buffer available: {game.get_state().labels is not None}")
    
    # Run 10 ticks
    for i in range(10):
        state = game.get_state()
        game.make_action([1, 0, 0, 0, 0, 0, 0, 0], 1)
        print(f"  Tick {i+1}: {len(state.labels) if state.labels else 0} objects detected")
    
    game.close()
    
    print("\n✓ Buffer visualization test PASSED")
    print("\nTo run the full interactive visualization, use:")
    print("  python visualize_buffers.py")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
