"""
Smart exploration using automap analysis.
Extract room layout, doors, and frontiers from the automap buffer.
Navigate toward unexplored areas instead of random patterns.
"""

import numpy as np
from scipy import ndimage
from agent.utils.action_decoder import ActionDecoder


class AutomapNavigator:
    """Uses automap to identify rooms, doors, and unexplored areas."""
    
    def __init__(self):
        self.last_automap = None
        self.explored_regions = set()
        self.current_room_id = None
        self.frontier_points = []
        
    def analyze_automap(self, automap_buffer):
        """
        Extract room structure, doors, and unexplored frontiers.
        Doom automap: Black/very dark = unexplored, Darker gray = walkable floor, Light gray/white = walls
        Returns: (current_room, frontier_direction, door_detected)
        """
        if automap_buffer is None:
            return None
            
        # Convert automap to numpy if needed
        if not isinstance(automap_buffer, np.ndarray):
            automap_buffer = np.array(automap_buffer)
        
        # Handle grayscale or RGB
        if len(automap_buffer.shape) == 2:
            gray = automap_buffer.astype(float)
        else:
            gray = np.mean(automap_buffer, axis=2).astype(float)
        
        # Recalibrate for Doom automap where values are very dark overall
        # Unexplored = near-black (0-20)
        # Explored floor = gray (20-120)
        # Walls = lighter gray-white (120+)
        
        unexplored = gray < 20
        walkable = (gray >= 20) & (gray < 120)  # Explored floors
        walls = gray >= 120  # Walls and boundaries
        
        # Label connected components in walkable area
        from scipy import ndimage
        labeled_rooms, num_rooms = ndimage.label(walkable)
        
        # Find the area with most walkable pixels near center (where player is)
        center_h, center_w = gray.shape[0] // 2, gray.shape[1] // 2
        region_size = 80
        center_region = labeled_rooms[
            max(0, center_h-region_size):min(gray.shape[0], center_h+region_size),
            max(0, center_w-region_size):min(gray.shape[1], center_w+region_size)
        ]
        
        if center_region.size > 0 and np.any(center_region > 0):
            # Find the most common room label in center
            room_labels, counts = np.unique(center_region[center_region > 0], return_counts=True)
            current_room = room_labels[np.argmax(counts)]
        else:
            current_room = 1
        
        # Find frontier: edges where explored meets unexplored
        dilated_unexplored = ndimage.binary_dilation(unexplored, iterations=3)
        frontier = walkable & dilated_unexplored
        
        # Get frontier coordinates for navigation target
        frontier_coords = np.argwhere(frontier)
        if frontier_coords.size > 0:
            # Pick a frontier point far from center
            distances = np.sqrt((frontier_coords[:, 0] - center_h)**2 + 
                              (frontier_coords[:, 1] - center_w)**2)
            furthest_idx = np.argmax(distances)
            frontier_point = frontier_coords[furthest_idx]
            frontier_direction = np.arctan2(
                frontier_point[0] - center_h,
                frontier_point[1] - center_w
            )
        else:
            frontier_direction = None
        
        return {
            'current_room': current_room,
            'num_rooms': num_rooms,
            'frontier_detected': frontier_coords.size > 0,
            'walkable_ratio': np.sum(walkable) / walkable.size if walkable.size > 0 else 0,
            'frontier_direction': frontier_direction,
            'unexplored_ratio': np.sum(unexplored) / gray.size,
        }


