"""Dataclass that holds game and agent information, including loot objects."""
from dataclasses import dataclass


@dataclass
class LootObject:
    """Used for loot objects seen by agent."""
    name: str
    pos_x: float
    pos_y: float


@dataclass
class GameState:
    health: int
    armor: int
    ammo: int
    enemies_visible: list[str]
    loots_visible: list[LootObject]
    pos_x: float
    pos_y: float
    angle: float
    enemies_killed: int
    is_dmg_taken_since_last_step: bool


