#!/usr/bin/env python3
"""Generate json nodes for loading into Graph and a map image (SVG) that highlights
the sector-level A* route from player start to exit. No gameplay control logic is included.

Usage:
    # Single map — outputs SVG and JSON for E1M1
    python maps/tools/navigation_planner.py --wad maps/wads/doom.wad --map E1M1

    # Specify output SVG path explicitly
    python maps/tools/navigation_planner.py --wad maps/wads/doom.wad --map E1M1 --out maps/svg/E1M1.svg

    # Generate SVG for every map in the WAD (outputs to maps/svg/all_maps_astar/)
    python maps/tools/navigation_planner.py --wad maps/wads/doom.wad --all-maps

    # Custom output directory for --all-maps
    python maps/tools/navigation_planner.py --wad maps/wads/doom.wad --all-maps --out-dir maps/svg/custom/
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NORMAL_EXIT_SPECIALS = {11, 52, 197}
SECRET_EXIT_SPECIALS = {51, 124}
EXIT_SPECIALS = NORMAL_EXIT_SPECIALS | SECRET_EXIT_SPECIALS
MAP_MARKER_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$")
BARREL_THING_TYPES = {2035}
BARREL_RADIUS = 16.0
DAMAGING_SECTOR_SPECIALS = {4, 5, 7, 11, 16}
DAMAGING_SECTOR_PENALTY = 8192.0
SVG_PAD = 30.0
SVG_WIDTH = 1400.0
SVG_HEIGHT = 1000.0
_SECTOR_BOUNDARY_CACHE: dict[int, dict[int, list[tuple[tuple[float, float], tuple[float, float]]]]] = {}
_SECTOR_BBOX_CACHE: dict[int, dict[int, tuple[float, float, float, float]]] = {}
_BARREL_OBSTACLE_CACHE: dict[int, list["BarrelObstacle"]] = {}
_LINEDEF_GEOM_CACHE: dict[int, list[tuple[tuple[float, float], tuple[float, float], tuple[float, float, float, float], frozenset[int]]]] = {}
_SEGMENT_INVALID_CACHE: dict[
    tuple[
        int,
        int,
        int,
        int,
        tuple[tuple[float, float], tuple[float, float]],
    ],
    bool,
] = {}

# Key bitmask
KEY_BLUE = 1
KEY_YELLOW = 2
KEY_RED = 4

# Classic Doom key things (cards + skull keys).
THING_KEY_MASK = {
    5: KEY_BLUE,    # Blue keycard
    6: KEY_YELLOW,  # Yellow keycard
    13: KEY_RED,    # Red keycard
    40: KEY_BLUE,   # Blue skull key
    39: KEY_YELLOW, # Yellow skull key
    38: KEY_RED,    # Red skull key
}

# Classic lock linedef specials (Doom 1/2 common set).
SPECIAL_REQ_KEY = {
    # D1/D2 classic key doors/switches/common lock actions
    26: KEY_BLUE,
    27: KEY_YELLOW,
    28: KEY_RED,
    32: KEY_BLUE,
    33: KEY_RED,
    34: KEY_YELLOW,
    99: KEY_BLUE,
    133: KEY_BLUE,
    134: KEY_RED,
    135: KEY_YELLOW,
    136: KEY_BLUE,
    137: KEY_RED,
    138: KEY_YELLOW,
}


@dataclass
class Linedef:
    v1: int
    v2: int
    sidefront: int
    sideback: int
    special: int
    blocking: bool


@dataclass
class ParsedMap:
    vertices: list[tuple[float, float]]
    sidedefs: list[int]
    sectors: list[dict[str, Any]]
    linedefs: list[Linedef]
    things: list[dict[str, Any]]


@dataclass
class BarrelObstacle:
    center: tuple[float, float]
    radius: float
    segments: list[tuple[tuple[float, float], tuple[float, float]]]


def parse_scalar(raw: str) -> Any:
    v = raw.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    lv = v.lower()
    if lv == "true":
        return True
    if lv == "false":
        return False
    try:
        if "." in v:
            return float(v)
        return int(v)
    except Exception:
        return v


def parse_textmap(text: str) -> ParsedMap:
    block_re = re.compile(r"(?is)\b([A-Za-z_][A-Za-z0-9_]*)\b[^\{]*\{(.*?)\}")
    kv_re = re.compile(r"(?is)\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+);")

    vertices: list[tuple[float, float]] = []
    sidedefs: list[int] = []
    sectors: list[dict[str, Any]] = []
    linedefs: list[Linedef] = []
    things: list[dict[str, Any]] = []

    for block_name, body in block_re.findall(text):
        kind = block_name.lower()
        kv: dict[str, Any] = {}
        for k, v in kv_re.findall(body):
            kv[k.lower()] = parse_scalar(v)

        if kind == "vertex":
            vertices.append((float(kv.get("x", 0.0)), float(kv.get("y", 0.0))))
        elif kind == "sidedef":
            sidedefs.append(int(kv.get("sector", -1)))
        elif kind == "sector":
            sectors.append(kv)
        elif kind == "linedef":
            linedefs.append(
                Linedef(
                    v1=int(kv.get("v1", -1)),
                    v2=int(kv.get("v2", -1)),
                    sidefront=int(kv.get("sidefront", -1)),
                    sideback=int(kv.get("sideback", -1)),
                    special=int(kv.get("special", 0)),
                    blocking=bool(kv.get("blocking", False) or kv.get("blockplayers", False)),
                )
            )
        elif kind == "thing":
            things.append(kv)

    return ParsedMap(vertices=vertices, sidedefs=sidedefs, sectors=sectors, linedefs=linedefs, things=things)


def parse_classic_map(raw: bytes, map_lumps: dict[str, tuple[int, int]]) -> ParsedMap:
    if "VERTEXES" not in map_lumps or "LINEDEFS" not in map_lumps or "SIDEDEFS" not in map_lumps:
        raise RuntimeError("Classic map missing VERTEXES/LINEDEFS/SIDEDEFS")

    vx_pos, vx_size = map_lumps["VERTEXES"]
    vertices: list[tuple[float, float]] = []
    for off in range(0, vx_size, 4):
        x, y = struct.unpack_from("<hh", raw, vx_pos + off)
        vertices.append((float(x), float(y)))

    sd_pos, sd_size = map_lumps["SIDEDEFS"]
    sidedefs: list[int] = []
    for off in range(0, sd_size, 30):
        sector = struct.unpack_from("<h", raw, sd_pos + off + 28)[0]
        sidedefs.append(int(sector))

    ld_pos, ld_size = map_lumps["LINEDEFS"]
    linedefs: list[Linedef] = []
    for off in range(0, ld_size, 14):
        v1, v2, flags, special, tag, right, left = struct.unpack_from("<hhhhhhh", raw, ld_pos + off)
        linedefs.append(
            Linedef(
                v1=int(v1),
                v2=int(v2),
                sidefront=int(right),
                sideback=int(left),
                special=int(special),
                blocking=bool(flags & 0x0001),
            )
        )

    sectors: list[dict[str, Any]] = []
    if "SECTORS" in map_lumps:
        sec_pos, sec_size = map_lumps["SECTORS"]
        for off in range(0, sec_size, 26):
            floor_h, ceil_h = struct.unpack_from("<hh", raw, sec_pos + off)
            floor_tex = raw[sec_pos + off + 4 : sec_pos + off + 12].split(b"\0", 1)[0].decode("ascii", errors="ignore")
            ceil_tex = raw[sec_pos + off + 12 : sec_pos + off + 20].split(b"\0", 1)[0].decode("ascii", errors="ignore")
            light, special, tag = struct.unpack_from("<hhh", raw, sec_pos + off + 20)
            sectors.append(
                {
                    "floorheight": int(floor_h),
                    "ceilingheight": int(ceil_h),
                    "floor": floor_tex,
                    "ceiling": ceil_tex,
                    "light": int(light),
                    "special": int(special),
                    "tag": int(tag),
                }
            )

    things: list[dict[str, Any]] = []
    if "THINGS" in map_lumps:
        th_pos, th_size = map_lumps["THINGS"]
        for off in range(0, th_size, 10):
            x, y, angle, type_id, flags = struct.unpack_from("<hhhhh", raw, th_pos + off)
            things.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "angle": int(angle),
                    "type": int(type_id),
                    "flags": int(flags),
                }
            )

    return ParsedMap(vertices=vertices, sidedefs=sidedefs, sectors=sectors, linedefs=linedefs, things=things)


def read_wad_directory(wad_path: str) -> tuple[bytes, list[tuple[str, int, int]]]:
    raw = Path(wad_path).read_bytes()
    ident, num_lumps, dir_ofs = struct.unpack_from("<4sii", raw, 0)
    if ident not in (b"IWAD", b"PWAD"):
        raise RuntimeError(f"Unsupported WAD type: {ident!r}")

    directory: list[tuple[str, int, int]] = []
    for i in range(num_lumps):
        pos, size, name_raw = struct.unpack_from("<ii8s", raw, dir_ofs + i * 16)
        name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="ignore").upper()
        directory.append((name, pos, size))
    return raw, directory


def list_map_markers(wad_path: str) -> list[str]:
    _, directory = read_wad_directory(wad_path)
    maps = [name for name, _, _ in directory if MAP_MARKER_RE.match(name)]
    # Keep order of first appearance and drop duplicates.
    out: list[str] = []
    seen = set()
    for m in maps:
        if m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def load_map_data(wad_path: str, map_name: str) -> ParsedMap:
    raw, directory = read_wad_directory(wad_path)

    marker = map_name.upper()
    marker_idx = -1
    for i, (name, _, _) in enumerate(directory):
        if name == marker:
            marker_idx = i
            break
    if marker_idx < 0:
        raise RuntimeError(f"Map marker {map_name} not found in {wad_path}")

    map_lumps: dict[str, tuple[int, int]] = {}
    classic_lump_names = {
        "THINGS",
        "LINEDEFS",
        "SIDEDEFS",
        "VERTEXES",
        "SEGS",
        "SSECTORS",
        "NODES",
        "SECTORS",
        "REJECT",
        "BLOCKMAP",
        "BEHAVIOR",
    }
    for name, pos, size in directory[marker_idx + 1 :]:
        if name == "ENDMAP":
            break
        if MAP_MARKER_RE.match(name):
            break
        # Keep the first instance only, so later maps can never overwrite.
        if name not in map_lumps:
            map_lumps[name] = (pos, size)
        # Classic maps are complete once we have the known lump set.
        if "TEXTMAP" not in map_lumps and {"VERTEXES", "LINEDEFS", "SIDEDEFS"}.issubset(map_lumps.keys()):
            if all(k in map_lumps for k in ("THINGS", "SECTORS")):
                # We already have enough for this tool; continue no further.
                # This avoids accidental spill into the next map.
                if all(k in map_lumps for k in classic_lump_names if k in map_lumps):
                    break

    if "TEXTMAP" in map_lumps:
        pos, size = map_lumps["TEXTMAP"]
        text = raw[pos : pos + size].decode("utf-8", errors="ignore")
        return parse_textmap(text)

    return parse_classic_map(raw, map_lumps)


def dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def build_sector_centroids(pm: ParsedMap) -> dict[int, tuple[float, float]]:
    points_by_sector: dict[int, list[tuple[float, float]]] = {}
    for ld in pm.linedefs:
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(pm.vertices) or ld.v2 >= len(pm.vertices):
            continue
        p1 = pm.vertices[ld.v1]
        p2 = pm.vertices[ld.v2]
        for side in (ld.sidefront, ld.sideback):
            if side < 0 or side >= len(pm.sidedefs):
                continue
            sec = pm.sidedefs[side]
            if sec < 0:
                continue
            points_by_sector.setdefault(sec, []).extend([p1, p2])

    centroids: dict[int, tuple[float, float]] = {}
    for sec, pts in points_by_sector.items():
        if not pts:
            continue
        ux = sum(p[0] for p in pts) / len(pts)
        uy = sum(p[1] for p in pts) / len(pts)
        centroids[sec] = (ux, uy)
    return centroids


def build_sector_graph(pm: ParsedMap) -> dict[int, list[int]]:
    graph: dict[int, list[int]] = {}
    for ld in pm.linedefs:
        if ld.blocking:
            continue
        if ld.sidefront < 0 or ld.sideback < 0:
            continue
        if ld.sidefront >= len(pm.sidedefs) or ld.sideback >= len(pm.sidedefs):
            continue
        a = pm.sidedefs[ld.sidefront]
        b = pm.sidedefs[ld.sideback]
        if a < 0 or b < 0 or a == b:
            continue
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)
    return graph


def build_sector_transition_graph(pm: ParsedMap) -> dict[int, list[tuple[int, int]]]:
    graph: dict[int, list[tuple[int, int]]] = {}
    for ld in pm.linedefs:
        if ld.blocking:
            continue
        if ld.sidefront < 0 or ld.sideback < 0:
            continue
        if ld.sidefront >= len(pm.sidedefs) or ld.sideback >= len(pm.sidedefs):
            continue
        a = pm.sidedefs[ld.sidefront]
        b = pm.sidedefs[ld.sideback]
        if a < 0 or b < 0 or a == b:
            continue
        req = SPECIAL_REQ_KEY.get(ld.special, 0)
        graph.setdefault(a, []).append((b, req))
        graph.setdefault(b, []).append((a, req))
    return graph


def build_sector_key_mask(
    pm: ParsedMap,
    centroids: dict[int, tuple[float, float]],
    reachable_sectors: set[int] | None = None,
) -> dict[int, int]:
    out: dict[int, int] = {}
    for t in pm.things:
        ttype = int(t.get("type", 0))
        km = THING_KEY_MASK.get(ttype, 0)
        if km == 0:
            continue
        x = float(t.get("x", 0.0))
        y = float(t.get("y", 0.0))
        sector_space = centroids
        if reachable_sectors:
            filtered = {sec: c for sec, c in centroids.items() if sec in reachable_sectors}
            if filtered:
                sector_space = filtered
        sec = nearest_sector((x, y), sector_space)
        out[sec] = out.get(sec, 0) | km
    return out


def nearest_sector(pt: tuple[float, float], centroids: dict[int, tuple[float, float]]) -> int:
    best_sec = -1
    best_d = float("inf")
    for sec, c in centroids.items():
        d = dist2(pt, c)
        if d < best_d:
            best_d = d
            best_sec = sec
    if best_sec < 0:
        raise RuntimeError("No sectors found for nearest-sector query")
    return best_sec


def _sector_geometry(pm: ParsedMap) -> tuple[
    dict[int, list[tuple[tuple[float, float], tuple[float, float]]]],
    dict[int, tuple[float, float, float, float]],
]:
    key = id(pm)
    cached_bounds = _SECTOR_BOUNDARY_CACHE.get(key)
    cached_boxes = _SECTOR_BBOX_CACHE.get(key)
    if cached_bounds is not None and cached_boxes is not None:
        return cached_bounds, cached_boxes

    boundaries: dict[int, list[tuple[tuple[float, float], tuple[float, float]]]] = {}
    for ld in pm.linedefs:
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(pm.vertices) or ld.v2 >= len(pm.vertices):
            continue
        sec_f = _sector_of_side(pm, ld.sidefront)
        sec_b = _sector_of_side(pm, ld.sideback)
        if sec_f == sec_b:
            continue
        seg = (pm.vertices[ld.v1], pm.vertices[ld.v2])
        if sec_f >= 0:
            boundaries.setdefault(sec_f, []).append(seg)
        if sec_b >= 0:
            boundaries.setdefault(sec_b, []).append(seg)

    boxes: dict[int, tuple[float, float, float, float]] = {}
    for sec, segs in boundaries.items():
        xs = [p[0] for seg in segs for p in seg]
        ys = [p[1] for seg in segs for p in seg]
        boxes[sec] = (min(xs), min(ys), max(xs), max(ys))

    _SECTOR_BOUNDARY_CACHE[key] = boundaries
    _SECTOR_BBOX_CACHE[key] = boxes
    return boundaries, boxes


def _point_on_segment(
    pt: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    eps: float = 1e-4,
) -> bool:
    px, py = pt
    ax, ay = a
    bx, by = b
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    dot = (px - ax) * (px - bx) + (py - ay) * (py - by)
    return dot <= eps


def _point_in_sector_segments(
    pt: tuple[float, float],
    segs: list[tuple[tuple[float, float], tuple[float, float]]],
) -> bool:
    x, y = pt
    inside = False
    for a, b in segs:
        if _point_on_segment(pt, a, b):
            return True
        x1, y1 = a
        x2, y2 = b
        if (y1 > y) == (y2 > y):
            continue
        x_cross = x1 + ((y - y1) * (x2 - x1) / (y2 - y1))
        if x_cross >= x - 1e-6:
            inside = not inside
    return inside


def sector_of_point(
    pm: ParsedMap,
    pt: tuple[float, float],
    centroids: dict[int, tuple[float, float]],
    candidate_sectors: set[int] | None = None,
) -> int:
    boundaries, boxes = _sector_geometry(pm)
    x, y = pt
    candidates: list[tuple[float, int]] = []
    sector_ids = candidate_sectors if candidate_sectors is not None else set(boundaries.keys())
    for sec in sector_ids:
        bbox = boxes.get(sec)
        if bbox is not None:
            min_x, min_y, max_x, max_y = bbox
            if x < min_x - 1e-4 or x > max_x + 1e-4 or y < min_y - 1e-4 or y > max_y + 1e-4:
                continue
        c = centroids.get(sec)
        candidates.append((dist2(pt, c) if c is not None else 0.0, sec))
    candidates.sort(key=lambda item: item[0])
    for _d, sec in candidates:
        segs = boundaries.get(sec)
        if segs and _point_in_sector_segments(pt, segs):
            return sec
    if candidate_sectors:
        fallback = {sec: centroids[sec] for sec in candidate_sectors if sec in centroids}
        if fallback:
            return nearest_sector(pt, fallback)
    return nearest_sector(pt, centroids)


def _sector_meta(pm: ParsedMap, sec: int) -> dict[str, Any]:
    if 0 <= sec < len(pm.sectors):
        meta = pm.sectors[sec]
        if isinstance(meta, dict):
            return meta
    return {}


def _sector_is_damaging(pm: ParsedMap, sec: int) -> bool:
    meta = _sector_meta(pm, sec)
    try:
        special = int(meta.get("special", 0))
    except Exception:
        special = 0
    return special in DAMAGING_SECTOR_SPECIALS


def _sector_step_cost(
    pm: ParsedMap,
    centroids: dict[int, tuple[float, float]],
    cur_sec: int,
    nxt_sec: int,
) -> float:
    cost = math.sqrt(dist2(centroids[cur_sec], centroids[nxt_sec]))
    if _sector_is_damaging(pm, nxt_sec):
        cost += DAMAGING_SECTOR_PENALTY
    return cost


def a_star_sector_path(
    pm: ParsedMap,
    graph: dict[int, list[int]],
    centroids: dict[int, tuple[float, float]],
    start_sec: int,
    goal_sec: int,
) -> list[int]:
    if start_sec == goal_sec:
        return [start_sec]

    open_heap: list[tuple[float, int, int]] = []
    g: dict[int, float] = {start_sec: 0.0}
    parent: dict[int, int] = {}
    closed = set()
    counter = 0

    def heuristic(a: int, b: int) -> float:
        return math.sqrt(dist2(centroids[a], centroids[b]))

    heapq.heappush(open_heap, (heuristic(start_sec, goal_sec), counter, start_sec))

    while open_heap:
        _, _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal_sec:
            path = [cur]
            while cur in parent:
                cur = parent[cur]
                path.append(cur)
            path.reverse()
            return path

        closed.add(cur)
        for nxt in graph.get(cur, []):
            if nxt in closed:
                continue
            ng = g[cur] + _sector_step_cost(pm, centroids, cur, nxt)
            if ng >= g.get(nxt, float("inf")):
                continue
            g[nxt] = ng
            parent[nxt] = cur
            counter += 1
            f = ng + heuristic(nxt, goal_sec)
            heapq.heappush(open_heap, (f, counter, nxt))
    return []


def a_star_sector_path_with_keys(
    pm: ParsedMap,
    graph: dict[int, list[tuple[int, int]]],
    centroids: dict[int, tuple[float, float]],
    sector_keys: dict[int, int],
    start_sec: int,
    goal_sec: int,
) -> tuple[list[int], int]:
    start_keys = sector_keys.get(start_sec, 0)
    start_state = (start_sec, start_keys)

    open_heap: list[tuple[float, int, tuple[int, int]]] = []
    g: dict[tuple[int, int], float] = {start_state: 0.0}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    closed = set()
    counter = 0

    def heuristic(sec: int, goal: int) -> float:
        return math.sqrt(dist2(centroids[sec], centroids[goal]))

    heapq.heappush(open_heap, (heuristic(start_sec, goal_sec), counter, start_state))

    goal_state: tuple[int, int] | None = None
    while open_heap:
        _, _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        cur_sec, cur_keys = cur
        if cur_sec == goal_sec:
            goal_state = cur
            break
        closed.add(cur)

        for nxt_sec, req in graph.get(cur_sec, []):
            if (cur_keys & req) != req:
                continue
            nxt_keys = cur_keys | sector_keys.get(nxt_sec, 0)
            nxt = (nxt_sec, nxt_keys)
            if nxt in closed:
                continue
            ng = g[cur] + _sector_step_cost(pm, centroids, cur_sec, nxt_sec)
            if ng >= g.get(nxt, float("inf")):
                continue
            g[nxt] = ng
            parent[nxt] = cur
            counter += 1
            f = ng + heuristic(nxt_sec, goal_sec)
            heapq.heappush(open_heap, (f, counter, nxt))

    if goal_state is None:
        return [], start_keys

    states = [goal_state]
    cur = goal_state
    while cur in parent:
        cur = parent[cur]
        states.append(cur)
    states.reverse()

    sector_path = [s for s, _k in states]
    final_keys = states[-1][1] if states else start_keys
    return sector_path, final_keys


def connected_sector_component(graph: dict[int, list[int]], start_sec: int) -> set[int]:
    seen = {start_sec}
    stack = [start_sec]
    while stack:
        cur = stack.pop()
        for nxt in graph.get(cur, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            stack.append(nxt)
    return seen


def _triarea2(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (c[0] - a[0]) * (b[1] - a[1]) - (b[0] - a[0]) * (c[1] - a[1])


def _vequal(a: tuple[float, float], b: tuple[float, float], eps: float = 1e-6) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _sector_of_side(pm: ParsedMap, side: int) -> int:
    if side < 0 or side >= len(pm.sidedefs):
        return -1
    return pm.sidedefs[side]


def _shared_portal_segment(pm: ParsedMap, sec_a: int, sec_b: int) -> tuple[tuple[float, float], tuple[float, float]] | None:
    best = None
    best_len2 = -1.0
    for ld in pm.linedefs:
        a = _sector_of_side(pm, ld.sidefront)
        b = _sector_of_side(pm, ld.sideback)
        if not ((a == sec_a and b == sec_b) or (a == sec_b and b == sec_a)):
            continue
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(pm.vertices) or ld.v2 >= len(pm.vertices):
            continue
        p = pm.vertices[ld.v1]
        q = pm.vertices[ld.v2]
        l2 = dist2(p, q)
        if l2 > best_len2:
            best_len2 = l2
            best = (p, q)
    return best


def _orient_portal(
    p: tuple[float, float],
    q: tuple[float, float],
    from_pt: tuple[float, float],
    to_pt: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    mx = 0.5 * (p[0] + q[0])
    my = 0.5 * (p[1] + q[1])
    dx = to_pt[0] - from_pt[0]
    dy = to_pt[1] - from_pt[1]
    side_p = dx * (p[1] - my) - dy * (p[0] - mx)
    side_q = dx * (q[1] - my) - dy * (q[0] - mx)
    if side_p >= side_q:
        return p, q
    return q, p


def _build_portals(
    pm: ParsedMap,
    sector_path: list[int],
    centroids: dict[int, tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    portals: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i in range(len(sector_path) - 1):
        a = sector_path[i]
        b = sector_path[i + 1]
        seg = _shared_portal_segment(pm, a, b)
        if seg is None:
            continue
        from_pt = centroids.get(a, seg[0])
        to_pt = centroids.get(b, seg[1])
        portals.append(_orient_portal(seg[0], seg[1], from_pt, to_pt))
    return portals


def _portal_midpoint_chain(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    portals: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = [start_xy]
    for left, right in portals:
        pts.append((0.5 * (left[0] + right[0]), 0.5 * (left[1] + right[1])))
    pts.append(end_xy)
    return pts


def _funnel_path(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    portals: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[tuple[float, float]]:
    if not portals:
        return [start_xy, end_xy]

    corridor: list[tuple[tuple[float, float], tuple[float, float]]] = [
        ((start_xy[0], start_xy[1]), (start_xy[0], start_xy[1]))
    ]
    corridor.extend(portals)
    corridor.append(((end_xy[0], end_xy[1]), (end_xy[0], end_xy[1])))

    pts: list[tuple[float, float]] = [start_xy]
    apex = start_xy
    left = start_xy
    right = start_xy
    apex_i = 0
    left_i = 0
    right_i = 0

    i = 1
    while i < len(corridor):
        cur_left, cur_right = corridor[i]

        if _triarea2(apex, right, cur_right) <= 0.0:
            if _vequal(apex, right) or _triarea2(apex, left, cur_right) > 0.0:
                right = cur_right
                right_i = i
            else:
                pts.append(left)
                apex = left
                apex_i = left_i
                left = apex
                right = apex
                left_i = apex_i
                right_i = apex_i
                i = apex_i + 1
                continue

        if _triarea2(apex, left, cur_left) >= 0.0:
            if _vequal(apex, left) or _triarea2(apex, right, cur_left) < 0.0:
                left = cur_left
                left_i = i
            else:
                pts.append(right)
                apex = right
                apex_i = right_i
                left = apex
                right = apex
                left_i = apex_i
                right_i = apex_i
                i = apex_i + 1
                continue

        i += 1

    if not _vequal(pts[-1], end_xy):
        pts.append(end_xy)
    return pts


def _seg_intersection(ax: float, ay: float, bx: float, by: float, cx: float, cy: float, dx: float, dy: float) -> bool:
    def orient(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    def on_segment(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> bool:
        return min(px, qx) - 1e-6 <= rx <= max(px, qx) + 1e-6 and min(py, qy) - 1e-6 <= ry <= max(py, qy) + 1e-6

    o1 = orient(ax, ay, bx, by, cx, cy)
    o2 = orient(ax, ay, bx, by, dx, dy)
    o3 = orient(cx, cy, dx, dy, ax, ay)
    o4 = orient(cx, cy, dx, dy, bx, by)

    if (o1 > 0 and o2 < 0 or o1 < 0 and o2 > 0) and (o3 > 0 and o4 < 0 or o3 < 0 and o4 > 0):
        return True
    if abs(o1) <= 1e-6 and on_segment(ax, ay, bx, by, cx, cy):
        return True
    if abs(o2) <= 1e-6 and on_segment(ax, ay, bx, by, dx, dy):
        return True
    if abs(o3) <= 1e-6 and on_segment(cx, cy, dx, dy, ax, ay):
        return True
    if abs(o4) <= 1e-6 and on_segment(cx, cy, dx, dy, bx, by):
        return True
    return False


def _centroid_path_points(
    sector_path: list[int],
    centroids: dict[int, tuple[float, float]],
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for sec in sector_path:
        if sec in centroids:
            out.append(centroids[sec])
    return out


def build_sector_key_pickups(
    pm: ParsedMap,
    centroids: dict[int, tuple[float, float]],
    reachable_sectors: set[int] | None = None,
) -> dict[int, list[tuple[float, float]]]:
    out: dict[int, list[tuple[float, float]]] = {}
    for t in pm.things:
        ttype = int(t.get("type", 0))
        if THING_KEY_MASK.get(ttype, 0) == 0:
            continue
        x = float(t.get("x", 0.0))
        y = float(t.get("y", 0.0))
        sector_space = centroids
        if reachable_sectors:
            filtered = {sec: c for sec, c in centroids.items() if sec in reachable_sectors}
            if filtered:
                sector_space = filtered
        sec = nearest_sector((x, y), sector_space)
        out.setdefault(sec, []).append((x, y))
    return out


def _inject_sector_pickups(
    sector_path: list[int],
    path_points: list[tuple[float, float]],
    sector_pickups: dict[int, list[tuple[float, float]]],
) -> list[tuple[float, float]]:
    if len(path_points) != len(sector_path):
        return path_points

    out: list[tuple[float, float]] = []
    injected: set[int] = set()
    for sec, pt in zip(sector_path, path_points):
        out.append(pt)
        if sec in injected:
            continue
        pickups = sector_pickups.get(sec)
        if not pickups:
            continue
        inserted_pickup = False
        for pickup in pickups:
            if dist2(pt, pickup) > 4.0:
                out.append(pickup)
                inserted_pickup = True
        if inserted_pickup:
            out.append(pt)
        injected.add(sec)
    return out


def _collect_barrel_obstacles(pm: ParsedMap) -> list[BarrelObstacle]:
    cached = _BARREL_OBSTACLE_CACHE.get(id(pm))
    if cached is not None:
        return cached

    obstacles: list[BarrelObstacle] = []
    r = BARREL_RADIUS
    for thing in pm.things:
        if int(thing.get("type", 0)) not in BARREL_THING_TYPES:
            continue
        cx = float(thing.get("x", 0.0))
        cy = float(thing.get("y", 0.0))
        corners = [
            (cx - r, cy - r),
            (cx + r, cy - r),
            (cx + r, cy + r),
            (cx - r, cy + r),
        ]
        segments = [
            (corners[0], corners[1]),
            (corners[1], corners[2]),
            (corners[2], corners[3]),
            (corners[3], corners[0]),
        ]
        obstacles.append(BarrelObstacle(center=(cx, cy), radius=r, segments=segments))
    _BARREL_OBSTACLE_CACHE[id(pm)] = obstacles
    return obstacles


def _linedef_geometry(
    pm: ParsedMap,
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float, float, float], frozenset[int]]]:
    cached = _LINEDEF_GEOM_CACHE.get(id(pm))
    if cached is not None:
        return cached

    geom: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float, float, float], frozenset[int]]] = []
    for ld in pm.linedefs:
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(pm.vertices) or ld.v2 >= len(pm.vertices):
            continue
        p1 = pm.vertices[ld.v1]
        p2 = pm.vertices[ld.v2]
        bbox = (
            min(p1[0], p2[0]),
            min(p1[1], p2[1]),
            max(p1[0], p2[0]),
            max(p1[1], p2[1]),
        )
        sec_f = _sector_of_side(pm, ld.sidefront)
        sec_b = _sector_of_side(pm, ld.sideback)
        geom.append((p1, p2, bbox, frozenset((sec_f, sec_b))))
    _LINEDEF_GEOM_CACHE[id(pm)] = geom
    return geom


def _segment_cache_key(
    pm: ParsedMap,
    p: tuple[float, float],
    q: tuple[float, float],
    allowed_pairs: set[frozenset[int]],
    allowed_sectors: set[int] | None,
    centroids: dict[int, tuple[float, float]] | None,
) -> tuple[int, int, int, int, tuple[tuple[float, float], tuple[float, float]]]:
    a = (round(p[0], 4), round(p[1], 4))
    b = (round(q[0], 4), round(q[1], 4))
    seg = (a, b) if a <= b else (b, a)
    return (id(pm), id(allowed_pairs), id(allowed_sectors), id(centroids), seg)


def _segment_invalid_for_pairs(
    pm: ParsedMap,
    p: tuple[float, float],
    q: tuple[float, float],
    allowed_pairs: set[frozenset[int]],
    allowed_sectors: set[int] | None = None,
    centroids: dict[int, tuple[float, float]] | None = None,
) -> bool:
    cache_key = _segment_cache_key(pm, p, q, allowed_pairs, allowed_sectors, centroids)
    cached = _SEGMENT_INVALID_CACHE.get(cache_key)
    if cached is not None:
        return cached

    seg_min_x = min(p[0], q[0])
    seg_min_y = min(p[1], q[1])
    seg_max_x = max(p[0], q[0])
    seg_max_y = max(p[1], q[1])

    for (v1, v2, bbox, pair) in _linedef_geometry(pm):
        if bbox[2] < seg_min_x or bbox[0] > seg_max_x or bbox[3] < seg_min_y or bbox[1] > seg_max_y:
            continue
        x1, y1 = v1
        x2, y2 = v2
        if not _seg_intersection(p[0], p[1], q[0], q[1], x1, y1, x2, y2):
            continue

        # Touching a wall exactly at the segment endpoint is allowed (graph node on a corner).
        if (
            dist2(p, (x1, y1)) < 1e-4
            or dist2(p, (x2, y2)) < 1e-4
            or dist2(q, (x1, y1)) < 1e-4
            or dist2(q, (x2, y2)) < 1e-4
        ):
            continue

        if pair in allowed_pairs:
            continue
        _SEGMENT_INVALID_CACHE[cache_key] = True
        return True

    for barrel in _collect_barrel_obstacles(pm):
        if _segment_invalid_for_obstacles(p, q, barrel.segments):
            _SEGMENT_INVALID_CACHE[cache_key] = True
            return True
    if allowed_sectors and centroids:
        samples = max(8, min(48, int(math.sqrt(dist2(p, q)) / 32.0) + 1))
        for i in range(samples + 1):
            t = i / samples
            probe = (p[0] * (1.0 - t) + q[0] * t, p[1] * (1.0 - t) + q[1] * t)
            if sector_of_point(pm, probe, centroids) not in allowed_sectors:
                _SEGMENT_INVALID_CACHE[cache_key] = True
                return True
    _SEGMENT_INVALID_CACHE[cache_key] = False
    return False


def _build_obstacle_segments(
    pm: ParsedMap,
    allowed_pairs: set[frozenset[int]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for p1, p2, _bbox, pair in _linedef_geometry(pm):
        if pair in allowed_pairs:
            continue
        out.append((p1, p2))
    for barrel in _collect_barrel_obstacles(pm):
        out.extend(barrel.segments)
    return out


def _segment_invalid_for_obstacles(
    p: tuple[float, float],
    q: tuple[float, float],
    obstacles: list[tuple[tuple[float, float], tuple[float, float]]],
) -> bool:
    for a, b in obstacles:
        x1, y1 = a
        x2, y2 = b
        if not _seg_intersection(p[0], p[1], q[0], q[1], x1, y1, x2, y2):
            continue
        if (
            dist2(p, a) < 1e-4
            or dist2(p, b) < 1e-4
            or dist2(q, a) < 1e-4
            or dist2(q, b) < 1e-4
        ):
            continue
        return True
    return False


def _collect_pair_vertices(
    pm: ParsedMap,
    sec_a: int,
    sec_b: int,
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for ld in pm.linedefs:
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(pm.vertices) or ld.v2 >= len(pm.vertices):
            continue
        sec_f = _sector_of_side(pm, ld.sidefront)
        sec_back = _sector_of_side(pm, ld.sideback)
        if sec_f in (sec_a, sec_b) or sec_back in (sec_a, sec_b):
            pts.append(pm.vertices[ld.v1])
            pts.append(pm.vertices[ld.v2])
    return pts


def _dedupe_points(points: list[tuple[float, float]], eps2: float = 1.0) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if any(dist2(p, q) <= eps2 for q in out):
            continue
        out.append(p)
    return out


def _dedupe_consecutive_points(points: list[tuple[float, float]], eps2: float = 1.0) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if out and dist2(out[-1], p) <= eps2:
            continue
        out.append(p)
    return out


def _dist2_point_to_segment(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    vx = b[0] - a[0]
    vy = b[1] - a[1]
    wx = p[0] - a[0]
    wy = p[1] - a[1]
    c1 = vx * wx + vy * wy
    if c1 <= 0.0:
        return dist2(p, a)
    c2 = vx * vx + vy * vy
    if c2 <= 1e-9:
        return dist2(p, a)
    if c1 >= c2:
        return dist2(p, b)
    t = c1 / c2
    proj = (a[0] + t * vx, a[1] + t * vy)
    return dist2(p, proj)


def _move_toward(
    src: tuple[float, float],
    dst: tuple[float, float],
    dist: float,
) -> tuple[float, float]:
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    l2 = dx * dx + dy * dy
    if l2 <= 1e-9:
        return src
    l = math.sqrt(l2)
    t = min(1.0, dist / l)
    return (src[0] + dx * t, src[1] + dy * t)


def _node_clearance(
    pm: ParsedMap,
    p: tuple[float, float],
    allowed_pairs: set[frozenset[int]],
    obstacle_segments: list[tuple[tuple[float, float], tuple[float, float]]] | None = None,
) -> float:
    obstacles = obstacle_segments
    if obstacles is None:
        obstacles = _build_obstacle_segments(pm, allowed_pairs)
    best = float("inf")
    for a, b in obstacles:
        d2 = _dist2_point_to_segment(p, a, b)
        if d2 < best:
            best = d2
    if best == float("inf"):
        return 1e9
    return math.sqrt(best)


def _segment_clearance(
    pm: ParsedMap,
    p: tuple[float, float],
    q: tuple[float, float],
    allowed_pairs: set[frozenset[int]],
    samples: int = 7,
    obstacle_segments: list[tuple[tuple[float, float], tuple[float, float]]] | None = None,
) -> float:
    obstacles = obstacle_segments
    if obstacles is None:
        obstacles = _build_obstacle_segments(pm, allowed_pairs)
    best = float("inf")
    for a, b in obstacles:
        for s in range(samples):
            t = s / max(1, samples - 1)
            x = p[0] + (q[0] - p[0]) * t
            y = p[1] + (q[1] - p[1]) * t
            d2 = _dist2_point_to_segment((x, y), a, b)
            if d2 < best:
                best = d2
    if best == float("inf"):
        return 1e9
    return math.sqrt(best)


def _collect_dense_corridor_nodes(
    pm: ParsedMap,
    sector_path: list[int],
    centroids: dict[int, tuple[float, float]],
    start_xy: tuple[float, float],
    exit_xy: tuple[float, float],
) -> list[tuple[float, float]]:
    corridor = set(sector_path)
    nodes: list[tuple[float, float]] = [start_xy, exit_xy]
    for s in sector_path:
        if s in centroids:
            nodes.append(centroids[s])

    for ld in pm.linedefs:
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(pm.vertices) or ld.v2 >= len(pm.vertices):
            continue
        sec_f = _sector_of_side(pm, ld.sidefront)
        sec_b = _sector_of_side(pm, ld.sideback)
        if sec_f not in corridor and sec_b not in corridor:
            continue
        p = pm.vertices[ld.v1]
        q = pm.vertices[ld.v2]
        for sec in (sec_f, sec_b):
            if sec not in corridor or sec not in centroids:
                continue
            c = centroids[sec]
            for t in (0.2, 0.5, 0.8):
                e = (p[0] * (1.0 - t) + q[0] * t, p[1] * (1.0 - t) + q[1] * t)
                nodes.append(_move_toward(e, c, 28.0))

    for i in range(len(sector_path) - 1):
        a = sector_path[i]
        b = sector_path[i + 1]
        portal = _shared_portal_segment(pm, a, b)
        if portal is None:
            continue
        p, q = portal
        m = (0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1]))
        if a in centroids:
            nodes.append(_move_toward(m, centroids[a], 16.0))
        if b in centroids:
            nodes.append(_move_toward(m, centroids[b], 16.0))

    return _dedupe_points(nodes, eps2=4.0)


def _build_sector_adjacency(pm: ParsedMap) -> dict[int, list[int]]:
    adj: dict[int, list[int]] = {}
    for ld in pm.linedefs:
        if ld.sidefront < 0 or ld.sideback < 0:
            continue
        if ld.sidefront >= len(pm.sidedefs) or ld.sideback >= len(pm.sidedefs):
            continue
        a = pm.sidedefs[ld.sidefront]
        b = pm.sidedefs[ld.sideback]
        if a < 0 or b < 0 or a == b:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    return adj


def _expand_sector_set(seed: set[int], adj: dict[int, list[int]], depth: int = 1) -> set[int]:
    cur = set(seed)
    frontier = set(seed)
    for _ in range(depth):
        nxt = set()
        for s in frontier:
            for nb in adj.get(s, []):
                if nb not in cur:
                    nxt.add(nb)
        if not nxt:
            break
        cur |= nxt
        frontier = nxt
    return cur


def _frange(a: float, b: float, step: float) -> list[float]:
    out: list[float] = []
    x = a
    # inclusive upper bound
    while x <= b + 1e-6:
        out.append(x)
        x += step
    return out


def _repair_segment_with_subdivision(
    pm: ParsedMap,
    p: tuple[float, float],
    q: tuple[float, float],
    dense_nodes: list[tuple[float, float]],
    allowed_pairs: set[frozenset[int]],
    centroids: dict[int, tuple[float, float]],
    sector_path: list[int],
) -> list[tuple[float, float]]:
    if not centroids:
        return [p, q]
    allowed_sectors = set(sector_path)
    obstacles = _build_obstacle_segments(pm, allowed_pairs)

    sec_p = nearest_sector(p, centroids)
    sec_q = nearest_sector(q, centroids)
    adj = _build_sector_adjacency(pm)

    seed = {sec_p, sec_q}
    # Include path sectors whose centroids lie near this failing segment.
    for s in sector_path:
        c = centroids.get(s)
        if c is None:
            continue
        if _dist2_point_to_segment(c, p, q) <= (320.0 * 320.0):
            seed.add(s)
    local_sectors = _expand_sector_set(seed, adj, depth=1)

    min_x = min(p[0], q[0]) - 160.0
    max_x = max(p[0], q[0]) + 160.0
    min_y = min(p[1], q[1]) - 160.0
    max_y = max(p[1], q[1]) + 160.0

    local_centroids = {s: c for s, c in centroids.items() if s in local_sectors}
    if not local_centroids:
        return [p, q]

    for step in (64.0, 40.0):
        grid_nodes: list[tuple[float, float]] = []
        for x in _frange(min_x, max_x, step):
            for y in _frange(min_y, max_y, step):
                pt = (x, y)
                s = sector_of_point(pm, pt, centroids)
                if s not in local_sectors:
                    continue
                if s not in allowed_sectors:
                    continue
                if _node_clearance(pm, pt, allowed_pairs, obstacle_segments=obstacles) < 8.0:
                    continue
                grid_nodes.append(pt)
        if not grid_nodes:
            continue

        if len(grid_nodes) > 280:
            ranked = sorted(
                ((_dist2_point_to_segment(n, p, q) + 0.15 * min(dist2(n, p), dist2(n, q)), n) for n in grid_nodes),
                key=lambda x: x[0],
            )
            grid_nodes = [n for _r, n in ranked[:280]]

        augmented = _dedupe_points(dense_nodes + grid_nodes + [p, q], eps2=4.0)
        detour = _local_waypoint_astar_segment(pm, p, q, augmented, allowed_pairs, allowed_sectors, centroids)
        if len(detour) > 1 and not _segment_invalid_for_pairs(pm, detour[0], detour[1], allowed_pairs, allowed_sectors, centroids):
            if all(not _segment_invalid_for_pairs(pm, detour[i], detour[i + 1], allowed_pairs, allowed_sectors, centroids) for i in range(len(detour) - 1)):
                return detour
    return [p, q]


def _portal_offset_chain(
    pm: ParsedMap,
    sector_path: list[int],
    centroids: dict[int, tuple[float, float]],
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = [start_xy]
    for i in range(len(sector_path) - 1):
        a = sector_path[i]
        b = sector_path[i + 1]
        portal = _shared_portal_segment(pm, a, b)
        if portal is None:
            continue
        m = (0.5 * (portal[0][0] + portal[1][0]), 0.5 * (portal[0][1] + portal[1][1]))
        if a in centroids:
            pts.append(_move_toward(m, centroids[a], 24.0))
        if b in centroids:
            pts.append(_move_toward(m, centroids[b], 24.0))
    pts.append(end_xy)
    # Keep loop/backtrack structure; only collapse immediate duplicates.
    return _dedupe_consecutive_points(pts, eps2=1.0)


def _build_visibility_graph(
    pm: ParsedMap,
    nodes: list[tuple[float, float]],
    allowed_pairs: set[frozenset[int]],
    allowed_sectors: set[int] | None = None,
    centroids: dict[int, tuple[float, float]] | None = None,
    clearance: dict[int, float] | None = None,
    clearance_weight: float = 0.0,
    min_edge_clearance: float = 0.0,
    obstacle_segments: list[tuple[tuple[float, float], tuple[float, float]]] | None = None,
    k_neighbors: int = 24,
) -> dict[int, list[tuple[int, float]]]:
    n = len(nodes)
    nearest: dict[int, list[int]] = {}
    for i in range(n):
        d = []
        pi = nodes[i]
        for j in range(n):
            if i == j:
                continue
            d.append((dist2(pi, nodes[j]), j))
        d.sort(key=lambda x: x[0])
        nearest[i] = [j for _distv, j in d[:k_neighbors]]

    edges: dict[int, list[tuple[int, float]]] = {}
    checked = set()
    edge_clear_cache: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in nearest[i]:
            a, b = (i, j) if i < j else (j, i)
            if (a, b) in checked:
                continue
            checked.add((a, b))
            if _segment_invalid_for_pairs(pm, nodes[i], nodes[j], allowed_pairs, allowed_sectors, centroids):
                continue
            w = math.sqrt(dist2(nodes[i], nodes[j]))
            edge_c = 1e9
            if min_edge_clearance > 0.0 or clearance_weight > 0.0:
                if (a, b) in edge_clear_cache:
                    edge_c = edge_clear_cache[(a, b)]
                else:
                    edge_c = _segment_clearance(
                        pm,
                        nodes[i],
                        nodes[j],
                        allowed_pairs,
                        samples=7,
                        obstacle_segments=obstacle_segments,
                    )
                    edge_clear_cache[(a, b)] = edge_c
            if min_edge_clearance > 0.0 and edge_c < min_edge_clearance:
                continue
            if clearance is not None and clearance_weight > 0.0:
                ci = clearance.get(i, 1.0)
                cj = clearance.get(j, 1.0)
                c = max(1.0, min(ci, cj, edge_c))
                w = w * (1.0 + clearance_weight / c)
            edges.setdefault(i, []).append((j, w))
            edges.setdefault(j, []).append((i, w))
    return edges


def _a_star_node_path(
    nodes: list[tuple[float, float]],
    edges: dict[int, list[tuple[int, float]]],
    start_idx: int,
    goal_idx: int,
) -> list[tuple[float, float]]:
    open_heap: list[tuple[float, int, int]] = []
    g = {start_idx: 0.0}
    parent: dict[int, int] = {}
    closed = set()
    counter = 0

    def h(i: int) -> float:
        return math.sqrt(dist2(nodes[i], nodes[goal_idx]))

    heapq.heappush(open_heap, (h(start_idx), counter, start_idx))
    while open_heap:
        _, _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal_idx:
            out = [cur]
            while cur in parent:
                cur = parent[cur]
                out.append(cur)
            out.reverse()
            return [nodes[k] for k in out]
        closed.add(cur)
        for nxt, w in edges.get(cur, []):
            if nxt in closed:
                continue
            ng = g[cur] + w
            if ng >= g.get(nxt, float("inf")):
                continue
            g[nxt] = ng
            parent[nxt] = cur
            counter += 1
            heapq.heappush(open_heap, (ng + h(nxt), counter, nxt))
    return []


def _local_waypoint_astar_segment(
    pm: ParsedMap,
    p: tuple[float, float],
    q: tuple[float, float],
    dense_nodes: list[tuple[float, float]],
    allowed_pairs: set[frozenset[int]],
    allowed_sectors: set[int] | None = None,
    centroids: dict[int, tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    pad = 256.0
    min_x = min(p[0], q[0]) - pad
    max_x = max(p[0], q[0]) + pad
    min_y = min(p[1], q[1]) - pad
    max_y = max(p[1], q[1]) + pad

    def point_allowed(pt: tuple[float, float]) -> bool:
        if not allowed_sectors or not centroids:
            return True
        return sector_of_point(pm, pt, centroids) in allowed_sectors

    local = [p, q]
    for n in dense_nodes:
        if not point_allowed(n):
            continue
        if min_x <= n[0] <= max_x and min_y <= n[1] <= max_y:
            local.append(n)
    local = _dedupe_points(local, eps2=4.0)

    if len(local) < 20:
        scored = []
        for n in dense_nodes:
            if not point_allowed(n):
                continue
            scored.append((_dist2_point_to_segment(n, p, q), n))
        scored.sort(key=lambda x: x[0])
        for _d, n in scored[:120]:
            local.append(n)
        local = _dedupe_points(local, eps2=4.0)

    max_local = 260
    if len(local) > max_local:
        scored = []
        for n in local:
            rank = _dist2_point_to_segment(n, p, q) + 0.2 * min(dist2(n, p), dist2(n, q))
            scored.append((rank, n))
        scored.sort(key=lambda x: x[0])
        keep = [p, q]
        for _r, n in scored:
            if dist2(n, p) < 1e-4 or dist2(n, q) < 1e-4:
                continue
            keep.append(n)
            if len(keep) >= max_local:
                break
        local = _dedupe_points(keep, eps2=4.0)

    base_local = local
    node_clear_cache: dict[tuple[int, int], float] = {}
    obstacles = _build_obstacle_segments(pm, allowed_pairs)

    def node_c(n: tuple[float, float]) -> float:
        k = (int(round(n[0] * 2.0)), int(round(n[1] * 2.0)))
        if k in node_clear_cache:
            return node_clear_cache[k]
        v = _node_clearance(pm, n, allowed_pairs, obstacle_segments=obstacles)
        node_clear_cache[k] = v
        return v

    tiers = (
        (44.0, 30.0),
        (36.0, 24.0),
        (28.0, 18.0),
        (20.0, 12.0),
        (12.0, 8.0),
        (0.0, 0.0),
    )

    for min_clearance, edge_clearance in tiers:
        local = [p, q]
        for n in base_local:
            if dist2(n, p) < 1e-4 or dist2(n, q) < 1e-4:
                continue
            c = node_c(n)
            if c >= min_clearance:
                local.append(n)
        local = _dedupe_points(local, eps2=4.0)

        clr: dict[int, float] = {}
        for i, n in enumerate(local):
            if i in (0, 1):
                clr[i] = 1e9
            else:
                clr[i] = node_c(n)

        edges = _build_visibility_graph(
            pm,
            local,
            allowed_pairs,
            allowed_sectors=allowed_sectors,
            centroids=centroids,
            clearance=clr,
            clearance_weight=22.0,
            min_edge_clearance=edge_clearance,
            obstacle_segments=obstacles,
            k_neighbors=30,
        )
        path = _a_star_node_path(local, edges, 0, 1)
        if path:
            return path
    return [p, q]


def _force_valid_by_local_waypoints(
    pm: ParsedMap,
    base_route: list[tuple[float, float]],
    sector_path: list[int],
    centroids: dict[int, tuple[float, float]],
    start_xy: tuple[float, float],
    exit_xy: tuple[float, float],
) -> list[tuple[float, float]]:
    if len(base_route) < 2:
        return base_route
    allowed_pairs = {frozenset((sector_path[i], sector_path[i + 1])) for i in range(len(sector_path) - 1)}
    allowed_sectors = set(sector_path)
    dense_nodes = _collect_dense_corridor_nodes(pm, sector_path, centroids, start_xy, exit_xy)

    out = [base_route[0]]
    subdivision_budget = 2
    for i in range(len(base_route) - 1):
        p = out[-1]
        q = base_route[i + 1]
        if not _segment_invalid_for_pairs(pm, p, q, allowed_pairs, allowed_sectors, centroids):
            out.append(q)
            continue
        detour = _local_waypoint_astar_segment(pm, p, q, dense_nodes, allowed_pairs, allowed_sectors, centroids)
        detour_invalid = (len(detour) <= 1 or any(
            _segment_invalid_for_pairs(pm, detour[k], detour[k + 1], allowed_pairs, allowed_sectors, centroids)
            for k in range(max(0, len(detour) - 1))
        ))
        if detour_invalid and subdivision_budget > 0 and dist2(p, q) >= (180.0 * 180.0):
            subdivision_budget -= 1
            detour = _repair_segment_with_subdivision(
                pm, p, q, dense_nodes, allowed_pairs, centroids, sector_path
            )
        if len(detour) > 1:
            out.extend(detour[1:])
        else:
            out.append(q)
    return out


def _find_detour_for_segment(
    pm: ParsedMap,
    p: tuple[float, float],
    q: tuple[float, float],
    pair: frozenset[int],
    allowed_pairs: set[frozenset[int]],
    max_nodes: int = 64,
) -> list[tuple[float, float]]:
    if not _segment_invalid_for_pairs(pm, p, q, allowed_pairs):
        return [p, q]

    pair_vals = list(pair)
    if len(pair_vals) < 2:
        return [p, q]
    sec_a, sec_b = pair_vals[0], pair_vals[1]

    candidates: list[tuple[float, float]] = [p, q]
    portal = _shared_portal_segment(pm, sec_a, sec_b)
    if portal is not None:
        candidates.append(portal[0])
        candidates.append(portal[1])
        candidates.append((0.5 * (portal[0][0] + portal[1][0]), 0.5 * (portal[0][1] + portal[1][1])))

    candidates.extend(_collect_pair_vertices(pm, sec_a, sec_b))
    candidates = _dedupe_points(candidates, eps2=1.0)
    candidates.sort(key=lambda c: dist2(c, p) + dist2(c, q))
    if len(candidates) > max_nodes:
        keep = [p, q]
        for c in candidates:
            if dist2(c, p) < 1e-4 or dist2(c, q) < 1e-4:
                continue
            keep.append(c)
            if len(keep) >= max_nodes:
                break
        candidates = keep

    n = len(candidates)
    if n < 2:
        return [p, q]

    start_idx = 0
    goal_idx = 1
    edges: dict[int, list[tuple[int, float]]] = {}
    vis_cache: dict[tuple[int, int], bool] = {}

    def visible(i: int, j: int) -> bool:
        k = (i, j) if i < j else (j, i)
        if k in vis_cache:
            return vis_cache[k]
        ok = not _segment_invalid_for_pairs(pm, candidates[i], candidates[j], allowed_pairs)
        vis_cache[k] = ok
        return ok

    for i in range(n):
        for j in range(i + 1, n):
            if not visible(i, j):
                continue
            w = math.sqrt(dist2(candidates[i], candidates[j]))
            edges.setdefault(i, []).append((j, w))
            edges.setdefault(j, []).append((i, w))

    open_heap: list[tuple[float, int, int]] = []
    g = {start_idx: 0.0}
    parent: dict[int, int] = {}
    closed = set()
    counter = 0

    def h(i: int) -> float:
        return math.sqrt(dist2(candidates[i], candidates[goal_idx]))

    heapq.heappush(open_heap, (h(start_idx), counter, start_idx))
    while open_heap:
        _, _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal_idx:
            path_idx = [cur]
            while cur in parent:
                cur = parent[cur]
                path_idx.append(cur)
            path_idx.reverse()
            return [candidates[k] for k in path_idx]
        closed.add(cur)
        for nxt, w in edges.get(cur, []):
            if nxt in closed:
                continue
            ng = g[cur] + w
            if ng >= g.get(nxt, float("inf")):
                continue
            g[nxt] = ng
            parent[nxt] = cur
            counter += 1
            heapq.heappush(open_heap, (ng + h(nxt), counter, nxt))

    return [p, q]


def _refined_path_points(
    pm: ParsedMap,
    sector_path: list[int],
    centroids: dict[int, tuple[float, float]],
    _depth_unused: int = 0,
) -> tuple[list[tuple[float, float]], list[frozenset[int]]]:
    if not sector_path:
        return [], []
    if len(sector_path) == 1:
        sec = sector_path[0]
        return ([centroids[sec]] if sec in centroids else []), []

    out_pts: list[tuple[float, float]] = [centroids[sector_path[0]]]
    out_pairs: list[frozenset[int]] = []
    first_sec = sector_path[0]
    if first_sec not in centroids:
        return [], []

    for i in range(len(sector_path) - 1):
        a = sector_path[i]
        b = sector_path[i + 1]
        if a not in centroids or b not in centroids:
            continue
        pair = frozenset((a, b))
        out_pairs.append(pair)
        out_pts.append(centroids[b])

    global_pairs = {frozenset((sector_path[i], sector_path[i + 1])) for i in range(len(sector_path) - 1)}

    # Refine only where a segment is invalid by inserting detour nodes.
    for _ in range(3):
        changed = False
        new_pts: list[tuple[float, float]] = [out_pts[0]]
        new_pairs: list[frozenset[int]] = []
        for i, pair in enumerate(out_pairs):
            p = out_pts[i]
            q = out_pts[i + 1]
            if not _segment_invalid_for_pairs(pm, p, q, global_pairs):
                new_pts.append(q)
                new_pairs.append(pair)
                continue
            detour = _find_detour_for_segment(pm, p, q, pair, global_pairs, max_nodes=64)
            if len(detour) > 2:
                changed = True
            for j in range(1, len(detour)):
                new_pts.append(detour[j])
                new_pairs.append(pair)
        out_pts = new_pts
        out_pairs = new_pairs
        if not changed:
            break
    return out_pts, out_pairs


def _invalid_route_segments(
    pm: ParsedMap,
    route_pts: list[tuple[float, float]],
    allowed_pairs: set[frozenset[int]],
    allowed_sectors: set[int] | None = None,
    centroids: dict[int, tuple[float, float]] | None = None,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    invalid: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i in range(max(0, len(route_pts) - 1)):
        p = route_pts[i]
        q = route_pts[i + 1]
        if _segment_invalid_for_pairs(pm, p, q, allowed_pairs, allowed_sectors, centroids):
            invalid.append((p, q))
    return invalid


def _route_node_payload(
    centroid_path: list[tuple[float, float]],
    tx: Any,
    ty: Any,
) -> list[dict[str, Any]]:
    return [
        {
            "number": number,
            "x": tx(pt[0]),
            "y": ty(pt[1]),
        }
        for number, pt in enumerate(centroid_path, start=1)
    ]


def draw_svg(
    pm: ParsedMap,
    centroids: dict[int, tuple[float, float]],
    sector_path: list[int],
    centroid_path: list[tuple[float, float]],
    typed_nodes: list[dict[str, Any]],
    invalid_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    start_xy: tuple[float, float],
    exit_xy: tuple[float, float],
    map_name: str,
    output_path: str,
) -> None:
    verts = pm.vertices
    w = SVG_WIDTH
    h = SVG_HEIGHT
    tx, ty = _svg_transform(pm)
    min_x = min(v[0] for v in verts)
    max_x = max(v[0] for v in verts)
    min_y = min(v[1] for v in verts)
    max_y = max(v[1] for v in verts)
    sx = (w - 2.0 * SVG_PAD) / max(1.0, (max_x - min_x))
    sy = (h - 2.0 * SVG_PAD) / max(1.0, (max_y - min_y))
    s = min(sx, sy)

    path_set = set(sector_path)
    barrel_obstacles = _collect_barrel_obstacles(pm)
    route_nodes = _route_node_payload(centroid_path, tx, ty)
    lines_svg: list[str] = []
    for ld in pm.linedefs:
        if ld.v1 < 0 or ld.v2 < 0 or ld.v1 >= len(verts) or ld.v2 >= len(verts):
            continue
        x1, y1 = verts[ld.v1]
        x2, y2 = verts[ld.v2]
        sec_a = pm.sidedefs[ld.sidefront] if 0 <= ld.sidefront < len(pm.sidedefs) else -1
        sec_b = pm.sidedefs[ld.sideback] if 0 <= ld.sideback < len(pm.sidedefs) else -1
        on_path = (sec_a in path_set) or (sec_b in path_set)
        color = "#ff6a00" if on_path else "#666666"
        width = "1.8" if on_path else "0.7"
        lines_svg.append(
            f'<line x1="{tx(x1):.2f}" y1="{ty(y1):.2f}" x2="{tx(x2):.2f}" y2="{ty(y2):.2f}" '
            f'stroke="{color}" stroke-width="{width}" />'
        )

    barrel_svg: list[str] = []
    for barrel in barrel_obstacles:
        r = barrel.radius * s
        bx = tx(barrel.center[0])
        by = ty(barrel.center[1])
        barrel_svg.append(
            f'<circle cx="{bx:.2f}" cy="{by:.2f}" r="{r:.2f}" fill="#d08a26" opacity="0.35" '
            f'stroke="#ffcc66" stroke-width="1.6" />'
        )
        for a, b in barrel.segments:
            barrel_svg.append(
                f'<line x1="{tx(a[0]):.2f}" y1="{ty(a[1]):.2f}" x2="{tx(b[0]):.2f}" y2="{ty(b[1]):.2f}" '
                f'stroke="#ffcc66" stroke-width="1.1" opacity="0.95" />'
            )

    centroid_svg = ""
    if len(route_nodes) >= 2:
        pts = " ".join(f"{node['x']:.2f},{node['y']:.2f}" for node in route_nodes)
        centroid_svg = f'<polyline points="{pts}" stroke="#00e0ff" stroke-width="2.6" fill="none" opacity="0.95" />'

    _NODE_COLORS = {"door": "#00ff55", "exit": "#ff3333"}
    centroid_dots = []
    node_labels = []
    for node, tnode in zip(route_nodes, typed_nodes):
        color = _NODE_COLORS.get(tnode["type"], "#00e0ff")
        centroid_dots.append(f'<circle cx="{node["x"]:.2f}" cy="{node["y"]:.2f}" r="2.2" fill="{color}" />')
        node_labels.append(
            f'<text x="{node["x"] + 6.0:.2f}" y="{node["y"] - 6.0:.2f}" fill="#ffffff" '
            f'font-family="monospace" font-size="13" font-weight="700" stroke="#121212" '
            f'stroke-width="3" paint-order="stroke fill">{node["number"]}</text>'
        )

    invalid_svg = []
    for p, q in invalid_segments:
        invalid_svg.append(
            f'<line x1="{tx(p[0]):.2f}" y1="{ty(p[1]):.2f}" x2="{tx(q[0]):.2f}" y2="{ty(q[1]):.2f}" '
            f'stroke="#ff3355" stroke-width="3.8" opacity="0.95" />'
        )

    sxp, syp = tx(start_xy[0]), ty(start_xy[1])
    exp, eyp = tx(exit_xy[0]), ty(exit_xy[1])

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{int(w)}" height="{int(h)}">
<rect width="100%" height="100%" fill="#121212" />
{''.join(lines_svg)}
{''.join(barrel_svg)}
{centroid_svg}
{''.join(centroid_dots)}
{''.join(node_labels)}
{''.join(invalid_svg)}
<circle cx="{sxp:.2f}" cy="{syp:.2f}" r="5" fill="#00ff55" />
<circle cx="{exp:.2f}" cy="{eyp:.2f}" r="5" fill="#ff3333" />
<text x="20" y="30" fill="#ffffff" font-family="monospace" font-size="18">{map_name} Sector A* Path</text>
<text x="20" y="54" fill="#bbbbbb" font-family="monospace" font-size="14">Orange lines: linedefs touching sectors on A* path</text>
<text x="20" y="74" fill="#bbbbbb" font-family="monospace" font-size="14">Yellow: barrel obstacles used by route validity/clearance checks</text>
<text x="20" y="94" fill="#bbbbbb" font-family="monospace" font-size="14">Cyan: portal midpoint route</text>
<text x="20" y="114" fill="#bbbbbb" font-family="monospace" font-size="14">Red: invalid node-link segments (cross non-portal geometry)</text>
<text x="20" y="134" fill="#bbbbbb" font-family="monospace" font-size="14">White labels: node numbers</text>
<text x="20" y="154" fill="#bbbbbb" font-family="monospace" font-size="14">Green dots: doors</text>
</svg>"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")


def _svg_transform(pm: ParsedMap) -> tuple[Any, Any]:
    verts = pm.vertices
    min_x = min(v[0] for v in verts)
    max_x = max(v[0] for v in verts)
    min_y = min(v[1] for v in verts)
    max_y = max(v[1] for v in verts)
    pad = SVG_PAD
    w = SVG_WIDTH
    h = SVG_HEIGHT

    sx = (w - 2.0 * pad) / max(1.0, (max_x - min_x))
    sy = (h - 2.0 * pad) / max(1.0, (max_y - min_y))
    s = min(sx, sy)

    def tx(x: float) -> float:
        return pad + (x - min_x) * s

    def ty(y: float) -> float:
        return h - (pad + (y - min_y) * s)

    return tx, ty


def write_route_json(
    output_path: str,
    wad_path: str,
    map_name: str,
    typed_nodes: list[dict[str, Any]],
) -> None:
    edges = [[i, i + 1] for i in range(len(typed_nodes) - 1)]
    payload = {
        "wad": wad_path,
        "map": map_name,
        "node_points": typed_nodes,
        "edges": edges,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_sector_door_specials(pm: ParsedMap) -> dict[int, int]:
    """Returns sector_id -> special for sectors where a non-exit special
    appears on at least two linedefs (the sector is a door)."""
    sector_special_counts: dict[int, dict[int, int]] = {}
    for ld in pm.linedefs:
        if ld.special == 0 or ld.special in EXIT_SPECIALS:
            continue
        for side in (ld.sidefront, ld.sideback):
            if side < 0 or side >= len(pm.sidedefs):
                continue
            sec = pm.sidedefs[side]
            if sec < 0:
                continue
            counts = sector_special_counts.setdefault(sec, {})
            counts[ld.special] = counts.get(ld.special, 0) + 1

    door_sectors: dict[int, int] = {}
    for sec, counts in sector_special_counts.items():
        for special, count in counts.items():
            if count >= 2:
                door_sectors[sec] = special
                break
    return door_sectors


def default_json_output_path(map_name: str) -> str:
    return str(Path("maps") / "json" / f"{map_name}.json")


def default_svg_output_path(map_name: str) -> str:
    return str(Path("maps") / "images" / f"{map_name}.svg")


def _choose_exit_linedef(pm: ParsedMap) -> Linedef:
    normal_exit_lines = [ld for ld in pm.linedefs if ld.special in NORMAL_EXIT_SPECIALS]
    if normal_exit_lines:
        return normal_exit_lines[0]

    secret_exit_lines = [ld for ld in pm.linedefs if ld.special in SECRET_EXIT_SPECIALS]
    if secret_exit_lines:
        return secret_exit_lines[0]

    raise RuntimeError("Exit linedef specials not found")


def generate_one_map(
    wad_path: str,
    map_name: str,
    out_svg: str,
    out_json: str | None = None,
) -> dict[str, Any]:
    pm = load_map_data(wad_path, map_name)
    if not pm.vertices or not pm.linedefs:
        raise RuntimeError("Failed to parse map geometry")

    start_things = [t for t in pm.things if int(t.get("type", 0)) == 1]
    if not start_things:
        raise RuntimeError("Player start (thing type 1) not found")
    start_xy = (float(start_things[0].get("x", 0.0)), float(start_things[0].get("y", 0.0)))

    ex_ld = _choose_exit_linedef(pm)
    ex_v1 = pm.vertices[ex_ld.v1]
    ex_v2 = pm.vertices[ex_ld.v2]
    exit_xy = (0.5 * (ex_v1[0] + ex_v2[0]), 0.5 * (ex_v1[1] + ex_v2[1]))

    centroids = build_sector_centroids(pm)
    graph = build_sector_graph(pm)
    transition_graph = build_sector_transition_graph(pm)
    start_sector = nearest_sector(start_xy, centroids)
    goal_sector = nearest_sector(exit_xy, centroids)
    reachable_sectors = connected_sector_component(graph, start_sector)
    sector_keys = build_sector_key_mask(pm, centroids, reachable_sectors=reachable_sectors)
    has_locked_edges = any(req != 0 for edges in transition_graph.values() for _to, req in edges)
    if has_locked_edges:
        sector_path, final_keys = a_star_sector_path_with_keys(
            pm, transition_graph, centroids, sector_keys, start_sector, goal_sector
        )
        if not sector_path:
            raise RuntimeError("Key-aware path not found on lock-gated map")
    else:
        sector_path = a_star_sector_path(pm, graph, centroids, start_sector, goal_sector)
        final_keys = sector_keys.get(start_sector, 0)
    if not sector_path:
        raise RuntimeError(f"No sector path found from {start_sector} to {goal_sector}")

    route_pairs = [frozenset((sector_path[i], sector_path[i + 1])) for i in range(max(0, len(sector_path) - 1))]
    allowed_pairs = set(route_pairs)

    portals = _build_portals(pm, sector_path, centroids)
    if portals:
        centroid_path = _portal_offset_chain(pm, sector_path, centroids, start_xy, exit_xy)
    else:
        centroid_path = _centroid_path_points(sector_path, centroids)
    sector_pickups = build_sector_key_pickups(pm, centroids, reachable_sectors=reachable_sectors)
    centroid_path = _inject_sector_pickups(sector_path, centroid_path, sector_pickups)
    centroid_path = _force_valid_by_local_waypoints(pm, centroid_path, sector_path, centroids, start_xy, exit_xy)
    if not centroid_path:
        centroid_path = _centroid_path_points(sector_path, centroids)
        centroid_path = _inject_sector_pickups(sector_path, centroid_path, sector_pickups)

    invalid_segments = _invalid_route_segments(pm, centroid_path, allowed_pairs, set(sector_path), centroids)

    if out_json is None:
        out_json = default_json_output_path(map_name)

    key_positions = {pt for pts in sector_pickups.values() for pt in pts}
    exit_special = ex_ld.special
    door_sectors = _build_sector_door_specials(pm)
    typed_nodes: list[dict[str, Any]] = []
    for pt in centroid_path:
        sec = sector_of_point(pm, pt, centroids)
        door_special = door_sectors.get(sec)
        if dist2(pt, exit_xy) < 1.0:
            typed_nodes.append({"x": pt[0], "y": pt[1], "type": "exit", "special": exit_special})
        elif pt in key_positions:
            typed_nodes.append({"x": pt[0], "y": pt[1], "type": "loot", "special": None})
        elif door_special is not None:
            typed_nodes.append({"x": pt[0], "y": pt[1], "type": "door", "special": door_special})
        else:
            typed_nodes.append({"x": pt[0], "y": pt[1], "type": "waypoint", "special": None})

    draw_svg(pm, centroids, sector_path, centroid_path, typed_nodes, invalid_segments, start_xy, exit_xy, map_name, out_svg)
    write_route_json(out_json, wad_path, map_name, typed_nodes)
    return {
        "wad": wad_path,
        "map": map_name,
        "start_xy": start_xy,
        "exit_xy": exit_xy,
        "start_sector": start_sector,
        "goal_sector": goal_sector,
        "path_sector_count": len(sector_path),
        "path_sectors": sector_path,
        "centroid_path_points": len(centroid_path),
        "invalid_segments": len(invalid_segments),
        "final_keys_mask": final_keys,
        "output_svg": out_svg,
        "output_json": out_json,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Draw map sector A* route")
    parser.add_argument("--wad", default="maps/wads/doom.wad", help="Path to the source WAD")
    parser.add_argument("--map", default="E1M1", help="Map marker")
    parser.add_argument("--out", default=None, help="Output SVG file")
    parser.add_argument("--all-maps", action="store_true", help="Generate SVG for every map marker in WAD")
    parser.add_argument("--out-dir", default="maps/svg/all_maps_astar", help="Output directory when --all-maps is set")
    args = parser.parse_args()

    if args.all_maps:
        svg_out_dir = Path(args.out_dir)
        svg_out_dir.mkdir(parents=True, exist_ok=True)
        maps = list_map_markers(args.wad)
        print("SECTOR_ASTAR_MAPS")
        print(f"wad: {args.wad}")
        print(f"map_count: {len(maps)}")
        ok = 0
        for m in maps:
            out_svg = str(svg_out_dir / f"{m}.svg")
            out_json = default_json_output_path(m)
            try:
                res = generate_one_map(args.wad, m, out_svg, out_json=out_json)
                ok += 1
                print(f"{m}: OK sectors={res['path_sector_count']} svg={out_svg} json={out_json}")
            except Exception as exc:
                print(f"{m}: SKIP reason={exc}")
        print(f"generated: {ok}/{len(maps)}")
        print(f"output_svg_dir: {svg_out_dir}")
        return 0

    out_svg = args.out if args.out else default_svg_output_path(args.map)
    res = generate_one_map(args.wad, args.map, out_svg)
    print("SECTOR_ASTAR_MAP")
    print(f"wad: {res['wad']}")
    print(f"map: {res['map']}")
    print(f"start_xy: {res['start_xy']}")
    print(f"exit_xy: {res['exit_xy']}")
    print(f"start_sector: {res['start_sector']}")
    print(f"goal_sector: {res['goal_sector']}")
    print(f"path_sector_count: {res['path_sector_count']}")
    print(f"path_sectors: {res['path_sectors']}")
    print(f"centroid_path_points: {res['centroid_path_points']}")
    print(f"invalid_segments: {res['invalid_segments']}")
    print(f"output_svg: {res['output_svg']}")
    print(f"output_json: {res['output_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
