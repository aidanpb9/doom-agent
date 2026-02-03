"""
Sector geometry builder for DOOM level analysis.
Parses sector and line data to create traversable geometry.
"""

import numpy as np
import logging
from typing import List, Tuple, Dict, Optional, Set

logger = logging.getLogger(__name__)


class LineSegment:
    """Represents a line segment in sector geometry."""
    
    def __init__(self, x1: float, y1: float, x2: float, y2: float, line_id: int = -1):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.line_id = line_id
        self.length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def point_at_distance(self, distance: float) -> Tuple[float, float]:
        """Get point along line at given distance from start."""
        if self.length == 0:
            return self.x1, self.y1
        
        t = distance / self.length
        t = max(0, min(1, t))
        
        x = self.x1 + t * (self.x2 - self.x1)
        y = self.y1 + t * (self.y2 - self.y1)
        return x, y
    
    def midpoint(self) -> Tuple[float, float]:
        """Get midpoint of line segment."""
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2


class SectorPolygon:
    """Represents the polygon boundary of a sector."""
    
    def __init__(self, sector_id: int, lines: List[LineSegment], floor_height: float = 0.0):
        self.sector_id = sector_id
        self.lines = lines
        self.floor_height = floor_height
        self._compute_bounds()
    
    def _compute_bounds(self):
        """Compute bounding box of sector."""
        if not self.lines:
            self.min_x = self.min_y = self.max_x = self.max_y = 0
            return
        
        all_points = []
        for line in self.lines:
            all_points.extend([(line.x1, line.y1), (line.x2, line.y2)])
        
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        
        self.min_x = min(xs)
        self.max_x = max(xs)
        self.min_y = min(ys)
        self.max_y = max(ys)
    
    def get_center(self) -> Tuple[float, float]:
        """Get geometric center of sector."""
        return (self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2
    
    def get_area(self) -> float:
        """Compute area of sector polygon using shoelace formula."""
        if len(self.lines) < 3:
            return 0
        
        # Collect all vertices in order
        vertices = []
        for line in self.lines:
            if not vertices or vertices[-1] != (line.x1, line.y1):
                vertices.append((line.x1, line.y1))
        
        # Shoelace formula
        area = 0
        for i in range(len(vertices)):
            x1, y1 = vertices[i]
            x2, y2 = vertices[(i + 1) % len(vertices)]
            area += x1 * y2 - x2 * y1
        
        return abs(area) / 2
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside sector polygon using ray casting."""
        # Get vertices from lines
        vertices = []
        for line in self.lines:
            if not vertices or vertices[-1] != (line.x1, line.y1):
                vertices.append((line.x1, line.y1))
        
        if len(vertices) < 3:
            return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y
        
        # Ray casting algorithm
        inside = False
        p1x, p1y = vertices[0]
        
        for i in range(1, len(vertices) + 1):
            p2x, p2y = vertices[i % len(vertices)]
            
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            
            p1x, p1y = p2x, p2y
        
        return inside
    
    def get_adjacent_lines(self) -> List[int]:
        """Get list of line IDs that border this sector."""
        return [line.line_id for line in self.lines if line.line_id >= 0]


class SectorGeometry:
    """Manages geometry data for all sectors in a level."""
    
    def __init__(self):
        self.sectors: Dict[int, SectorPolygon] = {}
        self.lines: Dict[int, LineSegment] = {}
        self.sector_adjacencies: Dict[int, Set[int]] = {}
        self.visited_sectors: Set[int] = set()
        self.secret_sectors: Set[int] = set()
        self._line_sector_pairs: List[Tuple[Optional[int], Optional[int]]] = []
    
    def build_from_state(self, state) -> bool:
        """
        Build sector geometry from ViZDoom game state.
        
        Args:
            state: ViZDoom game state with sectors and lines attributes
        
        Returns:
            True if geometry was built successfully
        """
        if not hasattr(state, 'sectors') or state.sectors is None:
            logger.warning("No sectors in game state")
            return False
        
        if not hasattr(state, 'lines') or state.lines is None:
            logger.warning("No lines in game state")
            return False
        
        self.sectors = {}
        self.lines = {}
        self.sector_adjacencies = {}
        self.visited_sectors.clear()
        self.secret_sectors.clear()

        sectors = state.sectors
        lines = state.lines
        
        logger.info(f"Building geometry from {len(sectors)} sectors and {len(lines)} lines")
        
        # First pass: create all line segments
        self._line_sector_pairs = []
        for i, line in enumerate(lines):
            if hasattr(line, 'x1') and hasattr(line, 'x2'):
                line_seg = LineSegment(
                    float(line.x1), float(line.y1),
                    float(line.x2), float(line.y2),
                    line_id=i
                )
                self.lines[i] = line_seg
            self._line_sector_pairs.append(self._extract_line_sector_pair(line))
        
        # Second pass: create sector polygons
        for i, sector in enumerate(sectors):
            try:
                if self._is_secret_sector(sector):
                    self.secret_sectors.add(i)
                    continue

                # Get lines for this sector (if available)
                sector_lines = []
                
                # If sector has line indices
                if hasattr(sector, 'line_indices'):
                    for line_idx in sector.line_indices:
                        if line_idx in self.lines:
                            sector_lines.append(self.lines[line_idx])
                if not sector_lines:
                    # Fall back to line front/back sector references
                    for line_idx, (front, back) in enumerate(self._line_sector_pairs):
                        if front == i or back == i:
                            if line_idx in self.lines:
                                sector_lines.append(self.lines[line_idx])
                
                # Get floor height
                floor_height = 0.0
                if hasattr(sector, 'floor_height'):
                    floor_height = float(sector.floor_height)
                
                polygon = SectorPolygon(i, sector_lines, floor_height)
                self.sectors[i] = polygon
                
            except Exception as e:
                logger.warning(f"Failed to process sector {i}: {e}")
                continue
        
        # Third pass: compute adjacencies
        self._compute_adjacencies()
        
        if self.secret_sectors:
            logger.info(f"Skipped {len(self.secret_sectors)} secret sectors")
        logger.info(f"Built geometry for {len(self.sectors)} sectors")
        return len(self.sectors) > 0
    
    def _compute_adjacencies(self):
        """Compute which sectors are adjacent (share lines or line front/back)."""
        self.sector_adjacencies = {sid: set() for sid in self.sectors.keys()}

        # Prefer line front/back relationships when available
        if self._line_sector_pairs:
            found_pair = False
            for front, back in self._line_sector_pairs:
                if front is None or back is None:
                    continue
                if front in self.sectors and back in self.sectors and front != back:
                    self.sector_adjacencies[front].add(back)
                    self.sector_adjacencies[back].add(front)
                    found_pair = True
            if found_pair:
                return

        # Fallback: infer adjacency by shared line IDs
        for sector_id, polygon in self.sectors.items():
            adjacent_line_ids = set(polygon.get_adjacent_lines())
            for other_id, other_polygon in self.sectors.items():
                if other_id != sector_id:
                    other_lines = set(other_polygon.get_adjacent_lines())
                    if adjacent_line_ids & other_lines:
                        self.sector_adjacencies[sector_id].add(other_id)
    
    def get_sector_by_position(self, x: float, y: float) -> Optional[int]:
        """Find which sector contains the given position."""
        for sector_id, polygon in self.sectors.items():
            if polygon.contains_point(x, y):
                return sector_id
        
        return None
    
    def get_adjacent_sectors(self, sector_id: int) -> Set[int]:
        """Get IDs of sectors adjacent to the given sector."""
        return self.sector_adjacencies.get(sector_id, set())
    
    def get_unvisited_adjacent_sectors(self, sector_id: int) -> Set[int]:
        """Get adjacent sectors that haven't been visited yet."""
        adjacent = self.get_adjacent_sectors(sector_id)
        return adjacent - self.visited_sectors
    
    def mark_sector_visited(self, sector_id: int):
        """Mark a sector as visited."""
        if sector_id in self.sectors:
            self.visited_sectors.add(sector_id)
    
    def get_visited_count(self) -> int:
        """Get number of visited sectors."""
        return len(self.visited_sectors)
    
    def get_total_count(self) -> int:
        """Get total number of sectors."""
        return len(self.sectors)
    
    def get_exploration_progress(self) -> float:
        """Get exploration progress as percentage (0-1)."""
        total = len(self.sectors)
        if total == 0:
            return 0.0
        return len(self.visited_sectors) / total
    
    def reset(self):
        """Reset visited sectors."""
        self.visited_sectors.clear()

    def get_world_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Get overall world bounds from line geometry."""
        if not self.lines:
            return None
        xs = []
        ys = []
        for line in self.lines.values():
            xs.extend([line.x1, line.x2])
            ys.extend([line.y1, line.y2])
        return (min(xs), max(xs), min(ys), max(ys))

    def _is_secret_sector(self, sector) -> bool:
        secret_flag = getattr(sector, "secret", False) or getattr(sector, "is_secret", False)
        if secret_flag:
            return True
        special = None
        for attr in ("special", "special_type", "sector_special", "specials"):
            if hasattr(sector, attr):
                special = getattr(sector, attr)
                break
        if special is None:
            return False
        try:
            return int(special) == 9
        except Exception:
            return False

    def _extract_line_sector_pair(self, line) -> Tuple[Optional[int], Optional[int]]:
        front = None
        back = None
        for attr in ("front_sector", "frontsector", "front"):
            if hasattr(line, attr):
                front = getattr(line, attr)
                break
        for attr in ("back_sector", "backsector", "back"):
            if hasattr(line, attr):
                back = getattr(line, attr)
                break
        try:
            front = int(front) if front is not None else None
        except Exception:
            front = None
        try:
            back = int(back) if back is not None else None
        except Exception:
            back = None
        return (front, back)
