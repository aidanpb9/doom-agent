"""Dataclass that holds game and agent information, including loot objects."""
from dataclasses import dataclass


@dataclass
class LootObject:
    """Used for loot objects seen by agent."""
    name: str
    pos_x: float
    pos_y: float


@dataclass
class EnemyObject:
    """Used for enemy name and position."""
    name: str
    pos_x: float
    pos_y: float
    #center of enemy's bounding box on screen, left edge + half of box width
    screen_x: float 


@dataclass
class GameState:
    health: int
    armor: int
    ammo: int
    enemies_visible: list[EnemyObject]
    loots_visible: list[LootObject]
    pos_x: float
    pos_y: float
    angle: float
    enemies_killed: int
    is_dmg_taken_since_last_step: bool
    screen_width: float #don't need height since only do horizontal movements


