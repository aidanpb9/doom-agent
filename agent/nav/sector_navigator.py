"""
Navmesh-based navigation using zdoom-navmesh-generator output and
zdoom-pathfinding algorithms (A* + funnel).
"""

from __future__ import annotations

import logging
import math
import json
import time
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict

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
        self.exit_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.node_visit_radius = 64.0
        self.door_specials = {
            1, 26, 27, 28, 31, 32, 33, 34, 35, 46,
            61, 62, 63, 90, 103, 105, 109, 111, 117, 118,
            133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
            143, 145, 146, 147, 148, 149, 150, 151, 152, 153,
            156, 157, 158, 159, 160, 162, 163, 166, 169, 170,
            171, 175, 176, 177, 179, 180, 181, 182, 183, 184,
            185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195,
        }
        self.last_visited_route_node: Optional[int] = None
        self.angle_sign_history: List[int] = []
        self.subroute_active = False
        self.subroute_stage: Optional[str] = None
        self.subroute_points: List[Vec3] = []
        self.subroute_end_id: Optional[int] = None
        self.subroute_start_id: Optional[int] = None
        self.helper_points: List[Tuple[float, float]] = []
        self.subroute_trace: List[Tuple[float, float]] = []
        self.last_subroute_points: List[Vec3] = []
        self.last_subroute_trace: List[Tuple[float, float]] = []
        self.last_helper_points: List[Tuple[float, float]] = []
        self.subroute_pause_ticks = 0
        self.subroute_pause_duration = 10
        self.subroute_cooldown = 0
        self.stuck_node_id: Optional[int] = None
        self.pos_history: List[Tuple[float, float, float]] = []
        self.dist_history: List[Tuple[float, float]] = []
        self.stuck_window_s = 3.0
        self.stuck_radius = 96.0
        self.stuck_dist_delta = 16.0
        self.stuck_min_progress = 16.0
        self.stuck_time_s = 5.0
        self.use_cooldown = 0
        self.last_special_use_seg = None
        self.last_special_use_step = -999
        self.episode_start_time = None
        self.dist_target_id: Optional[int] = None
        self.combat_active = False
        self.exit_combat_override = False
        self.end_subroute_block_dist = 1536.0
        self.exit_focus_active = False
        self.exit_focus_stage: Optional[str] = None
        self.exit_focus_turn_dir = 1
        self.exit_focus_turn_ticks = 0
        self.exit_focus_push_ticks = 0
        self.exit_target_point: Optional[Tuple[float, float]] = None
        self.exit_target_line_point: Optional[Tuple[float, float]] = None
        self.exit_no_progress = 0
        self.exit_last_dist: Optional[float] = None
        self.exit_strafe_dir = 1
        self.exit_strafe_ticks = 0
        self.exit_force_dist = 512.0
        self.end_subroute_block_dist = 1536.0
        self.exit_node_id: Optional[int] = None
        self.explore_mode_steps = 0
        self.explore_end_id: Optional[int] = None
        self.explore_cooldown = 0
        self.exit_use_burst_ticks = 0
        self.exit_side_swap_cooldown = 0

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
            self.exit_segments = []
            self.last_visited_route_node = None
            self.angle_sign_history = []
            self.subroute_active = False
            self.subroute_stage = None
            self.subroute_points = []
            self.subroute_end_id = None
            self.subroute_start_id = None
            self.helper_points = []
            self.subroute_trace = []
            self.last_subroute_points = []
            self.last_subroute_trace = []
            self.last_helper_points = []
            self.subroute_pause_ticks = 0
            self.subroute_cooldown = 0
            self.stuck_node_id = None
            self.pos_history = []
            self.dist_history = []
            self.use_cooldown = 0
            self.last_special_use_seg = None
            self.last_special_use_step = -999
            self.episode_start_time = None
            self.dist_target_id = None
            self.combat_active = False
            self.exit_combat_override = False
            self.exit_focus_active = False
            self.exit_focus_stage = None
            self.exit_focus_turn_dir = 1
            self.exit_focus_turn_ticks = 0
            self.exit_focus_push_ticks = 0
            self.exit_target_point = None
            self.exit_target_line_point = None
            self.exit_no_progress = 0
            self.exit_last_dist = None
            self.exit_strafe_dir = 1
            self.exit_strafe_ticks = 0
            self.exit_node_id = None
            self.explore_mode_steps = 0
            self.explore_end_id = None
            self.explore_cooldown = 0
            self.exit_use_burst_ticks = 0
            self.exit_side_swap_cooldown = 0
            self.exit_force_dist = 512.0
            self.exit_target_point = None
            self.exit_target_line_point = None
            self.exit_no_progress = 0
            self.exit_last_dist = None
            self.exit_strafe_dir = 1
            self.exit_strafe_ticks = 0

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
        self.exit_segments = []
        self.last_visited_route_node = None
        self.angle_sign_history = []
        self.subroute_active = False
        self.subroute_stage = None
        self.subroute_points = []
        self.subroute_end_id = None
        self.subroute_start_id = None
        self.helper_points = []
        self.subroute_trace = []
        self.last_subroute_points = []
        self.last_subroute_trace = []
        self.last_helper_points = []
        self.subroute_pause_ticks = 0
        self.subroute_cooldown = 0
        self.stuck_node_id = None
        self.pos_history = []
        self.dist_history = []
        self.use_cooldown = 0
        self.last_special_use_seg = None
        self.last_special_use_step = -999
        self.episode_start_time = None
        self.dist_target_id = None
        self.combat_active = False
        self.exit_combat_override = False
        self.exit_focus_active = False
        self.exit_focus_stage = None
        self.exit_focus_turn_dir = 1
        self.exit_focus_turn_ticks = 0
        self.exit_focus_push_ticks = 0
        self.exit_target_point = None
        self.exit_target_line_point = None
        self.exit_no_progress = 0
        self.exit_last_dist = None
        self.exit_strafe_dir = 1
        self.exit_strafe_ticks = 0
        self.exit_node_id = None
        self.explore_mode_steps = 0
        self.explore_end_id = None
        self.explore_cooldown = 0
        self.exit_use_burst_ticks = 0
        self.exit_side_swap_cooldown = 0

    def _clear_route(self) -> None:
        self.route_nodes = []
        self.route_idx = 0
        self.route_built = False
        self.path_points = []
        self.path_idx = 0
        self.current_target = None
        self.last_distance = None
        self.no_progress = 0

    def _pick_farthest_node_from(self, pos: Tuple[float, float]) -> Optional[int]:
        if self.mesh is None or not self.mesh.nodes:
            return None
        best_id = None
        best_dist = -1.0
        for node in self.mesh.nodes:
            dx = node.centroid[0] - pos[0]
            dy = node.centroid[1] - pos[1]
            d = dx * dx + dy * dy
            if d > best_dist:
                best_dist = d
                best_id = node.node_id
        return best_id
        self.exit_force_dist = 512.0
        self.exit_target_point = None
        self.exit_target_line_point = None
        self.exit_no_progress = 0
        self.exit_last_dist = None
        self.exit_strafe_dir = 1
        self.exit_strafe_ticks = 0

    def set_combat_active(self, active: bool) -> None:
        if active and not self.combat_active:
            # Reset stuck-related timers when entering combat.
            self.stuck_counter = 0
            self.no_progress = 0
            self.last_distance = None
            self.pos_history = []
            self.dist_history = []
            self.angle_sign_history = []
            self.dist_target_id = None
        self.combat_active = active
        if active:
            self.exit_combat_override = True

    def _set_exit_combat_override(self, active: bool) -> None:
        self.exit_combat_override = active

    def _reset_exit_focus(self) -> None:
        self.exit_focus_active = False
        self.exit_focus_stage = None
        self.exit_focus_turn_dir = 1
        self.exit_focus_turn_ticks = 0
        self.exit_focus_push_ticks = 0

    @staticmethod
    def _is_exit_special(special: int) -> bool:
        # Common DOOM exit specials (exit/secret exit variants).
        return special in {11, 51, 52, 124, 197}

    def _is_door_special(self, special: int) -> bool:
        return special in self.door_specials

    @staticmethod
    def _polygon_centroid(poly: List[Tuple[float, float]]) -> Tuple[float, float]:
        if not poly:
            return (0.0, 0.0)
        sx = 0.0
        sy = 0.0
        for x, y in poly:
            sx += x
            sy += y
        inv = 1.0 / float(len(poly))
        return (sx * inv, sy * inv)

    def _build_helper_points(
        self,
        poly: List[Tuple[float, float]],
        obstacles: List[List[Tuple[float, float]]],
        target_pt: Tuple[float, float],
        offset_in: float = 40.0,
        bias: float = 40.0,
        max_helpers: int = 12,
    ) -> List[Tuple[float, float]]:
        if len(poly) < 3:
            return []
        cx, cy = self._polygon_centroid(poly)
        dirx = target_pt[0] - cx
        diry = target_pt[1] - cy
        dir_mag = math.hypot(dirx, diry)
        if dir_mag > 1e-6:
            dirx /= dir_mag
            diry /= dir_mag
        else:
            dirx = 0.0
            diry = 0.0

        edge_info: List[Tuple[float, float, float]] = []
        radial_sum = 0.0
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            mx = (a[0] + b[0]) * 0.5
            my = (a[1] + b[1]) * 0.5
            vx = mx - cx
            vy = my - cy
            radial = math.hypot(vx, vy)
            radial_sum += radial
            dot = vx * dirx + vy * diry
            edge_info.append((dot, mx, my))

        edge_info.sort(key=lambda x: x[0], reverse=True)
        avg_radial = radial_sum / max(1, len(edge_info))
        min_sep = max(68.0, avg_radial * 0.22)

        helpers: List[Tuple[float, float]] = []
        def add_candidate(candidate: Tuple[float, float], min_dist: float) -> None:
            if not self._point_in_poly_2d(candidate, poly):
                return
            for obs in obstacles:
                if self._point_in_poly_2d(candidate, obs):
                    return
            if any(math.hypot(candidate[0] - h[0], candidate[1] - h[1]) < min_dist for h in helpers):
                return
            helpers.append(candidate)

        def add_edge_candidates(dot_threshold: float) -> None:
            for dot, mx, my in edge_info:
                if len(helpers) >= max_helpers:
                    break
                if dot < dot_threshold:
                    continue
                dx = mx - cx
                dy = my - cy
                mag = math.hypot(dx, dy)
                if mag < 1e-6:
                    continue
                # Move inward from edge toward centroid, then bias toward target.
                ox = mx - (dx / mag) * offset_in
                oy = my - (dy / mag) * offset_in
                ox += dirx * bias
                oy += diry * bias
                candidate = (ox, oy)
                # Try without bias if it pushed outside.
                if not self._point_in_poly_2d(candidate, poly):
                    ox = mx - (dx / mag) * offset_in
                    oy = my - (dy / mag) * offset_in
                    candidate = (ox, oy)
                add_candidate(candidate, min_sep)

        # Prefer edges in the direction of the next target.
        add_edge_candidates(avg_radial * 0.1)
        if len(helpers) < 3:
            add_edge_candidates(0.0)

        # Add a couple of interior points in the direction of the next sector.
        if dir_mag > 1e-6:
            for t in (0.35, 0.65):
                cx2 = cx + dirx * avg_radial * t
                cy2 = cy + diry * avg_radial * t
                candidate = (cx2, cy2)
                add_candidate(candidate, min_sep)
                if len(helpers) >= max_helpers:
                    break

        # Final fallback: small ring around centroid to ensure helpers inside base sector.
        if not helpers:
            ring_r = max(16.0, avg_radial * 0.4)
            for k in range(8):
                ang = (math.pi * 2.0 * k) / 8.0
                candidate = (cx + math.cos(ang) * ring_r, cy + math.sin(ang) * ring_r)
                add_candidate(candidate, min_sep)
                if len(helpers) >= max_helpers:
                    break
        # Ensure at least two helpers if possible by relaxing spacing slightly.
        if len(helpers) < 2:
            relaxed_sep = max(24.0, min_sep * 0.6)
            for t in (0.25, 0.5, 0.75):
                cx2 = cx + dirx * avg_radial * t
                cy2 = cy + diry * avg_radial * t
                add_candidate((cx2, cy2), relaxed_sep)
                if len(helpers) >= 2:
                    break
        return helpers

    def _segment_clear(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        obstacles: List[List[Tuple[float, float]]],
    ) -> bool:
        for obs in obstacles:
            if self._segment_intersects_polygon(p1, p2, obs):
                return False
        return True

    def _segment_inside_polygon(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        poly: List[Tuple[float, float]],
    ) -> bool:
        if len(poly) < 3:
            return False
        if not self._point_in_poly_2d(p1, poly) or not self._point_in_poly_2d(p2, poly):
            return False
        # If the segment crosses the boundary at a non-endpoint, it leaves the polygon.
        eps = 1e-4
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            inter = self._segment_intersection(p1, p2, a, b)
            if inter is None:
                continue
            if math.hypot(inter[0] - p1[0], inter[1] - p1[1]) <= eps:
                continue
            if math.hypot(inter[0] - p2[0], inter[1] - p2[1]) <= eps:
                continue
            return False
        # Midpoint guard for concave polygons / numeric edge cases.
        mx = (p1[0] + p2[0]) * 0.5
        my = (p1[1] + p2[1]) * 0.5
        return self._point_in_poly_2d((mx, my), poly)

    def _compute_subroute_points(
        self,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        helper_pts: List[Tuple[float, float]],
        obstacles: List[List[Tuple[float, float]]],
        base_poly: List[Tuple[float, float]],
        min_helpers: int = 1,
    ) -> List[Vec3]:
        points = [start_pt] + helper_pts + [end_pt]
        n = len(points)
        if n < 2:
            return []
        helper_count = max(0, n - 2)
        if helper_count < min_helpers:
            return []

        inside_flags = [self._point_in_poly_2d((p[0], p[1]), base_poly) for p in points]

        # Build visibility graph
        neighbors: List[List[int]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if not self._segment_clear(points[i], points[j], obstacles):
                    continue
                if inside_flags[i] and inside_flags[j]:
                    if not self._segment_inside_polygon(points[i], points[j], base_poly):
                        continue
                neighbors[i].append(j)
                neighbors[j].append(i)

        start_idx = 0
        end_idx = n - 1

        def h(i: int) -> float:
            dx = points[i][0] - points[end_idx][0]
            dy = points[i][1] - points[end_idx][1]
            return math.hypot(dx, dy)

        import heapq
        open_heap: List[Tuple[float, float, int, int]] = []
        start_state = (start_idx, 0)
        g_scores: Dict[Tuple[int, int], float] = {start_state: 0.0}
        parent: Dict[Tuple[int, int], Tuple[int, int]] = {}
        heapq.heappush(open_heap, (h(start_idx), 0.0, start_idx, 0))
        visited = set()
        end_state: Optional[Tuple[int, int]] = None

        while open_heap:
            _, cur_g, u, mask = heapq.heappop(open_heap)
            state = (u, mask)
            if state in visited:
                continue
            visited.add(state)
            if u == end_idx and mask.bit_count() >= min_helpers:
                end_state = state
                break
            for v in neighbors[u]:
                new_mask = mask
                if 1 <= v <= n - 2:
                    new_mask |= 1 << (v - 1)
                step_cost = math.hypot(points[u][0] - points[v][0], points[u][1] - points[v][1])
                cand_g = cur_g + step_cost
                nxt = (v, new_mask)
                if cand_g < g_scores.get(nxt, float("inf")):
                    g_scores[nxt] = cand_g
                    parent[nxt] = state
                    heapq.heappush(open_heap, (cand_g + h(v), cand_g, v, new_mask))

        if end_state is None:
            return []
        # Reconstruct path
        path_idx: List[int] = []
        cur_state = end_state
        while True:
            path_idx.append(cur_state[0])
            if cur_state == start_state:
                break
            cur_state = parent[cur_state]
        path_idx.reverse()
        return [(points[i][0], points[i][1], 0.0) for i in path_idx]

    def _angle_oscillating(self) -> bool:
        if len(self.angle_sign_history) < 4:
            return False
        flips = 0
        for i in range(1, len(self.angle_sign_history)):
            if self.angle_sign_history[i] != self.angle_sign_history[i - 1]:
                flips += 1
        return flips >= 3

    def _start_subroute(self, current_node_id: Optional[int], pos2d: Tuple[float, float]) -> bool:
        if self.mesh is None:
            return False
        if self.last_visited_route_node is None:
            return False
        if self.route_idx >= len(self.route_nodes):
            return False
        if current_node_id is None:
            return False

        start_id = self.last_visited_route_node
        end_id = self.route_nodes[self.route_idx]
        if not (0 <= start_id < len(self.mesh.nodes) and 0 <= end_id < len(self.mesh.nodes)):
            return False

        base_id = start_id
        base_poly = self.mesh.nodes[base_id].polygon
        if len(base_poly) < 3:
            return False

        obstacles: List[List[Tuple[float, float]]] = []
        for node in self.mesh.nodes:
            if node.node_id == base_id:
                continue
            centroid = (node.centroid[0], node.centroid[1])
            if self._point_in_poly_2d(centroid, base_poly):
                obstacles.append(node.polygon)

        end_pt = (self.mesh.nodes[end_id].centroid[0], self.mesh.nodes[end_id].centroid[1])
        start_pt = (self.mesh.nodes[start_id].centroid[0], self.mesh.nodes[start_id].centroid[1])
        helper_pts = self._build_helper_points(base_poly, obstacles, end_pt)
        if not helper_pts:
            return False
        best_subroute: Optional[List[Vec3]] = None
        best_helper: Optional[Tuple[float, float]] = None
        best_len = None
        for hp in helper_pts:
            candidate = self._compute_subroute_points(
                start_pt,
                end_pt,
                [hp],
                obstacles,
                base_poly,
                min_helpers=1,
            )
            if not candidate:
                continue
            total = 0.0
            for i in range(1, len(candidate)):
                total += math.hypot(
                    candidate[i][0] - candidate[i - 1][0],
                    candidate[i][1] - candidate[i - 1][1],
                )
            if best_len is None or total < best_len:
                best_len = total
                best_subroute = candidate
                best_helper = hp
        if best_subroute is None or best_helper is None:
            return False
        helper_pts = [best_helper]
        subroute = best_subroute

        self.subroute_active = True
        cur_dist_start = math.hypot(pos2d[0] - start_pt[0], pos2d[1] - start_pt[1])
        cur_dist_end = math.hypot(pos2d[0] - end_pt[0], pos2d[1] - end_pt[1])
        skip_return = cur_dist_end < cur_dist_start
        self.subroute_stage = "route" if skip_return else "return"
        self.subroute_points = subroute
        self.subroute_start_id = start_id
        self.subroute_end_id = end_id
        self.helper_points = helper_pts
        self.subroute_trace = []
        self.last_subroute_points = list(subroute)
        self.last_subroute_trace = []
        self.last_helper_points = list(helper_pts)
        self.subroute_pause_ticks = 0
        self.stuck_node_id = current_node_id
        self.subroute_cooldown = 60
        # Reset steering inversion so subroute follows the planned geometry.
        self.y_inverted = False
        # Force a fresh return path so we don't keep following the old main path.
        self.path_points = []
        self.path_idx = 0
        self.current_target = None
        self.last_distance = None
        self.no_progress = 0
        if skip_return:
            route_points = list(self.subroute_points)
            if route_points:
                route_points[0] = (pos2d[0], pos2d[1], 0.0)
            self.path_points = route_points
            self.path_idx = 0
            logger.info("[NAV] Subroute skipping return leg (already closer to target)")
        logger.info(
            "[NAV] Subroute start=%s end=%s helpers=%s",
            start_id,
            end_id,
            len(helper_pts),
        )
        return True

    def _compute_path_to_point(self, pos: Vec3, target_pos: Vec3) -> bool:
        if self.mesh is None:
            return False
        group_id = self.mesh.get_nearest_group_id(pos, use_poly=True)
        if group_id < 0:
            return False
        path = self.mesh.find_path(group_id, pos, target_pos)
        if path:
            self.path_points = path
            self.path_idx = 0
            self.current_target = None
            self.last_distance = None
            self.no_progress = 0
            return True
        return False

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

    def _closest_point_on_segment(
        self,
        p: Tuple[float, float],
        a: Tuple[float, float],
        b: Tuple[float, float],
    ) -> Tuple[float, float]:
        ax, ay = a
        bx, by = b
        px, py = p
        abx, aby = bx - ax, by - ay
        apx, apy = px - ax, py - ay
        denom = abx * abx + aby * aby
        if denom <= 1e-6:
            return (ax, ay)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
        return (ax + abx * t, ay + aby * t)

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

    def _segment_intersects_polygon(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        poly: List[Tuple[float, float]],
    ) -> bool:
        if len(poly) < 3:
            return False
        if self._point_in_poly_2d(p1, poly) or self._point_in_poly_2d(p2, poly):
            return True
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            if self._segment_intersection(p1, p2, a, b) is not None:
                return True
        return False

    @staticmethod
    def _point_in_poly_2d(pt: Tuple[float, float], poly: List[Tuple[float, float]]) -> bool:
        x, y = pt
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

    def _crossed_door_linedef(self, last_pos: Tuple[float, float], pos: Tuple[float, float]) -> bool:
        if not self.special_line_info:
            return False
        p1 = (float(last_pos[0]), float(last_pos[1]))
        p2 = (float(pos[0]), float(pos[1]))
        for info in self.special_line_info:
            try:
                special = int(info.get("special", 0))
            except Exception:
                continue
            if not self._is_door_special(special):
                continue
            seg = info.get("segment")
            if not seg or len(seg) != 2:
                continue
            if self._segment_intersection(p1, p2, seg[0], seg[1]) is not None:
                return True
        return False

    def _nearest_special(self, p2d: Tuple[float, float]) -> Tuple[Optional[float], Optional[Tuple[Tuple[float, float], Tuple[float, float]]]]:
        if not self.special_segments:
            return None, None
        best_dist = float("inf")
        best_seg = None
        for seg in self.special_segments:
            d = self._segment_distance(p2d, seg[0], seg[1])
            if d < best_dist:
                best_dist = d
                best_seg = seg
        if best_seg is None:
            return None, None
        return best_dist, best_seg

    def _nearest_exit(self, p2d: Tuple[float, float]) -> Tuple[Optional[float], Optional[Tuple[Tuple[float, float], Tuple[float, float]]]]:
        if not self.exit_segments:
            return None, None
        best_dist = float("inf")
        best_seg = None
        for seg in self.exit_segments:
            d = self._segment_distance(p2d, seg[0], seg[1])
            if d < best_dist:
                best_dist = d
                best_seg = seg
        if best_seg is None:
            return None, None
        return best_dist, best_seg

    def _nearest_door(self, p2d: Tuple[float, float]) -> Tuple[Optional[float], Optional[dict]]:
        if not self.special_line_info:
            return None, None
        best_dist = float("inf")
        best_info = None
        for info in self.special_line_info:
            try:
                special = int(info.get("special", 0))
            except Exception:
                continue
            if not self._is_door_special(special):
                continue
            seg = info.get("segment")
            if not seg or len(seg) != 2:
                continue
            d = self._segment_distance(p2d, seg[0], seg[1])
            if d < best_dist:
                best_dist = d
                best_info = info
        if best_info is None:
            return None, None
        return best_dist, best_info

    def _handle_exit(self, pos: Vec3, current_angle: float = 0.0) -> Optional[List[int]]:
        dist, seg = self._nearest_exit((pos[0], pos[1]))
        if dist is None or seg is None:
            self.exit_target_point = None
            self.exit_target_line_point = None
            self.exit_no_progress = 0
            self.exit_last_dist = None
            return None
        if self.step % 40 == 0:
            logger.info("[NAV] Exit mode dist=%.1f", dist)

        # If there's a nearby door between us and the exit, prioritize opening it.
        door_dist, door_info = self._nearest_door((pos[0], pos[1]))
        if door_info is not None and door_dist is not None and door_dist < 128.0 and door_dist <= dist + 32.0:
            door_seg = door_info.get("segment") if isinstance(door_info, dict) else None
            if door_seg and len(door_seg) == 2:
                door_pt = self._closest_point_on_segment((pos[0], pos[1]), door_seg[0], door_seg[1])
                dx_door = door_pt[0] - pos[0]
                dy_door = door_pt[1] - pos[1]
                door_angle = math.degrees(math.atan2(dy_door, dx_door))
                door_diff = door_angle - float(current_angle)
                while door_diff > 180:
                    door_diff -= 360
                while door_diff < -180:
                    door_diff += 360
                if abs(door_diff) > 20.0:
                    action = (
                        ActionDecoder.forward_left_turn()
                        if door_diff > 0
                        else ActionDecoder.forward_right_turn()
                    )
                else:
                    action = ActionDecoder.forward()
                if len(action) >= 7:
                    action[6] = 1
                return action
        ax, ay = seg[0]
        bx, by = seg[1]
        abx = bx - ax
        aby = by - ay
        denom = abx * abx + aby * aby
        t = 0.5
        if denom > 1e-6:
            t_raw = ((pos[0] - ax) * abx + (pos[1] - ay) * aby) / denom
            t_clamped = max(0.0, min(1.0, t_raw))
            # If we're hugging an endpoint, bias toward the midpoint to hit the switch face.
            if 0.15 <= t_clamped <= 0.85:
                t = t_clamped
        target_line = (ax + abx * t, ay + aby * t)
        self.exit_target_line_point = target_line
        dx_line = target_line[0] - pos[0]
        dy_line = target_line[1] - pos[1]
        target_angle = math.degrees(math.atan2(dy_line, dx_line))
        angle_diff = target_angle - float(current_angle)
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        if self.exit_last_dist is not None:
            if dist > self.exit_last_dist - 1.0:
                self.exit_no_progress += 1
            else:
                self.exit_no_progress = 0
        self.exit_last_dist = dist
        if dist < 256.0 and self.exit_no_progress > 10 and self.exit_side_swap_cooldown == 0:
            # Try approaching the exit line from the opposite side.
            vx = seg[1][0] - seg[0][0]
            vy = seg[1][1] - seg[0][1]
            vmag = math.hypot(vx, vy)
            if vmag > 1e-6:
                nx = vy / vmag
                ny = -vx / vmag
                side = 1.0 if ((pos[0] - target_line[0]) * nx + (pos[1] - target_line[1]) * ny) >= 0 else -1.0
                offset = 64.0
                swap_pt = (
                    target_line[0] - side * nx * offset,
                    target_line[1] - side * ny * offset,
                    0.0,
                )
                if self._compute_path_to_point(pos, swap_pt):
                    self.current_target = self.end_node_id
                    self.exit_no_progress = 0
                    self.exit_last_dist = None
                    self.exit_side_swap_cooldown = 60
                    logger.info("[NAV] Exit side-swap: offset=%.1f", offset)
                    return None
        dx = pos[0] - target_line[0]
        dy = pos[1] - target_line[1]
        target_x = target_line[0]
        target_y = target_line[1]
        dist_to_line = math.hypot(dx, dy)
        if dist_to_line > 1e-3:
            inset = min(24.0, dist_to_line * 0.5)
            target_x = target_line[0] + (dx / dist_to_line) * inset
            target_y = target_line[1] + (dy / dist_to_line) * inset
        self.exit_target_point = (target_x, target_y)
        if dist_to_line < 48.0:
            if self.exit_use_burst_ticks <= 0:
                self.exit_use_burst_ticks = 20
            if self.exit_use_burst_ticks > 0:
                self.exit_use_burst_ticks -= 1
                if abs(angle_diff) > 8.0:
                    return ActionDecoder.left_turn() if angle_diff > 0 else ActionDecoder.right_turn()
                else:
                    action = ActionDecoder.use()
                if len(action) >= 7:
                    action[6] = 1
                return action
        if dist < 200.0 and self.exit_no_progress > 6:
            target = (target_line[0], target_line[1], 0.0)
            if self._compute_path_to_point(pos, target):
                self.current_target = self.end_node_id
                self.last_distance = None
                self.no_progress = 0
                return None
        if dist < 256.0 and self.exit_no_progress > 6:
            # Stall shimmy: face the exit line, strafe along it, and use.
            self.exit_target_point = (target_line[0], target_line[1])
            self.exit_strafe_ticks += 1
            if self.exit_strafe_ticks >= 10:
                self.exit_strafe_ticks = 0
                self.exit_strafe_dir *= -1
            if abs(angle_diff) > 25.0:
                action = (
                    ActionDecoder.forward_left_turn()
                    if angle_diff > 0
                    else ActionDecoder.forward_right_turn()
                )
            else:
                action = (
                    ActionDecoder.forward_strafe_left()
                    if self.exit_strafe_dir > 0
                    else ActionDecoder.forward_strafe_right()
                )
            if len(action) >= 7:
                action[6] = 1
            return action
        if dist < 180.0 and self.exit_no_progress > 6:
            # Use-only burst while facing the exit line to ensure activation.
            if self.exit_use_burst_ticks <= 0:
                self.exit_use_burst_ticks = 20
            if self.exit_use_burst_ticks > 0:
                self.exit_use_burst_ticks -= 1
                if abs(angle_diff) > 10.0:
                    action = ActionDecoder.left_turn() if angle_diff > 0 else ActionDecoder.right_turn()
                else:
                    action = ActionDecoder.use()
                if len(action) >= 7:
                    action[6] = 1
                return action
        if dist_to_line < 64.0:
            if abs(angle_diff) > 12.0:
                action = (
                    ActionDecoder.forward_left_turn()
                    if angle_diff > 0
                    else ActionDecoder.forward_right_turn()
                )
            else:
                action = ActionDecoder.use()
            if len(action) >= 7:
                action[6] = 1
            return action
        if dist < 192.0:
            # Close to the exit: keep moving, use, and strafe if we aren't closing the gap.
            if self.exit_no_progress > 8:
                self.exit_strafe_ticks += 1
                if self.exit_strafe_ticks >= 12:
                    self.exit_strafe_ticks = 0
                    self.exit_strafe_dir *= -1
                action = (
                    ActionDecoder.forward_strafe_left()
                    if self.exit_strafe_dir > 0
                    else ActionDecoder.forward_strafe_right()
                )
            else:
                if abs(angle_diff) > 20.0:
                    action = (
                        ActionDecoder.forward_left_turn()
                        if angle_diff > 0
                        else ActionDecoder.forward_right_turn()
                    )
                else:
                    action = ActionDecoder.forward()
            if len(action) >= 7:
                action[6] = 1
            return action
        if dist < 320.0:
            # Close enough: steer directly at the exit line and keep using.
            self.exit_strafe_ticks += 1
            if self.exit_strafe_ticks >= 12:
                self.exit_strafe_ticks = 0
                self.exit_strafe_dir *= -1
            if abs(angle_diff) > 30.0:
                action = (
                    ActionDecoder.forward_left_turn()
                    if angle_diff > 0
                    else ActionDecoder.forward_right_turn()
                )
            elif self.exit_no_progress > 4:
                action = (
                    ActionDecoder.forward_strafe_left()
                    if self.exit_strafe_dir > 0
                    else ActionDecoder.forward_strafe_right()
                )
            else:
                action = ActionDecoder.forward()
            if len(action) >= 7:
                action[6] = 1
            return action
        target = (target_x, target_y, 0.0)
        # Force a fresh path toward the exit line target.
        self._compute_path_to_point(pos, target)
        self.current_target = self.end_node_id
        self.last_distance = None
        self.no_progress = 0
        return None

    def _handle_exit_focus(self, pos: Vec3, current_angle: float) -> Optional[List[int]]:
        dist, seg = self._nearest_exit((pos[0], pos[1]))
        if dist is None or seg is None:
            return None
        target_pt = self._closest_point_on_segment((pos[0], pos[1]), seg[0], seg[1])
        dx = target_pt[0] - pos[0]
        dy = target_pt[1] - pos[1]
        target_angle = math.degrees(math.atan2(dy, dx))
        angle_diff = target_angle - float(current_angle)
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        seen = abs(angle_diff) <= 25.0

        if not self.exit_focus_active:
            self.exit_focus_active = True
            self.exit_focus_stage = "scan"
            self.exit_focus_turn_dir = 1
            self.exit_focus_turn_ticks = 0
            self.exit_focus_push_ticks = 0
            logger.info("[NAV] Exit focus: scan for exit line")

        if self.exit_focus_stage == "scan":
            if seen:
                self.exit_focus_stage = "approach"
                logger.info("[NAV] Exit focus: exit line spotted, approaching")
            else:
                self.exit_focus_turn_ticks += 1
                if self.exit_focus_turn_ticks >= 60:
                    self.exit_focus_turn_ticks = 0
                    self.exit_focus_turn_dir *= -1
                return ActionDecoder.left_turn() if self.exit_focus_turn_dir > 0 else ActionDecoder.right_turn()

        if self.exit_focus_stage == "approach":
            if self.exit_focus_push_ticks > 0:
                self.exit_focus_push_ticks -= 1
                action = ActionDecoder.forward()
                if len(action) >= 7:
                    action[6] = 1
                return action
            if not seen and dist > 96.0:
                self.exit_focus_stage = "scan"
                return ActionDecoder.left_turn() if self.exit_focus_turn_dir > 0 else ActionDecoder.right_turn()
            if dist < 64.0:
                self.exit_focus_push_ticks = 25
                action = ActionDecoder.forward()
                if len(action) >= 7:
                    action[6] = 1
                return action
            if abs(angle_diff) > 12.0:
                return ActionDecoder.left_turn() if angle_diff > 0 else ActionDecoder.right_turn()
            return ActionDecoder.forward()

        return None

    def _update_pos_history(self, pos: Tuple[float, float]) -> Tuple[bool, float]:
        now = time.perf_counter()
        self.pos_history.append((now, pos[0], pos[1]))
        cutoff = now - self.stuck_window_s
        while self.pos_history and self.pos_history[0][0] < cutoff:
            self.pos_history.pop(0)
        if len(self.pos_history) < 2:
            return False, 0.0
        xs = [p[1] for p in self.pos_history]
        ys = [p[2] for p in self.pos_history]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        diag = math.hypot(dx, dy)
        return diag < self.stuck_radius, diag

    def _update_dist_history(self, distance: float) -> Tuple[bool, float]:
        now = time.perf_counter()
        self.dist_history.append((now, distance))
        cutoff = now - self.stuck_window_s
        while self.dist_history and self.dist_history[0][0] < cutoff:
            self.dist_history.pop(0)
        if len(self.dist_history) < 2:
            return False, 0.0
        start = self.dist_history[0][1]
        end = self.dist_history[-1][1]
        progress = start - end
        return progress < self.stuck_dist_delta, progress

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
            if self._is_exit_special(special_val):
                self.exit_segments.append(seg)

        if not specials:
            wad_specials, wad_info = self._load_special_linedefs_from_wad()
            if wad_specials:
                specials = wad_specials
                info = wad_info
                self.exit_segments = [
                    entry["segment"]
                    for entry in wad_info
                    if self._is_exit_special(int(entry.get("special", 0)))
                ]
                logger.info("[NAV] Loaded special linedefs from WAD: %s", len(specials))

        self.special_segments = specials
        self.special_line_info = info
        self.special_lines_built = True
        logger.info(
            "[NAV] Lines info: total=%s special=%s exit=%s",
            len(candidates),
            len(self.special_segments),
            len(self.exit_segments),
        )
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

    def _build_node_route(
        self,
        start_id: Optional[int],
        end_id_override: Optional[int] = None,
    ) -> List[int]:
        if start_id is None or self.mesh is None:
            return []
        self.start_node_id = start_id
        if end_id_override is not None:
            end_id = end_id_override
        else:
            if self.exit_node_id is None:
                self.exit_node_id = self._find_exit_node()
            end_id = self.exit_node_id
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
        if self.mesh is None:
            return False

        group_id = self.mesh.get_nearest_group_id(pos, use_poly=True)
        if group_id < 0:
            return False

        while self.route_idx < len(self.route_nodes):
            target_id = self.route_nodes[self.route_idx]
            target_pos = self.mesh.nodes[target_id].centroid
            path = self.mesh.find_path(group_id, pos, target_pos)
            if path:
                self.path_points = path
                self.path_idx = 0
                self.current_target = target_id
                self.last_distance = None
                self.no_progress = 0
                self._write_path_debug(path, current_node_id if current_node_id is not None else -1, target_id)
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
        if self.subroute_cooldown > 0:
            self.subroute_cooldown -= 1
        if self.explore_cooldown > 0:
            self.explore_cooldown -= 1
        if self.exit_side_swap_cooldown > 0:
            self.exit_side_swap_cooldown -= 1
        if self.explore_mode_steps > 0:
            self.explore_mode_steps -= 1
            if self.explore_mode_steps == 0 and self.explore_end_id is not None:
                logger.info("[NAV] Explore complete; returning to exit route")
                self.explore_end_id = None
                self._clear_route()

        if not self._ensure_mesh_loaded():
            return ActionDecoder.forward()

        if not self.special_lines_built:
            self._ingest_special_lines(lines, sectors)

        if self.episode_start_time is None:
            self.episode_start_time = time.perf_counter()

        pos = (float(pos_x), float(pos_y), 0.0)
        current_node = self.mesh.get_closest_node_in(pos, self.mesh.nodes, use_poly=True)
        current_node_id = current_node.node_id if current_node is not None else None
        p2d = (pos[0], pos[1])
        exploring = self.explore_mode_steps > 0 and self.explore_end_id is not None
        end_dist = None
        if (not exploring) and self.exit_node_id is not None and 0 <= self.exit_node_id < len(self.mesh.nodes):
            end_centroid = self.mesh.nodes[self.exit_node_id].centroid
            end_dist = math.hypot(end_centroid[0] - pos[0], end_centroid[1] - pos[1])
        nearest_special_dist, nearest_special_seg = self._nearest_special(p2d)
        near_special = nearest_special_dist is not None and nearest_special_dist < 48.0
        near_special_stuck = nearest_special_dist is not None and nearest_special_dist < 12.0
        door_dist, _ = self._nearest_door(p2d)
        near_door_stuck = door_dist is not None and door_dist < 24.0

        # Stuck detection
        prev_pos = self.last_pos
        if prev_pos is not None:
            dx = pos[0] - prev_pos[0]
            dy = pos[1] - prev_pos[1]
            if (dx * dx + dy * dy) < 8.0 * 8.0:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
        self.last_pos = (pos[0], pos[1])

        if self.combat_active or self.route_idx >= len(self.route_nodes):
            pos_stuck, pos_spread = False, 0.0
            min_elapsed = False
            has_progress = self.last_visited_route_node is not None and self.route_idx > 0
        else:
            pos_stuck, pos_spread = self._update_pos_history((pos[0], pos[1]))
            if near_special_stuck:
                pos_stuck = False
            min_elapsed = False
            if self.episode_start_time is not None:
                min_elapsed = (time.perf_counter() - self.episode_start_time) >= 3.0
            has_progress = self.last_visited_route_node is not None and self.route_idx > 0
            pos_stuck = pos_stuck and min_elapsed and has_progress

        if not self.route_built:
            self.route_nodes = self._build_node_route(
                current_node_id,
                end_id_override=self.explore_end_id if exploring else None,
            )
            self.route_idx = 0
            self.route_built = True
            if self.route_nodes:
                logger.info(f"[NAV] Route nodes: {len(self.route_nodes)}")

        if not self.route_nodes:
            return ActionDecoder.forward()

        in_end_sector = False
        # If we're already inside the end sector, stop everything and focus on the exit.
        if (not exploring) and self.exit_node_id is not None and self.mesh is not None:
            if 0 <= self.exit_node_id < len(self.mesh.nodes):
                end_poly = self.mesh.nodes[self.exit_node_id].polygon
                inside_end = self._point_in_poly_2d((pos[0], pos[1]), end_poly)
                entered_end = current_node_id == self.exit_node_id if current_node_id is not None else False
                if inside_end or entered_end:
                    in_end_sector = True
                    if self.subroute_active:
                        self.subroute_active = False
                        self.subroute_stage = None
                        self.subroute_points = []
                        self.helper_points = []
                        self.subroute_trace = []
                        self.stuck_node_id = None
                    self.path_points = []
                    self.path_idx = 0
                    self.current_target = None
                    self.last_distance = None
                    self.no_progress = 0
                    self.route_idx = len(self.route_nodes)
                    self.exit_combat_override = True
                    self._reset_exit_focus()
                    logger.info("[NAV] Exit focus: inside end sector (node=%s)", self.exit_node_id)
                    exit_action = self._handle_exit(pos, current_angle)
                    if exit_action is not None:
                        return exit_action

        # Do not bias to the exit until we actually reach the end sector.
        if (
            not exploring
            and not self.subroute_active
            and self.route_idx >= len(self.route_nodes)
            and not in_end_sector
        ):
            # Route ended but we're not in the end sector; rebuild instead of forcing exit.
            self.exit_combat_override = False
            self._clear_route()
        elif not in_end_sector:
            self.exit_combat_override = False

        if not self.subroute_active:
            crossed_door = False
            if prev_pos is not None:
                crossed_door = self._crossed_door_linedef(prev_pos, (pos[0], pos[1]))
            door_consumed = False
            # Follow route nodes in order; mark visited when close to centroid,
            # passing through the polygon, or crossing a door linedef.
            while self.route_idx < len(self.route_nodes):
                target_id = self.route_nodes[self.route_idx]
                if 0 <= target_id < len(self.mesh.nodes):
                    tgt = self.mesh.nodes[target_id].centroid
                    dist = math.hypot(tgt[0] - pos[0], tgt[1] - pos[1])
                    passed = False
                    if prev_pos is not None:
                        poly = self.mesh.nodes[target_id].polygon
                        passed = self._segment_intersects_polygon(prev_pos, (pos[0], pos[1]), poly)
                    door_hit = crossed_door and not door_consumed
                    entered = current_node_id == target_id if current_node_id is not None else False
                    if entered or dist <= self.node_visit_radius or passed or door_hit:
                        logger.info(
                            "[NAV] Visit node=%s dist=%.1f passed=%s door=%s entered=%s",
                            target_id,
                            dist,
                            passed,
                            door_hit,
                            entered,
                        )
                        self.last_visited_route_node = target_id
                        if self.end_node_id is not None and target_id == self.end_node_id:
                            self.route_idx = len(self.route_nodes)
                        else:
                            self.route_idx += 1
                        self.path_points = []
                        self.path_idx = 0
                        self.current_target = None
                        if door_hit:
                            door_consumed = True
                        continue
                break

        if self.subroute_active:
            if self.subroute_stage == "pause":
                if self.subroute_pause_ticks > 0:
                    self.subroute_pause_ticks -= 1
                    return ActionDecoder.null_action()
                self.subroute_stage = "route"
                route_points = list(self.subroute_points)
                if route_points:
                    route_points[0] = (pos[0], pos[1], 0.0)
                self.path_points = route_points
                self.path_idx = 0
            if self.subroute_stage == "return":
                if self.subroute_start_id is None or not (0 <= self.subroute_start_id < len(self.mesh.nodes)):
                    self.subroute_active = False
                else:
                    start_pos = self.mesh.nodes[self.subroute_start_id].centroid
                    entered_start = current_node_id == self.subroute_start_id if current_node_id is not None else False
                    # If we're back in the start node, switch to subroute.
                    if entered_start or math.hypot(start_pos[0] - pos[0], start_pos[1] - pos[1]) <= self.node_visit_radius:
                        self.subroute_stage = "pause"
                        self.subroute_pause_ticks = self.subroute_pause_duration
                        self.path_points = []
                        self.path_idx = 0
                        logger.info(
                            "[NAV] Subroute pause at start for %s ticks",
                            self.subroute_pause_duration,
                        )
                    else:
                        if not self.path_points or self.path_idx >= len(self.path_points):
                            self._compute_path_to_point(pos, start_pos)
            elif self.subroute_stage == "route":
                if not self.path_points:
                    self.path_points = list(self.subroute_points)
                    self.path_idx = 0
            if self.subroute_stage == "route":
                if not self.subroute_trace:
                    self.subroute_trace.append((pos[0], pos[1]))
                else:
                    last = self.subroute_trace[-1]
                    if math.hypot(pos[0] - last[0], pos[1] - last[1]) >= 8.0:
                        self.subroute_trace.append((pos[0], pos[1]))
            # End subroute as soon as we cross into the target node polygon (any stage).
            if (
                self.subroute_end_id is not None
                and self.mesh is not None
                and 0 <= self.subroute_end_id < len(self.mesh.nodes)
            ):
                end_poly = self.mesh.nodes[self.subroute_end_id].polygon
                entered = current_node_id == self.subroute_end_id if current_node_id is not None else False
                inside = self._point_in_poly_2d((pos[0], pos[1]), end_poly)
                crossed = False
                if prev_pos is not None:
                    crossed = self._segment_intersects_polygon(prev_pos, (pos[0], pos[1]), end_poly)
                if entered or inside or crossed:
                    logger.info(
                        "[NAV] Subroute reached end node=%s entered=%s inside=%s crossed=%s",
                        self.subroute_end_id,
                        entered,
                        inside,
                        crossed,
                    )
                    self.last_visited_route_node = self.subroute_end_id
                    if self.end_node_id is not None and self.subroute_end_id == self.end_node_id:
                        self.route_idx = len(self.route_nodes)
                    elif self.route_idx < len(self.route_nodes) and self.route_nodes[self.route_idx] == self.subroute_end_id:
                        self.route_idx += 1
                    self.last_subroute_points = list(self.subroute_points)
                    self.last_subroute_trace = list(self.subroute_trace)
                    self.last_helper_points = list(self.helper_points)
                    self.subroute_active = False
                    self.subroute_stage = None
                    self.subroute_points = []
                    self.helper_points = []
                    self.subroute_trace = []
                    self.stuck_node_id = None
                    self.path_points = []
                    self.path_idx = 0
                    self.current_target = None
                    return ActionDecoder.forward()
        else:
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
            if self.subroute_active and self.subroute_stage == "route":
                # Finished subroute: mark end node visited and resume main route.
                if self.subroute_end_id is not None:
                    logger.info(
                        "[NAV] Subroute complete start=%s end=%s",
                        self.subroute_start_id,
                        self.subroute_end_id,
                    )
                    self.last_visited_route_node = self.subroute_end_id
                    if self.end_node_id is not None and self.subroute_end_id == self.end_node_id:
                        self.route_idx = len(self.route_nodes)
                    elif self.route_idx < len(self.route_nodes) and self.route_nodes[self.route_idx] == self.subroute_end_id:
                        self.route_idx += 1
                self.last_subroute_points = list(self.subroute_points)
                self.last_subroute_trace = list(self.subroute_trace)
                self.last_helper_points = list(self.helper_points)
                self.subroute_active = False
                self.subroute_stage = None
                self.subroute_points = []
                self.helper_points = []
                self.subroute_trace = []
                self.stuck_node_id = None
            self.path_points = []
            self.path_idx = 0
            self.current_target = None
            return ActionDecoder.forward()

        target = self.path_points[self.path_idx]
        distance = math.hypot(target[0] - pos[0], target[1] - pos[1])

        if not self.combat_active and self.route_idx < len(self.route_nodes):
            if self.current_target is None:
                self.last_distance = distance
                self.no_progress = 0
            else:
                if self.last_distance is not None and distance > self.last_distance - 1.0:
                    self.no_progress += 1
                else:
                    self.no_progress = 0
                self.last_distance = distance
        else:
            self.no_progress = 0
            self.last_distance = distance

        if self.no_progress > 12 and not self.subroute_active and not self.combat_active and self.route_idx < len(self.route_nodes):
            if end_dist is not None and end_dist < self.end_subroute_block_dist:
                # Near the end, avoid Y-flip oscillations; just force a fresh path.
                self.y_inverted = False
                self.no_progress = 0
                self.path_points = []
                self.path_idx = 0
                self.current_target = None
                self.last_distance = None
                logger.info("[NAV] Near end: reset path instead of flipping Y")
            else:
                self.y_inverted = not self.y_inverted
                self.no_progress = 0
                logger.info(f"[NAV] Flipped Y axis to {self.y_inverted}")

        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        if self.y_inverted and not self.subroute_active:
            dy = -dy

        target_angle = math.degrees(math.atan2(dy, dx))
        angle_diff = target_angle - float(current_angle)
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360

        # Track angle oscillation for corner-stuck detection.
        sign = 0
        if angle_diff > 5.0:
            sign = 1
        elif angle_diff < -5.0:
            sign = -1
        if sign != 0:
            self.angle_sign_history.append(sign)
            if len(self.angle_sign_history) > 8:
                self.angle_sign_history.pop(0)

        corner_stuck = False

        if self.step % 20 == 0:
            logger.info(
                f"[NAV] node={current_node_id} target={self.current_target} "
                f"dist={distance:.1f} ang={current_angle:.1f} diff={angle_diff:.1f}"
            )

        # Check for nearby special linedefs (doors, lifts, switches)
        special_dist = None
        special_hit = None
        if nearest_special_seg is not None and nearest_special_dist is not None:
            t2d = (target[0], target[1])
            inter = self._segment_intersection(p2d, t2d, nearest_special_seg[0], nearest_special_seg[1])
            if inter is not None:
                inter_dist = math.hypot(inter[0] - p2d[0], inter[1] - p2d[1])
                special_dist = min(nearest_special_dist, inter_dist)
                special_hit = nearest_special_seg
            elif near_special_stuck:
                special_dist = nearest_special_dist
                special_hit = nearest_special_seg

        if self.use_cooldown > 0:
            self.use_cooldown -= 1
        if (
            self.exit_target_line_point is None
            and special_dist is not None
            and special_dist < 48.0
            and self.use_cooldown == 0
        ):
            same_seg = self.last_special_use_seg == special_hit
            recent_use = (self.step - self.last_special_use_step) < 70
            if not (same_seg and recent_use):
                self.use_ticks = 1
                self.use_cooldown = 35
                self.last_special_use_seg = special_hit
                self.last_special_use_step = self.step
                logger.info("[NAV] Using special linedef dist=%.1f", special_dist)

        if self.use_ticks > 0:
            self.use_ticks -= 1
            return ActionDecoder.use()

        dist_stuck = False
        progress = -1.0
        if not self.combat_active and self.route_idx < len(self.route_nodes) and self.current_target is not None:
            if self.current_target != self.dist_target_id:
                self.dist_history = []
                self.dist_target_id = self.current_target
            dist_stuck, progress = self._update_dist_history(distance)

        target_dist = distance
        hard_stuck = (
            min_elapsed
            and has_progress
            and self.no_progress > 20
            and target_dist > 128.0
            and not near_special_stuck
        )
        dist_only_stuck = (
            min_elapsed
            and has_progress
            and dist_stuck
            and target_dist > 128.0
            and not near_special_stuck
        )
        corner_stuck = False
        if not self.combat_active and self.route_idx < len(self.route_nodes):
            corner_stuck = (
                (pos_stuck and (self.no_progress > 12 or dist_stuck) and not near_special_stuck)
                or hard_stuck
                or (min_elapsed and has_progress and (pos_spread < 128.0) and self.no_progress > 40 and not near_special_stuck)
                or dist_only_stuck
            )
        if end_dist is not None and end_dist < self.end_subroute_block_dist:
            corner_stuck = False
        if self.step % 20 == 0 and has_progress:
            logger.info(
                "[NAV] StuckCheck spread=%.1f no_prog=%s dist_prog=%.1f near_special=%s tgt_dist=%.1f",
                pos_spread,
                self.no_progress,
                progress,
                near_special_stuck,
                target_dist,
            )
        if corner_stuck:
            if near_door_stuck:
                # Don't subroute while stuck on a door; push/use to open it.
                action = ActionDecoder.forward()
                if len(action) >= 7:
                    action[6] = 1
                logger.info("[NAV] Corner-stuck near door: forcing use")
                return action
            allow_subroute = True
            if end_dist is not None and end_dist < self.end_subroute_block_dist:
                allow_subroute = False
                logger.info(
                    "[NAV] Corner-stuck near end (dist=%.1f): skipping subroute",
                    end_dist,
                )
                exit_action = self._handle_exit(pos, current_angle)
                if exit_action is not None:
                    return exit_action
            if not self.subroute_active:
                if (
                    allow_subroute
                    and self.subroute_cooldown == 0
                    and self._start_subroute(current_node_id, (pos[0], pos[1]))
                ):
                    logger.info("[NAV] Corner-stuck: activating subroute")
                    return ActionDecoder.forward()
                escape = (self.stuck_counter // 3) % 4
                if escape == 0:
                    return ActionDecoder.strafe_left()
                if escape == 1:
                    return ActionDecoder.strafe_right()
                if escape == 2:
                    return ActionDecoder.left_turn()
                return ActionDecoder.right_turn()
            # Nudge while subrouting to prevent getting stuck in return/route legs.
            logger.info("[NAV] Corner-stuck during subroute: nudging")
            escape = (self.stuck_counter // 3) % 4
            if escape == 0:
                return ActionDecoder.strafe_left()
            if escape == 1:
                return ActionDecoder.strafe_right()
            if escape == 2:
                return ActionDecoder.left_turn()
            return ActionDecoder.right_turn()

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

        if self.exit_target_point is not None:
            tp = to_px(self.exit_target_point)
            cv2.circle(img, tp, 5, (0, 215, 255), -1)
            cv2.putText(
                img,
                "EXIT",
                (tp[0] + 6, tp[1] - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 215, 255),
                1,
                cv2.LINE_AA,
            )

        # Draw helper nodes (subroute)
        helper_pts = self.helper_points if self.helper_points else self.last_helper_points
        if helper_pts:
            for i, hp in enumerate(helper_pts):
                cv2.circle(img, to_px(hp), 4, (255, 0, 255), -1)
                cv2.putText(
                    img,
                    f"H{i}",
                    (to_px(hp)[0] + 4, to_px(hp)[1] - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    (255, 0, 255),
                    1,
                    cv2.LINE_AA,
                )

        # Draw subroute traversal
        planned = self.subroute_points if self.subroute_points else self.last_subroute_points
        if planned and len(planned) > 1:
            for i in range(1, len(planned)):
                a = (planned[i - 1][0], planned[i - 1][1])
                b = (planned[i][0], planned[i][1])
                cv2.line(img, to_px(a), to_px(b), (255, 255, 0), 2)

        traveled = self.subroute_trace if self.subroute_trace else self.last_subroute_trace
        if traveled and len(traveled) > 1:
            for i in range(1, len(traveled)):
                a = traveled[i - 1]
                b = traveled[i]
                cv2.line(img, to_px(a), to_px(b), (0, 165, 255), 2)

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

    def render_debug_overlay(self, automap_buffer: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if self.mesh is None or not self.mesh.vertices or automap_buffer is None:
            return None

        try:
            import cv2
        except Exception:
            return None

        img = np.array(automap_buffer, copy=True)
        if img.ndim == 2:
            img = np.stack([img, img, img], axis=2)
        elif img.ndim == 3 and img.shape[2] > 3:
            img = img[:, :, :3]

        height, width = img.shape[:2]
        if height <= 0 or width <= 0:
            return None

        xs = self.mesh.vertices[0::3]
        ys = self.mesh.vertices[1::3]
        if not xs or not ys:
            return None

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad = 6
        scale_x = (width - 2 * pad) / (max_x - min_x + 1e-6)
        scale_y = (height - 2 * pad) / (max_y - min_y + 1e-6)

        def to_px(p: Tuple[float, float]) -> Tuple[int, int]:
            x = int((p[0] - min_x) * scale_x + pad)
            y = int((p[1] - min_y) * scale_y + pad)
            return (x, height - y)

        allowed = set(self.pruned_nodes) if self.pruned_nodes else None
        for node in self.mesh.nodes:
            if allowed is not None and node.node_id not in allowed:
                continue
            c = (node.centroid[0], node.centroid[1])
            cv2.circle(img, to_px(c), 2, (0, 220, 0), -1)

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
                        2,
                    )

        if self.start_node_id is not None and 0 <= self.start_node_id < len(self.mesh.nodes):
            s = self.mesh.nodes[self.start_node_id].centroid
            cv2.circle(img, to_px((s[0], s[1])), 4, (0, 255, 0), -1)
        if self.end_node_id is not None and 0 <= self.end_node_id < len(self.mesh.nodes):
            e = self.mesh.nodes[self.end_node_id].centroid
            cv2.circle(img, to_px((e[0], e[1])), 4, (0, 0, 255), -1)

        if self.path_points and len(self.path_points) > 1:
            for i in range(1, len(self.path_points)):
                a = (self.path_points[i - 1][0], self.path_points[i - 1][1])
                b = (self.path_points[i][0], self.path_points[i][1])
                cv2.line(img, to_px(a), to_px(b), (255, 255, 255), 2)

        return img
