"""
Perception system for parsing game state and detecting enemies/items.
"""

import logging

from agent.config import ENEMY_KEYWORDS


class PerceptionManager:
    """Manages state parsing and object detection from game state."""

    _logged_line_attrs = False
    
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
        # HEALTH, AMMO2, POSITION_X, POSITION_Y, ANGLE, KILLCOUNT
        health = float(game_vars[0]) if len(game_vars) > 0 else 100.0
        ammo = float(game_vars[1]) if len(game_vars) > 1 else 0.0
        pos_x = float(game_vars[2]) if len(game_vars) > 2 else 0.0
        pos_y = float(game_vars[3]) if len(game_vars) > 3 else 0.0
        angle = float(game_vars[4]) if len(game_vars) > 4 else 0.0
        
        # Use actual KILLCOUNT variable from game state
        kills = int(game_vars[5]) if len(game_vars) > 5 else 0

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
            "angle": angle,
            "screen": screen,
            "labels": labels,
            "sectors": getattr(state, "sectors", None),
            "lines": lines,
        }
        
        return info

    def detect_enemies_from_labels(self, labels):
        """Detect enemy on screen from labels, return (x, y, confidence)."""
        if not labels:
            return None
        
        enemies = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            name_lower = name.lower()
            is_enemy = any(k in name_lower for k in ENEMY_KEYWORDS)
            is_not_dead = "dead" not in name_lower and "gibbe" not in name_lower
            
            # Must be a real enemy and have reasonable bounding box size
            # Walls/artifacts are usually very small or very large
            area = lbl.width * lbl.height
            reasonable_size = 80 < area < 50000  # Must be substantial but not huge
            
            if is_enemy and is_not_dead and reasonable_size:
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
            name_lower = name.lower()
            if any(k in name_lower for k in ENEMY_KEYWORDS):
                count += 1
        return count
    
