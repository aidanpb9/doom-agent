"""Contain resuable functions."""
from config.constants import OBSTACLE_KEYWORDS, OBSTACLE_RADIUS
from math import sqrt
from pathlib import Path
from functools import lru_cache
import struct
import re
MAP_MARKER_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$")
#Slack on the bounding box overlap test. _segments_intersect counts walls that touch the line
#within a tiny tolerance (1e-6), so the box test must not skip a wall that only just misses.
BOX_MARGIN = 1e-3



def calculate_euclidean_distance(point1_x, point1_y, point2_x, point2_y) -> float:
    """Distance between 2 points formula."""
    return sqrt((point2_x - point1_x)**2 + (point2_y - point1_y)**2)

def normalize_angle(angle_deg: float) -> float:
    """Wrap an angle -180 to 180 deg."""
    return (angle_deg + 180.0) % 360.0 - 180.0

@lru_cache(maxsize=64) #big enough to cache all doom maps
def load_blocking_segments_from_wad(wad_path: str, map_name: str) -> tuple[tuple[float, float, float, float], ...]:
    """Get wall data for better combat."""
    if not wad_path or not map_name:
        return []
    
    raw = Path(wad_path).read_bytes()
    ident, num_lumps, dir_ofs = struct.unpack_from("<4sii", raw, 0)
    if ident not in (b"IWAD", b"PWAD"):
        return []

    directory: list[tuple[str, int, int]] = []
    for index in range(num_lumps):
        pos, size, name_raw = struct.unpack_from("<ii8s", raw, dir_ofs + index * 16)
        name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="ignore").upper()
        directory.append((name, pos, size))

    marker = map_name.upper()
    marker_idx = -1
    for index, (name, _pos, _size) in enumerate(directory):
        if name == marker:
            marker_idx = index
            break
    if marker_idx < 0:
        return []

    map_lumps: dict[str, tuple[int, int]] = {}
    for name, pos, size in directory[marker_idx + 1 :]:
        if name == "ENDMAP" or MAP_MARKER_RE.match(name):
            break
        if name not in map_lumps:
            map_lumps[name] = (pos, size)
    if "VERTEXES" not in map_lumps or "LINEDEFS" not in map_lumps:
        return []

    vx_pos, vx_size = map_lumps["VERTEXES"]
    vertices: list[tuple[float, float]] = []
    for off in range(0, vx_size, 4):
        x, y = struct.unpack_from("<hh", raw, vx_pos + off)
        vertices.append((float(x), float(y)))

    ld_pos, ld_size = map_lumps["LINEDEFS"]
    segments: list[tuple[float, float, float, float]] = []
    for off in range(0, ld_size, 14):
        v1, v2, flags, _special, _tag, _right, left = struct.unpack_from("<hhhhhhh", raw, ld_pos + off)
        if not (flags & 0x0001) and int(left) >= 0:
            continue
        if not (0 <= v1 < len(vertices) and 0 <= v2 < len(vertices)):
            continue
        x1, y1 = vertices[v1]
        x2, y2 = vertices[v2]
        segments.append((x1, y1, x2, y2))
    
    if "THINGS" in map_lumps:
        th_pos, th_size = map_lumps["THINGS"]
        for off in range(0, th_size, 10):
            x, y, _angle, type_id, _flags = struct.unpack_from("<hhhhh", raw, th_pos + off)
            if type_id not in OBSTACLE_KEYWORDS:
                continue
            cx, cy, r = float(x), float(y), OBSTACLE_RADIUS
            segments.append((cx - r, cy - r, cx + r, cy - r))
            segments.append((cx + r, cy - r, cx + r, cy + r))
            segments.append((cx + r, cy + r, cx - r, cy + r))
            segments.append((cx - r, cy + r, cx - r, cy - r))
    return tuple(segments)

def has_clear_world_line(
        player_x: float,
        player_y: float,
        object_x: float | None,
        object_y: float | None,
        bounded_segments: tuple[tuple[float, ...], ...]
    ) -> bool:
        """Use blocking segments to determine if the agent has a clear line.
        Used for enemies and loot. bounded_segments comes from build_segment_bounds.
        A wall can only cross the line if its bounding box overlaps the line's bounding box,
        so segments whose box doesn't overlap are skipped before the exact intersection test."""
        if object_x is None or object_y is None or not bounded_segments:
            return True
        
        line_start = (float(player_x), float(player_y))
        line_end = (float(object_x), float(object_y))
        line_min_x, line_max_x = sorted((line_start[0], line_end[0]))
        line_min_y, line_max_y = sorted((line_start[1], line_end[1]))

        for min_x, max_x, min_y, max_y, x1, y1, x2, y2 in bounded_segments:
            if (max_x < line_min_x - BOX_MARGIN or min_x > line_max_x + BOX_MARGIN
                    or max_y < line_min_y - BOX_MARGIN or min_y > line_max_y + BOX_MARGIN):
                continue
            if _segments_intersect(line_start, line_end, (x1, y1), (x2, y2)):
                return False
        return True

def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Shortest distance from point (px,py) to line segment (x1,y1)-(x2,y2).
    Used to check if an anchor position is dangerously close to a wall."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return calculate_euclidean_distance(px, py, x1, y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return calculate_euclidean_distance(px, py, x1 + t * dx, y1 + t * dy)


def build_segment_bounds(
        segments: list[tuple[float, float, float, float]]
    ) -> tuple[tuple[float, ...], ...]:
    """Pair each segment with its bounding box as (min_x, max_x, min_y, max_y, x1, y1, x2, y2).
    Build once per map so is_near_any_segment can skip far-away segments cheaply."""
    return tuple(
        (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2), x1, y1, x2, y2)
        for x1, y1, x2, y2 in segments
    )


def is_near_any_segment(
        px: float,
        py: float,
        bounded_segments: tuple[tuple[float, ...], ...],
        distance: float
    ) -> bool:
    """True if (px, py) is closer than distance to any segment.
    bounded_segments comes from build_segment_bounds. A segment lies inside its bounding box,
    so a point more than distance outside that box can't be within distance of the segment.
    Those segments are skipped before the exact (slower) distance test."""
    for min_x, max_x, min_y, max_y, x1, y1, x2, y2 in bounded_segments:
        if px < min_x - distance or px > max_x + distance or py < min_y - distance or py > max_y + distance:
            continue
        if point_to_segment_distance(px, py, x1, y1, x2, y2) < distance:
            return True
    return False


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    q1: tuple[float, float],
    q2: tuple[float, float],
) -> bool:
    """Return True if line segment p1-p2 intersects line segment q1-q2."""
    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)

    if ((o1 > 0.0 and o2 < 0.0) or (o1 < 0.0 and o2 > 0.0)) and ((o3 > 0.0 and o4 < 0.0) or (o3 < 0.0 and o4 > 0.0)):
        return True
    if abs(o1) <= 1e-6 and _on_segment(p1, p2, q1):
        return True
    if abs(o2) <= 1e-6 and _on_segment(p1, p2, q2):
        return True
    if abs(o3) <= 1e-6 and _on_segment(q1, q2, p1):
        return True
    if abs(o4) <= 1e-6 and _on_segment(q1, q2, p2):
        return True
    return False

def _orientation(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Used in utils.segments_intersect."""
    return ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0]))

def _on_segment(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    *,
    eps: float = 1e-6,
) -> bool:
    """Used in utils.segments_intersect."""
    return (
        min(a[0], b[0]) - eps <= c[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= c[1] <= max(a[1], b[1]) + eps)

