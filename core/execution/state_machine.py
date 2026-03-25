"""Manages what state the agent should be in, returns the agent's actions."""
from core.navigation.path_tracker import PathTracker
from core.execution.game_state import GameState
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


    def update(self, game_state: GameState):
        """Switches to the correct state based on priority."""
        pass
    
    
    def _traverse(self, gamestate: GameState) -> list[int]:
        """Calls path_tracker. Returns movement action"""
        pass


    def _combat(self, gamestate: GameState) -> list[int]:
        """Aims, fires, and returns attack action."""
        pass
    

    def _recover(self, gamestate: GameState) -> list[int]:
        """Navigates to loot. Returns movement action"""
        pass


    def _scan(self, gamestate: GameState) -> list[int]:
        """Spins 360 degrees. Returns turn action."""
        pass