import numpy as np
import logging
from agent.utils.action_decoder import ActionDecoder
from agent.perception.perception import PerceptionManager
from agent.navigation.sector_navigator import SectorNavigator
from config.defaults import ACTION_ATTACK, ACTION_USE

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
        self.barrel_avoid_ticks = 0
        self.barrel_avoid_dir = 1
        self.barrel_avoid_cooldown = 0
        self.proactive_barrel_cooldown = 0

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
        self.barrel_avoid_ticks = 0
        self.barrel_avoid_dir = 1
        self.barrel_avoid_cooldown = 0
        self.proactive_barrel_cooldown = 0
    
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
        pos_z = state_info.get('pos_z', 0.0)
        ammo = state_info.get('ammo', 0)
        health = state_info.get('health', 0)
        screen = state_info.get("screen")
        took_damage = False
        if self.last_health is not None and health < self.last_health - 0.1:
            took_damage = True
        self.last_health = health

        nav_action = None

        if self.combat_enabled:
            if self.barrel_avoid_cooldown > 0:
                self.barrel_avoid_cooldown -= 1
            if self.proactive_barrel_cooldown > 0:
                self.proactive_barrel_cooldown -= 1
            screen_h = screen.shape[0] if screen is not None and hasattr(screen, "shape") else None
            screen_shape = screen.shape if screen is not None and hasattr(screen, "shape") else None
            enemy = self.perception.detect_enemies_from_labels(
                state_info.get("labels", []),
                pos_z=pos_z,
                screen_height=screen_h,
            )
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
            nav_action = self.sector_navigator.decide_action(
                pos_x,
                pos_y,
                sectors,
                current_angle,
                lines=lines,
                labels=state_info.get("labels", []),
                screen_shape=screen_shape,
            )
            labels = state_info.get("labels", [])
            blocking_barrel = self.perception.detect_blocking_barrel(labels, screen_shape=screen_shape, require_center=True)
            # Proactive barrel avoidance: if collision is likely, veer now.
            if blocking_barrel is not None and screen_shape is not None and len(screen_shape) >= 2:
                cx, cy, area, _ = blocking_barrel
                screen_w = float(screen_shape[1])
                screen_h = float(screen_shape[0])
                nav_stalling_now = (
                    getattr(nav, "stuck_counter", 0) > 8
                    and getattr(nav, "no_progress", 0) > 6
                )
                nav_slowing = getattr(nav, "no_progress", 0) > 2
                imminent_collision = (
                    area > 700.0
                    and abs(cx - (screen_w * 0.5)) <= screen_w * 0.08
                    and cy >= screen_h * 0.62
                )
                if imminent_collision and nav_slowing and not nav_stalling_now and self.proactive_barrel_cooldown == 0:
                    avoid_right = cx < (screen_w * 0.5)
                    # For near-center barrels, bias by nav steering direction so we
                    # don't dodge into the wall side.
                    try:
                        node_id = nav._node_id_for_point((pos_x, pos_y))
                        right_clear = nav._side_clearance_score((pos_x, pos_y), current_angle, node_id, 1)
                        left_clear = nav._side_clearance_score((pos_x, pos_y), current_angle, node_id, -1)
                        if right_clear > left_clear + 2.0:
                            avoid_right = True
                        elif left_clear > right_clear + 2.0:
                            avoid_right = False
                    except Exception:
                        pass
                    logger.info(
                        "[NAV] Imminent barrel collision: veer dir=%s area=%.1f cx=%.1f no_prog=%s",
                        "right" if avoid_right else "left",
                        area,
                        cx,
                        getattr(nav, "no_progress", 0),
                    )
                    self.proactive_barrel_cooldown = 18
                    if avoid_right:
                        return ActionDecoder.forward_strafe_right()
                    return ActionDecoder.forward_strafe_left()
            if self.barrel_avoid_ticks > 0:
                # Stop recovery early if progress resumed and barrel is no longer blocking.
                if (
                    getattr(nav, "stuck_counter", 0) < 6
                    and getattr(nav, "no_progress", 0) < 4
                    and blocking_barrel is None
                ):
                    self.barrel_avoid_ticks = 0
                    self.barrel_avoid_cooldown = 24
                else:
                    self.barrel_avoid_ticks -= 1
                    if self.barrel_avoid_ticks == 0:
                        self.barrel_avoid_cooldown = 24
                    # Pseudo "back off": turn in place first, then veer/strafe around.
                    if self.barrel_avoid_ticks > 8:
                        if self.barrel_avoid_dir > 0:
                            return ActionDecoder.backward_right_turn()
                        return ActionDecoder.backward_left_turn()
                    if self.barrel_avoid_ticks > 4:
                        if self.barrel_avoid_dir > 0:
                            return ActionDecoder.forward_strafe_right()
                        return ActionDecoder.forward_strafe_left()
                    if self.barrel_avoid_dir > 0:
                        return ActionDecoder.forward_right_turn()
                    return ActionDecoder.forward_left_turn()
            nav_stalling = (
                getattr(nav, "stuck_counter", 0) > 10
                and getattr(nav, "no_progress", 0) > 8
            )
            if blocking_barrel is None and nav_stalling:
                blocking_barrel = self.perception.detect_blocking_barrel(
                    labels,
                    screen_shape=screen_shape,
                    require_center=False,
                )
            if (
                blocking_barrel is not None
                and nav_stalling
                and self.barrel_avoid_cooldown == 0
            ):
                cx, _, _, _ = blocking_barrel
                if screen_shape is not None and len(screen_shape) >= 2:
                    center_x = float(screen_shape[1]) * 0.5
                    self.barrel_avoid_dir = 1 if cx < center_x else -1
                else:
                    self.barrel_avoid_dir = -self.barrel_avoid_dir
                self.barrel_avoid_ticks = 12
                logger.info(
                    "[NAV] Barrel block detected: recover dir=%s stuck=%s no_prog=%s",
                    "right" if self.barrel_avoid_dir > 0 else "left",
                    getattr(nav, "stuck_counter", 0),
                    getattr(nav, "no_progress", 0),
                )
                if self.barrel_avoid_dir > 0:
                    return ActionDecoder.backward_right_turn()
                return ActionDecoder.backward_left_turn()
            elif nav_stalling and self.barrel_avoid_cooldown == 0 and self.barrel_avoid_ticks == 0 and (self.sector_navigator.step % 35 == 0):
                logger.info(
                    "[NAV] Barrel recovery not triggered: no barrel label while stalled (stuck=%s no_prog=%s)",
                    getattr(nav, "stuck_counter", 0),
                    getattr(nav, "no_progress", 0),
                )
            if nav.exit_combat_override:
                force_exit = (
                    isinstance(nav_action, list)
                    and len(nav_action) > ACTION_USE
                    and nav_action[ACTION_USE] == 1
                )
                if force_exit or (enemy is None and not took_damage):
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
                    if len(action) > ACTION_ATTACK:
                        action[ACTION_ATTACK] = 1
                return action

            self.combat_active_ticks = 0
            if isinstance(nav_action, list) and len(nav_action) > ACTION_USE and nav_action[ACTION_USE] == 1:
                return nav_action

            return nav_action

        # Navigation fallback when combat disabled.
        self.sector_navigator.set_combat_active(False)
        if self.barrel_avoid_cooldown > 0:
            self.barrel_avoid_cooldown -= 1
        if self.proactive_barrel_cooldown > 0:
            self.proactive_barrel_cooldown -= 1
        current_angle = state_info.get('angle', 0)
        sectors = state_info.get("sectors")
        lines = state_info.get("lines")
        screen_shape = screen.shape if screen is not None and hasattr(screen, "shape") else None
        nav_action = self.sector_navigator.decide_action(
            pos_x,
            pos_y,
            sectors,
            current_angle,
            lines=lines,
            labels=state_info.get("labels", []),
            screen_shape=screen_shape,
        )
        nav = self.sector_navigator
        labels = state_info.get("labels", [])
        blocking_barrel = self.perception.detect_blocking_barrel(labels, screen_shape=screen_shape, require_center=True)
        if blocking_barrel is not None and screen_shape is not None and len(screen_shape) >= 2:
            cx, cy, area, _ = blocking_barrel
            screen_w = float(screen_shape[1])
            screen_h = float(screen_shape[0])
            nav_stalling_now = (
                getattr(nav, "stuck_counter", 0) > 8
                and getattr(nav, "no_progress", 0) > 6
            )
            nav_slowing = getattr(nav, "no_progress", 0) > 2
            imminent_collision = (
                area > 700.0
                and abs(cx - (screen_w * 0.5)) <= screen_w * 0.08
                and cy >= screen_h * 0.62
            )
            if imminent_collision and nav_slowing and not nav_stalling_now and self.proactive_barrel_cooldown == 0:
                avoid_right = cx < (screen_w * 0.5)
                try:
                    node_id = nav._node_id_for_point((pos_x, pos_y))
                    right_clear = nav._side_clearance_score((pos_x, pos_y), current_angle, node_id, 1)
                    left_clear = nav._side_clearance_score((pos_x, pos_y), current_angle, node_id, -1)
                    if right_clear > left_clear + 2.0:
                        avoid_right = True
                    elif left_clear > right_clear + 2.0:
                        avoid_right = False
                except Exception:
                    pass
                logger.info(
                    "[NAV] Imminent barrel collision: veer dir=%s area=%.1f cx=%.1f no_prog=%s",
                    "right" if avoid_right else "left",
                    area,
                    cx,
                    getattr(nav, "no_progress", 0),
                )
                self.proactive_barrel_cooldown = 18
                if avoid_right:
                    return ActionDecoder.forward_strafe_right()
                return ActionDecoder.forward_strafe_left()
        if self.barrel_avoid_ticks > 0:
            if (
                getattr(nav, "stuck_counter", 0) < 6
                and getattr(nav, "no_progress", 0) < 4
                and blocking_barrel is None
            ):
                self.barrel_avoid_ticks = 0
                self.barrel_avoid_cooldown = 24
            else:
                self.barrel_avoid_ticks -= 1
                if self.barrel_avoid_ticks == 0:
                    self.barrel_avoid_cooldown = 24
                if self.barrel_avoid_ticks > 8:
                    if self.barrel_avoid_dir > 0:
                        return ActionDecoder.backward_right_turn()
                    return ActionDecoder.backward_left_turn()
                if self.barrel_avoid_ticks > 4:
                    if self.barrel_avoid_dir > 0:
                        return ActionDecoder.forward_strafe_right()
                    return ActionDecoder.forward_strafe_left()
                if self.barrel_avoid_dir > 0:
                    return ActionDecoder.forward_right_turn()
                return ActionDecoder.forward_left_turn()
        nav_stalling = (
            getattr(nav, "stuck_counter", 0) > 10
            and getattr(nav, "no_progress", 0) > 8
        )
        if blocking_barrel is None and nav_stalling:
            blocking_barrel = self.perception.detect_blocking_barrel(
                labels,
                screen_shape=screen_shape,
                require_center=False,
            )
        if (
            blocking_barrel is not None
            and nav_stalling
            and self.barrel_avoid_cooldown == 0
        ):
            cx, _, _, _ = blocking_barrel
            if screen_shape is not None and len(screen_shape) >= 2:
                center_x = float(screen_shape[1]) * 0.5
                self.barrel_avoid_dir = 1 if cx < center_x else -1
            else:
                self.barrel_avoid_dir = -self.barrel_avoid_dir
            self.barrel_avoid_ticks = 12
            logger.info(
                "[NAV] Barrel block detected: recover dir=%s stuck=%s no_prog=%s",
                "right" if self.barrel_avoid_dir > 0 else "left",
                getattr(nav, "stuck_counter", 0),
                getattr(nav, "no_progress", 0),
            )
            if self.barrel_avoid_dir > 0:
                return ActionDecoder.backward_right_turn()
            return ActionDecoder.backward_left_turn()
        elif nav_stalling and self.barrel_avoid_cooldown == 0 and self.barrel_avoid_ticks == 0 and (self.sector_navigator.step % 35 == 0):
            logger.info(
                "[NAV] Barrel recovery not triggered: no barrel label while stalled (stuck=%s no_prog=%s)",
                getattr(nav, "stuck_counter", 0),
                getattr(nav, "no_progress", 0),
            )

        if isinstance(nav_action, list) and len(nav_action) > ACTION_USE and nav_action[ACTION_USE] == 1:
            return nav_action

        return nav_action
    
    def get_navigation_debug_frame(self, automap_buffer):
        """Return a debug overlay image for navigation, if available."""
        nav = self.sector_navigator
        if nav is None:
            return None
        return nav.render_debug_overlay(automap_buffer)
