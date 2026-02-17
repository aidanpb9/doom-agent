"""
Perception system for parsing game state and detecting enemies/items.
"""

import logging
import re

from config import ENEMY_KEYWORDS


class PerceptionManager:
    """Manages state parsing and object detection from game state."""

    _logged_line_attrs = False
    _enemy_name_aliases = {
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
    _pickup_name_aliases = {
        "shotgun",
        "chaingun",
        "stimpack",
        "medikit",
        "healthbonus",
        "armorbonus",
        "clip",
        "shell",
        "rocket",
        "cell",
        "backpack",
    }

    @staticmethod
    def _normalize_alnum(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _is_dead_name(name_lower: str) -> bool:
        return "dead" in name_lower or "gibbe" in name_lower

    def _is_enemy_name(self, name: str) -> bool:
        if not name:
            return False
        name_lower = name.lower()
        if self._is_dead_name(name_lower):
            return False

        flat = self._normalize_alnum(name_lower)
        if not flat:
            return False
        if flat in self._enemy_name_aliases:
            return True

        tokens = [tok for tok in re.findall(r"[a-z0-9]+", name_lower) if tok]
        for tok in tokens:
            if tok in self._enemy_name_aliases:
                return True

        for raw_kw in ENEMY_KEYWORDS:
            kw = self._normalize_alnum(raw_kw)
            if not kw:
                continue
            for tok in tokens:
                if tok == kw:
                    if kw in {"shotgun", "chaingun"} and tok in self._pickup_name_aliases:
                        continue
                    return True
                if tok.startswith(kw) or tok.endswith(kw):
                    if kw in {"shotgun", "chaingun"} and tok in self._pickup_name_aliases:
                        continue
                    return True
            if flat == kw or flat.startswith(kw) or flat.endswith(kw):
                if kw in {"shotgun", "chaingun"} and flat in self._pickup_name_aliases:
                    continue
                return True
        return False
    
    def get_state_info(self, state):
        """Parse vizdoom state into structured info."""
        if state is None:
            return None
            
        game_vars = state.game_variables
        screen = state.screen_buffer
        labels = state.labels if hasattr(state, 'labels') else []
        
        if game_vars is None or len(game_vars) == 0:
            return None

        # doom/doom.cfg game var order:
        # HEALTH, AMMO2, POSITION_X, POSITION_Y, POSITION_Z, ANGLE, KILLCOUNT
        health = float(game_vars[0]) if len(game_vars) > 0 else 100.0
        ammo = float(game_vars[1]) if len(game_vars) > 1 else 0.0
        pos_x = float(game_vars[2]) if len(game_vars) > 2 else 0.0
        pos_y = float(game_vars[3]) if len(game_vars) > 3 else 0.0
        pos_z = float(game_vars[4]) if len(game_vars) > 4 else 0.0
        angle = float(game_vars[5]) if len(game_vars) > 5 else 0.0
        
        # Use actual KILLCOUNT variable from game state
        kills = int(game_vars[6]) if len(game_vars) > 6 else 0

        lines = getattr(state, "lines", None)
        if not self._logged_line_attrs:
            self._logged_line_attrs = True
            attrs = [a for a in dir(state) if "line" in a.lower()]
            logging.getLogger(__name__).info("[NAV] State line attrs: %s", attrs)
            if lines is None:
                logging.getLogger(__name__).info("[NAV] State lines: None")
            else:
                logging.getLogger(__name__).info("[NAV] State lines count: %s", len(lines))

        info = {
            "health": health,
            "ammo": ammo,
            "kills": kills,
            "pos_x": pos_x,
            "pos_y": pos_y,
            "pos_z": pos_z,
            "angle": angle,
            "screen": screen,
            "labels": labels,
            "sectors": getattr(state, "sectors", None),
            "lines": lines,
        }
        
        return info

    def detect_enemies_from_labels(self, labels, pos_z=None, screen_height=None):
        """Detect enemy on screen from labels, return (x, y, confidence)."""
        if not labels:
            return None
        
        enemies = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            is_enemy = self._is_enemy_name(name)
            
            # Must be a real enemy and have reasonable bounding box size
            # Walls/artifacts are usually very small or very large
            area = lbl.width * lbl.height
            reasonable_size = 80 < area < 50000  # Must be substantial but not huge
            
            if is_enemy and reasonable_size:
                enemy_z = getattr(lbl, "object_position_z", None)
                if enemy_z is not None and pos_z is not None:
                    if (enemy_z - pos_z) > 48.0:
                        continue
                cx = lbl.x + lbl.width / 2
                cy = lbl.y + lbl.height / 2
                
                enemies.append({
                    'x': cx,
                    'y': cy,
                    'area': area,
                    'name': lbl.object_name
                })
        
        if enemies:
            enemies.sort(key=lambda e: e['area'], reverse=True)
            enemy = enemies[0]
            return (int(enemy['x']), int(enemy['y']), min(enemy['area'] / 2000.0, 1.0))
        
        return None

    def count_enemies_from_labels(self, labels):
        """Count living enemies from labels."""
        if not labels:
            return 0
        count = 0
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            if self._is_enemy_name(name):
                count += 1
        return count
    
