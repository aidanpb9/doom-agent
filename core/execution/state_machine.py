"""Manages what state the agent should be in, returns the agent's actions."""
from core.navigation.path_tracker import PathTracker
from core.execution.game_state import GameState
from config.constants import (HEALTH_THRESHOLD, ARMOR_THRESHOLD, AMMO_THRESHOLD,
    HEALTH_KEYWORDS, ARMOR_KEYWORDS, AMMO_KEYWORDS, SCAN_FREQUENCY, SCAN_FREQUENCY_MAX, 
    SCAN_COOLDOWN, COMBAT_HOLD_TICKS, TICK)
from enum import Enum
import random


class StateMachine:

    def __init__(self, path_tracker: PathTracker):
        self.path_tracker = path_tracker
        self.combat_hold = 0 #keeps combat active after last enemy seen, avoid flickering
        self.scan_cooldown = 0 #update() decrements this


    def update(self, gamestate: GameState) -> list[int]:
        """Updates game info, then switches to the correct state based on priority."""
        self.combat_hold = max(0, self.combat_hold - TICK)
        self.scan_cooldown = max(0, self.scan_cooldown - TICK)
        self.path_tracker.update(gamestate)

        #RECOVER (highest priority)
        if (gamestate.health < HEALTH_THRESHOLD and self.path_tracker.has_loot_node(HEALTH_KEYWORDS) or
            gamestate.armor < ARMOR_THRESHOLD and self.path_tracker.has_loot_node(ARMOR_KEYWORDS) or
            gamestate.ammo < AMMO_THRESHOLD and self.path_tracker.has_loot_node(AMMO_KEYWORDS)
        ):
            return self._recover(gamestate)
        
        #COMBAT
        if self.combat_hold or (gamestate.enemies_visible and gamestate.ammo > 0):
            return self._combat(gamestate)

        #SCAN
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
        """Calls path_tracker. Returns movement action"""
        #call path_tracker.get_next_move(x, y, angle)
        pass

    def _combat(self, gamestate: GameState) -> list[int]:
        """Aims, fires, and returns attack action."""
        #set self.combat_hold
        pass
    

    def _recover(self, gamestate: GameState) -> list[int]:
        """Navigates to loot. Returns movement action"""
        #call path_tracker.get_next_move(x, y, angle)
        pass


    def _scan(self, gamestate: GameState) -> list[int]:
        """Spins 360 degrees. Returns turn action."""
        #set self.scan_cooldown
        pass