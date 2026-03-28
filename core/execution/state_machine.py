"""Priority/hierarchal state machine. Each tick, update() evaluates
conditions highest to lowest priority and returns an action."""
from core.navigation.graph import NodeType
from core.navigation.path_tracker import PathTracker
from core.execution.game_state import GameState, EnemyObject
from core.execution.action_decoder import ActionDecoder
from core.utils import has_clear_world_line
from config.constants import (HEALTH_THRESHOLD, ARMOR_THRESHOLD, AMMO_THRESHOLD,
    HEALTH_KEYWORDS, ARMOR_KEYWORDS, AMMO_KEYWORDS, SCAN_INTERVAL, COMBAT_HOLD_TICKS, 
    COMBAT_AIM_THRESHOLD, VERTICAL_IGNORE_THRESHOLD, TICK, STUCK_RECOVERY_TICKS)
from enum import Enum
import random


class State(Enum):
    """Represent the different states."""
    STUCK = 1
    COMBAT = 2
    RECOVER = 3
    SCAN = 4
    TRAVERSE = 5


class StateMachine:
    """Manage what state the agent should be in, returns the agent's actions."""
    def __init__(self, path_tracker: PathTracker, blocking_segments: list[tuple[float, float, float, float]]):
        self.path_tracker = path_tracker
        self.last_state = State.TRAVERSE
        self.recover_type = None #so we know what type of loot to find when entering RECOVER
        self.combat_hold = 0 #keeps combat active after last enemy seen, avoid flickering
        self.blocking_segments = blocking_segments
        self.scan_cooldown = 0 #update() decrements this
        self.scan_last_angle = 0 #for calculating how far we've turned since last tick
        self.scan_total_deg = 0 #number of degs since starting a scan
        self.stuck_recovery_ticks = 0 #counts down from STUCK_RECOVERY_TICKS, STUCK state active while > 0
        self.stuck_direction = None #need to maintain one direction per attempt

    def update(self, gamestate: GameState) -> list[int]:
        """Updates game info, then switches to the correct state based on priority."""
        #Updates
        self.combat_hold = max(0, self.combat_hold - TICK)
        self.scan_cooldown = max(0, self.scan_cooldown - TICK)
        self.path_tracker.update(gamestate)

        #STUCK
        if self.path_tracker.is_stuck:
            self.path_tracker.is_stuck = False
            self.stuck_recovery_ticks = STUCK_RECOVERY_TICKS
            self.stuck_direction = random.choice([ActionDecoder.turn_right, ActionDecoder.turn_left])
        if self.stuck_recovery_ticks > 0:
            return self._stuck()

        #COMBAT
        if self.combat_hold or (gamestate.enemies_visible and gamestate.ammo > 0):
            return self._combat(gamestate)

        #RECOVER
        if (gamestate.health < HEALTH_THRESHOLD and 
            self.path_tracker.has_loot_node(HEALTH_KEYWORDS)
        ):
            self.recover_type = HEALTH_KEYWORDS
            return self._recover(gamestate)

        if (gamestate.armor < ARMOR_THRESHOLD and 
            self.path_tracker.has_loot_node(ARMOR_KEYWORDS)
        ):
            self.recover_type = ARMOR_KEYWORDS
            return self._recover(gamestate)

        if (gamestate.ammo < AMMO_THRESHOLD and 
            self.path_tracker.has_loot_node(AMMO_KEYWORDS)
        ):
            self.recover_type = AMMO_KEYWORDS
            return self._recover(gamestate)

        #SCAN
        if self.last_state == State.SCAN:
            return self._scan(gamestate)
        
        is_scan_chance = random.randint(1, SCAN_INTERVAL) == 1
        if not self.scan_cooldown and (gamestate.is_dmg_taken_since_last_step or is_scan_chance):
            self.scan_cooldown = SCAN_INTERVAL
            return self._scan(gamestate)

        #TRAVERSE
        return self._traverse(gamestate)
    
    def _stuck(self) -> list[int]:
        """Choose left or right turn direction + forward for duration of stuck.
        Main purpose is to dislodge from obstacles like barrels or candles."""
        self.stuck_recovery_ticks -= TICK
        self.last_state = State.STUCK
        return ActionDecoder.combine(self.stuck_direction(), ActionDecoder.forward())

    def _combat(self, gamestate: GameState) -> list[int]:
        """Aiming and firing. Return attack, turn, or null action."""
        enemy, offset = self._get_best_enemy(gamestate)
        if not enemy: #offset can be 0 (perfectly aligned), so check enemy only
            #keep moving without updating state to avoid unneeded state transitions
            return self.path_tracker.get_next_move(gamestate.pos_x, gamestate.pos_y, gamestate.angle)
        
        self.combat_hold = COMBAT_HOLD_TICKS #only hold if valid target found
        self.last_state = State.COMBAT

        #shoot at enemy or make adjustments if not accurate enough yet
        if abs(offset) < COMBAT_AIM_THRESHOLD:
            return ActionDecoder.attack()
        if offset > 0: #enemy right of center
            return ActionDecoder.turn_right()
        if offset < 0: #enemy left of center
            return ActionDecoder.turn_left()

    def _recover(self, gamestate: GameState) -> list[int]:
        """Navigates to closest LOOT node. Return movement action."""
        self.path_tracker.set_goal_by_type(gamestate, NodeType.LOOT, self.recover_type)
        action = self.path_tracker.get_next_move(gamestate.pos_x, gamestate.pos_y, gamestate.angle)
        self.last_state = State.RECOVER
        return action

    def _scan(self, gamestate: GameState) -> list[int]:
        """Spin right until 360 is done. Return turn action."""
        #reset cooldown every time we enter, so when we leave it decrements naturally
        self.scan_cooldown = SCAN_INTERVAL

        #update total turn degrees if came from scan
        if self.last_state == State.SCAN:
            deg = self.scan_last_angle - gamestate.angle #degrees are clockwise in this game
            if deg < 0:
                deg += 360 #this works since we do right turns only
            self.scan_total_deg += deg
        else: #need to reset progress since we're entering scan for the first time
            self.scan_total_deg = 0

        #stop when 360 degrees accumulated.
        if self.scan_total_deg > 360:
            self.last_state = State.TRAVERSE
            self.scan_total_deg = 0
            self.scan_last_angle = 0
            return ActionDecoder.null_action()

        #continue scan
        self.last_state = State.SCAN
        self.scan_last_angle = gamestate.angle
        return ActionDecoder.turn_right()
    
    def _traverse(self, gamestate: GameState) -> list[int]:
        """Navigates to EXIT node. Return movement action."""
        self.path_tracker.set_goal_by_type(gamestate, NodeType.EXIT)
        action = self.path_tracker.get_next_move(gamestate.pos_x, gamestate.pos_y, gamestate.angle)
        self.last_state = State.TRAVERSE
        return action

    def _get_best_enemy(self, gamestate: GameState) -> tuple[EnemyObject | None, float]:
        """Find the most centered visible enemy with a clear line of sight.
        A returned enemy is not blocked by a wall."""
        best = None
        best_offset = float('inf')
        best_raw_offset = 0.0

        for enemy in gamestate.enemies_visible:
            if enemy.pos_x is None or enemy.pos_y is None:
                continue
            if not has_clear_world_line(gamestate.pos_x, gamestate.pos_y, enemy.pos_x, enemy.pos_y, self.blocking_segments):
                continue
            screen_y_center = (enemy.screen_y - gamestate.screen_height * 0.5) / gamestate.screen_height
            if abs(screen_y_center) > VERTICAL_IGNORE_THRESHOLD:
                continue
            
            #normalize to -0.5 to 0.5, negative=left of center, positive=right of center
            offset_x = (enemy.screen_x - gamestate.screen_width * 0.5) / gamestate.screen_width
            if abs(offset_x) < best_offset:
                best = enemy
                best_offset = abs(offset_x)
                best_raw_offset = offset_x
        return best, best_raw_offset