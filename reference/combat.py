"""Minimal combat behavior with active aim correction."""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


COMBAT_MIN_LABEL_AREA = 24.0
COMBAT_MIN_Y_FRACTION = 0.10
COMBAT_MAX_Y_FRACTION = 0.88
COMBAT_TRACK_WINDOW = 0.48
COMBAT_FIRE_WINDOW_MIN = 0.018
COMBAT_FIRE_WINDOW_MAX = 0.045
COMBAT_FIRE_WINDOW_SCALE = 0.32
COMBAT_HOLD_TICKS = 4
COMBAT_COOLDOWN_TICKS = 35
COMBAT_DAMAGE_EPSILON = 0.5
COMBAT_MAX_TARGET_Z_DELTA = 48.0
COMBAT_BELOW_TARGET_Z_DELTA = 24.0
COMBAT_RECENT_ENEMY_TICKS = 35
COMBAT_TARGET_LOCK_BONUS = 0.18
COMBAT_TARGET_PERSIST_SCORE_MARGIN = 0.10
COMBAT_TARGET_PERSIST_MAX_OFFSET = 0.22
COMBAT_TARGET_COMMIT_TICKS = 8
COMBAT_TARGET_COMMIT_MAX_OFFSET = 0.26
COMBAT_DISTANCE_SCORE_SCALE = 8192.0
COMBAT_DISTANCE_SCORE_CAP = 0.20
COMBAT_PREDICTION_GAIN = 1.35
COMBAT_FIRE_ANGLE_DEG = 1.8
COMBAT_TURN_ANGLE_DEG = 0.7
COMBAT_READY_GRACE_TICKS = 2
COMBAT_RUNTIME_SLIVER_WIDTH_PX = 6.0
COMBAT_RUNTIME_SLIVER_ASPECT = 0.45
COMBAT_MISS_STREAK_LIMIT = 3
COMBAT_IGNORED_TARGET_TICKS = 35
COMBAT_FALLBACK_MISS_STREAK_LIMIT = 1
COMBAT_FALLBACK_IGNORED_TARGET_TICKS = 45
COMBAT_BELOW_TARGET_MAX_Y_FRACTION = 0.96
COMBAT_HINT_MAX_Y_FRACTION = 0.98
COMBAT_E1M3_MIN_LABEL_AREA = 72.0
COMBAT_E1M3_MIN_WIDTH_PX = 10.0
COMBAT_E1M3_MAX_TRACK_WINDOW = 0.30
COMBAT_E1M3_MAX_WORLD_ANGLE_ERROR = 18.0

ENEMY_NAME_ALIASES = {
    "marine",
    "marinechainsaw",
    "marinefist",
    "marineberserk",
    "marinepistol",
    "marineshotgun",
    "marinesupershotgun",
    "marinechaingun",
    "marinerocket",
    "marineplasma",
    "marinebfg",
    "zombie",
    "zombieman",
    "shotgunguy",
    "chaingunguy",
    "doomimp",
    "imp",
    "demon",
    "spectre",
    "cacodemon",
    "baronofhell",
    "hellknight",
    "lostsoul",
    "painelemental",
    "arachnotron",
    "revenant",
    "mancubus",
    "archvile",
    "spidermastermind",
    "cyberdemon",
    "trooper",
    "troop",
}

MAP_MARKER_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$")


def _normalize_alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _screen_dimensions(screen: Any) -> Optional[Tuple[int, int]]:
    shape = getattr(screen, "shape", None)
    if shape is None or len(shape) < 2:
        return None
    if len(shape) == 2:
        return int(shape[1]), int(shape[0])
    if int(shape[0]) in (1, 3, 4):
        return int(shape[2]), int(shape[1])
    return int(shape[1]), int(shape[0])


def _normalize_angle_delta_deg(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def _orientation(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
) -> float:
    return ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0]))


def _on_segment(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
    *,
    eps: float = 1e-6,
) -> bool:
    return (
        min(a[0], b[0]) - eps <= c[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= c[1] <= max(a[1], b[1]) + eps
    )


def _segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float],
) -> bool:
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


