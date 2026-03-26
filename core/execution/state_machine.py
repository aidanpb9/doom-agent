"""Manage what state the agent should be in, returns the agent's actions."""
from core.navigation.graph import NodeType
from core.navigation.path_tracker import PathTracker
from core.execution.game_state import GameState
from core.execution.action_decoder import ActionDecoder
from config.constants import (HEALTH_THRESHOLD, ARMOR_THRESHOLD, AMMO_THRESHOLD,
    HEALTH_KEYWORDS, ARMOR_KEYWORDS, AMMO_KEYWORDS, SCAN_FREQUENCY, SCAN_FREQUENCY_MAX, 
    SCAN_COOLDOWN, COMBAT_HOLD_TICKS, TICK)
from enum import Enum
import random


class State(Enum):
    """Represent the different states."""
    RECOVER = 1
    COMBAT = 2
    TRAVERSE = 3
    SCAN = 4


class StateMachine:
    """"""
    def __init__(self, path_tracker: PathTracker):
        self.path_tracker = path_tracker
        self.last_state = State.TRAVERSE
        self.recover_type = None#so we now what type of loot to find when entering RECOVER
        self.combat_hold = 0 #keeps combat active after last enemy seen, avoid flickering
        self.scan_cooldown = 0 #update() decrements this
        self.scan_last_angle = 0 #for calculating how far we've turned since last tick
        self.scan_total_deg = 0 #number of degs since starting a scan

    def update(self, gamestate: GameState) -> list[int]:
        """Updates game info, then switches to the correct state based on priority."""
        #Updates
        self.combat_hold = max(0, self.combat_hold - TICK)
        self.scan_cooldown = max(0, self.scan_cooldown - TICK)
        self.path_tracker.update(gamestate)

        #RECOVER (highest priority)
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
        
        #COMBAT
        if self.combat_hold or (gamestate.enemies_visible and gamestate.ammo > 0):
            return self._combat(gamestate)

        #SCAN
        if self.last_state == State.SCAN:
            return self._scan(gamestate)
        
        if not SCAN_FREQUENCY:
            is_scan_chance = False
        else:
            scan_range = int(SCAN_FREQUENCY_MAX / SCAN_FREQUENCY)
            is_scan_chance = random.randint(1, scan_range) == random.randint(1, scan_range)
        if not self.scan_cooldown and (gamestate.is_dmg_taken_since_last_step or is_scan_chance):
            return self._scan(gamestate)

        #TRAVERSE
        return self._traverse(gamestate)
    
    def _traverse(self, gamestate: GameState) -> list[int]:
        """Navigates to EXIT node. Return movement action."""
        self.path_tracker.set_goal_by_type(gamestate, NodeType.EXIT)
        action = self.path_tracker.get_next_move(gamestate.pos_x, gamestate.pos_y, gamestate.angle)
        self.last_state = State.TRAVERSE
        return action

    def _combat(self, gamestate: GameState) -> list[int]:
        """Aiming and firing. Return attack action."""
        #set self.combat_hold
        self.last_state = State.COMBAT
        pass

    def _recover(self, gamestate: GameState) -> list[int]:
        """Navigates to closest LOOT node. Return movement action."""
        self.path_tracker.set_goal_by_type(gamestate, NodeType.LOOT, self.recover_type)
        action = self.path_tracker.get_next_move(gamestate.pos_x, gamestate.pos_y, gamestate.angle)
        self.last_state = State.RECOVER
        return action

    def _scan(self, gamestate: GameState) -> list[int]:
        """Spin right until 360 is done. Return turn action."""
        #reset cooldown every time we enter, so when we leave it decrements naturally
        self.scan_cooldown = SCAN_COOLDOWN 

        #update total turn degrees 
        if self.last_state == State.SCAN:
            deg = gamestate.angle - self.scan_last_angle
            if deg < 0:
                deg += 360 #this works since we do right turns only
            self.scan_total_deg += deg

        #Stop when 360 degrees accumulated.
        if self.scan_total_deg > 360:
            self.last_state = State.TRAVERSE
            self.scan_total_deg = 0
            self.scan_last_angle = 0
            return ActionDecoder.null_action()

        self.last_state = State.SCAN
        self.scan_last_angle = gamestate.angle
        return ActionDecoder.turn_right()

        
