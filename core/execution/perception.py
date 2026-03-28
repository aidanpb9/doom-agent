"""Parses raw VizDoom state into a useable GameState."""
from config.constants import ENEMY_KEYWORDS, LOOT_KEYWORDS
from core.execution.game_state import LootObject, EnemyObject, GameState
from typing import Any
import re


class Perception:

    def __init__(self):
        self.enemy_keywords = ENEMY_KEYWORDS
        self.loot_keywords = LOOT_KEYWORDS
        self.last_health = 100

    def parse(self, vizdoom_state: Any) -> GameState:
        """Take raw VizDoom state, extract all game variables/labels,
        run enemy/loot detection. Return a populated GameState each tick for StateMachine."""
        info = self._get_state_info(vizdoom_state)
        labels = info["labels"]

        return GameState(
            health=info["health"],
            armor=info["armor"],
            ammo=info["ammo"],
            enemies_visible=self._detect_enemies(labels),
            loots_visible=self._detect_loot(labels),
            pos_x=info["pos_x"],
            pos_y=info["pos_y"],
            angle=info["angle"],
            enemies_killed=info["enemies_killed"],
            is_dmg_taken_since_last_step=self._detect_damage(info["health"]),
            ##screen_buffer shape is (height, width), index 0=height, 1=width
            screen_width=vizdoom_state.screen_buffer.shape[1] if vizdoom_state.screen_buffer is not None else 0
        )

    @staticmethod
    def _normalize_name(value: str) -> str:
        """alpha numeric and lowercase."""
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _is_dead_name(name_lower: str) -> bool:
        return "dead" in name_lower or "gibbe" in name_lower

    def _is_enemy_name(self, name: str) -> bool:
        """Check if an object is an enemy. name must be normalized already."""
        if not name or self._is_dead_name(name):
            return False
        return name in self.enemy_keywords
    
    def _is_loot_name(self, name: str) -> bool:
        """Check if an object is loot. name must be normalized already."""
        if not name:
            return False
        return name in self.loot_keywords

    def _get_state_info(self, vizdoom_state: Any) -> dict:
        """Extract raw game variables from vizdoom state into dict."""
        game_vars = vizdoom_state.game_variables
        labels = getattr(vizdoom_state, "labels", []) or []
        if len(game_vars) >= 7:
            #game_variables order defined in vizdoom.cfg: health, armor, ammo, x, y, angle, kills
            return {
                "health": float(game_vars[0]),
                "armor": float(game_vars[1]),
                "ammo": float(game_vars[2]),
                "pos_x": float(game_vars[3]),
                "pos_y": float(game_vars[4]),
                "angle": float(game_vars[5]),
                "enemies_killed": int(game_vars[6]),
                "labels": labels,
            }
        else:
            return {"health": 100.0, "armor": 0.0, "ammo": 0.0, "pos_x": 0.0, 
                    "pos_y": 0.0, "angle": 0.0, "enemies_killed": 0, "labels": labels}

    def _detect_enemies(self, labels: list[Any]) -> list[EnemyObject]:
        """Return list of EnemyObjects from visible labels."""
        enemies = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "")
            if self._is_enemy_name(self._normalize_name(name)):
                #x and y are top left corner
                box_x = float(getattr(lbl, "x", 0))
                box_y = float(getattr(lbl, "y", 0))
                #w(idth) and h(eight) are dimensions
                box_w = float(getattr(lbl, "width", 0))
                box_h = float(getattr(lbl, "height", 0))

                enemies.append(EnemyObject(
                    name=self._normalize_name(name),
                    pos_x=float(getattr(lbl, "object_position_x", 0)),
                    pos_y=float(getattr(lbl, "object_position_y", 0)),
                    screen_x=box_x + box_w * 0.5,
                    screen_y=box_y + box_h * 0.5
                ))
        return enemies

    def _detect_loot(self, labels: list[Any]) -> list[LootObject]:
        """Return list of LootObjects from visible labels."""
        loot = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "")
            if self._is_loot_name(self._normalize_name(name)):
                loot.append(LootObject(
                    name=self._normalize_name(name),
                    pos_x=float(getattr(lbl, "object_position_x", 0)),
                    pos_y=float(getattr(lbl, "object_position_y", 0)),
                ))
        return loot

    def _detect_damage(self, health: float) -> bool:
        """Return True if health decreased since last tick. Update last_health."""
        is_dmg_taken = health < self.last_health
        self.last_health = health
        return is_dmg_taken