import numpy as np
import logging
from typing import Dict, Optional
from agent.utils.action_decoder import ActionDecoder
from agent.core.perception import PerceptionManager
from agent.nav.sector_navigator import SectorNavigator

logger = logging.getLogger(__name__)


class BehaviorSelector:
    """Selects and executes behaviors based on game state."""
    
    def __init__(
        self,
        mapper=None,
        navigator=None,
        heading_controller=None,
        progress_tracker=None,
        combat_enabled=True,
        items_enabled=True,
    ):
        self.perception = PerceptionManager()
        self.sector_navigator = SectorNavigator()
        self.combat_enabled = combat_enabled
        self.items_enabled = items_enabled
    
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
    
    def decide_action(self, state_info, automap_buffer=None, angle=None, state=None):
        """
        Fast decision logic: simplified behavior selection.
        Priority: Navigation (sector-based pathfinding)
        
        Args:
            state_info: Parsed state information dict
            automap_buffer: Automap image buffer
            angle: Current agent angle
            state: Full ViZDoom state (used for sector navigator initialization)
        
        Returns:
            Action array
        """
        if state_info is None:
            return ActionDecoder.forward()
        
        pos_x = state_info.get('pos_x', 0)
        pos_y = state_info.get('pos_y', 0)

        # Navigation only: Sector-based pathfinding
        current_angle = state_info.get('angle', 0)
        sectors = state_info.get("sectors")
        return self.sector_navigator.decide_action(pos_x, pos_y, sectors, current_angle)
    
    def _fallback_exploration(self, pos_x: float, pos_y: float, angle: Optional[float] = None) -> np.ndarray:
        """
        Simple fallback exploration pattern when sector navigator not available.
        """
        # Simple alternating exploration pattern
        pattern_idx = (getattr(self, '_exploration_frame', 0) // 30) % 4
        frame_in_pattern = getattr(self, '_exploration_frame', 0) % 30
        self._exploration_frame = getattr(self, '_exploration_frame', 0) + 1
        
        if pattern_idx == 0:
            # Forward with occasional left turns
            if frame_in_pattern % 10 == 0:
                return ActionDecoder.forward_left_turn()
            return ActionDecoder.forward()
        elif pattern_idx == 1:
            # Forward with occasional right turns
            if frame_in_pattern % 10 == 0:
                return ActionDecoder.forward_right_turn()
            return ActionDecoder.forward()
        elif pattern_idx == 2:
            # Strafe left + forward
            return ActionDecoder.forward_strafe_left()
        else:
            # Strafe right + forward
            return ActionDecoder.forward_strafe_right()
    
    def get_navigator_status(self) -> Dict:
        """Get current sector navigation status."""
        return {'status': 'active'}

    def get_navigation_debug_frame(self, automap_buffer):
        """Return a debug overlay image for navigation, if available."""
        return None
    
    def _angle_to_radians(self, angle):
        """Convert angle to radians if necessary."""
        import math
        if angle is None:
            return 0.0
        if abs(angle) > (2 * math.pi + 0.1):
            return math.radians(angle)
        return angle
