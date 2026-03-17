#!/usr/bin/env python3
"""
Monolithic E1M1-only traversal prototype.
Focus: route replay from logs/json output, with simple waypoint following and
no dynamic replanning.
"""

import argparse
import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import vizdoom as vzd


BUTTON_NAMES = [
    "MOVE_FORWARD",
    "MOVE_BACKWARD",
    "TURN_LEFT",
    "TURN_RIGHT",
    "MOVE_LEFT",
    "MOVE_RIGHT",
    "JUMP",
    "SPEED",
    "ATTACK",
    "USE",
]

BUTTON_INDEX = {name: idx for idx, name in enumerate(BUTTON_NAMES)}
EXIT_SPECIALS = {11, 51, 52, 124, 197}
USE_SPECIALS = {1}
MAP_MARKER_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$")
WAYPOINT_REACHED_DIST = 32.0


def _normalize_angle_delta_deg(a: float) -> float:
    d = (a + 180.0) % 360.0 - 180.0
    return d if d <= 180.0 else d - 360.0


def _dist2d(ax: float, ay: float, bx: float, by: float) -> float:
    dx = ax - bx
    dy = ay - by
    return math.hypot(dx, dy)


def _coerce_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def _line_endpoint_value(line: Any, key: str) -> Optional[float]:
    v = getattr(line, key, None)
    if v is not None:
        return _coerce_float(v)
    pair = key.split(".")
    if len(pair) == 2 and hasattr(line, pair[0]):
        obj = getattr(line, pair[0], None)
        if obj is not None:
            return _coerce_float(getattr(obj, pair[1], None))
    return None


def _read_wad_directory(wad_path: str) -> Tuple[bytes, List[Tuple[str, int, int]]]:
    raw = Path(wad_path).read_bytes()
    ident, num_lumps, dir_ofs = struct.unpack_from("<4sii", raw, 0)
    if ident not in (b"IWAD", b"PWAD"):
        raise RuntimeError(f"Unsupported WAD type: {ident!r}")

    directory: List[Tuple[str, int, int]] = []
    for i in range(num_lumps):
        pos, size, name_raw = struct.unpack_from("<ii8s", raw, dir_ofs + i * 16)
        name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="ignore").upper()
        directory.append((name, pos, size))
    return raw, directory


def _load_map_lumps(wad_path: str, map_name: str) -> Tuple[bytes, Dict[str, Tuple[int, int]]]:
    raw, directory = _read_wad_directory(wad_path)
    marker = map_name.upper()
    marker_idx = -1
    for i, (name, _, _) in enumerate(directory):
        if name == marker:
            marker_idx = i
            break
    if marker_idx < 0:
        raise RuntimeError(f"Map marker {map_name} not found in {wad_path}")

    map_lumps: Dict[str, Tuple[int, int]] = {}
    for name, pos, size in directory[marker_idx + 1 :]:
        if name == "ENDMAP" or MAP_MARKER_RE.match(name):
            break
        if name not in map_lumps:
            map_lumps[name] = (pos, size)
    return raw, map_lumps


def _load_map_vertices(wad_path: str, map_name: str) -> List[Tuple[float, float]]:
    raw, map_lumps = _load_map_lumps(wad_path, map_name)
    if "VERTEXES" not in map_lumps:
        raise RuntimeError(f"Classic map VERTEXES lump not found for {map_name}")

    vx_pos, vx_size = map_lumps["VERTEXES"]
    vertices: List[Tuple[float, float]] = []
    for off in range(0, vx_size, 4):
        x, y = struct.unpack_from("<hh", raw, vx_pos + off)
        vertices.append((float(x), float(y)))
    if not vertices:
        raise RuntimeError(f"No vertices found for {map_name}")
    return vertices


def _load_exit_segments_from_wad(wad_path: str, map_name: str) -> List[Tuple[float, float, float, float]]:
    return [
        (x1, y1, x2, y2)
        for x1, y1, x2, y2, _special in _load_special_segments_from_wad(wad_path, map_name, EXIT_SPECIALS)
    ]


