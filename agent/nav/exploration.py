"""
Exploration behavior system - lightweight and efficient.
Uses simple heuristics rather than expensive pathfinding.
Includes wall detection and escape logic.
"""

import numpy as np
import random
from agent.utils.action_decoder import ActionDecoder


class ExplorationBehavior:
    """Manages exploration patterns without expensive computation."""
    
    def __init__(self):
        self.explore_step = 0
        self.direction_changes = 0
        self.last_pos = None
        self.stuck_frames = 0
        self.last_5_positions = []  # Track last 5 positions to detect stuck
    
    def reset_episode(self):
        """Reset exploration state."""
        self.explore_step = 0
        self.direction_changes = 0
        self.stuck_frames = 0
        self.last_5_positions = []
    
    def is_stuck_against_wall(self, pos_x, pos_y):
        """
        Detect if agent is stuck against a wall.
        Returns True if position hasn't changed significantly in last 5 steps.
        """
        self.last_5_positions.append((pos_x, pos_y))
        if len(self.last_5_positions) > 5:
            self.last_5_positions.pop(0)
        
        if len(self.last_5_positions) >= 5:
            # Check if all last 5 positions are within 100 units variance
            positions = np.array(self.last_5_positions)
            variance_x = np.var(positions[:, 0])
            variance_y = np.var(positions[:, 1])
            
            # If variance is very low, agent is stuck
            if variance_x < 100 and variance_y < 100:
                self.stuck_frames += 1
                if self.stuck_frames == 1:  # Log once when detected
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"STUCK DETECTED: pos=({pos_x:.1f},{pos_y:.1f}) var_x={variance_x:.1f} var_y={variance_y:.1f}")
                return self.stuck_frames > 2  # Stuck if no movement for 3+ frames
        
        if self.stuck_frames > 0 and (variance_x >= 100 or variance_y >= 100):
            self.stuck_frames = 0
        
        return False
    
    def decide_exploration_action(self, pos_x=None, pos_y=None):
        """
        Fast, lightweight exploration that alternates between patterns.
        Now includes detection and escape from wall collisions.
        """
        # Check if stuck
        if pos_x is not None and pos_y is not None:
            if self.is_stuck_against_wall(pos_x, pos_y):
                # Escape from wall: try different direction
                # Aggressive escape - try extreme actions
                escape_action = (self.stuck_frames % 5)
                if escape_action == 0:
                    return ActionDecoder.strafe_left()
                elif escape_action == 1:
                    return ActionDecoder.strafe_right()
                elif escape_action == 2:
                    return ActionDecoder.left_turn()
                elif escape_action == 3:
                    return ActionDecoder.right_turn()
                else:
                    return ActionDecoder.forward_strafe_left()
        
        self.explore_step += 1
        
        # More aggressive exploration: shorter cycle (30 instead of 40)
        pattern = (self.explore_step // 30) % 4
        step_in_pattern = self.explore_step % 30
        
        if pattern == 0:
            # Pattern 0: Aggressive forward with early turns
            if step_in_pattern < 20:
                if step_in_pattern % 8 == 0:  # More frequent turns (every 8 vs 15)
                    if self.direction_changes % 2 == 0:
                        self.direction_changes += 1
                        return ActionDecoder.forward_left_turn()
                    else:
                        self.direction_changes += 1
                        return ActionDecoder.forward_right_turn()
                return ActionDecoder.forward()
            else:
                # Hard turn to change direction
                return ActionDecoder.left_turn()
        
        elif pattern == 1:
            # Pattern 1: Wide strafe left
            if step_in_pattern < 15:
                return ActionDecoder.forward_strafe_left()
            else:
                return ActionDecoder.strafe_left()
        
        elif pattern == 2:
            # Pattern 2: Wide strafe right
            if step_in_pattern < 15:
                return ActionDecoder.forward_strafe_right()
            else:
                return ActionDecoder.strafe_right()
        
        else:
            # Pattern 3: Aggressive zigzag to escape corners
            if step_in_pattern < 15:
                if step_in_pattern % 6 == 0:
                    return ActionDecoder.forward_right_turn()
                return ActionDecoder.forward()
            else:
                if step_in_pattern % 6 == 0:
                    return ActionDecoder.forward_left_turn()
                return ActionDecoder.forward()


