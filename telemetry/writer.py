"""
Telemetry emission utilities for DoomSat schema v2.
Implements Tier 0, Tier 1, Tier 2, and Two-Line-Plus (TLP) outputs.
"""

from __future__ import annotations

import csv
import gc
import json
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None


SCHEMA_VERSION = "v2"
TIER0_TYPE = "tier0_telemetry"
TIER1_TYPE = "level_summary"
TIER2_CSV_HEADER = "t,tick,scene,frame,action,seed,state,cpu_ms"

DEFAULT_TLE_LINE1 = "1 25544U 98067A   25273.51782528  .00002182  00000 -0  43188 -4 0  9993"
DEFAULT_TLE_LINE2 = "2 25544  51.6421 187.1234 0004053 160.4321 310.5678 15.50012345678901"

SPACECRAFT_STATE_CODES = {
    "safe": 0,
    "idle": 1,
    "comms": 2,
    "nominal": 3,
    "safety1": 4,
    "safety2": 5,
}

TIMEOUT_REASON_CODES = {
    "none": 0,
    "wall_clock": 1,
    "max_steps": 2,
    "hang_no_movement": 3,
    "player_dead": 4,
    "state_none": 5,
    "error": 6,
}

_EM_RE = re.compile(r"^E(\d+)M(\d+)$", re.IGNORECASE)
_MAP_RE = re.compile(r"^MAP(\d+)$", re.IGNORECASE)
_CRC32C_TABLE: List[int] = []


def _build_crc32c_table() -> List[int]:
    table: List[int] = []
    poly = 0x82F63B78
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
        table.append(crc & 0xFFFFFFFF)
    return table


def crc32c(data: bytes) -> int:
    global _CRC32C_TABLE
    if not _CRC32C_TABLE:
        _CRC32C_TABLE = _build_crc32c_table()
    crc = 0xFFFFFFFF
    for byte in data:
        crc = (crc >> 8) ^ _CRC32C_TABLE[(crc ^ byte) & 0xFF]
    return (~crc) & 0xFFFFFFFF


def _json_crc32c(payload: Dict[str, Any]) -> str:
    serial = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{crc32c(serial):08x}"


