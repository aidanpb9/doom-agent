"""
Combat behavior system for the Doom agent.
"""

from agent.utils.action_decoder import ActionDecoder


class CombatBehavior:
    """Manages combat decisions and aiming."""
    
    def __init__(self):
        self.frames_since_enemy = 0
    
    def decide_combat_action(self, enemy_detection, ammo, screen_width):
        """Decide combat action based on enemy detection and resources."""
        if enemy_detection is None:
            self.frames_since_enemy += 1
            return None
        
        self.frames_since_enemy = 0
        
        if len(enemy_detection) == 3:
            enemy_x, enemy_y, confidence = enemy_detection
        else:
            enemy_x, enemy_y = enemy_detection
            confidence = 0.5
        
        # Don't shoot if confidence is too low or target is too small
        if confidence < 0.1:
            return None
        
        screen_center_x = screen_width // 2
        offset = enemy_x - screen_center_x
        abs_offset = abs(offset)
        
        # PROVEN AIMING - DO NOT CHANGE
        if ammo > 5:  # Need at least 5 ammo to attack
            # CENTERED: Pure attack
            if abs_offset < 25:
                return ActionDecoder.attack()
            # RIGHT: Turn right and attack
            elif offset > 25:
                if abs_offset > 80:
                    return ActionDecoder.right_turn_attack()  # Strong turn
                else:
                    return ActionDecoder.forward_right_turn_attack()  # Forward + turn right + attack
            # LEFT: Turn left and attack
            else:
                if abs_offset > 80:
                    return ActionDecoder.left_turn_attack()  # Strong turn
                else:
                    return ActionDecoder.forward_left_turn_attack()  # Forward + turn left + attack
        else:
            # Too low ammo - just approach without attacking
            if offset > 25:
                return ActionDecoder.forward_right_turn()
            elif offset < -25:
                return ActionDecoder.forward_left_turn()
            else:
                return ActionDecoder.forward()
    
    def decide_survival_action(self, health):
        """Decide action for survival when health is critical."""
        from agent.utils.action_decoder import ActionDecoder
        
        if health < 30:
            # Strafe back and forth to avoid fire
            if int(health) % 2 == 0:
                return ActionDecoder.strafe_left()
            else:
                return ActionDecoder.strafe_right()
        
        return None
