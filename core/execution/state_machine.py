"""Manages what state the agent should be in, returns the agent's actions."""
from core.navigation.path_tracker import PathTracker
from core.execution.game_state import GameState
from config.constants import (HEALTH_THRESHOLD, ARMOR_THRESHOLD, AMMO_THRESHOLD,
    HEALTH_KEYWORDS, ARMOR_KEYWORDS, AMMO_KEYWORDS)
from enum import Enum


class State(Enum):
    RECOVER = 1
    COMBAT = 2
    TRAVERSE = 3
    SCAN = 4


class StateMachine:

    def __init__(self, path_tracker: PathTracker):
        self.current_state = State.TRAVERSE
        self.path_tracker = path_tracker
        self.combat_hold_ticks = 0 #keeps combat active after last enemy seen, avoid flickering
        self.scan_cooldown_timer = 0 #update() decrements this


    def update(self, gamestate: GameState) -> list[int]:
        """Updates game info, then switches to the correct state based on priority."""
        self.path_tracker.update(gamestate)

        if (gamestate.health < HEALTH_THRESHOLD and self.path_tracker.has_loot_node(HEALTH_KEYWORDS) or
            gamestate.armor < ARMOR_THRESHOLD and self.path_tracker.has_loot_node(ARMOR_KEYWORDS) or
            gamestate.ammo < AMMO_THRESHOLD and self.path_tracker.has_loot_node(AMMO_KEYWORDS)
        ):
            return self._recover
    
    def _traverse(self, gamestate: GameState) -> list[int]:
        """Calls path_tracker. Returns movement action"""
        #call path_tracker.get_next_move(x, y, angle)
        pass

    def _combat(self, gamestate: GameState) -> list[int]:
        """Aims, fires, and returns attack action."""
        pass
    

    def _recover(self, gamestate: GameState) -> list[int]:
        """Navigates to loot. Returns movement action"""
        #call path_tracker.get_next_move(x, y, angle)
        pass


    def _scan(self, gamestate: GameState) -> list[int]:
        """Spins 360 degrees. Returns turn action."""
        pass