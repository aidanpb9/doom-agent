"""
A* Pathfinding using automap collision map.
Provides perfect navigation by calculating safe paths ahead of time.
"""

import numpy as np
import heapq
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class PathNode:
    """Node for A* pathfinding."""
    
    def __init__(self, x, y, g=0, h=0):
        self.x = x
        self.y = y
        self.g = g  # Cost from start
        self.h = h  # Heuristic cost to goal
        self.f = g + h  # Total estimated cost
        self.parent = None
    
    def __lt__(self, other):
        return self.f < other.f
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))


class AStarPathfinder:
    """A* pathfinding with automap-based collision detection."""
    
    def __init__(self, walkable_threshold_min=20, walkable_threshold_max=120):
        """
        Initialize pathfinder.
        
        Args:
            walkable_threshold_min: Automap pixel value minimum for walkable
            walkable_threshold_max: Automap pixel value maximum for walkable
        """
        self.walkable_min = walkable_threshold_min
        self.walkable_max = walkable_threshold_max
        self.last_path = None
        self.path_idx = 0
    
    def heuristic(self, x1, y1, x2, y2):
        """Euclidean distance heuristic."""
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def is_walkable(self, x, y, automap):
        """Check if pixel is walkable from automap."""
        if x < 0 or x >= automap.shape[1] or y < 0 or y >= automap.shape[0]:
            return False
        
        pixel_value = automap[int(y), int(x)]
        return self.walkable_min <= pixel_value < self.walkable_max
    
    def get_neighbors(self, x, y, automap):
        """
        Get valid neighbors for pathfinding.
        Uses 8-directional movement (including diagonals).
        """
        neighbors = []
        
        # 8 directions: up, down, left, right, and diagonals
        directions = [
            (0, -1), (0, 1), (-1, 0), (1, 0),  # Cardinal
            (-1, -1), (-1, 1), (1, -1), (1, 1)  # Diagonal
        ]
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny, automap):
                # Diagonal movement costs slightly more
                cost = 1.414 if dx != 0 and dy != 0 else 1.0
                neighbors.append((nx, ny, cost))
        
        return neighbors
    
    def find_path(self, start_x, start_y, goal_x, goal_y, automap) -> Optional[List[Tuple[float, float]]]:
        """
        Find optimal path from start to goal using A*.
        
        Args:
            start_x, start_y: Starting position in automap pixels
            goal_x, goal_y: Goal position in automap pixels
            automap: Automap buffer (grayscale)
        
        Returns:
            List of (x, y) coordinates forming the path, or None if no path exists
        """
        if automap is None or len(automap) == 0:
            return None
        
        # Convert to automap coordinates if needed
        start_x, start_y = int(start_x), int(start_y)
        goal_x, goal_y = int(goal_x), int(goal_y)
        
        # Ensure goal is walkable
        if not self.is_walkable(goal_x, goal_y, automap):
            # Try to find nearest walkable pixel to goal
            goal_x, goal_y = self._find_nearest_walkable(goal_x, goal_y, automap, search_radius=10)
            if goal_x is None:
                logger.warning(f"No walkable area near goal ({goal_x}, {goal_y})")
                return None
        
        # Start A* search
        start_node = PathNode(start_x, start_y, 0, 0)
        open_set = [start_node]
        closed_set = set()
        open_dict = {(start_x, start_y): start_node}
        
        max_iterations = 5000
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Get node with lowest f cost
            current = heapq.heappop(open_set)
            current_key = (current.x, current.y)
            
            if current_key in open_dict:
                del open_dict[current_key]
            
            closed_set.add(current_key)
            
            # Check if we reached goal
            if current.x == goal_x and current.y == goal_y:
                # Reconstruct path
                path = []
                node = current
                while node is not None:
                    path.append((float(node.x), float(node.y)))
                    node = node.parent
                path.reverse()
                
                logger.debug(f"Path found in {iterations} iterations, length: {len(path)}")
                self.last_path = path
                self.path_idx = 0
                return path
            
            # Explore neighbors
            for nx, ny, cost in self.get_neighbors(current.x, current.y, automap):
                neighbor_key = (nx, ny)
                
                if neighbor_key in closed_set:
                    continue
                
                g = current.g + cost
                h = self.heuristic(nx, ny, goal_x, goal_y)
                
                # Check if this neighbor is already in open set
                if neighbor_key in open_dict:
                    existing = open_dict[neighbor_key]
                    if g < existing.g:
                        # Found better path, update
                        existing.g = g
                        existing.f = g + h
                        existing.parent = current
                        heapq.heapify(open_set)
                else:
                    # New node
                    neighbor = PathNode(nx, ny, g, h)
                    neighbor.parent = current
                    open_dict[neighbor_key] = neighbor
                    heapq.heappush(open_set, neighbor)
        
        logger.warning(f"No path found after {iterations} iterations (max: {max_iterations})")
        return None
    
    def _find_nearest_walkable(self, x, y, automap, search_radius=10):
        """Find nearest walkable pixel within search radius."""
        for radius in range(1, search_radius + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    nx, ny = x + dx, y + dy
                    if self.is_walkable(nx, ny, automap):
                        return nx, ny
        return None, None
    
    def get_next_waypoint(self, current_x, current_y, lookahead=5):
        """
        Get next waypoint on current path.
        
        Args:
            current_x, current_y: Current position
            lookahead: How many steps ahead to look (for smoother movement)
        
        Returns:
            (target_x, target_y) for next waypoint, or None if path complete
        """
        if self.last_path is None or len(self.last_path) == 0:
            return None
        
        # Find closest point on path to current position
        min_dist = float('inf')
        closest_idx = self.path_idx
        
        for i in range(self.path_idx, min(self.path_idx + 20, len(self.last_path))):
            px, py = self.last_path[i]
            dist = np.sqrt((px - current_x)**2 + (py - current_y)**2)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        
        # Update path index
        self.path_idx = closest_idx
        
        # Look ahead for next waypoint
        lookahead_idx = min(self.path_idx + lookahead, len(self.last_path) - 1)
        
        if lookahead_idx >= len(self.last_path):
            return None
        
        target_x, target_y = self.last_path[lookahead_idx]
        return target_x, target_y
    
    def path_complete(self):
        """Check if current path is fully traversed."""
        if self.last_path is None:
            return True
        return self.path_idx >= len(self.last_path) - 1
    
    def clear_path(self):
        """Clear current path."""
        self.last_path = None
        self.path_idx = 0
