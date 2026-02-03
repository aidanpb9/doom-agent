"""
Node placement system for sector-based navigation.
Intelligently places navigation nodes in safe, visitable areas within sectors.
"""

import numpy as np
import logging
from typing import List, Tuple, Dict, Optional, Set
from agent.nav.sector_geometry import SectorPolygon

logger = logging.getLogger(__name__)


class NavigationNode:
    """Represents a navigation waypoint in a sector."""
    
    def __init__(self, node_id: int, sector_id: int, x: float, y: float, is_safe: bool = True):
        self.node_id = node_id
        self.sector_id = sector_id
        self.x = x
        self.y = y
        self.is_safe = is_safe
        self.visited = False
        self.visit_count = 0
    
    def distance_to(self, x: float, y: float) -> float:
        """Calculate Euclidean distance to point."""
        return np.sqrt((self.x - x)**2 + (self.y - y)**2)
    
    def __repr__(self):
        return f"Node({self.node_id}, sector={self.sector_id}, pos=({self.x:.1f},{self.y:.1f}), safe={self.is_safe})"


class NodePlacement:
    """Manages placement of navigation nodes in sectors."""
    
    def __init__(self, min_distance_between_nodes: float = 100.0):
        """
        Initialize node placement system.
        
        Args:
            min_distance_between_nodes: Minimum distance to maintain between nodes
        """
        self.nodes: Dict[int, NavigationNode] = {}
        self.next_node_id = 0
        self.min_distance = min_distance_between_nodes
        self.node_count_per_sector = {}
    
    def place_nodes_in_sectors(self, 
                              sectors: Dict[int, SectorPolygon],
                              automap: Optional[np.ndarray] = None,
                              automap_scale: float = 1.0) -> Dict[int, List[NavigationNode]]:
        """
        Place navigation nodes in all sectors.
        
        Strategy:
        - For each sector, compute candidate positions
        - Validate walkability using automap if available
        - Place node at center or offset if center is blocked
        - Multiple nodes for large sectors
        
        Args:
            sectors: Dictionary of sector_id -> SectorPolygon
            automap: Optional automap buffer for walkability validation
            automap_scale: Scale factor from world coordinates to automap
        
        Returns:
            Dictionary of sector_id -> List[NavigationNode]
        """
        sector_nodes = {sid: [] for sid in sectors.keys()}
        
        for sector_id, polygon in sectors.items():
            # Determine how many nodes this sector needs
            area = polygon.get_area()
            node_count = max(1, int(area / 10000.0) + 1)  # 1 node per ~10k units
            
            self.node_count_per_sector[sector_id] = node_count
            
            # Generate candidate positions
            candidates = self._generate_candidates(polygon, node_count)
            
            # Place nodes at candidates
            for x, y in candidates:
                # Check walkability
                is_safe = True
                if automap is not None:
                    is_safe = self._is_walkable_on_automap(x, y, automap, automap_scale)
                
                if is_safe:
                    node = NavigationNode(self.next_node_id, sector_id, x, y, is_safe=True)
                    self.nodes[self.next_node_id] = node
                    sector_nodes[sector_id].append(node)
                    self.next_node_id += 1
            
            # Log placement
            placed = len(sector_nodes[sector_id])
            logger.debug(f"Sector {sector_id}: placed {placed}/{node_count} nodes (area={area:.0f})")
        
        logger.info(f"Placed {len(self.nodes)} total navigation nodes across {len(sectors)} sectors")
        return sector_nodes
    
    def _generate_candidates(self, polygon: SectorPolygon, count: int) -> List[Tuple[float, float]]:
        """
        Generate candidate positions for node placement in sector.
        
        Uses a combination of:
        - Center position
        - Positions offset from center toward walls (for large sectors)
        - Grid-based sampling for very large sectors
        """
        candidates = []
        
        center_x, center_y = polygon.get_center()
        candidates.append((center_x, center_y))
        
        if count > 1:
            # For larger sectors, add offset candidates
            width = polygon.max_x - polygon.min_x
            height = polygon.max_y - polygon.min_y
            
            # Add candidates in quadrants
            if count >= 2:
                # Quadrant offsets
                offsets = [
                    (-width * 0.25, -height * 0.25),  # NW
                    (width * 0.25, -height * 0.25),   # NE
                    (-width * 0.25, height * 0.25),   # SW
                    (width * 0.25, height * 0.25),    # SE
                ]
                
                for i, (ox, oy) in enumerate(offsets):
                    if len(candidates) < count:
                        candidates.append((center_x + ox, center_y + oy))
            
            # Add grid-based candidates for very large sectors
            if count > 5:
                grid_spacing = max(width, height) / (int(np.sqrt(count)) + 1)
                for x in np.arange(polygon.min_x, polygon.max_x, grid_spacing):
                    for y in np.arange(polygon.min_y, polygon.max_y, grid_spacing):
                        if len(candidates) >= count:
                            break
                        if polygon.contains_point(x, y):
                            candidates.append((x, y))
        
        return candidates[:count]
    
    def _is_walkable_on_automap(self, x: float, y: float, automap: np.ndarray,
                                scale: float = 1.0, search_radius: int = 10) -> bool:
        """
        Check if position is walkable on automap.
        Returns True if position or nearby position is walkable.
        
        Args:
            x, y: World coordinates
            automap: Automap buffer (grayscale)
            scale: Scale factor from world to automap coordinates
            search_radius: Radius to search for walkable area
        
        Returns:
            True if position is (or nearby area is) walkable
        """
        if automap is None or len(automap) == 0:
            return True  # Assume walkable if no map available
        
        # Convert to automap coordinates
        map_x = int(x * scale)
        map_y = int(y * scale)
        
        # Check bounds
        h, w = automap.shape
        if map_x < 0 or map_x >= w or map_y < 0 or map_y >= h:
            return False
        
        # Walkable pixels have values in range [20, 120] typically
        # Empty/walkable: ~96, walls: darker or ~0
        pixel = automap[map_y, map_x]
        
        if 20 <= pixel < 120:
            return True
        
        # Search nearby for walkable position
        for r in range(1, search_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx = map_x + dx
                    ny = map_y + dy
                    
                    if 0 <= nx < w and 0 <= ny < h:
                        if 20 <= automap[ny, nx] < 120:
                            return True
        
        return False
    
    def get_nearest_node(self, x: float, y: float, sector_id: Optional[int] = None) -> Optional[NavigationNode]:
        """
        Get nearest navigation node to position.
        
        Args:
            x, y: Position to search from
            sector_id: If provided, only search in this sector
        
        Returns:
            Nearest NavigationNode or None
        """
        candidates = []
        
        for node in self.nodes.values():
            if sector_id is not None and node.sector_id != sector_id:
                continue
            
            distance = node.distance_to(x, y)
            candidates.append((distance, node))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    
    def get_nodes_in_sector(self, sector_id: int) -> List[NavigationNode]:
        """Get all nodes in a specific sector."""
        return [n for n in self.nodes.values() if n.sector_id == sector_id]
    
    def get_unvisited_nodes(self) -> List[NavigationNode]:
        """Get all unvisited nodes."""
        return [n for n in self.nodes.values() if not n.visited]
    
    def get_unvisited_nodes_in_sector(self, sector_id: int) -> List[NavigationNode]:
        """Get unvisited nodes in a specific sector."""
        return [n for n in self.nodes.values() if not n.visited and n.sector_id == sector_id]
    
    def mark_node_visited(self, node_id: int):
        """Mark a node as visited."""
        if node_id in self.nodes:
            self.nodes[node_id].visited = True
            self.nodes[node_id].visit_count += 1
    
    def get_node_by_id(self, node_id: int) -> Optional[NavigationNode]:
        """Get node by ID."""
        return self.nodes.get(node_id)
    
    def get_coverage_stats(self) -> Dict:
        """Get statistics about node coverage."""
        total_nodes = len(self.nodes)
        visited_nodes = sum(1 for n in self.nodes.values() if n.visited)
        safe_nodes = sum(1 for n in self.nodes.values() if n.is_safe)
        
        return {
            'total_nodes': total_nodes,
            'visited_nodes': visited_nodes,
            'unvisited_nodes': total_nodes - visited_nodes,
            'safe_nodes': safe_nodes,
            'coverage': visited_nodes / total_nodes if total_nodes > 0 else 0.0
        }
    
    def reset(self):
        """Reset all nodes to unvisited."""
        for node in self.nodes.values():
            node.visited = False
            node.visit_count = 0
