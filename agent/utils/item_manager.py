"""
Item and target prioritization system.
"""

from agent.config import PRIORITY_LABELS


class ItemManager:
    """Manages item detection and prioritization."""
    
    def find_priority_target_on_screen(self, labels, health, ammo):
        """Find the most important item/target on screen to navigate toward."""
        if not labels:
            return None
        
        targets = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            name_lower = name.lower()
            
            # Skip player and weapons
            if "player" in name_lower or "weapon" in name_lower:
                continue
            
            # Check priority
            priority = 0
            for keyword, score in PRIORITY_LABELS.items():
                if keyword in name_lower:
                    priority = max(priority, score)
                    break
            
            if priority > 0:
                cx = lbl.x + lbl.width / 2
                cy = lbl.y + lbl.height / 2
                targets.append({
                    "x": cx,
                    "y": cy,
                    "name": name,
                    "priority": priority,
                })
        
        if targets:
            # Sort by priority (higher first)
            targets.sort(key=lambda t: t["priority"], reverse=True)
            target = targets[0]
            return (int(target["x"]), int(target["y"]), target["name"])
        
        return None
    
    @staticmethod
    def navigate_toward_screen_target(target_x, screen_width, screen_center_x):
        """Return action to navigate toward a target on screen."""
        from agent.utils.action_decoder import ActionDecoder
        
        offset = target_x - screen_center_x
        abs_offset = abs(offset)
        
        if abs_offset < 40:
            # Target centered, move toward it
            return ActionDecoder.forward()
        elif offset > 40:
            # Target on right
            if abs_offset > 100:
                return ActionDecoder.right_turn()
            else:
                return ActionDecoder.forward_right_turn()
        else:
            # Target on left
            if abs_offset > 100:
                return ActionDecoder.left_turn()
            else:
                return ActionDecoder.forward_left_turn()
