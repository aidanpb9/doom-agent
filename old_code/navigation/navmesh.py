"""
Lightweight Python port of the zdoom-pathfinding navmesh parser + A* + funnel.
Consumes navmesh JSON produced by zdoom-navmesh-generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import heapq
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

Vec2 = Tuple[float, float]
Vec3 = Tuple[float, float, float]

logger = logging.getLogger(__name__)


def _dist2(a: Vec3, b: Vec3) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx * dx + dy * dy + dz * dz


def _dist2_2d(a: Vec3, b: Vec3) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _triarea2(a: Vec3, b: Vec3, c: Vec3) -> float:
    ax = b[0] - a[0]
    ay = b[1] - a[1]
    bx = c[0] - a[0]
    by = c[1] - a[1]
    return bx * ay - ax * by


def _point_in_poly(pt: Vec3, poly: List[Vec2]) -> bool:
    if len(poly) < 3:
        return False
    x, y = pt[0], pt[1]
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


@dataclass
class NavPortal:
    vertex_ids: Tuple[int, int]


@dataclass
class NavNode:
    node_id: int
    group_id: int
    centroid: Vec3
    vertex_ids: List[int]
    neighbor_ids: List[int]
    portals: List[NavPortal]
    flags: int = 0
    mesh: "NavMesh" = None
    polygon: List[Vec2] = field(default_factory=list)
    portal_by_neighbor: Dict[int, NavPortal] = field(default_factory=dict)

    # A* state
    parent: Optional["NavNode"] = None
    closed: bool = False
    visited: bool = False
    cost: int = 1
    f: float = 0.0
    g: float = 0.0
    h: float = 0.0

    def reset(self) -> None:
        self.parent = None
        self.closed = False
        self.visited = False
        self.cost = 1
        self.f = 0.0
        self.g = 0.0
        self.h = 0.0

    def get_portal_to(self, neighbor_id: int) -> Optional[NavPortal]:
        return self.portal_by_neighbor.get(neighbor_id)

    def contains_point(self, pos: Vec3) -> bool:
        return _point_in_poly(pos, self.polygon)


@dataclass
class NavGroup:
    group_id: int
    nodes: List[NavNode] = field(default_factory=list)

    def reset_nodes(self) -> None:
        for node in self.nodes:
            node.reset()


class NavChannel:
    def __init__(self) -> None:
        self.positions: List[float] = []
        self.length: int = 0

    def clear(self) -> None:
        self.positions.clear()
        self.length = 0

    def add_pair(self, left: Vec3, right: Vec3) -> None:
        self._add_pos(left)
        self._add_pos(right)
        self.length += 1

    def add_single(self, v: Vec3) -> None:
        self._add_pos(v)
        self._add_pos(v)
        self.length += 1

    def _add_pos(self, v: Vec3) -> None:
        self.positions.extend([v[0], v[1], v[2]])

    def _get_left(self, index: int) -> Vec3:
        i = index * 6
        return (self.positions[i], self.positions[i + 1], self.positions[i + 2])

    def _get_right(self, index: int) -> Vec3:
        i = index * 6
        return (self.positions[i + 3], self.positions[i + 4], self.positions[i + 5])

    @staticmethod
    def _vequal(a: Vec3, b: Vec3) -> bool:
        return a[0] == b[0] and a[1] == b[1] and a[2] == b[2]

    def string_pull(self) -> List[Vec3]:
        if self.length == 0:
            return []

        pts: List[Vec3] = []
        portal_apex = self._get_left(0)
        portal_left = portal_apex
        portal_right = portal_apex
        apex_index = 0
        left_index = 0
        right_index = 0

        pts.append(portal_apex)

        i = 1
        max_iters = max(10, self.length * 8)
        iters = 0
        last_reset_index = -1
        reset_streak = 0
        while i < self.length:
            iters += 1
            if iters > max_iters:
                logger.warning("Funnel guard: exceeded max iters=%s length=%s", max_iters, self.length)
                break
            left = self._get_left(i)
            right = self._get_right(i)

            # Update right portal
            if _triarea2(portal_apex, portal_right, right) >= 0.0:
                if self._vequal(portal_apex, portal_right) or _triarea2(
                    portal_apex, portal_left, right
                ) < 0.0:
                    portal_right = right
                    right_index = i
                else:
                    pts.append(portal_left)
                    portal_apex = portal_left
                    apex_index = left_index
                    portal_left = portal_apex
                    portal_right = portal_apex
                    left_index = apex_index
                    right_index = apex_index
                    if last_reset_index == apex_index:
                        reset_streak += 1
                    else:
                        reset_streak = 0
                        last_reset_index = apex_index
                    i = apex_index if reset_streak == 0 else apex_index + 1
                    continue

            # Update left portal
            if _triarea2(portal_apex, portal_left, left) <= 0.0:
                if self._vequal(portal_apex, portal_left) or _triarea2(
                    portal_apex, portal_right, left
                ) > 0.0:
                    portal_left = left
                    left_index = i
                else:
                    pts.append(portal_right)
                    portal_apex = portal_right
                    apex_index = right_index
                    portal_left = portal_apex
                    portal_right = portal_apex
                    left_index = apex_index
                    right_index = apex_index
                    if last_reset_index == apex_index:
                        reset_streak += 1
                    else:
                        reset_streak = 0
                        last_reset_index = apex_index
                    i = apex_index if reset_streak == 0 else apex_index + 1
                    continue

            i += 1

        last_left = self._get_left(self.length - 1)
        if not pts or not self._vequal(pts[-1], last_left):
            pts.append(last_left)

        return pts


class NavMesh:
    def __init__(self) -> None:
        self.vertices: List[float] = []
        self.nodes: List[NavNode] = []
        self.groups: List[NavGroup] = []
        self.debug_astar: bool = False
        self.debug_astar_interval: int = 20
        self.debug_geometry_path: Optional[Path] = None

    @staticmethod
    def from_json(path: Path) -> "NavMesh":
        data = json.loads(path.read_text())
        mesh = NavMesh()
        mesh.vertices = [float(v) for v in data.get("vertices", [])]

        group_count = int(data.get("groups", 1))
        mesh.groups = [NavGroup(group_id=i) for i in range(group_count)]

        nodes_data = data.get("nodes", [])
        for idx, node_obj in enumerate(nodes_data):
            group_id = int(node_obj.get("g", 0))
            centroid_raw = node_obj.get("c", [0, 0, 0])
            centroid = (float(centroid_raw[0]), float(centroid_raw[1]), float(centroid_raw[2]))
            vertex_ids = [int(v) for v in node_obj.get("v", [])]
            neighbor_ids = [int(n) for n in node_obj.get("n", [])]
            portals_raw = node_obj.get("p", [])
            portals: List[NavPortal] = []
            for pair in portals_raw:
                if len(pair) >= 2:
                    portals.append(NavPortal((int(pair[0]), int(pair[1]))))
            flags = int(node_obj.get("f", 0))
            node = NavNode(
                node_id=idx,
                group_id=group_id,
                centroid=centroid,
                vertex_ids=vertex_ids,
                neighbor_ids=neighbor_ids,
                portals=portals,
                flags=flags,
                mesh=mesh,
            )

            # Cache polygon 2D points
            poly: List[Vec2] = []
            for vid in vertex_ids:
                v = mesh.get_vertex(vid)
                poly.append((v[0], v[1]))
            node.polygon = poly

            # Map portals to neighbors (index-aligned in the schema)
            for i, neighbor_id in enumerate(neighbor_ids):
                if i < len(portals):
                    node.portal_by_neighbor[neighbor_id] = portals[i]

            mesh.nodes.append(node)
            if 0 <= group_id < len(mesh.groups):
                mesh.groups[group_id].nodes.append(node)

        bounds = mesh._compute_bounds()
        logger.info(
            "[NAV] Mesh loaded: verts=%s nodes=%s groups=%s bounds=%s",
            len(mesh.vertices) // 3,
            len(mesh.nodes),
            len(mesh.groups),
            bounds,
        )
        try:
            mesh._write_geometry_debug(path)
        except Exception as exc:
            logger.warning("[NAV] Failed to write geometry debug: %s", exc)

        return mesh

    def _compute_bounds(self) -> Tuple[float, float, float, float]:
        xs = self.vertices[0::3]
        ys = self.vertices[1::3]
        if not xs or not ys:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def _write_geometry_debug(self, source_path: Path) -> None:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        out_path = logs_dir / "navmesh_geometry.json"
        data = {
            "source": str(source_path),
            "bounds": self._compute_bounds(),
            "vertices": len(self.vertices) // 3,
            "nodes": len(self.nodes),
            "groups": len(self.groups),
            "polygons": [
                {
                    "id": node.node_id,
                    "centroid": node.centroid,
                    "neighbors": node.neighbor_ids,
                    "polygon": node.polygon,
                }
                for node in self.nodes
            ],
        }
        out_path.write_text(json.dumps(data, indent=2))
        self.debug_geometry_path = out_path
        logger.info("[NAV] Wrote geometry debug: %s", out_path)

    def get_vertex(self, vertex_id: int) -> Vec3:
        idx = vertex_id * 3
        return (
            float(self.vertices[idx]),
            float(self.vertices[idx + 1]),
            float(self.vertices[idx + 2]),
        )

    def get_closest_node_in(self, pos: Vec3, nodes: Iterable[NavNode], use_poly: bool = False) -> Optional[NavNode]:
        closest = None
        closest_dist = float("inf")
        closest_inside = None
        closest_inside_dist = float("inf")
        for node in nodes:
            d = _dist2(pos, node.centroid)
            if d < closest_dist:
                closest_dist = d
                closest = node
            if use_poly and node.contains_point(pos):
                if d < closest_inside_dist:
                    closest_inside_dist = d
                    closest_inside = node
        return closest_inside if closest_inside is not None else closest

    def get_nearest_group_id(self, pos: Vec3, use_poly: bool = False) -> int:
        node = self.get_closest_node_in(pos, self.nodes, use_poly=use_poly)
        return node.group_id if node is not None else -1

    def get_closest_node_in_group(self, pos: Vec3, group_id: int, use_poly: bool = True) -> Optional[NavNode]:
        if group_id < 0 or group_id >= len(self.groups):
            return None
        return self.get_closest_node_in(pos, self.groups[group_id].nodes, use_poly=use_poly)

    def _a_star(self, group: NavGroup, start: NavNode, end: NavNode) -> List[NavNode]:
        group.reset_nodes()
        counter = 0
        heap: List[Tuple[float, int, NavNode]] = []
        start.visited = True
        heapq.heappush(heap, (0.0, counter, start))
        expansions = 0

        while heap:
            _, _, current = heapq.heappop(heap)
            if current.closed:
                continue
            if current == end:
                path: List[NavNode] = []
                cur = current
                while cur.parent is not None:
                    path.append(cur)
                    cur = cur.parent
                path.reverse()
                if self.debug_astar:
                    logger.info(
                        "[ASTAR] Path found: nodes=%s expansions=%s",
                        len(path),
                        expansions,
                    )
                return path

            current.closed = True
            expansions += 1
            if self.debug_astar and (expansions % max(1, self.debug_astar_interval) == 0):
                logger.info(
                    "[ASTAR] expand=%s current=%s f=%.1f g=%.1f h=%.1f open=%s",
                    expansions,
                    current.node_id,
                    current.f,
                    current.g,
                    current.h,
                    len(heap),
                )
            for neighbor_id in current.neighbor_ids:
                neighbor = self.nodes[neighbor_id]
                if neighbor.closed:
                    continue
                g_score = current.g + neighbor.cost
                if not neighbor.visited or g_score < neighbor.g:
                    neighbor.visited = True
                    neighbor.parent = current
                    if neighbor.h == 0.0:
                        neighbor.h = _dist2(neighbor.centroid, end.centroid)
                    neighbor.g = g_score
                    neighbor.f = neighbor.g + neighbor.h
                    counter += 1
                    heapq.heappush(heap, (neighbor.f, counter, neighbor))

        if self.debug_astar:
            logger.info("[ASTAR] No path found: expansions=%s", expansions)
        return []

    def find_path(self, group_id: int, start_pos: Vec3, end_pos: Vec3) -> List[Vec3]:
        if group_id < 0 or group_id >= len(self.groups):
            return []
        start_node = self.get_closest_node_in_group(start_pos, group_id, use_poly=True)
        end_node = self.get_closest_node_in_group(end_pos, group_id, use_poly=True)
        if start_node is None or end_node is None:
            return []
        if self.debug_astar:
            logger.info(
                "[ASTAR] FindPath group=%s start_node=%s end_node=%s start=%s end=%s",
                group_id,
                start_node.node_id if start_node else None,
                end_node.node_id if end_node else None,
                start_pos,
                end_pos,
            )
        if start_node == end_node:
            return [start_pos, end_pos]

        group = self.groups[group_id]
        path_nodes = self._a_star(group, start_node, end_node)
        if not path_nodes:
            return []

        channel = NavChannel()
        channel.add_single(start_pos)

        for i in range(len(path_nodes) - 1):
            polygon = path_nodes[i]
            next_polygon = path_nodes[i + 1]
            if polygon.flags:
                end_pos = polygon.centroid
                break
            portal = polygon.get_portal_to(next_polygon.node_id)
            if portal is None:
                continue
            channel.add_pair(
                self.get_vertex(portal.vertex_ids[0]),
                self.get_vertex(portal.vertex_ids[1]),
            )

        channel.add_single(end_pos)
        points = channel.string_pull()
        if self.debug_astar:
            logger.info("[ASTAR] Funnel points=%s", len(points))
        return points
