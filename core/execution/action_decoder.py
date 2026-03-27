"""Provide utilities to construct action vectors for agent actions 
and decode them. All static methods, no fields."""
from config.constants import (
    ACTION_FORWARD, ACTION_BACKWARD, ACTION_TURN_LEFT, ACTION_TURN_RIGHT,
    ACTION_ATTACK, ACTION_USE, ACTION_COUNT, ACTION_NAMES
)


class ActionDecoder:
    """Decode and encode Doom actions.

    Explanation: vizdoom.cfg has available buttons. We assign those in constants.py.
    Then import those constants here. 
    In each function, we make an array of 0's with size=8.
    Then we set a 1 in an array position that corresponds to the action and return it.
    """
    
    @staticmethod
    def null_action() -> list[int]:
        """Return a null action (stand still)."""
        return [0] * ACTION_COUNT
    
    @staticmethod
    def forward() -> list[int]:
        """Move forward."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        return action

    @staticmethod
    def backward() -> list[int]:
        """Move backward."""
        action = [0] * ACTION_COUNT
        action[ACTION_BACKWARD] = 1
        return action
    
    @staticmethod
    def turn_left() -> list[int]:
        """Turn left."""
        action = [0] * ACTION_COUNT
        action[ACTION_TURN_LEFT] = 1
        return action
    
    @staticmethod
    def turn_right() -> list[int]:
        """Turn right."""
        action = [0] * ACTION_COUNT
        action[ACTION_TURN_RIGHT] = 1
        return action
    
    @staticmethod
    def attack() -> list[int]:
        """Pure attack."""
        action = [0] * ACTION_COUNT
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def use() -> list[int]:
        """Use/activate."""
        action = [0] * ACTION_COUNT
        action[ACTION_USE] = 1
        return action
    
    @staticmethod
    def combine(*actions) -> list[int]:
        """Combines multiple actions together."""
        result = [0] * ACTION_COUNT
        for action in actions:
             for index, value in enumerate(action):
                if value:
                    result[index] = value
        return result