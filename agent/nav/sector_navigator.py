"""
Sector-graph navigation using VizDoom sector geometry.
Builds a node per sector and plans routes through adjacent sectors.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
import json
from pathlib import Path

import numpy as np

from agent.utils.action_decoder import ActionDecoder

logger = logging.getLogger(__name__)

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


@dataclass
class SectorNode:
    idx: int
    node: Point
    bbox: Tuple[float, float, float, float]
    polygon: Optional[List[Point]]
    neighbors: List[int]
    segments: List[Segment]
    floor_height: float
    ceiling_height: float
    visited: bool = False


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _segment_distance(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-6:
        return _dist(p, a)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
    cx = ax + abx * t
    cy = ay + aby * t
    return math.hypot(px - cx, py - cy)


def _point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _normalize_point(p: Point, ndigits: int = 1) -> Point:
    return (round(p[0], ndigits), round(p[1], ndigits))


def _normalize_segment(a: Point, b: Point) -> Tuple[Point, Point]:
    na = _normalize_point(a)
    nb = _normalize_point(b)
    return (na, nb) if na <= nb else (nb, na)


def _order_polygon(segments: Sequence[Segment]) -> Optional[List[Point]]:
    adjacency: Dict[Point, List[Point]] = {}
    for a, b in segments:
        na = _normalize_point(a)
        nb = _normalize_point(b)
        adjacency.setdefault(na, []).append(nb)
        adjacency.setdefault(nb, []).append(na)

    if not adjacency:
        return None

    start = next(iter(adjacency))
    polygon = [start]
    prev = None
    current = start

    for _ in range(len(adjacency) + 2):
        neighbors = adjacency.get(current, [])
        if not neighbors:
            break
        nxt = neighbors[0] if neighbors[0] != prev else (neighbors[1] if len(neighbors) > 1 else None)
        if nxt is None:
            break
        if nxt == start:
            polygon.append(start)
            return polygon[:-1]
        polygon.append(nxt)
        prev, current = current, nxt

    return None


def _segment_intersection(p1: Point, p2: Point, q1: Point, q2: Point) -> Optional[Point]:
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


class SectorNavigator:
    """Node-based navigation across sectors using geometry info."""

    def __init__(self):
        self.sectors: Dict[int, SectorNode] = {}
        self.path: List[int] = []
        self.path_idx = 0
        self.sector_path: List[int] = []
        self.sector_path_idx = 0
        self.last_pos: Optional[Point] = None
        self.stuck_counter = 0
        self.built = False
        self.route_built = False
        self.bounds: Optional[Tuple[float, float, float, float]] = None
        self.step = 0
        self.current_target: Optional[int] = None
        self.last_distance: Optional[float] = None
        self.no_progress = 0
        self.y_inverted = False
        self.blocked_edges: set[Tuple[int, int]] = set()
        self.portal_segments: Dict[Tuple[Point, Point], Tuple[bool, bool]] = {}
        self.door_use_ticks = 0
        self.door_nudge_ticks = 0
        self.portal_by_edge: Dict[Tuple[int, int], List[Tuple[Segment, bool]]] = {}
        self.route_plan: List[int] = []
        self.secret_sectors: set[int] = set()
        self.skip_sectors: set[int] = set()

    def reset_episode(self):
        self.sectors.clear()
        self.path = []
        self.path_idx = 0
        self.sector_path = []
        self.sector_path_idx = 0
        self.last_pos = None
        self.stuck_counter = 0
        self.built = False
        self.route_built = False
        self.bounds = None
        self.step = 0
        self.current_target = None
        self.last_distance = None
        self.no_progress = 0
        self.y_inverted = False
        self.blocked_edges.clear()
        self.portal_segments.clear()
        self.door_use_ticks = 0
        self.door_nudge_ticks = 0
        self.portal_by_edge.clear()
        self.route_plan = []
        self.secret_sectors = set()
        self.skip_sectors = set()

    def _load_route_plan(self) -> None:
        candidates = [Path("route_plan.json"), Path("agent/nav/route_plan.json")]
        for path in candidates:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text())
                self.route_plan = [int(v) for v in data.get("route_sectors", [])]
                self.secret_sectors = set(int(v) for v in data.get("secret_sectors", []))
                self.skip_sectors = set(int(v) for v in data.get("skip_sectors", []))
                logger.info(
                    f"[ROUTE_PLAN] route={self.route_plan} "
                    f"secrets={sorted(self.secret_sectors)} skip={sorted(self.skip_sectors)}"
                )
                return
            except Exception as e:
                logger.warning(f"[ROUTE_PLAN] Failed to read {path}: {e}")

    def _save_sector_nodes(self) -> None:
        try:
            data = []
            for idx, sec in self.sectors.items():
                min_x, min_y, max_x, max_y = sec.bbox
                data.append(
                    {
                        "id": idx,
                        "node": [sec.node[0], sec.node[1]],
                        "bbox": [min_x, min_y, max_x, max_y],
                        "neighbors": sec.neighbors,
                        "area": (max_x - min_x) * (max_y - min_y),
                    }
                )
            Path("logs").mkdir(exist_ok=True)
            Path("logs/sector_nodes.json").write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def update_from_state(self, sectors) -> None:
        if self.built or not sectors:
            return

        sector_nodes: Dict[int, SectorNode] = {}
        segment_to_sectors: Dict[Tuple[Point, Point], List[int]] = {}
        segment_blocking: Dict[Tuple[Point, Point], bool] = {}
        segment_geom: Dict[Tuple[Point, Point], Segment] = {}

        all_x: List[float] = []
        all_y: List[float] = []

        for idx, sec in enumerate(sectors):
            lines = getattr(sec, "lines", [])
            segments: List[Segment] = []
            xs: List[float] = []
            ys: List[float] = []

            for line in lines:
                a = (float(line.x1), float(line.y1))
                b = (float(line.x2), float(line.y2))
                segments.append((a, b))
                xs.extend([a[0], b[0]])
                ys.extend([a[1], b[1]])
                all_x.extend([a[0], b[0]])
                all_y.extend([a[1], b[1]])

                norm_seg = _normalize_segment(a, b)
                segment_to_sectors.setdefault(norm_seg, []).append(idx)
                blocking = bool(getattr(line, "is_blocking", False))
                if blocking:
                    segment_blocking[norm_seg] = True
                segment_geom[norm_seg] = (a, b)

            if not xs or not ys:
                continue

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            polygon = _order_polygon(segments)

            node = self._pick_node(segments, (min_x, min_y, max_x, max_y), polygon)
            sector_nodes[idx] = SectorNode(
                idx=idx,
                node=node,
                bbox=(min_x, min_y, max_x, max_y),
                polygon=polygon,
                neighbors=[],
                segments=segments,
                floor_height=float(getattr(sec, "floor_height", 0.0)),
                ceiling_height=float(getattr(sec, "ceiling_height", 0.0)),
            )

        # Build adjacency
        for seg, ids in segment_to_sectors.items():
            if len(ids) < 2:
                continue
            a, b = ids[0], ids[1]
            if a in sector_nodes and b in sector_nodes:
                sec_a = sector_nodes[a]
                sec_b = sector_nodes[b]
                height_delta = abs(sec_a.ceiling_height - sec_b.ceiling_height)
                floor_delta = abs(sec_a.floor_height - sec_b.floor_height)
                door_candidate = height_delta > 8.0 or floor_delta > 24.0
                if b not in sector_nodes[a].neighbors:
                    sector_nodes[a].neighbors.append(b)
                if a not in sector_nodes[b].neighbors:
                    sector_nodes[b].neighbors.append(a)
                is_blocking = segment_blocking.get(seg, False)
                self.portal_segments[seg] = (is_blocking, door_candidate)
                geom = segment_geom.get(seg)
                if geom is not None:
                    self.portal_by_edge.setdefault((a, b), []).append((geom, is_blocking or door_candidate))
                    self.portal_by_edge.setdefault((b, a), []).append((geom, is_blocking or door_candidate))

        self.sectors = sector_nodes
        if all_x and all_y:
            self.bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
        self.built = True
        self._load_route_plan()
        self._save_sector_nodes()
        for idx in self.secret_sectors.union(self.skip_sectors):
            if idx in self.sectors:
                self.sectors[idx].visited = True
        logger.info(
            f"[SECTORS] Built {len(self.sectors)} sector nodes "
            f"with {sum(len(s.neighbors) for s in self.sectors.values())} links"
        )

    def _pick_node(
        self,
        segments: Sequence[Segment],
        bbox: Tuple[float, float, float, float],
        polygon: Optional[Sequence[Point]],
    ) -> Point:
        min_x, min_y, max_x, max_y = bbox
        if max_x - min_x < 1 or max_y - min_y < 1:
            return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

        grid_x = np.linspace(min_x + 16, max_x - 16, num=6)
        grid_y = np.linspace(min_y + 16, max_y - 16, num=6)

        best_point = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        best_score = -1.0

        for gx in grid_x:
            for gy in grid_y:
                p = (float(gx), float(gy))
                if polygon is not None and not _point_in_polygon(p, polygon):
                    continue
                clearance = min(_segment_distance(p, a, b) for a, b in segments)
                if clearance > best_score:
                    best_score = clearance
                    best_point = p

        return best_point

    def _current_sector(self, pos: Point) -> Optional[int]:
        for idx, sec in self.sectors.items():
            if sec.polygon is not None and _point_in_polygon(pos, sec.polygon):
                return idx
        # Fallback to closest node
        closest = None
        closest_dist = float("inf")
        for idx, sec in self.sectors.items():
            d = _dist(pos, sec.node)
            if d < closest_dist:
                closest_dist = d
                closest = idx
        return closest

    def _build_full_route(self, start_idx: int) -> List[int]:
        if start_idx is None:
            return []
        visited = set()
        route: List[int] = [start_idx]

        def dfs(u: int):
            visited.add(u)
            for v in sorted(self.sectors[u].neighbors):
                if v in self.secret_sectors or v in self.skip_sectors:
                    continue
                if v in visited:
                    continue
                route.append(v)
                dfs(v)
                route.append(u)

        dfs(start_idx)
        return route

    def _bfs_path(self, start_idx: int, goal_idx: int) -> List[int]:
        if start_idx is None or goal_idx is None:
            return []
        if start_idx == goal_idx:
            return [start_idx]
        queue = [start_idx]
        prev: Dict[int, Optional[int]] = {start_idx: None}
        while queue:
            cur = queue.pop(0)
            for nxt in self.sectors[cur].neighbors:
                if (cur, nxt) in self.blocked_edges:
                    continue
                if nxt in self.secret_sectors or nxt in self.skip_sectors:
                    continue
                if nxt in prev:
                    continue
                prev[nxt] = cur
                if nxt == goal_idx:
                    queue = []
                    break
                queue.append(nxt)
        if goal_idx not in prev:
            return []
        path: List[int] = []
        node = goal_idx
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        return path

    def _compute_sector_path(self, current_sector: Optional[int]) -> bool:
        if current_sector is None or not self.path:
            self.sector_path = []
            return False

        while self.path_idx < len(self.path):
            target = self.path[self.path_idx]
            if target in self.secret_sectors or target in self.skip_sectors:
                self.path_idx += 1
                continue
            if self.sectors[target].visited and target != current_sector:
                self.path_idx += 1
                continue
            if target == current_sector:
                self.path_idx += 1
                continue
            path = self._bfs_path(current_sector, target)
            if path:
                self.sector_path = path
                self.sector_path_idx = 0
                self.current_target = target
                self.last_distance = None
                self.no_progress = 0
                return True
            self.path_idx += 1

        self.sector_path = []
        return False

    def decide_action(self, pos_x, pos_y, sectors, current_angle=0.0):
        self.step += 1
        if sectors is None:
            return ActionDecoder.forward()

        self.update_from_state(sectors)
        if not self.sectors:
            return ActionDecoder.forward()

        pos = (float(pos_x), float(pos_y))
        current_sector = self._current_sector(pos)
        if current_sector is not None:
            self.sectors[current_sector].visited = True

        # Stuck detection
        if self.last_pos is not None:
            if _dist(pos, self.last_pos) < 8.0:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
        self.last_pos = pos

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
            if self.route_plan:
                self.path = [p for p in self.route_plan if p in self.sectors and p not in self.skip_sectors]
                if current_sector is not None and current_sector in self.path:
                    self.path_idx = self.path.index(current_sector)
                else:
                    self.path_idx = 0
                logger.info(f"[ROUTE] Using route plan: {self.path}")
            else:
                self.path = self._build_full_route(current_sector)
            self.path_idx = 0
            self.route_built = True
            if self.path:
                logger.info(f"[ROUTE] Full route length: {len(self.path)}")

        if not self.path:
            return ActionDecoder.forward()

        if not self.sector_path or self.sector_path_idx >= len(self.sector_path):
            if not self._compute_sector_path(current_sector):
                return ActionDecoder.forward()

        # Advance sector path if we're already in the next sector
        if (
            self.sector_path_idx + 1 < len(self.sector_path)
            and current_sector == self.sector_path[self.sector_path_idx + 1]
        ):
            self.sector_path_idx += 1

        target_sector = self.sector_path[self.sector_path_idx]
        next_sector = None
        if self.sector_path_idx + 1 < len(self.sector_path):
            next_sector = self.sector_path[self.sector_path_idx + 1]
            target_sector = next_sector

        target_node = self.sectors[target_sector].node
        desired_point = target_node
        portal_point = None
        if next_sector is not None and current_sector is not None:
            portals = self.portal_by_edge.get((current_sector, next_sector), [])
            if portals:
                # Prefer blocking segments (doors)
                portals = sorted(portals, key=lambda p: (not p[1]))
                seg = portals[0][0]
                portal_point = ((seg[0][0] + seg[1][0]) / 2.0, (seg[0][1] + seg[1][1]) / 2.0)
                desired_point = portal_point

        # Ray-cast along path to detect blocking portal segments
        if current_sector is not None:
            best_hit = None
            best_dist = float("inf")
            for (seg, blocking) in self.portal_by_edge.get((current_sector, target_sector), []):
                if not blocking:
                    continue
                hit = _segment_intersection(pos, desired_point, seg[0], seg[1])
                if hit is None:
                    continue
                d = _dist(pos, hit)
                if d < best_dist:
                    best_dist = d
                    best_hit = hit
            if best_hit is not None and best_dist < 256:
                portal_point = best_hit
                desired_point = portal_point

        distance = _dist(pos, desired_point)
        if self.current_target != target_sector:
            self.current_target = target_sector
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
            logger.info(f"[CALIBRATE] Flipped Y axis to {self.y_inverted}")

        dx = desired_point[0] - pos[0]
        dy = desired_point[1] - pos[1]
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
                f"[NAV] sector={current_sector} target={target_sector} "
                f"dist={distance:.1f} ang={current_angle:.1f} diff={angle_diff:.1f}"
            )

        # Door interaction heuristic: if we're facing the target but not getting closer, try USE
        if self.door_use_ticks > 0:
            self.door_use_ticks -= 1
            return ActionDecoder.use()
        if self.door_nudge_ticks > 0:
            self.door_nudge_ticks -= 1
            return ActionDecoder.forward()
        if portal_point is not None and distance < 48.0:
            self.door_use_ticks = 4
            self.door_nudge_ticks = 3
            return ActionDecoder.use()
        if self.no_progress > 6 and abs(angle_diff) < 15 and distance > 64.0:
            self.door_use_ticks = 4
            self.door_nudge_ticks = 3
            return ActionDecoder.use()

        # If still no progress, mark edge blocked and recompute path
        if self.no_progress > 8 and self.sector_path_idx + 1 < len(self.sector_path):
            cur = self.sector_path[self.sector_path_idx]
            nxt = self.sector_path[self.sector_path_idx + 1]
            self.blocked_edges.add((cur, nxt))
            self.blocked_edges.add((nxt, cur))
            logger.info(f"[BLOCK] Edge blocked between sectors {cur} and {nxt}")
            self.sector_path = []
            self.sector_path_idx = 0
            self.no_progress = 0

        if abs(angle_diff) < 10:
            return ActionDecoder.forward()
        if abs(angle_diff) > 60:
            return ActionDecoder.left_turn() if angle_diff > 0 else ActionDecoder.right_turn()
        if angle_diff > 0:
            return ActionDecoder.forward_left_turn()
        return ActionDecoder.forward_right_turn()

    def render_debug_map(self, path: str, player_pos: Optional[Point] = None) -> None:
        if not self.sectors or self.bounds is None:
            return

        import cv2

        min_x, min_y, max_x, max_y = self.bounds
        width = 800
        height = 800
        pad = 20
        img = np.zeros((height, width, 3), dtype=np.uint8)

        scale_x = (width - 2 * pad) / (max_x - min_x + 1e-6)
        scale_y = (height - 2 * pad) / (max_y - min_y + 1e-6)

        def to_px(p: Point) -> Tuple[int, int]:
            x = int((p[0] - min_x) * scale_x + pad)
            y = int((p[1] - min_y) * scale_y + pad)
            return (x, height - y)

        # Draw sector lines
        for sec in self.sectors.values():
            for a, b in sec.segments:
                pa = to_px(a)
                pb = to_px(b)
                color = (120, 120, 120)
                norm_seg = _normalize_segment(a, b)
                if norm_seg in self.portal_segments:
                    is_blocking, door_candidate = self.portal_segments[norm_seg]
                    if is_blocking:
                        color = (0, 0, 255)
                    elif door_candidate:
                        color = (0, 140, 255)
                    else:
                        color = (0, 200, 0)
                cv2.line(img, pa, pb, color, 1)

        # Draw planned route
        if self.path:
            for i in range(1, len(self.path)):
                a = self.sectors[self.path[i - 1]].node
                b = self.sectors[self.path[i]].node
                cv2.line(img, to_px(a), to_px(b), (255, 220, 80), 2)

        # Draw current sector path (active route segment)
        if self.sector_path and len(self.sector_path) > 1:
            for i in range(1, len(self.sector_path)):
                a = self.sectors[self.sector_path[i - 1]].node
                b = self.sectors[self.sector_path[i]].node
                cv2.line(img, to_px(a), to_px(b), (255, 255, 255), 2)

        # Draw nodes
        for sec in self.sectors.values():
            if sec.idx in self.secret_sectors:
                color = (180, 0, 180)
            else:
                color = (0, 255, 0) if sec.visited else (0, 140, 255)
            cv2.circle(img, to_px(sec.node), 3, color, -1)

        # Draw sector ids (small, optional)
        for sec in self.sectors.values():
            pos = to_px(sec.node)
            cv2.putText(
                img,
                str(sec.idx),
                (pos[0] + 4, pos[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (200, 200, 200),
                1,
                cv2.LINE_AA,
            )

        # Draw current target
        if self.path and 0 <= self.path_idx < len(self.path):
            target_node = self.sectors[self.path[self.path_idx]].node
            cv2.circle(img, to_px(target_node), 5, (255, 255, 255), 1)

        # Draw player
        if player_pos is not None:
            cv2.circle(img, to_px(player_pos), 5, (255, 0, 0), -1)

        cv2.imwrite(path, img)
