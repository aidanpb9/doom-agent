"""
Visualization script for reviewing Doom agent gameplay.
Can display screenshots or run live visualization.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
import json

def visualize_screenshots(screenshot_dir="screenshots"):
    """Display saved screenshots in sequence."""
    screenshot_dir = Path(screenshot_dir)
    
    if not screenshot_dir.exists():
        print(f"Screenshot directory not found: {screenshot_dir}")
        return
    
    screenshots = sorted(screenshot_dir.glob("frame_*.png"))
    
    if not screenshots:
        print("No screenshots found.")
        return
    
    print(f"Found {len(screenshots)} screenshots. Press 'q' to quit, 'n' for next, 'p' for previous.")
    
    idx = 0
    while idx < len(screenshots):
        img = cv2.imread(str(screenshots[idx]))
        if img is None:
            idx += 1
            continue
        
        # Add frame number overlay
        cv2.putText(img, f"Frame {idx}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Doom Agent Gameplay", img)
        
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('n') or key == ord(' '):
            idx = min(idx + 1, len(screenshots) - 1)
        elif key == ord('p'):
            idx = max(idx - 1, 0)
    
    cv2.destroyAllWindows()

def create_summary_video(screenshot_dir="screenshots", output_file="gameplay_summary.avi", fps=10):
    """Create a video from screenshots."""
    screenshot_dir = Path(screenshot_dir)
    screenshots = sorted(screenshot_dir.glob("frame_*.png"))
    
    if not screenshots:
        print("No screenshots found.")
        return
    
    # Read first image to get dimensions
    first_img = cv2.imread(str(screenshots[0]))
    if first_img is None:
        print("Could not read screenshots.")
        return
    
    height, width = first_img.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    
    print(f"Creating video from {len(screenshots)} frames...")
    
    for i, screenshot_path in enumerate(screenshots):
        img = cv2.imread(str(screenshot_path))
        if img is not None:
            # Add frame number
            cv2.putText(img, f"Frame {i}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            out.write(img)
        
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(screenshots)} frames...")
    
    out.release()
    print(f"Video saved to: {output_file}")

def analyze_performance(log_dir="logs"):
    """Analyze performance metrics from logs."""
    log_dir = Path(log_dir)
    summary_file = log_dir / "summary.json"
    
    if not summary_file.exists():
        print("No summary file found. Run the agent first.")
        return
    
    with open(summary_file, 'r') as f:
        summary = json.load(f)
    
    print("\n" + "="*60)
    print("PERFORMANCE ANALYSIS")
    print("="*60)
    print(f"\nTotal Iterations: {summary['iterations']}")
    print(f"\nAverage Metrics:")
    print(f"  Kills: {summary['average_kills']:.2f}")
    print(f"  Reward: {summary['average_reward']:.2f}")
    print(f"  Health Lost: {summary['average_health_lost']:.2f}")
    
    print(f"\nBest Iteration: {summary['best_iteration']}")
    print(f"  Kills: {summary['best_kills']}")
    
    # Load best iteration details
    best_iter_file = log_dir / f"iteration_{summary['best_iteration']}_results.json"
    if best_iter_file.exists():
        with open(best_iter_file, 'r') as f:
            best_stats = json.load(f)
        print(f"\nBest Iteration Details:")
        print(f"  Total Reward: {best_stats['episode_reward']:.2f}")
        print(f"  Kills: {best_stats['kills']}")
        print(f"  Health Lost: {best_stats['health_lost']}")
        print(f"  Actions Taken: {best_stats['actions_taken']}")
        print(f"  Episode Time: {best_stats['episode_time']:.2f}s")
    
    print("\n" + "="*60)

def main():
    parser = argparse.ArgumentParser(description="Visualize Doom agent gameplay")
    parser.add_argument("--mode", choices=["screenshots", "video", "analyze"], 
                       default="analyze", help="Visualization mode")
    parser.add_argument("--screenshot-dir", default="screenshots", 
                       help="Directory containing screenshots")
    parser.add_argument("--output", default="gameplay_summary.avi", 
                       help="Output video file")
    parser.add_argument("--fps", type=int, default=10, 
                       help="Frames per second for video")
    parser.add_argument("--log-dir", default="logs", 
                       help="Directory containing logs")
    
    args = parser.parse_args()
    
    if args.mode == "screenshots":
        visualize_screenshots(args.screenshot_dir)
    elif args.mode == "video":
        create_summary_video(args.screenshot_dir, args.output, args.fps)
    elif args.mode == "analyze":
        analyze_performance(args.log_dir)

if __name__ == "__main__":
    main()