def _add_crc32c(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    data.pop("crc32c", None)
    data["crc32c"] = _json_crc32c(data)
    return data


def _u8(value: Any) -> int:
    iv = int(float(value))
    return max(0, min(255, iv))


def _u16(value: Any) -> int:
    iv = int(float(value))
    return max(0, min(65535, iv))


def _u32(value: Any) -> int:
    iv = int(float(value))
    return max(0, min(0xFFFFFFFF, iv))


def _u64(value: Any) -> int:
    iv = int(float(value))
    return max(0, min(0xFFFFFFFFFFFFFFFF, iv))


def _i8(value: Any) -> int:
    iv = int(float(value))
    return max(-128, min(127, iv))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _now_unix_s() -> int:
    return _u64(int(time.time()))


def _now_unix_ms() -> int:
    return _u64(int(time.time() * 1000))


def _detect_git_hash(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        value = (proc.stdout or "").strip()
        if value:
            return value
    except Exception:
        pass
    return "unknown"


def derive_episode_id(level_id: str, fallback_episode: int) -> int:
    level = (level_id or "").strip().upper()
    match = _EM_RE.match(level)
    if match:
        return _u16(match.group(1))
    match = _MAP_RE.match(level)
    if match:
        return _u16(match.group(1))
    return _u16(fallback_episode)


def derive_scene_id(level_id: str, fallback_scene: int) -> int:
    level = (level_id or "").strip().upper()
    match = _EM_RE.match(level)
    if match:
        ep = int(match.group(1))
        mission = int(match.group(2))
        return _u16(ep * 100 + mission)
    match = _MAP_RE.match(level)
    if match:
        return _u16(match.group(1))
    return _u16(fallback_scene)


def encode_action_bitmask(action_vector: Sequence[int]) -> int:
    """
    Encoding from design spec:
    Bit0 ATTACK, Bit1 USE, Bit2 MOVE_FORWARD, Bit3 MOVE_BACKWARD,
    Bit4 TURN_LEFT, Bit5 TURN_RIGHT, Bit6 STRAFE_LEFT, Bit7 STRAFE_RIGHT,
    Bit8 SPEED, Bit9 STRAFE.
    """
    bits = 0
    if len(action_vector) > 6 and int(action_vector[6]):
        bits |= 1 << 0
    if len(action_vector) > 7 and int(action_vector[7]):
        bits |= 1 << 1
    if len(action_vector) > 0 and int(action_vector[0]):
        bits |= 1 << 2
    if len(action_vector) > 1 and int(action_vector[1]):
        bits |= 1 << 3
    if len(action_vector) > 2 and int(action_vector[2]):
        bits |= 1 << 4
    if len(action_vector) > 3 and int(action_vector[3]):
        bits |= 1 << 5
    if len(action_vector) > 4 and int(action_vector[4]):
        bits |= 1 << 6
        bits |= 1 << 9
    if len(action_vector) > 5 and int(action_vector[5]):
        bits |= 1 << 7
        bits |= 1 << 9
    return _u16(bits)


def _hex4(value: int) -> str:
    return f"{_u16(value):04x}"


def _state_hash(
    *,
    tick: int,
    frame_id: int,
    scene_id: int,
    health: float,
    ammo: float,
    kills: int,
    pos_x: float,
    pos_y: float,
    angle: float,
) -> int:
    payload = (
        f"{_u32(tick)}|{_u32(frame_id)}|{_u16(scene_id)}|"
        f"{health:.3f}|{ammo:.3f}|{int(kills)}|{pos_x:.3f}|{pos_y:.3f}|{angle:.3f}"
    )
    return _u32(crc32c(payload.encode("utf-8")))


def _gc_collection_count() -> int:
    try:
        stats = gc.get_stats()
        total = 0
        for item in stats:
            total += int(item.get("collections", 0))
        return _u32(total)
    except Exception:
        return 0


class TelemetryWriter:
    """Collects and writes telemetry artifacts defined in design-doc schema v2."""

    def __init__(
        self,
        *,
        repo_root: Path,
        telemetry_dir: Path,
        algo_id: str = "rule-based-selector",
        spacecraft_state: str = "nominal",
    ) -> None:
        self.repo_root = Path(repo_root)
        self.telemetry_dir = Path(telemetry_dir)
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self._tier_dirs = {
            "tier0": self.telemetry_dir / "tier0",
            "tier1": self.telemetry_dir / "tier1",
            "tier2": self.telemetry_dir / "tier2",
            "tlp": self.telemetry_dir / "tlp",
        }
        for tier_dir in self._tier_dirs.values():
            tier_dir.mkdir(parents=True, exist_ok=True)
        self.algo_id = (algo_id or "rule-based-selector").strip().lower()
        self.spacecraft_state = (spacecraft_state or "nominal").strip().lower()
        if self.spacecraft_state not in SPACECRAFT_STATE_CODES:
            self.spacecraft_state = "nominal"
        self.state_change_unix_ms = _now_unix_ms()
        self.run_id = int((time.time_ns() ^ random.getrandbits(32)) & 0xFFFFFFFF)
        if self.run_id == 0:
            self.run_id = 1
        self.git_hash = _detect_git_hash(self.repo_root)
        self.process = psutil.Process(os.getpid()) if psutil else None
        self.gc_base = _gc_collection_count()

        self.episode_index = 0
        self.episode_id = 0
        self.level_id = "UNKNOWN"
        self.scene_id = 0
        self.rng_seed = 0

        self._tier0_path: Optional[Path] = None
        self._tier1_path: Optional[Path] = None
        self._tier2_path: Optional[Path] = None
        self._tlp_path: Optional[Path] = None
        self._tier0_file = None
        self._tier2_file = None
        self._tier2_writer: Optional[csv.writer] = None

        self._tier2_rows: List[Dict[str, Any]] = []
        self._last_tier0: Optional[Dict[str, Any]] = None
        self._last_health = 100.0
        self._last_ammo = 0.0
        self._last_kills = 0
        self._path_len_m = 0.0
        self._last_pos = None
        self._damage_taken_total = 0
        self._damage_dealt_total = 0
        self._ammo_start = 0.0
        self._ammo_end = 0.0
        self._clock_skew_ppm = 0
        self._timeout_count = 0

    def _clear_previous_outputs(self) -> None:
        # Remove legacy root-level telemetry files from older naming schemes.
        for pattern in ("run*_tier0.jsonl", "run*_tier1.json", "run*_tier2.csv", "run*_tlp.txt"):
            for path in self.telemetry_dir.glob(pattern):
                try:
                    path.unlink()
                except Exception:
                    pass

        # Keep only one telemetry output file per tier.
        for tier_key, tier_dir in self._tier_dirs.items():
            suffixes = {
                "tier0": ("*.jsonl",),
                "tier1": ("*.json",),
                "tier2": ("*.csv",),
                "tlp": ("*.txt",),
            }[tier_key]
            for suffix_pattern in suffixes:
                for path in tier_dir.glob(suffix_pattern):
                    try:
                        path.unlink()
                    except Exception:
                        pass

    def start_episode(
        self,
        *,
        level_id: str,
        episode_index: int,
        rng_seed: Optional[int] = None,
    ) -> int:
        self.close()

        self.episode_index = max(1, int(episode_index))
        self.level_id = (level_id or "UNKNOWN").strip().upper()
        self.episode_id = derive_episode_id(self.level_id, self.episode_index)
        self.scene_id = derive_scene_id(self.level_id, self.episode_id)
        if rng_seed is None:
            rng_seed = time.time_ns() ^ self.run_id ^ self.episode_index
        self.rng_seed = _u32(rng_seed)
        self._timeout_count = 0

        self._clear_previous_outputs()
        self._tier0_path = self._tier_dirs["tier0"] / "latest.jsonl"
        self._tier1_path = self._tier_dirs["tier1"] / "latest.json"
        self._tier2_path = self._tier_dirs["tier2"] / "latest.csv"
        self._tlp_path = self._tier_dirs["tlp"] / "latest.txt"

        self._tier0_file = self._tier0_path.open("w", encoding="utf-8", newline="\n")
        self._tier2_file = self._tier2_path.open("w", encoding="utf-8", newline="\n")
        self._tier2_writer = csv.writer(self._tier2_file)
        self._tier2_writer.writerow(TIER2_CSV_HEADER.split(","))

        self._tier2_rows = []
        self._last_tier0 = None
        self._last_health = 100.0
        self._last_ammo = 0.0
        self._last_kills = 0
        self._path_len_m = 0.0
        self._last_pos = None
        self._damage_taken_total = 0
        self._damage_dealt_total = 0
        self._ammo_start = 0.0
        self._ammo_end = 0.0
        self.gc_base = _gc_collection_count()
        return self.rng_seed

    def _platform_snapshot(self) -> Dict[str, Any]:
        soc_pct = 100
        if psutil and hasattr(psutil, "sensors_battery"):
            try:
                battery = psutil.sensors_battery()
                if battery and battery.percent is not None:
                    soc_pct = _u8(round(float(battery.percent)))
            except Exception:
                pass

        cpu_temp = 0.0
        board_temp = 0.0
        if psutil and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures(fahrenheit=False)  # type: ignore[arg-type]
                if temps:
                    for readings in temps.values():
                        if readings:
                            current = readings[0].current
                            cpu_temp = _float(current, 0.0)
                            board_temp = cpu_temp
                            break
            except Exception:
                pass

        mem_b = 0
        rss_mb = 0.0
        if self.process is not None:
            try:
                mem = self.process.memory_info()
                mem_b = _u32(mem.rss)
                rss_mb = float(mem_b) / (1024.0 * 1024.0)
            except Exception:
                pass

        return {
            "soc_pct": soc_pct,
            "cpu_temp_c": cpu_temp,
            "board_temp_c": board_temp,
            "mem_b": mem_b,
            "rss_mb": rss_mb,
        }

    @staticmethod
    def _extract_keys(labels: Any) -> Dict[str, bool]:
        keys = {"red": False, "blue": False, "yellow": False}
        if not labels:
            return keys
        for lbl in labels:
            name = (getattr(lbl, "object_name", "") or "").lower()
            if "key" not in name and "card" not in name and "skull" not in name:
                continue
            if "red" in name:
                keys["red"] = True
            if "blue" in name:
                keys["blue"] = True
            if "yellow" in name:
                keys["yellow"] = True
        return keys

    @staticmethod
    def _pick_enemy_name(labels: Any) -> str:
        if not labels:
            return "unknown"
        for lbl in labels:
            name = (getattr(lbl, "object_name", "") or "").strip()
            if name:
                return name.lower()
        return "unknown"

    def record_step(
        self,
        *,
        state_info: Optional[Dict[str, Any]],
        action_vector: Sequence[int],
        tick: int,
        frame_id: int,
        step_wall_ms: float,
        step_cpu_ms: int,
        timeout_active: bool,
        timeout_reason: str,
        timeout_count: int,
        outcome: str,
        emit_action_row: bool = True,
    ) -> Optional[Dict[str, Any]]:
        if self._tier0_file is None:
            return None

        if state_info is None:
            state_info = {}

        health = _float(state_info.get("health", self._last_health), self._last_health)
        ammo = _float(state_info.get("ammo", self._last_ammo), self._last_ammo)
        kills = int(state_info.get("kills", self._last_kills))
        pos_x = _float(state_info.get("pos_x", 0.0), 0.0)
        pos_y = _float(state_info.get("pos_y", 0.0), 0.0)
        angle = _float(state_info.get("angle", 0.0), 0.0)
        labels = state_info.get("labels", [])

        if self._last_pos is None:
            self._last_pos = (pos_x, pos_y)
        else:
            dx = pos_x - self._last_pos[0]
            dy = pos_y - self._last_pos[1]
            self._path_len_m += (dx * dx + dy * dy) ** 0.5
            self._last_pos = (pos_x, pos_y)

        damage_taken_step = max(0.0, self._last_health - health)
        kill_delta = max(0, kills - self._last_kills)
        damage_dealt_step = float(kill_delta * 100.0)
        self._damage_taken_total += _u32(round(damage_taken_step))
        self._damage_dealt_total += _u32(round(damage_dealt_step))
        if self._last_ammo == 0.0 and not self._tier2_rows:
            self._ammo_start = ammo
        self._ammo_end = ammo

        self._last_health = health
        self._last_ammo = ammo
        self._last_kills = kills
        self._timeout_count = _u16(timeout_count)

        platform = self._platform_snapshot()
        action_mask = encode_action_bitmask(action_vector)
        state_hash = _state_hash(
            tick=tick,
            frame_id=frame_id,
            scene_id=self.scene_id,
            health=health,
            ammo=ammo,
            kills=kills,
            pos_x=pos_x,
            pos_y=pos_y,
            angle=angle,
        )

        frame_ms = max(0.0, _float(step_wall_ms, 0.0))
        cpu_ms = _u16(step_cpu_ms)
        fps = 0.0 if frame_ms <= 0.0 else 1000.0 / frame_ms
        cpu_pct = 0.0 if frame_ms <= 0.0 else min(100.0, max(0.0, 100.0 * (cpu_ms / frame_ms)))
        timeout_reason_norm = (timeout_reason or "none").strip().lower()
        if timeout_reason_norm.startswith("error:"):
            timeout_reason_norm = "error"
        if timeout_reason_norm not in TIMEOUT_REASON_CODES:
            timeout_reason_norm = "none"

        packet: Dict[str, Any] = {
            "type": TIER0_TYPE,
            "schema": SCHEMA_VERSION,
            "unix_time": _now_unix_s(),
            "run_id": _u32(self.run_id),
            "episode_id": _u16(self.episode_id),
            "algo_id": self.algo_id,
            "git": self.git_hash,
            "rng_seed": _u32(self.rng_seed),
            "spacecraft": {
                "state": self.spacecraft_state,
                "state_change_unix_ms": _u64(self.state_change_unix_ms),
                "vbat_v": 0.0,
                "ibat_a": 0.0,
                "soc_pct": _u8(platform["soc_pct"]),
                "board_temp_c": _float(platform["board_temp_c"]),
                "cpu_temp_c": _float(platform["cpu_temp_c"]),
                "seu_count": _u16(0),
                "sed_count": _u16(0),
                "heap_free_b": _u32(0),
                "stack_hwm_b": _u32(0),
                "rssi_dbm": _i8(-92),
                "err_rate_ppm": _u16(0),
            },
            "vizdoom": {
                "tick": _u32(tick),
                "frame_id": _u32(frame_id),
                "scene_id": _u16(self.scene_id),
                "action": _u16(action_mask),
                "step_ms": _u16(round(frame_ms)),
                "timeout_active": bool(timeout_active),
                "timeout_reason": timeout_reason_norm,
                "timeout_count": _u16(timeout_count),
                "cpu_ms": _u16(cpu_ms),
                "mem_b": _u32(platform["mem_b"]),
                "state_hash": _u32(state_hash),
            },
            "player": {
                "hp": _u8(round(health)),
                "armor": _u8(0),
                "keys": self._extract_keys(labels),
                "secrets_found": _u8(0),
                "ammo": {
                    "bullets": _u16(round(ammo)),
                    "shells": _u16(0),
                    "rockets": _u16(0),
                    "cells": _u16(0),
                },
                "combat": {
                    "damage_in": _u16(round(damage_taken_step)),
                    "damage_out": _u16(round(damage_dealt_step)),
                    "source": self._pick_enemy_name(labels) if damage_taken_step > 0.0 else "none",
                    "target": self._pick_enemy_name(labels) if damage_dealt_step > 0.0 else "none",
                },
            },
            "perf": {
                "fps": _float(fps),
                "frame_ms": _float(frame_ms),
                "cpu_pct": _float(cpu_pct),
                "rss_mb": _float(platform["rss_mb"]),
                "gc_events": _u16(_gc_collection_count() - self.gc_base),
            },
            "outcome": (outcome or "alive").strip().lower(),
        }
        packet = _add_crc32c(packet)
        self._tier0_file.write(json.dumps(packet, ensure_ascii=True, separators=(",", ":")) + "\n")
        self._tier0_file.flush()
        self._last_tier0 = packet

        if emit_action_row and self._tier2_writer is not None:
            row = {
                "t": _now_unix_ms(),
                "tick": _u32(tick),
                "scene": _u16(self.scene_id),
                "frame": _u32(frame_id),
                "action": f"0x{_hex4(action_mask)}",
                "seed": _u32(self.rng_seed),
                "state": f"{_u32(state_hash):08x}",
                "cpu_ms": _u16(cpu_ms),
            }
            self._tier2_writer.writerow(
                [
                    row["t"],
                    row["tick"],
                    row["scene"],
                    row["frame"],
                    row["action"],
                    row["seed"],
                    row["state"],
                    row["cpu_ms"],
                ]
            )
            self._tier2_file.flush()
            self._tier2_rows.append(row)

        return packet

    def finalize_episode(
        self,
        *,
        end_reason: str,
        episode_time_s: float,
        nav_stuck_events: int,
        nav_recoveries: int,
    ) -> Dict[str, str]:
        if self._tier1_path is None or self._tlp_path is None:
            return {}

        reason = (end_reason or "unknown").strip().lower()
        if reason.startswith("error:"):
            timeout_reason = "error"
        elif reason in {"timeout", "max_steps", "hang_no_movement", "state_none"}:
            timeout_reason = {
                "timeout": "wall_clock",
                "max_steps": "max_steps",
                "hang_no_movement": "hang_no_movement",
                "state_none": "state_none",
            }[reason]
        elif reason == "player_dead":
            timeout_reason = "player_dead"
        else:
            timeout_reason = "none"

        if timeout_reason != "none":
            self._timeout_count = max(_u16(self._timeout_count), 1)

        if self._last_tier0 is not None:
            last_state = self._last_tier0.get("player", {})
            hp = _u8(last_state.get("hp", 0))
            armor = _u8(last_state.get("armor", 0))
            keys = last_state.get("keys", {"red": False, "blue": False, "yellow": False})
        else:
            hp = 0
            armor = 0
            keys = {"red": False, "blue": False, "yellow": False}

        ammo_used_bullets = _u16(max(0, round(self._ammo_start - self._ammo_end)))
        tier1 = {
            "type": TIER1_TYPE,
            "schema": SCHEMA_VERSION,
            "unix_time": _now_unix_s(),
            "run_id": _u32(self.run_id),
            "episode_id": _u16(self.episode_id),
            "algo_id": self.algo_id,
            "git": self.git_hash,
            "rng_seed": _u32(self.rng_seed),
            "level_id": self.level_id,
            "result": "win" if reason == "exit" else "loss",
            "duration_s": _float(max(0.0, episode_time_s)),
            "hp_end": _u8(hp),
            "armor_end": _u8(armor),
            "keys": keys,
            "secrets_found": _u8(0),
            "damage": {
                "taken": _u32(self._damage_taken_total),
                "dealt_total": _u32(self._damage_dealt_total),
                "dealt_by_enemy": {},
            },
            "resources": {
                "ammo_used": {
                    "bullets": _u16(ammo_used_bullets),
                    "shells": _u16(0),
                    "rockets": _u16(0),
                    "cells": _u16(0),
                },
                "medkits_used": _u8(0),
                "armor_picked": _u16(0),
            },
            "efficiency": {
                "damage_per_ammo": _float(
                    float(self._damage_dealt_total) / float(ammo_used_bullets) if ammo_used_bullets > 0 else 0.0
                ),
                "targeting_pct": _float(0.0),
                "overkill_pct": _float(0.0),
            },
            "navigation": {
                "path_len_m": _float(self._path_len_m),
                "backtrack_pct": _float(0.0),
                "stuck_events": _u8(nav_stuck_events),
                "recoveries": _u8(nav_recoveries),
            },
            "faults": {
                "ecc_corrected": _u16(0),
                "bitflips_injected": _u16(0),
                "watchdog_resets": _u16(0),
                "divergence_events": _u16(0),
            },
        }
        tier1 = _add_crc32c(tier1)
        self._tier1_path.write_text(json.dumps(tier1, indent=2, ensure_ascii=True), encoding="utf-8")

        self._write_tlp(timeout_reason=timeout_reason)

        paths = {
            "tier0": str(self._tier0_path) if self._tier0_path is not None else "",
            "tier1": str(self._tier1_path),
            "tier2": str(self._tier2_path) if self._tier2_path is not None else "",
            "tlp": str(self._tlp_path),
        }
        self.close()
        return paths

    def _write_tlp(self, *, timeout_reason: str) -> None:
        if self._tlp_path is None:
            return
        last = self._last_tier0 or {}
        spacecraft = last.get("spacecraft", {})
        payload = last.get("vizdoom", {})

        unix_ms = _now_unix_ms()
        state_code = SPACECRAFT_STATE_CODES.get(self.spacecraft_state, 3)
        vbat = _float(spacecraft.get("vbat_v", 0.0))
        ibat = _float(spacecraft.get("ibat_a", 0.0))
        soc = _u8(spacecraft.get("soc_pct", 100))
        board_temp_tenths = int(round(_float(spacecraft.get("board_temp_c", 0.0)) * 10.0))
        cpu_temp_tenths = int(round(_float(spacecraft.get("cpu_temp_c", 0.0)) * 10.0))
        seu = _u16(spacecraft.get("seu_count", 0))
        sed = _u16(spacecraft.get("sed_count", 0))
        heap = _u32(spacecraft.get("heap_free_b", 0))
        stack = _u32(spacecraft.get("stack_hwm_b", 0))
        rssi = _i8(spacecraft.get("rssi_dbm", -92))
        err_rate = _u16(spacecraft.get("err_rate_ppm", 0))

        if self._tier2_rows:
            row = self._tier2_rows[-1]
            tick = _u32(row.get("tick", payload.get("tick", 0)))
            scene = _u16(row.get("scene", payload.get("scene_id", self.scene_id)))
            frame = _u32(row.get("frame", payload.get("frame_id", 0)))
            action_hex = str(row.get("action", "0x0000")).replace("0x", "")
            state_hash_hex = str(row.get("state", f"{_u32(payload.get('state_hash', 0)):08x}"))
            cpu_ms = _u16(row.get("cpu_ms", payload.get("cpu_ms", 0)))
        else:
            tick = _u32(payload.get("tick", 0))
            scene = _u16(payload.get("scene_id", self.scene_id))
            frame = _u32(payload.get("frame_id", 0))
            action_hex = _hex4(_u16(payload.get("action", 0)))
            state_hash_hex = f"{_u32(payload.get('state_hash', 0)):08x}"
            cpu_ms = _u16(payload.get("cpu_ms", 0))
        mem_b = _u32(payload.get("mem_b", 0))
        timeout_active = 1 if bool(payload.get("timeout_active", False)) else 0
        timeout_reason_code = TIMEOUT_REASON_CODES.get(timeout_reason, 0)
        timeout_count = _u16(self._timeout_count)

        lines = [
            DEFAULT_TLE_LINE1,
            DEFAULT_TLE_LINE2,
            (
                f"3 {unix_ms} {state_code} {vbat:.2f} {ibat:.2f} {soc} "
                f"{board_temp_tenths} {cpu_temp_tenths} {seu} {sed} {heap} {stack} "
                f"{rssi} {err_rate} {self._clock_skew_ppm}"
            ),
            (
                f"4 {tick} {scene} {frame} {action_hex} {self.rng_seed} "
                f"{state_hash_hex} {cpu_ms} {mem_b} {timeout_active} {timeout_reason_code} {timeout_count}"
            ),
        ]

        line_no = 5
        for row in self._tier2_rows:
            lines.append(
                f"{line_no} {row['t']} {row['tick']} {row['scene']} {row['frame']} "
                f"{str(row['action']).replace('0x', '')} {row['seed']} {row['state']} {row['cpu_ms']}"
            )
            line_no += 1

        self._tlp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def close(self) -> None:
        if self._tier0_file is not None:
            try:
                self._tier0_file.close()
            except Exception:
                pass
            self._tier0_file = None

        if self._tier2_file is not None:
            try:
                self._tier2_file.close()
            except Exception:
                pass
            self._tier2_file = None

        self._tier2_writer = None