def _load_blocking_segments_from_wad(wad_path: str, map_name: str) -> List[Tuple[float, float, float, float]]:
    if not wad_path or not map_name:
        return []
    raw = Path(wad_path).read_bytes()
    ident, num_lumps, dir_ofs = struct.unpack_from("<4sii", raw, 0)
    if ident not in (b"IWAD", b"PWAD"):
        return []

    directory: List[Tuple[str, int, int]] = []
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

    map_lumps: Dict[str, Tuple[int, int]] = {}
    for name, pos, size in directory[marker_idx + 1 :]:
        if name == "ENDMAP" or MAP_MARKER_RE.match(name):
            break
        if name not in map_lumps:
            map_lumps[name] = (pos, size)
    if "VERTEXES" not in map_lumps or "LINEDEFS" not in map_lumps:
        return []

    vx_pos, vx_size = map_lumps["VERTEXES"]
    vertices: List[Tuple[float, float]] = []
    for off in range(0, vx_size, 4):
        x, y = struct.unpack_from("<hh", raw, vx_pos + off)
        vertices.append((float(x), float(y)))

    ld_pos, ld_size = map_lumps["LINEDEFS"]
    segments: List[Tuple[float, float, float, float]] = []
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


class CombatAction:
    """Turns only in specialized arena states and otherwise overlays controlled fire."""

    def __init__(self, map_name: str = "", wad_path: str = ""):
        self.map_name = str(map_name).upper()
        self.blocking_segments = _load_blocking_segments_from_wad(wad_path, self.map_name)
        self.combat_cooldown = 0
        self.control_active = False
        self.hold_ticks = 0
        self.last_health: Optional[float] = None
        self.recent_enemy_ticks = 0
        self.search_direction = -1
        self.last_target_key: Optional[str] = None
        self.last_target_object_id: Optional[int] = None
        self.last_target_offset_x: Optional[float] = None
        self.last_target_angle_error: Optional[float] = None
        self.ready_grace_ticks = 0
        self.last_ammo: Optional[float] = None
        self.last_hitcount: Optional[int] = None
        self.last_damagecount: Optional[int] = None
        self.pending_shot_target_key: Optional[str] = None
        self.pending_shot_target_is_fallback = False
        self.miss_streak_target_key: Optional[str] = None
        self.miss_streak_count = 0
        self.ignored_target_key: Optional[str] = None
        self.ignored_target_ticks = 0
        self.target_commit_key: Optional[str] = None
        self.target_commit_ticks = 0

    def _has_clear_world_line(
        self,
        player_x: float,
        player_y: float,
        enemy_x: Optional[float],
        enemy_y: Optional[float],
    ) -> bool:
        if enemy_x is None or enemy_y is None or not self.blocking_segments:
            return True
        line_start = (float(player_x), float(player_y))
        line_end = (float(enemy_x), float(enemy_y))
        for x1, y1, x2, y2 in self.blocking_segments:
            if _segments_intersect(line_start, line_end, (x1, y1), (x2, y2)):
                return False
        return True

    def _is_enemy_name(self, name: str) -> bool:
        if not name:
            return False
        name_lower = name.lower()
        if "dead" in name_lower or "gibbe" in name_lower:
            return False
        flat = _normalize_alnum(name_lower)
        if flat.startswith("marine"):
            return True
        if flat in ENEMY_NAME_ALIASES:
            return True
        for token in re.findall(r"[a-z0-9]+", name_lower):
            if token in ENEMY_NAME_ALIASES:
                return True
        return False

    @staticmethod
    def _bucket(value: Optional[float], size: float) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(round(float(value) / max(1e-6, float(size))))
        except Exception:
            return None

    def _target_signature(self, label: object, *, width: int, height: int) -> Tuple[str, bool, Optional[int]]:
        object_id = getattr(label, "object_id", None)
        if object_id is not None:
            try:
                return f"id:{int(object_id)}", False, int(object_id)
            except Exception:
                pass

        name = _normalize_alnum(str(getattr(label, "object_name", "") or "unknown"))
        box_w = float(getattr(label, "width", 0.0) or 0.0)
        box_h = float(getattr(label, "height", 0.0) or 0.0)
        center_x = float(getattr(label, "x", 0.0) or 0.0) + (box_w * 0.5)
        center_y = float(getattr(label, "y", 0.0) or 0.0) + (box_h * 0.5)
        enemy_x = getattr(label, "object_position_x", None)
        enemy_y = getattr(label, "object_position_y", None)
        enemy_z = getattr(label, "object_position_z", None)
        parts = [
            f"name:{name}",
            f"wx:{self._bucket(enemy_x, 64.0)}",
            f"wy:{self._bucket(enemy_y, 64.0)}",
            f"wz:{self._bucket(enemy_z, 32.0)}",
            f"cx:{self._bucket(center_x, 16.0)}",
            f"cy:{self._bucket(center_y, 16.0)}",
            f"ww:{self._bucket(box_w, 8.0)}",
            f"wh:{self._bucket(box_h, 8.0)}",
            f"sw:{self._bucket(width, 32.0)}",
            f"sh:{self._bucket(height, 32.0)}",
        ]
        return "fallback:" + "|".join(parts), True, None

    def _visible_enemy(self, state: Dict[str, object]) -> Optional[Dict[str, float]]:
        labels = state.get("labels") or []
        screen = state.get("screen")
        player_x = float(state.get("x", 0.0) or 0.0)
        player_y = float(state.get("y", 0.0) or 0.0)
        player_z = float(state.get("z", 0.0) or 0.0)
        player_angle = float(state.get("angle", 0.0) or 0.0)
        autonomous_turning = self._autonomous_turning_enabled(state)
        dims = _screen_dimensions(screen)
        if dims is None:
            return None
        width, height = dims
        screen_center_x = width * 0.5
        e1m3_tight_gate = self.map_name == "E1M3" and not autonomous_turning

        best = None
        best_score = None
        persistent = None
        persistent_score = None
        committed = None
        for label in labels:
            name = getattr(label, "object_name", "") or ""
            if not self._is_enemy_name(name):
                continue
            target_key, is_fallback, object_id = self._target_signature(label, width=width, height=height)
            if not autonomous_turning and self.ignored_target_key == target_key and self.ignored_target_ticks > 0:
                continue
            enemy_z = getattr(label, "object_position_z", None)
            if enemy_z is not None:
                try:
                    if float(enemy_z) > player_z + COMBAT_MAX_TARGET_Z_DELTA:
                        continue
                except Exception:
                    pass
            box_w = float(getattr(label, "width", 0.0) or 0.0)
            box_h = float(getattr(label, "height", 0.0) or 0.0)
            area = box_w * box_h
            min_area = COMBAT_E1M3_MIN_LABEL_AREA if e1m3_tight_gate else COMBAT_MIN_LABEL_AREA
            if area < min_area:
                continue
            if (
                not autonomous_turning
                and box_w < COMBAT_RUNTIME_SLIVER_WIDTH_PX
                and (box_w / max(1.0, box_h)) < COMBAT_RUNTIME_SLIVER_ASPECT
            ):
                continue

            center_x = float(getattr(label, "x", 0.0) or 0.0) + (box_w * 0.5)
            center_y = float(getattr(label, "y", 0.0) or 0.0) + (box_h * 0.5)
            y_fraction = center_y / max(1.0, float(height))
            max_y_fraction = COMBAT_MAX_Y_FRACTION
            if enemy_z is not None:
                try:
                    if float(enemy_z) < player_z - COMBAT_BELOW_TARGET_Z_DELTA:
                        max_y_fraction = COMBAT_BELOW_TARGET_MAX_Y_FRACTION
                except Exception:
                    pass
            if y_fraction < COMBAT_MIN_Y_FRACTION or y_fraction > max_y_fraction:
                continue

            offset_x = (center_x - screen_center_x) / max(1.0, float(width))
            abs_offset = abs(offset_x)
            track_window = COMBAT_E1M3_MAX_TRACK_WINDOW if e1m3_tight_gate else COMBAT_TRACK_WINDOW
            if abs_offset > track_window:
                continue

            world_angle_error = None
            world_distance = None
            enemy_x = getattr(label, "object_position_x", None)
            enemy_y = getattr(label, "object_position_y", None)
            if enemy_x is not None and enemy_y is not None:
                try:
                    if not self._has_clear_world_line(player_x, player_y, float(enemy_x), float(enemy_y)):
                        continue
                    world_distance = math.hypot(float(enemy_x) - player_x, float(enemy_y) - player_y)
                    target_angle = math.degrees(math.atan2(float(enemy_y) - player_y, float(enemy_x) - player_x))
                    world_angle_error = _normalize_angle_delta_deg(target_angle - player_angle)
                except Exception:
                    world_angle_error = None
                    world_distance = None
            if e1m3_tight_gate and world_angle_error is not None and abs(float(world_angle_error)) > COMBAT_E1M3_MAX_WORLD_ANGLE_ERROR:
                continue

            width_fraction = box_w / max(1.0, float(width))
            height_fraction = box_h / max(1.0, float(height))
            score = abs_offset - (width_fraction * 0.55) - (height_fraction * 0.20)
            if world_angle_error is not None:
                score += abs(world_angle_error) / 120.0
            if world_distance is not None:
                score += min(COMBAT_DISTANCE_SCORE_CAP, max(0.0, float(world_distance)) / COMBAT_DISTANCE_SCORE_SCALE)
            if self.last_target_key == target_key:
                score -= COMBAT_TARGET_LOCK_BONUS
            candidate = {
                "object_id": object_id,
                "target_key": target_key,
                "target_is_fallback": is_fallback,
                "offset_x": offset_x,
                "abs_offset": abs_offset,
                "width_fraction": width_fraction,
                "angle_error_deg": world_angle_error,
            }
            if self.last_target_key == target_key:
                persistent = candidate
                persistent_score = score
            if (
                self.target_commit_ticks > 0
                and self.target_commit_key is not None
                and self.target_commit_key == target_key
            ):
                committed = candidate
            if best_score is None or score < best_score:
                best_score = score
                best = candidate
        if committed is not None and float(committed["abs_offset"]) <= COMBAT_TARGET_COMMIT_MAX_OFFSET:
            return committed
        if (
            persistent is not None
            and persistent_score is not None
            and best is not None
            and best_score is not None
        ):
            persistent_abs_offset = float(persistent["abs_offset"])
            if (
                persistent_abs_offset <= COMBAT_TARGET_PERSIST_MAX_OFFSET
                and persistent_score <= (best_score + COMBAT_TARGET_PERSIST_SCORE_MARGIN)
            ):
                return persistent
        return best

    def _enemy_hint_visible(self, state: Dict[str, object]) -> bool:
        labels = state.get("labels") or []
        dims = _screen_dimensions(state.get("screen"))
        if dims is None:
            return False
        _width, height = dims
        player_x = float(state.get("x", 0.0) or 0.0)
        player_y = float(state.get("y", 0.0) or 0.0)
        player_z = float(state.get("z", 0.0) or 0.0)
        autonomous_turning = self._autonomous_turning_enabled(state)
        e1m3_tight_gate = self.map_name == "E1M3" and not autonomous_turning

        for label in labels:
            name = getattr(label, "object_name", "") or ""
            if not self._is_enemy_name(name):
                continue
            target_key, _is_fallback, _object_id = self._target_signature(label, width=dims[0], height=height)
            if not autonomous_turning and self.ignored_target_key == target_key and self.ignored_target_ticks > 0:
                continue
            enemy_z = getattr(label, "object_position_z", None)
            if enemy_z is not None:
                try:
                    if float(enemy_z) > player_z + COMBAT_MAX_TARGET_Z_DELTA:
                        continue
                except Exception:
                    pass
            enemy_x = getattr(label, "object_position_x", None)
            enemy_y = getattr(label, "object_position_y", None)
            try:
                if not self._has_clear_world_line(player_x, player_y, float(enemy_x), float(enemy_y)):
                    continue
            except Exception:
                pass
            box_w = float(getattr(label, "width", 0.0) or 0.0)
            box_h = float(getattr(label, "height", 0.0) or 0.0)
            min_area = COMBAT_E1M3_MIN_LABEL_AREA if e1m3_tight_gate else COMBAT_MIN_LABEL_AREA
            if (box_w * box_h) < min_area:
                continue
            if (
                not autonomous_turning
                and box_w < COMBAT_RUNTIME_SLIVER_WIDTH_PX
                and (box_w / max(1.0, box_h)) < COMBAT_RUNTIME_SLIVER_ASPECT
                ):
                continue
            center_y = float(getattr(label, "y", 0.0) or 0.0) + (box_h * 0.5)
            y_fraction = center_y / max(1.0, float(height))
            if y_fraction < COMBAT_MIN_Y_FRACTION or y_fraction > COMBAT_HINT_MAX_Y_FRACTION:
                continue
            if e1m3_tight_gate and box_w < COMBAT_E1M3_MIN_WIDTH_PX:
                continue
            return True
        return False

    @staticmethod
    def _attack_ready(state: Dict[str, object]) -> bool:
        value = state.get("attack_ready")
        if value is None:
            return True
        try:
            return int(value) > 0
        except Exception:
            return bool(value)

    @staticmethod
    def _fire_window(target: Dict[str, float]) -> float:
        width_fraction = float(target["width_fraction"])
        return max(
            COMBAT_FIRE_WINDOW_MIN,
            min(COMBAT_FIRE_WINDOW_MAX, width_fraction * COMBAT_FIRE_WINDOW_SCALE),
        )

    @staticmethod
    def _autonomous_turning_enabled(state: Dict[str, object]) -> bool:
        return bool(state.get("autonomous_combat", False))

    def _update_shot_feedback(self, state: Dict[str, object], *, autonomous_turning: bool) -> None:
        current_ammo = float(state.get("ammo", 0.0) or 0.0)
        current_hitcount = int(state.get("hitcount", 0) or 0)
        current_damagecount = int(state.get("damagecount", 0) or 0)

        if self.ignored_target_ticks > 0:
            self.ignored_target_ticks -= 1
            if self.ignored_target_ticks <= 0:
                self.ignored_target_key = None

        if (
            self.last_ammo is not None
            and self.pending_shot_target_key is not None
            and current_ammo < self.last_ammo
        ):
            shots_fired = max(1, int(round(self.last_ammo - current_ammo)))
            hit_delta = (
                current_hitcount - self.last_hitcount
                if self.last_hitcount is not None
                else 0
            )
            damage_delta = (
                current_damagecount - self.last_damagecount
                if self.last_damagecount is not None
                else 0
            )
            if not autonomous_turning and hit_delta <= 0 and damage_delta <= 0:
                miss_limit = (
                    COMBAT_FALLBACK_MISS_STREAK_LIMIT
                    if self.pending_shot_target_is_fallback
                    else COMBAT_MISS_STREAK_LIMIT
                )
                if self.miss_streak_target_key == self.pending_shot_target_key:
                    self.miss_streak_count += shots_fired
                else:
                    self.miss_streak_target_key = self.pending_shot_target_key
                    self.miss_streak_count = shots_fired
                if self.miss_streak_count >= miss_limit:
                    self.ignored_target_key = self.pending_shot_target_key
                    self.ignored_target_ticks = (
                        COMBAT_FALLBACK_IGNORED_TARGET_TICKS
                        if self.pending_shot_target_is_fallback
                        else COMBAT_IGNORED_TARGET_TICKS
                    )
                    if self.last_target_key == self.ignored_target_key:
                        if self.target_commit_key == self.ignored_target_key:
                            self.target_commit_key = None
                            self.target_commit_ticks = 0
                        self.last_target_key = None
                        self.last_target_object_id = None
                        self.last_target_offset_x = None
                        self.last_target_angle_error = None
                    self.miss_streak_target_key = None
                    self.miss_streak_count = 0
            else:
                self.miss_streak_target_key = None
                self.miss_streak_count = 0

        self.pending_shot_target_key = None
        self.pending_shot_target_is_fallback = False
        self.last_ammo = current_ammo
        self.last_hitcount = current_hitcount
        self.last_damagecount = current_damagecount
        if self.target_commit_ticks > 0:
            self.target_commit_ticks -= 1
            if self.target_commit_ticks <= 0:
                self.target_commit_key = None

    def _remember_attack_target(
        self,
        buttons: Set[str],
        target: Optional[Dict[str, float]],
        state: Dict[str, object],
    ) -> Set[str]:
        if "ATTACK" not in buttons or not self._attack_ready(state) or target is None:
            self.pending_shot_target_key = None
            self.pending_shot_target_is_fallback = False
            return buttons
        self.pending_shot_target_key = str(target.get("target_key") or "")
        self.pending_shot_target_is_fallback = bool(target.get("target_is_fallback", False))
        self.target_commit_key = self.pending_shot_target_key or None
        self.target_commit_ticks = COMBAT_TARGET_COMMIT_TICKS
        return buttons

    def _prepare_target(self, target: Optional[Dict[str, float]], *, autonomous_turning: bool) -> Optional[Dict[str, float]]:
        if target is None:
            if self.target_commit_ticks <= 0:
                self.last_target_key = None
                self.last_target_object_id = None
                self.last_target_offset_x = None
                self.last_target_angle_error = None
                self.target_commit_key = None
            return None

        prepared = dict(target)
        predicted_offset_x = float(prepared["offset_x"])
        predicted_angle_error = prepared.get("angle_error_deg")

        target_key = str(prepared.get("target_key") or "")
        target_id = prepared.get("object_id")
        if (
            not autonomous_turning
            and self.target_commit_ticks > 0
            and self.target_commit_key is not None
            and target_key
            and target_key != self.target_commit_key
        ):
            return None
        if (
            not autonomous_turning
            and target_key
            and self.last_target_key == target_key
            and self.last_target_offset_x is not None
        ):
            offset_velocity = predicted_offset_x - self.last_target_offset_x
            predicted_offset_x += offset_velocity * COMBAT_PREDICTION_GAIN
            if predicted_angle_error is not None and self.last_target_angle_error is not None:
                angle_velocity = float(predicted_angle_error) - self.last_target_angle_error
                predicted_angle_error = float(predicted_angle_error) + (angle_velocity * COMBAT_PREDICTION_GAIN)

        prepared["predicted_offset_x"] = predicted_offset_x
        prepared["predicted_abs_offset"] = abs(predicted_offset_x)
        prepared["predicted_angle_error_deg"] = predicted_angle_error

        self.last_target_key = target_key or None
        self.last_target_object_id = int(target_id) if target_id is not None else None
        self.last_target_offset_x = float(prepared["offset_x"])
        self.last_target_angle_error = float(prepared["angle_error_deg"]) if prepared["angle_error_deg"] is not None else None
        if self.target_commit_key == self.last_target_key or self.target_commit_ticks <= 0:
            self.target_commit_key = self.last_target_key
            self.target_commit_ticks = COMBAT_TARGET_COMMIT_TICKS
        return prepared

    def _update_control_state(
        self,
        state: Dict[str, object],
        target: Optional[Dict[str, float]],
        *,
        enemy_hint_visible: bool,
    ) -> bool:
        health = float(state.get("health", 0.0) or 0.0)
        took_damage = self.last_health is not None and health < (self.last_health - COMBAT_DAMAGE_EPSILON)
        autonomous_turning = self._autonomous_turning_enabled(state)
        if target is not None or enemy_hint_visible:
            self.recent_enemy_ticks = COMBAT_RECENT_ENEMY_TICKS
        elif self.recent_enemy_ticks > 0:
            self.recent_enemy_ticks -= 1
        hostile_damage = took_damage and (target is not None or enemy_hint_visible or self.recent_enemy_ticks > 0)

        if autonomous_turning:
            self.control_active = True
        else:
            if target is not None or enemy_hint_visible or hostile_damage:
                self.combat_cooldown = COMBAT_COOLDOWN_TICKS
            elif self.combat_cooldown > 0:
                self.combat_cooldown -= 1
            self.control_active = self.combat_cooldown > 0

        self.last_health = health
        return autonomous_turning

    def in_control(self) -> bool:
        return self.control_active

    def _overlay_buttons(self, state: Dict[str, object], target: Optional[Dict[str, float]]) -> Set[str]:
        if target is None:
            if self.hold_ticks > 0:
                self.hold_ticks -= 1
            return {"ATTACK"} if self.hold_ticks > 0 else set()

        fire_window = self._fire_window(target)
        predicted_abs_offset = float(target.get("predicted_abs_offset", target["abs_offset"]))
        predicted_angle_error = target.get("predicted_angle_error_deg")
        if (
            predicted_abs_offset <= fire_window
            or (predicted_angle_error is not None and abs(float(predicted_angle_error)) <= COMBAT_FIRE_ANGLE_DEG)
        ):
            self.hold_ticks = COMBAT_HOLD_TICKS
        if self.hold_ticks > 0:
            return {"ATTACK"}
        return set()

    def _control_buttons(
        self,
        state: Dict[str, object],
        target: Optional[Dict[str, float]],
        *,
        autonomous_turning: bool,
    ) -> Set[str]:
        if target is None:
            self.hold_ticks = 0
            self.ready_grace_ticks = 0
            return {"TURN_LEFT"} if self.search_direction < 0 else {"TURN_RIGHT"}

        offset_x = float(target.get("predicted_offset_x", target["offset_x"]))
        angle_error = target.get("predicted_angle_error_deg")
        if offset_x < 0.0:
            self.search_direction = -1
        elif offset_x > 0.0:
            self.search_direction = 1

        fire_window = self._fire_window(target)
        predicted_abs_offset = float(target.get("predicted_abs_offset", target["abs_offset"]))
        attack_ready = self._attack_ready(state)
        if (
            predicted_abs_offset <= fire_window
            or (angle_error is not None and abs(float(angle_error)) <= COMBAT_FIRE_ANGLE_DEG)
        ):
            if not attack_ready:
                self.ready_grace_ticks = COMBAT_READY_GRACE_TICKS
                self.hold_ticks = 0
                return set()
            if autonomous_turning and not attack_ready:
                return set()
            self.ready_grace_ticks = 0
            self.hold_ticks = COMBAT_HOLD_TICKS
            return {"ATTACK"}

        if self.ready_grace_ticks > 0 and not attack_ready:
            self.ready_grace_ticks -= 1
            self.hold_ticks = 0
            return set()

        if angle_error is not None and abs(float(angle_error)) <= COMBAT_TURN_ANGLE_DEG:
            self.hold_ticks = 0
            self.ready_grace_ticks = 0
            return set()

        self.hold_ticks = 0
        self.ready_grace_ticks = 0
        return {"TURN_LEFT"} if offset_x < 0.0 else {"TURN_RIGHT"}

    def select(self, state: Dict[str, object]) -> Set[str]:
        ammo = float(state.get("ammo", 0.0) or 0.0)
        if ammo <= 0.0:
            self.combat_cooldown = 0
            self.control_active = False
            self.hold_ticks = 0
            self.last_health = float(state.get("health", 0.0) or 0.0)
            self.recent_enemy_ticks = 0
            self.ready_grace_ticks = 0
            self.last_ammo = ammo
            self.last_hitcount = int(state.get("hitcount", 0) or 0)
            self.last_damagecount = int(state.get("damagecount", 0) or 0)
            self.pending_shot_target_key = None
            self.pending_shot_target_is_fallback = False
            self.miss_streak_target_key = None
            self.miss_streak_count = 0
            self.ignored_target_key = None
            self.ignored_target_ticks = 0
            self.target_commit_key = None
            self.target_commit_ticks = 0
            return set()

        autonomous_turning = self._autonomous_turning_enabled(state)
        self._update_shot_feedback(state, autonomous_turning=autonomous_turning)
        target = self._prepare_target(self._visible_enemy(state), autonomous_turning=autonomous_turning)
        enemy_hint_visible = self._enemy_hint_visible(state)
        autonomous_turning = self._update_control_state(
            state,
            target,
            enemy_hint_visible=enemy_hint_visible,
        )
        if self.control_active:
            buttons = self._control_buttons(state, target, autonomous_turning=autonomous_turning)
            return self._remember_attack_target(buttons, target, state)
        buttons = self._overlay_buttons(state, target)
        return self._remember_attack_target(buttons, target, state)