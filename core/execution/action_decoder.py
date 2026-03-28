"""Provide utilities to construct action vectors for agent actions.
All static methods, no fields. vizdoom.cfg has available buttons. 
We assign indices in constants.py. Each method builds a zero array
of size ACTION_COUNT and sets a 1 at the relevant index."""
from config.constants import (
    ACTION_FORWARD, ACTION_BACKWARD, ACTION_TURN_LEFT, ACTION_TURN_RIGHT,
    ACTION_ATTACK, ACTION_USE, ACTION_COUNT
)


class ActionDecoder:

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
        """Move backward. NOTE: not used yet, but no harm in keeping."""
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