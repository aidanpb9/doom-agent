"""
Navmesh-based navigation using zdoom-navmesh-generator output and
zdoom-pathfinding algorithms (A* + funnel).
"""

from __future__ import annotations

import logging
import math
import json
from pathlib import Path
from typing import List, Optional, Tuple, Any

import numpy as np

from agent.utils.action_decoder import ActionDecoder
from agent.nav.zdoom_navmesh import NavMesh, Vec3

logger = logging.getLogger(__name__)


class SectorNavigator:
    """Navmesh navigation across nodes using zdoom-pathfinding logic."""

    def __init__(self, map_name: Optional[str] = None, navmesh_dir: str = "models/nav"):
        self.map_name = map_name
        self.navmesh_dir = Path(navmesh_dir)
        self.mesh: Optional[NavMesh] = None
        self.mesh_path: Optional[Path] = None
        self.wad_path: Optional[Path] = None

        self.route_nodes: List[int] = []
        self.route_idx = 0
        self.route_built = False
        self.start_node_id: Optional[int] = None
        self.end_node_id: Optional[int] = None
        self.pruned_nodes: Optional[List[int]] = None

        self.path_points: List[Vec3] = []
        self.path_idx = 0
        self.current_target: Optional[int] = None

        self.last_pos: Optional[Tuple[float, float]] = None
        self.stuck_counter = 0
        self.step = 0
        self.no_progress = 0
        self.last_distance: Optional[float] = None
        self.y_inverted = False
        self.use_ticks = 0
        self.special_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.special_line_info: List[dict] = []
        self.special_lines_built = False

    def set_map_name(self, map_name: str) -> None:
        if map_name and map_name != self.map_name:
            self.map_name = map_name
            self.mesh = None
            self.mesh_path = None
            self.route_built = False
            self.route_nodes = []
            self.route_idx = 0
            self.start_node_id = None
            self.end_node_id = None
            self.pruned_nodes = None
            self.path_points = []
            self.path_idx = 0
            self.current_target = None
            self.special_lines_built = False

    def set_wad_path(self, wad_path: str) -> None:
        if wad_path:
            self.wad_path = Path(wad_path)
            self.special_lines_built = False

    def reset_episode(self) -> None:
        self.route_nodes = []
        self.route_idx = 0
        self.route_built = False
        self.start_node_id = None
        self.end_node_id = None
        self.pruned_nodes = None
        self.path_points = []
        self.path_idx = 0
        self.current_target = None
        self.last_pos = None
        self.stuck_counter = 0
        self.step = 0
        self.no_progress = 0
        self.last_distance = None
        self.y_inverted = False
        self.use_ticks = 0
        self.special_segments = []
        self.special_line_info = []
        self.special_lines_built = False

    @staticmethod
    def _is_exit_special(special: int) -> bool:
        # Common DOOM exit specials (exit/secret exit variants).
        return special in {11, 51, 52, 124, 197}

    def _find_exit_node(self) -> Optional[int]:
        if self.mesh is None or not self.special_line_info:
            return None

        best_node = None
        best_dist = float("inf")
        for info in self.special_line_info:
            try:
                special = int(info.get("special", 0))
            except Exception:
                continue
            if not self._is_exit_special(special):
                continue
            seg = info.get("segment")
            if not seg or len(seg) != 2:
                continue
            (x1, y1), (x2, y2) = seg
            mid = (float(x1 + x2) * 0.5, float(y1 + y2) * 0.5, 0.0)
            node = self.mesh.get_closest_node_in(mid, self.mesh.nodes, use_poly=False)
            if node is None:
                continue
            dx = node.centroid[0] - mid[0]
            dy = node.centroid[1] - mid[1]
            d = dx * dx + dy * dy
            if d < best_dist:
                best_dist = d
                best_node = node.node_id

        return best_node

    def _prune_to_simple_st_paths(self, start_id: int, end_id: int) -> Optional[List[int]]:
        if self.mesh is None:
            return None
        node_count = len(self.mesh.nodes)
        if not (0 <= start_id < node_count and 0 <= end_id < node_count):
            return None

        adjacency = {i: set() for i in range(node_count)}
        for node in self.mesh.nodes:
            for n_id in node.neighbor_ids:
                if 0 <= n_id < node_count:
                    adjacency[node.node_id].add(n_id)
                    adjacency[n_id].add(node.node_id)

        # Reachability check
        reachable = set()
        stack = [start_id]
        while stack:
            u = stack.pop()
            if u in reachable:
                continue
            reachable.add(u)
            for v in adjacency.get(u, ()):
                if v not in reachable:
                    stack.append(v)
        if end_id not in reachable:
            logger.warning("[NAV] End node %s not reachable from start %s", end_id, start_id)
            return sorted(reachable)

        # Tarjan biconnected components
        disc = [-1] * node_count
        low = [0] * node_count
        parent = [-1] * node_count
        time = 0
        edge_stack: List[Tuple[int, int]] = []
        bccs: List[set] = []
        articulation = set()

        def dfs(u: int) -> None:
            nonlocal time
            disc[u] = time
            low[u] = time
            time += 1
            child_count = 0
            for v in adjacency[u]:
                if disc[v] == -1:
                    parent[v] = u
                    child_count += 1
                    edge_stack.append((u, v))
                    dfs(v)
                    low[u] = min(low[u], low[v])
                    if low[v] >= disc[u]:
                        if parent[u] != -1 or child_count > 1:
                            articulation.add(u)
                        bcc = set()
                        while edge_stack:
                            e = edge_stack.pop()
                            bcc.add(e[0])
                            bcc.add(e[1])
                            if e == (u, v):
                                break
                        if bcc:
                            bccs.append(bcc)
                elif v != parent[u] and disc[v] < disc[u]:
                    low[u] = min(low[u], disc[v])
                    edge_stack.append((u, v))

        for i in range(node_count):
            if i in reachable and disc[i] == -1:
                dfs(i)
                if edge_stack:
                    bcc = set()
                    while edge_stack:
                        e = edge_stack.pop()
                        bcc.add(e[0])
                        bcc.add(e[1])
                    if bcc:
                        bccs.append(bcc)

        if not bccs:
            return sorted(reachable)

        # Build block-cut tree
        bcc_of_vertex: List[List[int]] = [[] for _ in range(node_count)]
        for idx, bcc in enumerate(bccs):
            for v in bcc:
                bcc_of_vertex[v].append(idx)

        tree_adj: Dict[Tuple[str, int], set] = {}

        def add_tree_edge(a: Tuple[str, int], b: Tuple[str, int]) -> None:
            tree_adj.setdefault(a, set()).add(b)
            tree_adj.setdefault(b, set()).add(a)

        for idx, bcc in enumerate(bccs):
            b_node = ("B", idx)
            for v in bcc:
                if v in articulation:
                    a_node = ("A", v)
                    add_tree_edge(b_node, a_node)

        def tree_node_for_vertex(v: int) -> Optional[Tuple[str, int]]:
            if v in articulation:
                return ("A", v)
            comps = bcc_of_vertex[v]
            if not comps:
                return None
            return ("B", comps[0])

        s_node = tree_node_for_vertex(start_id)
        t_node = tree_node_for_vertex(end_id)
        if s_node is None or t_node is None:
            return sorted(reachable)

        # BFS on block-cut tree to get path
        queue = [s_node]
        parent_tree: Dict[Tuple[str, int], Optional[Tuple[str, int]]] = {s_node: None}
        idx = 0
        while idx < len(queue):
            cur = queue[idx]
            idx += 1
            if cur == t_node:
                break
            for nxt in tree_adj.get(cur, ()):
                if nxt not in parent_tree:
                    parent_tree[nxt] = cur
                    queue.append(nxt)

        if t_node not in parent_tree:
            return sorted(reachable)

        path_nodes = set()
        cur = t_node
        while cur is not None:
            path_nodes.add(cur)
            cur = parent_tree[cur]

        keep = set()
        for node in path_nodes:
            if node[0] == "A":
                keep.add(node[1])
            else:
                keep.update(bccs[node[1]])

        return sorted(keep)

    def _dfs_route_nodes(self, start_id: int, allowed: Optional[set]) -> List[int]:
        if self.mesh is None:
            return []
        node_count = len(self.mesh.nodes)
        if not (0 <= start_id < node_count):
            return []
        if allowed is not None and start_id not in allowed:
            return []

        visited = set()
        route = [start_id]

        def dfs(u: int) -> None:
            visited.add(u)
            neighbors = sorted(self.mesh.nodes[u].neighbor_ids)
            for v in neighbors:
                if allowed is not None and v not in allowed:
                    continue
                if v in visited:
                    continue
                route.append(v)
                dfs(v)
                route.append(u)

        dfs(start_id)
        return route

    def _simple_path_to_end(self, start_id: int, end_id: int, allowed: Optional[set]) -> List[int]:
        if self.mesh is None:
            return []
        node_count = len(self.mesh.nodes)
        if not (0 <= start_id < node_count and 0 <= end_id < node_count):
            return []
        if allowed is not None and (start_id not in allowed or end_id not in allowed):
            return []

        visited = set()
        path: List[int] = []
        found = False

        def dfs(u: int) -> None:
            nonlocal found
            if found:
                return
            visited.add(u)
            path.append(u)
            if u == end_id:
                found = True
                return
            neighbors = sorted(self.mesh.nodes[u].neighbor_ids)
            for v in neighbors:
                if allowed is not None and v not in allowed:
                    continue
                if v in visited:
                    continue
                dfs(v)
                if found:
                    return
            path.pop()

        dfs(start_id)
        return path if found else []

    def _segment_distance(self, p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        ax, ay = a
        bx, by = b
        px, py = p
        abx, aby = bx - ax, by - ay
        apx, apy = px - ax, py - ay
        denom = abx * abx + aby * aby
        if denom <= 1e-6:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
        cx = ax + abx * t
        cy = ay + aby * t
        return math.hypot(px - cx, py - cy)

    def _segment_intersection(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        q1: Tuple[float, float],
        q2: Tuple[float, float],
    ) -> Optional[Tuple[float, float]]:
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = q1
        x4, y4 = q2

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-9:
            return None
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom

        def on_segment(a, b, c):
            return (
                min(a[0], b[0]) - 1e-6 <= c[0] <= max(a[0], b[0]) + 1e-6
                and min(a[1], b[1]) - 1e-6 <= c[1] <= max(a[1], b[1]) + 1e-6
            )

        p = (px, py)
        if on_segment(p1, p2, p) and on_segment(q1, q2, p):
            return p
        return None

    def _line_special_value(self, line: Any) -> int:
        for name in (
            "special",
            "line_special",
            "special_type",
            "line_action",
            "action",
        ):
            val = getattr(line, name, None)
            if isinstance(val, bool):
                if val:
                    return 1
                continue
            if isinstance(val, (int, float)) and int(val) != 0:
                return int(val)
        return 0

    def _ingest_special_lines(self, lines: Optional[List[Any]], sectors: Optional[List[Any]]) -> None:
        if self.special_lines_built:
            return

        candidates: List[Any] = []
        if lines:
            candidates = list(lines)
        elif sectors:
            for sec in sectors:
                for line in getattr(sec, "lines", []) or []:
                    candidates.append(line)

        if not candidates:
            return

        if lines:
            logger.info("[NAV] Using lines info for special linedefs")
        else:
            logger.info("[NAV] Using sectors' lines for special linedefs")

        specials = []
        info = []
        sample = None
        for idx, line in enumerate(candidates):
            if sample is None:
                sample = line
            try:
                x1 = float(getattr(line, "x1"))
                y1 = float(getattr(line, "y1"))
                x2 = float(getattr(line, "x2"))
                y2 = float(getattr(line, "y2"))
            except Exception:
                continue
            special_val = self._line_special_value(line)
            if special_val <= 0:
                continue
            seg = ((x1, y1), (x2, y2))
            specials.append(seg)
            info.append(
                {
                    "id": idx,
                    "special": special_val,
                    "segment": seg,
                }
            )

        if not specials:
            wad_specials, wad_info = self._load_special_linedefs_from_wad()
            if wad_specials:
                specials = wad_specials
                info = wad_info
                logger.info("[NAV] Loaded special linedefs from WAD: %s", len(specials))

        self.special_segments = specials
        self.special_line_info = info
        self.special_lines_built = True
        logger.info("[NAV] Lines info: total=%s special=%s", len(candidates), len(self.special_segments))
        if sample is not None:
            fields = {}
            for name in (
                "special",
                "line_special",
                "special_type",
                "line_action",
                "action",
                "flags",
                "is_blocking",
                "is_two_sided",
                "is_switch",
                "is_secret",
            ):
                if hasattr(sample, name):
                    fields[name] = getattr(sample, name)
            logger.info("[NAV] Line sample fields: %s", fields)

    def _load_special_linedefs_from_wad(self) -> Tuple[List[Tuple[Tuple[float, float], Tuple[float, float]]], List[dict]]:
        if not self.wad_path or not self.wad_path.exists() or not self.map_name:
            return [], []

        try:
            with self.wad_path.open("rb") as f:
                header = f.read(12)
                if len(header) < 12:
                    return [], []
                num_lumps = int.from_bytes(header[4:8], "little")
                dir_offset = int.from_bytes(header[8:12], "little")
                f.seek(dir_offset)
                directory = []
                for _ in range(num_lumps):
                    offset = int.from_bytes(f.read(4), "little")
                    size = int.from_bytes(f.read(4), "little")
                    name = f.read(8).rstrip(b"\0").decode("ascii", errors="ignore")
                    directory.append((name, offset, size))

            def is_map_marker(name: str) -> bool:
                if len(name) == 4 and name[0] == "E" and name[2] == "M":
                    return name[1].isdigit() and name[3].isdigit()
                if len(name) == 5 and name.startswith("MAP"):
                    return name[3].isdigit() and name[4].isdigit()
                return False

            map_name = self.map_name.upper()
            start_idx = None
            for i, (name, _, _) in enumerate(directory):
                if name.upper() == map_name:
                    start_idx = i
                    break
            if start_idx is None:
                return [], []

            end_idx = len(directory)
            for i in range(start_idx + 1, len(directory)):
                if is_map_marker(directory[i][0]):
                    end_idx = i
                    break

            vertex_lump = None
            linedef_lump = None
            for name, offset, size in directory[start_idx:end_idx]:
                if name.upper() == "VERTEXES":
                    vertex_lump = (offset, size)
                elif name.upper() == "LINEDEFS":
                    linedef_lump = (offset, size)

            if vertex_lump is None or linedef_lump is None:
                return [], []

            vertices: List[Tuple[float, float]] = []
            with self.wad_path.open("rb") as f:
                f.seek(vertex_lump[0])
                raw = f.read(vertex_lump[1])
                for i in range(0, len(raw), 4):
                    if i + 4 > len(raw):
                        break
                    x = int.from_bytes(raw[i:i+2], "little", signed=True)
                    y = int.from_bytes(raw[i+2:i+4], "little", signed=True)
                    vertices.append((float(x), float(y)))

            specials: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
            info: List[dict] = []
            with self.wad_path.open("rb") as f:
                f.seek(linedef_lump[0])
                raw = f.read(linedef_lump[1])
                for i in range(0, len(raw), 14):
                    if i + 14 > len(raw):
                        break
                    v1 = int.from_bytes(raw[i:i+2], "little", signed=False)
                    v2 = int.from_bytes(raw[i+2:i+4], "little", signed=False)
                    flags = int.from_bytes(raw[i+4:i+6], "little", signed=False)
                    special = int.from_bytes(raw[i+6:i+8], "little", signed=False)
                    tag = int.from_bytes(raw[i+8:i+10], "little", signed=False)
                    if special == 0:
                        continue
                    if v1 >= len(vertices) or v2 >= len(vertices):
                        continue
                    seg = (vertices[v1], vertices[v2])
                    specials.append(seg)
                    info.append(
                        {
                            "v1": v1,
                            "v2": v2,
                            "flags": flags,
                            "special": special,
                            "tag": tag,
                            "segment": seg,
                        }
                    )

            return specials, info
        except Exception as exc:
            logger.warning("[NAV] WAD special linedefs failed: %s", exc)
            return [], []

    def _pick_mesh_path(self) -> Optional[Path]:
        candidates: List[Path] = []
        if self.map_name:
            candidates.append(self.navmesh_dir / f"{self.map_name}.json")
            candidates.append(self.navmesh_dir / f"{self.map_name.lower()}.json")
        for name in ("E1M1.json", "MAP01.json", "e1m1.json", "map01.json"):
            candidates.append(self.navmesh_dir / name)

        for path in candidates:
            if path.exists():
                return path

        if self.navmesh_dir.exists():
            for path in sorted(self.navmesh_dir.glob("*.json")):
                return path
        return None

    def _ensure_mesh_loaded(self) -> bool:
        if self.mesh is not None:
            return True

        path = self._pick_mesh_path()
        if path is None:
            if self.mesh_path is None:
                logger.warning("[NAV] No navmesh JSON found in models/nav")
            self.mesh_path = None
            return False

        try:
            self.mesh = NavMesh.from_json(path)
            self.mesh.debug_astar = True
            self.mesh.debug_astar_interval = 10
            self.mesh_path = path
            logger.info(f"[NAV] Loaded navmesh: {path}")
            return True
        except Exception as exc:
            logger.warning(f"[NAV] Failed to load navmesh {path}: {exc}")
            self.mesh = None
            self.mesh_path = None
            return False

    def _build_node_route(self, start_id: Optional[int]) -> List[int]:
        if start_id is None or self.mesh is None:
            return []
        self.start_node_id = start_id
        end_id = self._find_exit_node()
        if end_id is None:
            # Fallback: pick the farthest reachable node if no exit is detected.
            best = None
            best_dist = -1.0
            start_pos = self.mesh.nodes[start_id].centroid
            for node in self.mesh.nodes:
                dx = node.centroid[0] - start_pos[0]
                dy = node.centroid[1] - start_pos[1]
                d = dx * dx + dy * dy
                if d > best_dist:
                    best_dist = d
                    best = node.node_id
            end_id = best
            logger.warning("[NAV] No exit special found; using farthest node %s", end_id)
        self.end_node_id = end_id

        pruned = None
        if end_id is not None:
            pruned = self._prune_to_simple_st_paths(start_id, end_id)
        self.pruned_nodes = pruned
        allowed = set(pruned) if pruned else None
        route = self._simple_path_to_end(start_id, end_id, allowed) if end_id is not None else []
        if not route and end_id is not None:
            logger.warning("[NAV] No pruned path found from %s to %s", start_id, end_id)
        self._write_route_debug(route)
        return route

    def _write_route_debug(self, route: List[int]) -> None:
        if self.mesh is None:
            return
        try:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            route_nodes = []
            for node_id in route:
                if 0 <= node_id < len(self.mesh.nodes):
                    node = self.mesh.nodes[node_id]
                    route_nodes.append(
                        {
                            "id": node.node_id,
                            "centroid": node.centroid,
                            "neighbors": node.neighbor_ids,
                        }
                    )
            payload = {
                "mesh": str(self.mesh_path) if self.mesh_path else None,
                "route_nodes": route,
                "route": route_nodes,
                "start_node": self.start_node_id,
                "end_node": self.end_node_id,
                "pruned_nodes": self.pruned_nodes,
            }
            (logs_dir / "navmesh_route.json").write_text(
                json.dumps(payload, indent=2)
            )
        except Exception as exc:
            logger.warning("[NAV] Failed to write route debug: %s", exc)

    def _compute_path_to_next_target(self, pos: Vec3, current_node_id: Optional[int]) -> bool:
        if self.mesh is None or current_node_id is None:
            return False

        group_id = self.mesh.get_nearest_group_id(pos, use_poly=True)
        if group_id < 0:
            return False

        while self.route_idx < len(self.route_nodes):
            target_id = self.route_nodes[self.route_idx]
            if target_id == current_node_id:
                self.route_idx += 1
                continue
            target_pos = self.mesh.nodes[target_id].centroid
            path = self.mesh.find_path(group_id, pos, target_pos)
            if path:
                self.path_points = path
                self.path_idx = 0
                self.current_target = target_id
                self.last_distance = None
                self.no_progress = 0
                self._write_path_debug(path, current_node_id, target_id)
                return True
            self.route_idx += 1

        self.path_points = []
        return False

    def _write_path_debug(self, path: List[Vec3], start_id: int, target_id: int) -> None:
        try:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            payload = {
                "mesh": str(self.mesh_path) if self.mesh_path else None,
                "start_node": start_id,
                "target_node": target_id,
                "points": path,
            }
            (logs_dir / "navmesh_path.json").write_text(
                json.dumps(payload, indent=2)
            )
        except Exception as exc:
            logger.warning("[NAV] Failed to write path debug: %s", exc)

    def decide_action(self, pos_x, pos_y, sectors=None, current_angle=0.0, lines=None):
        self.step += 1

        if not self._ensure_mesh_loaded():
            return ActionDecoder.forward()

        if not self.special_lines_built:
            self._ingest_special_lines(lines, sectors)

        pos = (float(pos_x), float(pos_y), 0.0)
        current_node = self.mesh.get_closest_node_in(pos, self.mesh.nodes, use_poly=True)
        current_node_id = current_node.node_id if current_node is not None else None

        # Stuck detection
        if self.last_pos is not None:
            dx = pos[0] - self.last_pos[0]
            dy = pos[1] - self.last_pos[1]
            if (dx * dx + dy * dy) < 8.0 * 8.0:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
        self.last_pos = (pos[0], pos[1])

        if self.stuck_counter > 10:
            escape = (self.stuck_counter // 3) % 4
            if self.stuck_counter % 5 == 0:
                return ActionDecoder.use()
            if escape == 0:
                return ActionDecoder.strafe_left()
            if escape == 1:
                return ActionDecoder.strafe_right()
            if escape == 2:
                return ActionDecoder.left_turn()
            return ActionDecoder.right_turn()

        if not self.route_built:
            self.route_nodes = self._build_node_route(current_node_id)
            self.route_idx = 0
            self.route_built = True
            if self.route_nodes:
                logger.info(f"[NAV] Route nodes: {len(self.route_nodes)}")

        if not self.route_nodes:
            return ActionDecoder.forward()

        if not self.path_points or self.path_idx >= len(self.path_points):
            if not self._compute_path_to_next_target(pos, current_node_id):
                return ActionDecoder.forward()

        # Advance to next path point when close enough
        while self.path_idx < len(self.path_points):
            target_pt = self.path_points[self.path_idx]
            dist = math.hypot(target_pt[0] - pos[0], target_pt[1] - pos[1])
            if dist < 32.0:
                self.path_idx += 1
                if self.path_idx >= len(self.path_points):
                    break
                continue
            break

        if self.path_idx >= len(self.path_points):
            self.path_points = []
            self.path_idx = 0
            self.current_target = None
            return ActionDecoder.forward()

        target = self.path_points[self.path_idx]
        distance = math.hypot(target[0] - pos[0], target[1] - pos[1])

        if self.current_target is None:
            self.last_distance = distance
            self.no_progress = 0
        else:
            if self.last_distance is not None and distance > self.last_distance - 1.0:
                self.no_progress += 1
            else:
                self.no_progress = 0
            self.last_distance = distance

        if self.no_progress > 12:
            self.y_inverted = not self.y_inverted
            self.no_progress = 0
            logger.info(f"[NAV] Flipped Y axis to {self.y_inverted}")

        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        if self.y_inverted:
            dy = -dy

        target_angle = math.degrees(math.atan2(dy, dx))
        angle_diff = target_angle - float(current_angle)
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360

        if self.step % 20 == 0:
            logger.info(
                f"[NAV] node={current_node_id} target={self.current_target} "
                f"dist={distance:.1f} ang={current_angle:.1f} diff={angle_diff:.1f}"
            )

        # Check for nearby special linedefs (doors, lifts, switches)
        special_dist = None
        special_hit = None
        if self.special_segments:
            p2d = (pos[0], pos[1])
            t2d = (target[0], target[1])
            best_dist = float("inf")
            for seg in self.special_segments:
                d = self._segment_distance(p2d, seg[0], seg[1])
                if d < best_dist:
                    best_dist = d
                    best_seg = seg
            if best_dist < float("inf"):
                special_dist = best_dist
                special_hit = best_seg

            if special_hit is not None:
                inter = self._segment_intersection(p2d, t2d, special_hit[0], special_hit[1])
                if inter is not None:
                    inter_dist = math.hypot(inter[0] - p2d[0], inter[1] - p2d[1])
                    special_dist = min(special_dist, inter_dist)

        if special_dist is not None and special_dist < 48.0:
            self.use_ticks = 4
            logger.info("[NAV] Using special linedef dist=%.1f", special_dist)

        if self.use_ticks > 0:
            self.use_ticks -= 1
            return ActionDecoder.use()
        if self.no_progress > 8 and distance < 128.0:
            self.use_ticks = 3
            return ActionDecoder.use()

        if abs(angle_diff) < 10:
            return ActionDecoder.forward()
        if abs(angle_diff) > 60:
            return ActionDecoder.left_turn() if angle_diff > 0 else ActionDecoder.right_turn()
        if angle_diff > 0:
            return ActionDecoder.forward_left_turn()
        return ActionDecoder.forward_right_turn()

    def render_debug_map(self, path: str, player_pos: Optional[Tuple[float, float]] = None) -> None:
        if self.mesh is None or not self.mesh.vertices:
            return

        try:
            import cv2
        except Exception:
            return

        xs = self.mesh.vertices[0::3]
        ys = self.mesh.vertices[1::3]
        if not xs or not ys:
            return

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = 800
        height = 800
        pad = 20
        img = np.zeros((height, width, 3), dtype=np.uint8)

        scale_x = (width - 2 * pad) / (max_x - min_x + 1e-6)
        scale_y = (height - 2 * pad) / (max_y - min_y + 1e-6)

        def to_px(p: Tuple[float, float]) -> Tuple[int, int]:
            x = int((p[0] - min_x) * scale_x + pad)
            y = int((p[1] - min_y) * scale_y + pad)
            return (x, height - y)

        # Draw polygons
        for node in self.mesh.nodes:
            if len(node.polygon) < 2:
                continue
            for i in range(len(node.polygon)):
                a = node.polygon[i]
                b = node.polygon[(i + 1) % len(node.polygon)]
                cv2.line(img, to_px(a), to_px(b), (120, 120, 120), 1)

        # Draw node centroids (all nodes)
        allowed = set(self.pruned_nodes) if self.pruned_nodes else None
        for node in self.mesh.nodes:
            if allowed is not None and node.node_id not in allowed:
                continue
            c = (node.centroid[0], node.centroid[1])
            cv2.circle(img, to_px(c), 3, (0, 220, 0), -1)
            cv2.putText(
                img,
                str(node.node_id),
                (to_px(c)[0] + 3, to_px(c)[1] - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

        # Draw planned node route
        if self.route_nodes and len(self.route_nodes) > 1:
            for i in range(1, len(self.route_nodes)):
                a_id = self.route_nodes[i - 1]
                b_id = self.route_nodes[i]
                if 0 <= a_id < len(self.mesh.nodes) and 0 <= b_id < len(self.mesh.nodes):
                    a = self.mesh.nodes[a_id].centroid
                    b = self.mesh.nodes[b_id].centroid
                    cv2.line(
                        img,
                        to_px((a[0], a[1])),
                        to_px((b[0], b[1])),
                        (0, 180, 255),
                        1,
                    )

        # Label start/end nodes
        if self.start_node_id is not None and 0 <= self.start_node_id < len(self.mesh.nodes):
            s = self.mesh.nodes[self.start_node_id].centroid
            sp = to_px((s[0], s[1]))
            cv2.circle(img, sp, 6, (0, 255, 0), -1)
            cv2.putText(
                img,
                f"S:{self.start_node_id}",
                (sp[0] + 6, sp[1] - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
        if self.end_node_id is not None and 0 <= self.end_node_id < len(self.mesh.nodes):
            e = self.mesh.nodes[self.end_node_id].centroid
            ep = to_px((e[0], e[1]))
            cv2.circle(img, ep, 6, (0, 0, 255), -1)
            cv2.putText(
                img,
                f"E:{self.end_node_id}",
                (ep[0] + 6, ep[1] - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        # Draw special linedefs
        for seg in self.special_segments:
            cv2.line(
                img,
                to_px(seg[0]),
                to_px(seg[1]),
                (255, 0, 0),
                2,
            )

        # Draw current path
        if self.path_points and len(self.path_points) > 1:
            for i in range(1, len(self.path_points)):
                a = (self.path_points[i - 1][0], self.path_points[i - 1][1])
                b = (self.path_points[i][0], self.path_points[i][1])
                cv2.line(img, to_px(a), to_px(b), (255, 255, 255), 2)

        # Draw player
        if player_pos is not None:
            cv2.circle(img, to_px(player_pos), 5, (255, 0, 0), -1)

        cv2.imwrite(path, img)