def _load_special_segments_from_wad(
    wad_path: str,
    map_name: str,
    wanted_specials: Sequence[int],
) -> List[Tuple[float, float, float, float, int]]:
    raw, map_lumps = _load_map_lumps(wad_path, map_name)
    if "VERTEXES" not in map_lumps or "LINEDEFS" not in map_lumps:
        raise RuntimeError(f"Classic map LINEDEFS/VERTEXES lumps not found for {map_name}")

    vertices = _load_map_vertices(wad_path, map_name)
    ld_pos, ld_size = map_lumps["LINEDEFS"]
    wanted = set(int(v) for v in wanted_specials)
    segments: List[Tuple[float, float, float, float, int]] = []
    for off in range(0, ld_size, 14):
        v1, v2, _flags, special, _tag, _right, _left = struct.unpack_from("<hhhhhhh", raw, ld_pos + off)
        special = int(special)
        if special not in wanted:
            continue
        if not (0 <= v1 < len(vertices) and 0 <= v2 < len(vertices)):
            continue
        x1, y1 = vertices[v1]
        x2, y2 = vertices[v2]
        segments.append((x1, y1, x2, y2, special))
    return segments


def _point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    qx, qy = _closest_point_on_segment(px, py, x1, y1, x2, y2)
    return _dist2d(px, py, qx, qy)


def _closest_point_on_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / denom
    t = max(0.0, min(1.0, t))
    qx = x1 + t * dx
    qy = y1 + t * dy
    return qx, qy


def _ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_intersect(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
) -> bool:
    ab_c = _ccw(ax, ay, bx, by, cx, cy)
    ab_d = _ccw(ax, ay, bx, by, dx, dy)
    cd_a = _ccw(cx, cy, dx, dy, ax, ay)
    cd_b = _ccw(cx, cy, dx, dy, bx, by)
    return (ab_c == 0.0 or ab_d == 0.0 or (ab_c > 0.0) != (ab_d > 0.0)) and (
        cd_a == 0.0 or cd_b == 0.0 or (cd_a > 0.0) != (cd_b > 0.0)
    )


def _inverse_svg_point(
    sx: float,
    sy: float,
    vertices: Sequence[Tuple[float, float]],
    width: float = 1400.0,
    height: float = 1000.0,
    pad: float = 30.0,
) -> Tuple[float, float]:
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)
    scale_x = (width - 2.0 * pad) / max(1.0, (max_x - min_x))
    scale_y = (height - 2.0 * pad) / max(1.0, (max_y - min_y))
    scale = min(scale_x, scale_y)
    x = ((sx - pad) / scale) + min_x
    y = (((height - sy) - pad) / scale) + min_y
    return x, y


def _line_endpoints(line: Any) -> Optional[Tuple[float, float, float, float]]:
    candidate_keys = (
        ("x1", "y1", "x2", "y2"),
        ("x", "y", "x2", "y2"),
        ("vx1", "vy1", "vx2", "vy2"),
        ("from_x", "from_y", "to_x", "to_y"),
        ("v1.x", "v1.y", "v2.x", "v2.y"),
    )
    for x1_key, y1_key, x2_key, y2_key in candidate_keys:
        x1 = _line_endpoint_value(line, x1_key)
        y1 = _line_endpoint_value(line, y1_key)
        x2 = _line_endpoint_value(line, x2_key)
        y2 = _line_endpoint_value(line, y2_key)
        if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
            return x1, y1, x2, y2
    return None


def _line_segments_from_state_lines(lines: Sequence[Any]) -> List[Tuple[float, float, float, float]]:
    segs: List[Tuple[float, float, float, float]] = []
    for line in lines:
        special = int(getattr(line, "special", 0) or 0)
        if special not in EXIT_SPECIALS:
            continue
        p = _line_endpoints(line)
        if p is None:
            continue
        x1, y1, x2, y2 = p
        segs.append((x1, y1, x2, y2))
    return segs


def _zero_action() -> List[int]:
    return [0] * len(BUTTON_NAMES)


def _action_names(action: Sequence[int]) -> str:
    active = [name for idx, name in enumerate(BUTTON_NAMES) if idx < len(action) and action[idx]]
    return "+".join(active) if active else "IDLE"


def _action_move_forward(speed: bool = False) -> List[int]:
    action = _zero_action()
    action[BUTTON_INDEX["MOVE_FORWARD"]] = 1
    if speed:
        action[BUTTON_INDEX["SPEED"]] = 1
    return action


def _action_turn_left(speed: bool = False) -> List[int]:
    action = _zero_action()
    action[BUTTON_INDEX["TURN_LEFT"]] = 1
    if speed:
        action[BUTTON_INDEX["SPEED"]] = 1
    return action


def _action_turn_right(speed: bool = False) -> List[int]:
    action = _zero_action()
    action[BUTTON_INDEX["TURN_RIGHT"]] = 1
    if speed:
        action[BUTTON_INDEX["SPEED"]] = 1
    return action