class SmartExploration:
    """
    Navigation that:
    1. Uses automap to find room structure
    2. Identifies unexplored frontiers
    3. Navigates toward doors and exits
    4. Avoids getting stuck in corners
    """
    
    def __init__(self):
        self.automap_nav = AutomapNavigator()
        self.explore_step = 0
        self.last_frontier_direction = None
        self.stuck_counter = 0
        self.last_5_positions = []
    
    def reset_episode(self):
        self.explore_step = 0
        self.last_frontier_direction = None
        self.stuck_counter = 0
        self.last_5_positions = []
    
    def decide_action(self, pos_x, pos_y, automap_buffer):
        """
        Decide action based on automap analysis and position.
        Priority: Find frontier → Navigate to doors → Avoid walls
        """
        # Analyze automap
        map_info = self.automap_nav.analyze_automap(automap_buffer)
        
        if map_info is None:
            # No automap, fall back to default exploration
            return self._default_exploration()
        
        # Detect stuck: if variance too low, break out aggressively
        self.last_5_positions.append((pos_x, pos_y))
        if len(self.last_5_positions) > 5:
            self.last_5_positions.pop(0)
        
        if len(self.last_5_positions) >= 5:
            positions = np.array(self.last_5_positions)
            var_x = np.var(positions[:, 0])
            var_y = np.var(positions[:, 1])
            
            if var_x < 100 and var_y < 100:
                # Agent is stuck in a small area
                self.stuck_counter += 1
                
                # Use strafe/turn escape actions
                if self.stuck_counter > 2:
                    escape_action = (self.stuck_counter // 3) % 6
                    if escape_action == 0:
                        return ActionDecoder.strafe_left()
                    elif escape_action == 1:
                        return ActionDecoder.strafe_right()
                    elif escape_action == 2:
                        return ActionDecoder.left_turn()
                    elif escape_action == 3:
                        return ActionDecoder.right_turn()
                    elif escape_action == 4:
                        return ActionDecoder.forward_strafe_left()
                    else:
                        return ActionDecoder.forward_strafe_right()
            else:
                self.stuck_counter = 0
        
        # If frontier detected, navigate toward it
        if map_info and map_info['frontier_detected'] and map_info['frontier_direction'] is not None:
            direction = map_info['frontier_direction']
            # Convert frontier direction to action
            # Frontier at angle tells us where to go
            return self._navigate_to_direction(direction)
        
        # If no frontier but unexplored area exists, keep exploring
        if map_info and map_info['unexplored_ratio'] > 0.5:
            return ActionDecoder.forward()
        
        # Otherwise, do safe forward exploration with turns
        return self._safe_forward_exploration()
    
    def _default_exploration(self):
        """Fallback simple exploration."""
        self.explore_step += 1
        pattern = (self.explore_step // 40) % 2
        step_mod = self.explore_step % 40
        
        if pattern == 0:
            if step_mod < 20:
                return ActionDecoder.forward() if step_mod % 10 < 8 else ActionDecoder.forward_left_turn()
            else:
                return ActionDecoder.left_turn()
        else:
            if step_mod < 20:
                return ActionDecoder.forward() if step_mod % 10 < 8 else ActionDecoder.forward_right_turn()
            else:
                return ActionDecoder.right_turn()
    
    def _navigate_to_direction(self, direction):
        """Convert frontier direction to movement action."""
        # Normalize direction to -π to π
        while direction > np.pi:
            direction -= 2 * np.pi
        while direction < -np.pi:
            direction += 2 * np.pi
        
        # Map direction to action
        if abs(direction) < 0.3:  # Forward-ish
            return ActionDecoder.forward()
        elif 0.3 <= direction < 1.5:  # Right-forward
            return ActionDecoder.forward_strafe_right()
        elif direction >= 1.5:  # Hard right
            return ActionDecoder.strafe_right()
        elif -1.5 <= direction < -0.3:  # Left-forward
            return ActionDecoder.forward_strafe_left()
        else:  # Hard left
            return ActionDecoder.strafe_left()
    
    def _safe_forward_exploration(self):
        """Safe forward movement with periodic turns."""
        self.explore_step += 1
        step_mod = self.explore_step % 50
        
        if step_mod < 40:
            return ActionDecoder.forward() if step_mod % 8 != 0 else ActionDecoder.forward_left_turn()
        else:
            return ActionDecoder.left_turn()
