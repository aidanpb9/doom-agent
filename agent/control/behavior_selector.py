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

    def set_map_name(self, map_name: str) -> None:
        if map_name:
            self.sector_navigator.set_map_name(map_name)

    def set_wad_path(self, wad_path: str) -> None:
        if wad_path:
            self.sector_navigator.set_wad_path(wad_path)
    
    def reset_episode(self):
        """Reset all behavior states for new episode."""
        self.sector_navigator.reset_episode()
    
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
        screen = state_info.get("screen")

        if self.combat_enabled:
            enemy = self.perception.detect_enemies_from_labels(state_info.get("labels", []))
            if enemy is not None:
                ex, _, _ = enemy
                if screen is not None and hasattr(screen, "shape"):
                    width = screen.shape[1]
                    center_x = width / 2.0
                    dx = ex - center_x
                    if abs(dx) > width * 0.08:
                        return ActionDecoder.left_turn() if dx < 0 else ActionDecoder.right_turn()
                if not self.is_aiming_at_wall(screen):
                    return ActionDecoder.forward_attack()

        # Navigation only: Sector-based pathfinding
        current_angle = state_info.get('angle', 0)
        sectors = state_info.get("sectors")
        lines = state_info.get("lines")
        return self.sector_navigator.decide_action(pos_x, pos_y, sectors, current_angle, lines=lines)
    
    def get_navigation_debug_frame(self, automap_buffer):
        """Return a debug overlay image for navigation, if available."""
        return None
