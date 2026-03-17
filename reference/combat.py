"""Minimal combat overlay behavior."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Set, Tuple


COMBAT_CENTER_TOLERANCE = 0.18
COMBAT_MIN_CONFIDENCE = 0.12
COMBAT_MAX_CENTER_OFFSET = 0.42
COMBAT_HOLD_TICKS = 4 #IMPORTANT, KEEP THIS

ENEMY_NAME_ALIASES = {
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


class CombatAction:
    """Adds ATTACK when a visible enemy is already on the current line of travel."""

    def __init__(self):
        self.hold_ticks = 0

    def _is_enemy_name(self, name: str) -> bool:
        if not name:
            return False
        name_lower = name.lower()
        if "dead" in name_lower or "gibbe" in name_lower:
            return False
        flat = _normalize_alnum(name_lower)
        if flat in ENEMY_NAME_ALIASES:
            return True
        for token in re.findall(r"[a-z0-9]+", name_lower):
            if token in ENEMY_NAME_ALIASES:
                return True
        return False

    def _visible_enemy(self, state: Dict[str, object]) -> Optional[Dict[str, float]]:
        labels = state.get("labels") or []
        screen = state.get("screen")
        pos_z = float(state["z"])
        dims = _screen_dimensions(screen)
        if dims is None:
            return None
        width, height = dims

        best = None
        best_score = None
        for label in labels:
            name = getattr(label, "object_name", "") or ""
            if not self._is_enemy_name(name):
                continue
            enemy_z = getattr(label, "object_position_z", None)
            if enemy_z is not None and (float(enemy_z) - pos_z) > 48.0:
                continue
            w = float(getattr(label, "width", 0.0) or 0.0)
            h = float(getattr(label, "height", 0.0) or 0.0)
            area = w * h
            if area < 16.0:
                continue
            x = float(getattr(label, "x", 0.0) or 0.0) + (w * 0.5)
            y = float(getattr(label, "y", 0.0) or 0.0) + (h * 0.5)
            if y < height * 0.12:
                continue
            center_dx = abs(x - (width * 0.5)) / max(1.0, width)
            confidence = min(max(area / 600.0, 0.0), 1.0)
            score = center_dx - (confidence * 0.2)
            if best_score is None or score < best_score:
                best_score = score
                best = {"center_dx": center_dx, "confidence": confidence}
        return best

    def select(self, state: Dict[str, object]) -> Set[str]:
        ammo = float(state["ammo"])
        if ammo <= 0.0:
            self.hold_ticks = 0
            return set()

        enemy = self._visible_enemy(state)
        if enemy is not None:
            if (
                enemy["center_dx"] <= COMBAT_MAX_CENTER_OFFSET
                and (
                    enemy["center_dx"] <= COMBAT_CENTER_TOLERANCE
                    or enemy["confidence"] >= COMBAT_MIN_CONFIDENCE
                )
            ):
                self.hold_ticks = COMBAT_HOLD_TICKS
        elif self.hold_ticks > 0:
            self.hold_ticks -= 1

        if self.hold_ticks <= 0:
            return set()
        return {"ATTACK"}