def _action_forward_and_strafe_right(speed: bool = False) -> List[int]:
    action = _action_move_forward(speed)
    action[BUTTON_INDEX["MOVE_RIGHT"]] = 1
    return action


def _action_forward_and_strafe_left(speed: bool = False) -> List[int]:
    action = _action_move_forward(speed)
    action[BUTTON_INDEX["MOVE_LEFT"]] = 1
    return action


def _action_backward() -> List[int]:
    action = _zero_action()
    action[BUTTON_INDEX["MOVE_BACKWARD"]] = 1
    return action


def _action_strafe_left() -> List[int]:
    action = _zero_action()
    action[BUTTON_INDEX["MOVE_LEFT"]] = 1
    return action


def _action_strafe_right() -> List[int]:
    action = _zero_action()
    action[BUTTON_INDEX["MOVE_RIGHT"]] = 1
    return action


def _action_turn_and_forward_left(speed: bool = False) -> List[int]:
    action = _action_move_forward(speed)
    action[BUTTON_INDEX["TURN_LEFT"]] = 1
    return action


def _action_turn_and_forward_right(speed: bool = False) -> List[int]:
    action = _action_move_forward(speed)
    action[BUTTON_INDEX["TURN_RIGHT"]] = 1
    return action


class MonolithicE1M1Traverser:
    def __init__(
        self,
        wad_path: str,
        map_name: str,
        fast_mode: bool,
        no_enemies: bool,
        route_json_path: Optional[str] = None,
    ):
        self.wad_path = wad_path
        self.map_name = map_name
        self.fast_mode = bool(fast_mode)
        self.no_enemies = bool(no_enemies)
        self.route_json_path = route_json_path
        self.game = None
        self.path_points: List[Tuple[float, float, float]] = []
        self.exit_segments: List[Tuple[float, float, float, float]] = []
        self.use_segments: List[Tuple[float, float, float, float, int]] = []
        self.path_idx = 0
        self.prev_x = None
        self.prev_y = None
        self.stuck_counter = 0
        self.route_replan_count = 0
        self.no_progress_steps = 0
        self.last_target_dist = None
        self.use_attempts = 0

    def _default_route_json_path(self) -> Path:
        return Path("logs") / "json" / f"{self.map_name.lower()}_astar.json"

    def _load_route_points(self) -> List[Tuple[float, float, float]]:
        route_path = Path(self.route_json_path) if self.route_json_path else self._default_route_json_path()
        if not route_path.exists():
            raise FileNotFoundError(f"Missing route JSON: {route_path}")

        payload = json.loads(route_path.read_text(encoding="utf-8"))
        raw_points = payload.get("node_points")
        if not isinstance(raw_points, list) or not raw_points:
            raise RuntimeError(f"Route JSON has no node_points: {route_path}")

        vertices = _load_map_vertices(self.wad_path, self.map_name)
        points: List[Tuple[float, float, float]] = []
        for idx, point in enumerate(raw_points):
            if not isinstance(point, dict):
                raise RuntimeError(f"Route point {idx} is not an object in {route_path}")
            sx = _coerce_float(point.get("x"))
            sy = _coerce_float(point.get("y"))
            if sx is None or sy is None:
                raise RuntimeError(f"Route point {idx} is missing x/y in {route_path}")
            wx, wy = _inverse_svg_point(sx, sy, vertices)
            points.append((wx, wy, 0.0))

        self.path_points = points
        self.path_idx = 0
        self.last_target_dist = None
        self.no_progress_steps = 0
        return points

    def _load_exit_segments(self) -> List[Tuple[float, float, float, float]]:
        self.exit_segments = _load_exit_segments_from_wad(self.wad_path, self.map_name)
        return self.exit_segments

    def _load_use_segments(self) -> List[Tuple[float, float, float, float, int]]:
        self.use_segments = _load_special_segments_from_wad(self.wad_path, self.map_name, USE_SPECIALS)
        return self.use_segments

    def _nearest_exit(self, pos_x: float, pos_y: float) -> Optional[Tuple[Tuple[float, float, float, float], float, Tuple[float, float]]]:
        best = None
        best_dist = None
        for seg in self.exit_segments:
            x1, y1, x2, y2 = seg
            dist = _point_to_segment_distance(pos_x, pos_y, x1, y1, x2, y2)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (seg, dist, _closest_point_on_segment(pos_x, pos_y, x1, y1, x2, y2))
        return best

    def _blocking_use_segment(
        self,
        pos: Tuple[float, float, float],
        target: Optional[Tuple[float, float, float]],
    ) -> Optional[Tuple[Tuple[float, float, float, float, int], float, Tuple[float, float]]]:
        if target is None:
            return None
        best = None
        best_dist = None
        for seg in self.use_segments:
            x1, y1, x2, y2, _special = seg
            dist = _point_to_segment_distance(pos[0], pos[1], x1, y1, x2, y2)
            if dist > 32.0:
                continue
            if not _segments_intersect(pos[0], pos[1], target[0], target[1], x1, y1, x2, y2):
                continue
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (seg, dist, _closest_point_on_segment(pos[0], pos[1], x1, y1, x2, y2))
        return best

    def _init_game(self) -> None:
        self.game = vzd.DoomGame()
        self.game.load_config("vizdoom_config.cfg")
        self.game.set_doom_scenario_path(self.wad_path)
        self.game.set_doom_map(self.map_name)
        if self.no_enemies:
            self.game.add_game_args("-nomonsters")

        def _safe_call(fn_name: str, *args):
            fn = getattr(self.game, fn_name, None)
            if callable(fn):
                fn(*args)

        _safe_call("set_sectors_info_enabled", True)
        _safe_call("set_lines_info_enabled", True)

        if self.fast_mode:
            self.game.set_window_visible(False)
            self.game.set_render_hud(False)
            self.game.set_render_weapon(False)
            self.game.set_render_crosshair(False)
            self.game.set_render_decals(False)
            self.game.set_render_particles(False)
            self.game.set_render_messages(False)
            self.game.set_render_corpses(False)
            self.game.set_screen_resolution(vzd.ScreenResolution.RES_320X240)
            self.game.set_render_all_frames(False)
            self.game.set_depth_buffer_enabled(False)
            self.game.set_automap_buffer_enabled(False)
            self.game.set_automap_render_textures(False)
        else:
            self.game.set_window_visible(True)
            self.game.set_render_hud(True)
            self.game.set_render_weapon(True)
            self.game.set_render_crosshair(True)
            self.game.set_render_decals(True)
            self.game.set_render_particles(True)
            self.game.set_render_messages(True)
            self.game.set_render_corpses(True)

    @staticmethod
    def _state_vars(state) -> Dict[str, float]:
        vars_list = state.game_variables
        return {
            "health": float(vars_list[0]) if len(vars_list) > 0 else 0.0,
            "ammo2": float(vars_list[1]) if len(vars_list) > 1 else 0.0,
            "x": float(vars_list[2]) if len(vars_list) > 2 else 0.0,
            "y": float(vars_list[3]) if len(vars_list) > 3 else 0.0,
            "z": float(vars_list[4]) if len(vars_list) > 4 else 0.0,
            "angle": float(vars_list[5]) if len(vars_list) > 5 else 0.0,
            "kills": float(vars_list[6]) if len(vars_list) > 6 else 0.0,
        }

    def _path_step_target(self) -> Optional[Tuple[float, float, float]]:
        if self.path_idx >= len(self.path_points):
            return None
        return self.path_points[self.path_idx]

    def _advance_path(self, pos_x: float, pos_y: float) -> None:
        while True:
            target = self._path_step_target()
            if target is None:
                break
            dist = _dist2d(pos_x, pos_y, target[0], target[1])
            if dist <= WAYPOINT_REACHED_DIST:
                self.path_idx += 1
            else:
                break

    def _step_snapshot(self, pos: Tuple[float, float, float], angle: float) -> Dict[str, Any]:
        target = self._path_step_target()
        target_dist = None
        target_angle = None
        target_delta = None
        if target is not None:
            dx = target[0] - pos[0]
            dy = target[1] - pos[1]
            target_angle = math.degrees(math.atan2(dy, dx))
            target_dist = _dist2d(pos[0], pos[1], target[0], target[1])
            target_delta = _normalize_angle_delta_deg(target_angle - angle)

        exit_info = self._nearest_exit(pos[0], pos[1]) if self.exit_segments else None
        exit_dist = None
        exit_angle = None
        exit_delta = None
        exit_mid = None
        if exit_info is not None:
            _seg, exit_dist, exit_mid = exit_info
            exit_angle = math.degrees(math.atan2(exit_mid[1] - pos[1], exit_mid[0] - pos[0]))
            exit_delta = _normalize_angle_delta_deg(exit_angle - angle)

        return {
            "target": target,
            "target_dist": target_dist,
            "target_angle": target_angle,
            "target_delta": target_delta,
            "exit_dist": exit_dist,
            "exit_angle": exit_angle,
            "exit_delta": exit_delta,
            "exit_mid": exit_mid,
            "path_idx": self.path_idx,
            "path_len": len(self.path_points),
        }

    def _pick_action(self, pos: Tuple[float, float, float], angle: float) -> Tuple[List[int], str, Dict[str, Any]]:
        if self.path_points is None or len(self.path_points) == 0:
            debug = self._step_snapshot(pos, angle)
            return _zero_action(), "no_path_points", debug

        self._advance_path(pos[0], pos[1])
        debug = self._step_snapshot(pos, angle)
        use_line = self._blocking_use_segment(pos, debug["target"])
        if use_line is not None:
            _seg, use_dist, use_mid = use_line
            use_angle = math.degrees(math.atan2(use_mid[1] - pos[1], use_mid[0] - pos[0]))
            use_delta = _normalize_angle_delta_deg(use_angle - angle)
            debug["use_dist"] = use_dist
            debug["use_delta"] = use_delta
            if abs(use_delta) > 8.0:
                action = _action_turn_right(speed=False) if use_delta < 0 else _action_turn_left(speed=False)
                return action, "use_line_turn", debug
            action = _zero_action()
            action[BUTTON_INDEX["MOVE_FORWARD"]] = 1
            action[BUTTON_INDEX["USE"]] = 1
            return action, "use_line_activate", debug
        exit_dist = debug["exit_dist"]
        exit_delta = debug["exit_delta"]
        if exit_dist is not None and exit_delta is not None:
            at_end_of_route = self.path_idx >= len(self.path_points)
            if at_end_of_route or exit_dist <= 48.0:
                if abs(exit_delta) > 10.0:
                    action = _action_turn_right(speed=False) if exit_delta < 0 else _action_turn_left(speed=False)
                    return action, "exit_turn", debug
                action = _zero_action()
                action[BUTTON_INDEX["MOVE_FORWARD"]] = 1
                action[BUTTON_INDEX["USE"]] = 1
                return action, "exit_use", debug

        target = debug["target"]
        if target is None:
            return _zero_action(), "route_complete_idle", debug

        target_dist = debug["target_dist"]
        delta = debug["target_delta"]
        if target_dist is None or delta is None:
            return _zero_action(), "missing_target_debug", debug

        if self.last_target_dist is not None:
            if target_dist >= self.last_target_dist - 4.0:
                self.no_progress_steps += 1
            else:
                self.no_progress_steps = 0
        self.last_target_dist = target_dist

        if abs(delta) > 20.0:
            action = _action_turn_right(speed=False) if delta < 0 else _action_turn_left(speed=False)
            return action, "route_turn", debug
        if abs(delta) > 6.0:
            action = _action_turn_and_forward_right(speed=False) if delta < 0 else _action_turn_and_forward_left(speed=False)
            return action, "route_turn_forward", debug
        if target_dist > 64.0:
            return _action_move_forward(speed=True), "route_forward_fast", debug
        return _action_move_forward(speed=False), "route_forward", debug

    @staticmethod
    def _action_frame_skip(action: Sequence[int], default_frame_skip: int) -> int:
        # Keep one logged decision equal to one game tick so the trace reflects
        # continuous motion instead of mixing short turns with long forward bursts.
        return 1

    @staticmethod
    def _fmt_optional(value: Optional[float]) -> str:
        return "None" if value is None else f"{value:.1f}"

    def _print_step_trace(
        self,
        step: int,
        pos: Tuple[float, float, float],
        angle: float,
        action: Sequence[int],
        reason: str,
        debug: Dict[str, Any],
    ) -> None:
        print(
            "STEP "
            f"{step:04d} "
            f"pos=({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f}) "
            f"angle={angle:.1f} "
            f"path_idx={debug['path_idx']}/{debug['path_len']} "
            f"target_dist={self._fmt_optional(debug['target_dist'])} "
            f"target_delta={self._fmt_optional(debug['target_delta'])} "
            f"use_dist={self._fmt_optional(debug.get('use_dist'))} "
            f"use_delta={self._fmt_optional(debug.get('use_delta'))} "
            f"exit_dist={self._fmt_optional(debug['exit_dist'])} "
            f"exit_delta={self._fmt_optional(debug['exit_delta'])} "
            f"no_progress={self.no_progress_steps} "
            f"stuck={self.stuck_counter} "
            f"action={_action_names(action)} "
            f"reason={reason}"
        )

    def run(self, timeout_s: int, frame_skip: int = 8, do_run: bool = False) -> Dict[str, Any]:
        self._load_route_points()
        self._load_exit_segments()
        self._load_use_segments()
        self._init_game()
        self.game.set_episode_timeout(int(timeout_s * 35))
        self.game.set_ticrate(35)
        self.game.init()
        self.game.new_episode()

        state = self.game.get_state()
        if state is None:
            raise RuntimeError("Failed to start episode")
        vars0 = self._state_vars(state)
        start_pos = (vars0["x"], vars0["y"], vars0["z"])
        if self.path_points and _dist2d(start_pos[0], start_pos[1], self.path_points[0][0], self.path_points[0][1]) <= 48.0:
            self.path_idx = 1

        metrics: Dict[str, Any] = {
            "route_points": len(self.path_points),
            "route_source": str(Path(self.route_json_path) if self.route_json_path else self._default_route_json_path()),
            "route_replans": 0,
            "steps": 0,
            "completed": False,
            "timed_out": False,
            "player_dead": False,
            "ticks": 0,
            "stuck_events": 0,
            "use_attempts": 0,
            "end_reason": "unknown",
            "final_x": start_pos[0],
            "final_y": start_pos[1],
            "final_z": start_pos[2],
        }

        if do_run is False:
            metrics["end_reason"] = "prove_only"
            return metrics

        while not self.game.is_episode_finished():
            state = self.game.get_state()
            if state is None:
                break
            vars_cur = self._state_vars(state)
            pos = (vars_cur["x"], vars_cur["y"], vars_cur["z"])
            angle = vars_cur["angle"]

            if metrics["steps"] > 0 and self.prev_x is not None:
                moved = _dist2d(pos[0], pos[1], self.prev_x, self.prev_y)
                if moved < 8.0:
                    self.stuck_counter += 1
                    if self.stuck_counter in (10, 18, 24):
                        metrics["stuck_events"] += 1
                else:
                    self.stuck_counter = 0

            self.prev_x, self.prev_y = pos[0], pos[1]

            action, reason, debug = self._pick_action(pos, angle)
            self._print_step_trace(metrics["steps"], pos, angle, action, reason, debug)
            if action[BUTTON_INDEX["USE"]]:
                self.use_attempts += 1
                metrics["use_attempts"] = self.use_attempts
            action_frame_skip = self._action_frame_skip(action, frame_skip)
            self.game.make_action(action, action_frame_skip)
            metrics["steps"] += 1
            metrics["ticks"] += action_frame_skip
            metrics["final_x"] = pos[0]
            metrics["final_y"] = pos[1]
            metrics["final_z"] = pos[2]

        metrics["completed"] = self.game.is_episode_finished()
        metrics["timed_out"] = metrics["ticks"] >= int(timeout_s * 35)
        metrics["player_dead"] = bool(self.game.is_player_dead())
        if metrics["player_dead"]:
            metrics["end_reason"] = "player_dead"
        elif metrics["timed_out"]:
            metrics["end_reason"] = "timeout"
        elif metrics["completed"]:
            metrics["end_reason"] = "exit"
        else:
            metrics["end_reason"] = "timeout_or_crash"
        self.game.close()
        return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a JSON route to the E1M1 exit")
    parser.add_argument("--wad", default="wads/doom.wad", help="Path to WAD file")
    parser.add_argument("--map", default="E1M1", help="Map name (default: E1M1)")
    parser.add_argument(
        "--route-json",
        default=None,
        help="Path to logs/json route file (default: logs/json/<map>_astar.json)",
    )
    parser.add_argument("--timeout", type=int, default=60, help="Episode timeout in seconds")
    parser.add_argument("--skip", type=int, default=8, help="Action frame skip")
    parser.add_argument("--fast", action="store_true", help="Headless mode")
    parser.add_argument("--no-enemies", action="store_true", help="Use -nomonsters")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Load the JSON route and report metrics without running the episode",
    )
    args = parser.parse_args()

    trav = MonolithicE1M1Traverser(
        wad_path=args.wad,
        map_name=args.map,
        fast_mode=args.fast,
        no_enemies=args.no_enemies,
        route_json_path=args.route_json,
    )
    metrics = trav.run(timeout_s=args.timeout, frame_skip=args.skip, do_run=not args.verify_only)
    print("MONO_NAV_METRICS")
    for k, v in metrics.items():
        print(f"{k}: {v}")
    return 0 if metrics.get("end_reason") == "exit" else 1


if __name__ == "__main__":
    raise SystemExit(main())
