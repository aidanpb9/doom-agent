import numpy as np
import logging
from agent.utils.action_decoder import ActionDecoder
from agent.core.perception import PerceptionManager
from agent.nav.sector_navigator import SectorNavigator

logger = logging.getLogger(__name__)


class BehaviorSelector:
    """Selects and executes behaviors based on game state."""
    
    def __init__(
        self,
        combat_enabled=True,
    ):
        self.perception = PerceptionManager()
        self.sector_navigator = SectorNavigator()
        self.combat_enabled = combat_enabled
        self.combat_ticks = 0
        self.combat_cooldown = 0
        self.last_enemy_dx = 0.0
        self.last_enemy_conf = 0.0
        self.combat_burst = 8
        self.combat_cooldown_duration = 20
        self.combat_rearm_duration = 8
        self.combat_strafe_dir = 1
        self.combat_strafe_ticks = 0
        self.combat_strafe_switch = 8
        self.last_health = None
        self.combat_rearm = 0
        self.combat_seen_ticks = 0
        self.combat_active_ticks = 0
        self.combat_max_active = 120

    def set_map_name(self, map_name: str) -> None:
        if map_name:
            self.sector_navigator.set_map_name(map_name)

    def set_wad_path(self, wad_path: str) -> None:
        if wad_path:
            self.sector_navigator.set_wad_path(wad_path)
    
    def reset_episode(self):
        """Reset all behavior states for new episode."""
        self.sector_navigator.reset_episode()
        self.combat_ticks = 0
        self.combat_cooldown = 0
        self.last_enemy_dx = 0.0
        self.last_enemy_conf = 0.0
        self.combat_strafe_dir = 1
        self.combat_strafe_ticks = 0
        self.last_health = None
        self.combat_rearm = 0
        self.combat_seen_ticks = 0
        self.combat_active_ticks = 0
    
    def is_aiming_at_wall(self, screen):
        """Check if screen center shows a wall (uniform, bright color)."""
        if screen is None or len(screen) == 0:
            return False
        
        # Convert to grayscale
        if len(screen.shape) == 3:
            gray = np.mean(screen, axis=2)
        else:
            gray = screen
        
        # Check center 30% of screen for wall-like characteristics
        h, w = gray.shape
        center = gray[h//3:2*h//3, w//3:2*w//3]
        
        # Walls are bright and uniform
        brightness = np.mean(center)
        variance = np.var(center)
        
        # If it looks like a wall (bright + uniform), don't shoot
        looks_like_wall = brightness > 140 and variance < 1500
        
        return looks_like_wall
    
    def decide_action(self, state_info, angle=None):
        """
        Fast decision logic: simplified behavior selection.
        Priority: Navigation (sector-based pathfinding)
        
        Args:
            state_info: Parsed state information dict
            angle: Current agent angle
        
        Returns:
            Action array
        """
        if state_info is None:
            return ActionDecoder.forward()
        
        pos_x = state_info.get('pos_x', 0)
        pos_y = state_info.get('pos_y', 0)
        ammo = state_info.get('ammo', 0)
        health = state_info.get('health', 0)
        screen = state_info.get("screen")
        took_damage = False
        if self.last_health is not None and health < self.last_health - 0.1:
            took_damage = True
        self.last_health = health

        nav_action = None

        if self.combat_enabled:
            enemy = self.perception.detect_enemies_from_labels(state_info.get("labels", []))
            if enemy is not None:
                ex, _, conf = enemy
                if screen is not None and hasattr(screen, "shape"):
                    width = screen.shape[1]
                    center_x = width / 2.0
                    dx = ex - center_x
                    self.last_enemy_dx = dx
                else:
                    self.last_enemy_dx = 0.0
                self.last_enemy_conf = conf

            if self.combat_rearm > 0:
                self.combat_rearm -= 1
            if enemy is not None:
                self.combat_seen_ticks = 10
            elif self.combat_seen_ticks > 0:
                self.combat_seen_ticks -= 1
            if (enemy is not None or took_damage) and self.combat_cooldown == 0 and self.combat_rearm == 0:
                if ammo > 0 or took_damage:
                    duration = self.combat_cooldown_duration if ammo > 0 else max(6, self.combat_cooldown_duration // 3)
                    self.combat_ticks = max(self.combat_ticks, min(self.combat_burst, duration))
                    self.combat_cooldown = max(self.combat_cooldown, duration)

            if self.combat_ticks > 0:
                self.combat_ticks -= 1
            if self.combat_cooldown > 0:
                self.combat_cooldown -= 1
                if self.combat_cooldown == 0:
                    self.combat_rearm = self.combat_rearm_duration

            combat_active = self.combat_cooldown > 0
            nav = self.sector_navigator
            self.sector_navigator.set_combat_active(combat_active)

            # Navigation: Sector-based pathfinding
            current_angle = state_info.get('angle', 0)
            sectors = state_info.get("sectors")
            lines = state_info.get("lines")
            nav_action = self.sector_navigator.decide_action(pos_x, pos_y, sectors, current_angle, lines=lines)
            if nav.exit_combat_override:
                combat_active = False
                self.combat_cooldown = 0
                self.combat_ticks = 0
                self.combat_active_ticks = 0
            if combat_active:
                self.combat_active_ticks += 1
                if ammo <= 0:
                    self.combat_cooldown = 0
                    self.combat_ticks = 0
                    self.combat_active_ticks = 0
                    return nav_action
                if self.combat_active_ticks >= self.combat_max_active:
                    self.combat_cooldown = 0
                    self.combat_ticks = 0
                    self.combat_active_ticks = 0
                    return nav_action
                if ammo <= 0 and enemy is None and self.combat_seen_ticks == 0 and not took_damage:
                    self.combat_cooldown = 0
                    self.combat_ticks = 0
                    return nav_action
                if enemy is None and self.combat_seen_ticks == 0 and not took_damage:
                    self.combat_cooldown = 0
                    self.combat_ticks = 0
                    return nav_action
                if self.combat_strafe_ticks <= 0:
                    self.combat_strafe_dir *= -1
                    self.combat_strafe_ticks = self.combat_strafe_switch
                self.combat_strafe_ticks -= 1

                turn_action = None
                dx = 0.0
                width = None
                if enemy is not None and screen is not None and hasattr(screen, "shape"):
                    width = screen.shape[1]
                    dx = self.last_enemy_dx
                    if abs(dx) > width * 0.08:
                        turn_action = ActionDecoder.left_turn() if dx < 0 else ActionDecoder.right_turn()
                action = turn_action
                if action is None:
                    action = (
                        ActionDecoder.strafe_right()
                        if self.combat_strafe_dir > 0
                        else ActionDecoder.strafe_left()
                    )
                shoot_ok = False
                if enemy is not None:
                    if width is not None:
                        shoot_ok = abs(dx) <= width * 0.12 or self.last_enemy_conf >= 0.5
                    else:
                        shoot_ok = self.last_enemy_conf >= 0.5
                if ammo > 0 and shoot_ok:
                    if len(action) >= 6:
                        action[5] = 1
                return action

            self.combat_active_ticks = 0
            if isinstance(nav_action, list) and len(nav_action) >= 7 and nav_action[6] == 1:
                return nav_action

            return nav_action

        # Navigation fallback when combat disabled.
        self.sector_navigator.set_combat_active(False)
        current_angle = state_info.get('angle', 0)
        sectors = state_info.get("sectors")
        lines = state_info.get("lines")
        nav_action = self.sector_navigator.decide_action(pos_x, pos_y, sectors, current_angle, lines=lines)

        if isinstance(nav_action, list) and len(nav_action) >= 7 and nav_action[6] == 1:
            return nav_action

        return nav_action
    
    def get_navigation_debug_frame(self, automap_buffer):
        """Return a debug overlay image for navigation, if available."""
        return None
