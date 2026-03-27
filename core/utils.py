"""Contain resuable functions."""
from math import sqrt
from pathlib import Path
import struct
import re
MAP_MARKER_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$")

def calculate_euclidean_distance(point1_x, point1_y, point2_x, point2_y) -> float:
    """Distance between 2 points formula."""
    return sqrt((point2_x - point1_x)**2 + (point2_y - point1_y)**2)

def normalize_angle(angle_deg: float) -> float:
    """Wrap an angle -180 to 180 deg."""
    return (angle_deg + 180.0) % 360.0 - 180.0

def load_blocking_segments_from_wad(wad_path: str, map_name: str) -> list[tuple[float, float, float, float]]:
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
    return segments

def segments_intersect(
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

