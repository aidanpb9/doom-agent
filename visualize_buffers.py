#!/usr/bin/env python3
"""
Buffer Visualization Tool for DOOM Agent
=========================================

Displays all active DOOM game buffers in real-time while running the agent:
- Screen Buffer: RGB game view with agent actions
- Depth Buffer: Depth map visualization
- Automap Buffer: Top-down map view (with cheat mode showing all enemies)
- Labels Buffer: Objects with bounding boxes and names

This tool runs the actual agent decision logic while visualizing what the agent
is seeing and doing, making it easy to debug navigation and targeting issues.

Usage:
    python visualize_buffers.py [wad] [timeout]
    
    wad: Path to WAD file (default: wads/doom2.wad)
    timeout: Episode timeout in seconds (default: 30)

Controls:
    ESC or Q        - Quit visualization
    SPACE           - Pause/Resume

Examples:
    python visualize_buffers.py
    python visualize_buffers.py wads/doom1.wad 20
"""

import sys
from pathlib import Path
import numpy as np
import cv2
import vizdoom as vzd
from doom_agent import DoomAgent

def visualize_buffers(wad_path="wads/doom2.wad", episode_timeout=30):
    """
    Run the agent with real-time visualization of all buffers.
    """
    # Initialize agent
    agent = DoomAgent(wad_path, episode_timeout=episode_timeout)
    agent.initialize_game()
    
    print("\n" + "="*60)
    print("BUFFER VISUALIZATION MODE")
    print("="*60)
    print(f"WAD: {wad_path}")
    print(f"Timeout: {episode_timeout}s")
    print("\nControls:")
    print("  ESC or Q - Quit")
    print("  SPACE    - Pause/Resume")
    print("="*60 + "\n")
    
    paused = False
    
    try:
        agent.game.new_episode()
        
        while not agent.game.is_episode_finished():
            state = agent.game.get_state()
            if state is None:
                break
                
            # Get state info
            state_info = agent.get_state_info(state)
            automap_buffer = state.automap_buffer if hasattr(state, "automap_buffer") else None
            angle = state_info.get('angle', None)
            
            # Get action from agent
            if not paused:
                action = agent.behavior_selector.decide_action(state_info, automap_buffer, angle)
            
            # Prepare buffers for visualization
            buffers_to_show = []
            
            # 1. Screen Buffer (RGB)
            if state.screen_buffer is not None:
                # Screen buffer shape is (channels, height, width) - need to transpose
                screen = state.screen_buffer
                if len(screen.shape) == 3 and screen.shape[0] == 3:
                    screen = np.transpose(screen, (1, 2, 0))
                
                screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
                
                # Add status overlay
                health = state_info.get('health', 0)
                ammo = state_info.get('ammo', 0)
                kills = state_info.get('kills', 0)
                pos_x = state_info.get('pos_x', 0)
                pos_y = state_info.get('pos_y', 0)
                
                cv2.putText(screen_bgr, f"Health: {health:.0f}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(screen_bgr, f"Ammo: {ammo:.0f}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(screen_bgr, f"Kills: {kills}", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(screen_bgr, f"Pos: ({pos_x:.0f}, {pos_y:.0f})", (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                if paused:
                    cv2.putText(screen_bgr, "PAUSED", (screen_bgr.shape[1]//2 - 60, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                
                cv2.putText(screen_bgr, "Screen View", (10, screen_bgr.shape[0]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                buffers_to_show.append(screen_bgr)
            
            # 2. Depth Buffer
            if state.depth_buffer is not None:
                depth = state.depth_buffer
                depth_normalized = ((depth - depth.min()) / (depth.max() - depth.min() + 1e-6) * 255).astype(np.uint8)
                depth_colored = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
                cv2.putText(depth_colored, "Depth Buffer", (10, depth_colored.shape[0]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                buffers_to_show.append(depth_colored)
            
            # 3. Automap Buffer (WITH CHEATS - shows all enemies!)
            if automap_buffer is not None and len(automap_buffer) > 0:
                # Automap is grayscale, convert to BGR
                if len(automap_buffer.shape) == 2:
                    automap_bgr = cv2.cvtColor(automap_buffer, cv2.COLOR_GRAY2BGR)
                else:
                    automap_bgr = automap_buffer
                    
                # Add text overlay
                cv2.putText(automap_bgr, "Automap (CHEAT MODE)", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(automap_bgr, "All enemies visible!", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                cv2.putText(automap_bgr, "Automap", (10, automap_bgr.shape[0]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                buffers_to_show.append(automap_bgr)
            
            # 4. Labels Buffer (with bounding boxes)
            if state.labels_buffer is not None:
                labels_img = np.zeros((state.screen_buffer.shape[1], state.screen_buffer.shape[2], 3), dtype=np.uint8)
                
                # Draw bounding boxes for each label
                labels = state_info.get('labels', [])
                for lbl in labels:
                    name = getattr(lbl, "object_name", "Unknown")
                    x, y, w, h = lbl.x, lbl.y, lbl.width, lbl.height
                    
                    # Color code: enemies=red, items=green, player=blue
                    if "Zombieman" in name or "ShotgunGuy" in name or "Imp" in name or "Demon" in name:
                        color = (0, 0, 255)  # Red for enemies
                    elif "Player" in name:
                        color = (255, 0, 0)  # Blue for player
                    else:
                        color = (0, 255, 0)  # Green for items
                    
                    cv2.rectangle(labels_img, (x, y), (x+w, y+h), color, 2)
                    cv2.putText(labels_img, name, (x, max(y-5, 10)), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                
                cv2.putText(labels_img, f"Labels: {len(labels)} objects", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(labels_img, "Labels Buffer", (10, labels_img.shape[0]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                buffers_to_show.append(labels_img)
            
            # Stack buffers in 2x2 grid
            # Resize all buffers to same size for stacking
            target_h, target_w = 480, 640
            resized_buffers = []
            for buf in buffers_to_show:
                if buf.shape[:2] != (target_h, target_w):
                    resized = cv2.resize(buf, (target_w, target_h))
                    resized_buffers.append(resized)
                else:
                    resized_buffers.append(buf)
            
            if len(resized_buffers) >= 4:
                row1 = np.hstack([resized_buffers[0], resized_buffers[1]])
                row2 = np.hstack([resized_buffers[2], resized_buffers[3]])
                combined = np.vstack([row1, row2])
            elif len(resized_buffers) == 3:
                row1 = np.hstack([resized_buffers[0], resized_buffers[1]])
                row2 = np.hstack([resized_buffers[2], np.zeros((target_h, target_w, 3), dtype=np.uint8)])
                combined = np.vstack([row1, row2])
            elif len(resized_buffers) == 2:
                combined = np.hstack(resized_buffers)
            elif len(resized_buffers) == 1:
                combined = resized_buffers[0]
            else:
                # No buffers available
                combined = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(combined, "No buffers available", (200, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            
            # Display
            cv2.imshow("DOOM Agent - All Buffers", combined)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):  # ESC or Q
                print("\nVisualization stopped by user")
                break
            elif key == ord(' '):  # SPACE
                paused = not paused
                print(f"{'PAUSED' if paused else 'RESUMED'}")
            
            # Make action if not paused
            if not paused:
                agent.game.make_action(action, 4)
            
    except KeyboardInterrupt:
        print("\nVisualization interrupted by user")
    except Exception as e:
        print(f"\nError during visualization: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()
        agent.close()
        print("\nVisualization ended")

if __name__ == "__main__":
    wad_file = "wads/doom2.wad"
    episode_timeout = 30
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        wad_file = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            episode_timeout = int(sys.argv[2])
        except:
            episode_timeout = 30
    
    if not Path(wad_file).exists():
        print(f"Error: WAD file not found: {wad_file}")
        sys.exit(1)
    
    print(__doc__)
    visualize_buffers(wad_path=wad_file, episode_timeout=episode_timeout)
