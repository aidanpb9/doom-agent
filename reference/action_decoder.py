"""
Action encoder/decoder for Doom agent actions.
Provides utilities to construct action vectors and decode them.
"""
#Reference
@staticmethod
    def _buttons_to_vector(buttons: Iterable[str]) -> List[int]:
        action = [0] * len(BUTTON_NAMES)
        for name in buttons:
            idx = BUTTON_INDEX.get(name)
            if idx is not None:
                action[idx] = 1
        return action
        
BUTTON_INDEX = {name: idx for idx, name in enumerate(BUTTON_NAMES)}



from config.defaults import (
    ACTION_FORWARD, ACTION_BACKWARD, ACTION_LEFT_TURN, ACTION_RIGHT_TURN,
    ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT, ACTION_ATTACK, ACTION_USE,
    ACTION_COUNT, ACTION_NAMES
)


class ActionDecoder:
    """Decode and encode Doom actions."""
    
    @staticmethod
    def null_action():
        """Return a null action (stand still)."""
        return [0] * ACTION_COUNT
    
    @staticmethod
    def forward():
        """Move forward."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        return action

    @staticmethod
    def backward():
        """Move backward."""
        action = [0] * ACTION_COUNT
        action[ACTION_BACKWARD] = 1
        return action
    
    @staticmethod
    def forward_attack():
        """Move forward and attack."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def left_turn():
        """Turn left."""
        action = [0] * ACTION_COUNT
        action[ACTION_LEFT_TURN] = 1
        return action
    
    @staticmethod
    def right_turn():
        """Turn right."""
        action = [0] * ACTION_COUNT
        action[ACTION_RIGHT_TURN] = 1
        return action
    
    @staticmethod
    def forward_left_turn():
        """Forward and turn left."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_LEFT_TURN] = 1
        return action
    
    @staticmethod
    def forward_right_turn():
        """Forward and turn right."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_RIGHT_TURN] = 1
        return action

    @staticmethod
    def backward_left_turn():
        """Backward and turn left."""
        action = [0] * ACTION_COUNT
        action[ACTION_BACKWARD] = 1
        action[ACTION_LEFT_TURN] = 1
        return action

    @staticmethod
    def backward_right_turn():
        """Backward and turn right."""
        action = [0] * ACTION_COUNT
        action[ACTION_BACKWARD] = 1
        action[ACTION_RIGHT_TURN] = 1
        return action
    
    @staticmethod
    def forward_left_turn_attack():
        """Forward, turn left, and attack."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_LEFT_TURN] = 1
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def forward_right_turn_attack():
        """Forward, turn right, and attack."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_RIGHT_TURN] = 1
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def left_turn_attack():
        """Turn left and attack (strong turn)."""
        action = [0] * ACTION_COUNT
        action[ACTION_LEFT_TURN] = 1
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def right_turn_attack():
        """Turn right and attack (strong turn)."""
        action = [0] * ACTION_COUNT
        action[ACTION_RIGHT_TURN] = 1
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def attack():
        """Pure attack."""
        action = [0] * ACTION_COUNT
        action[ACTION_ATTACK] = 1
        return action
    
    @staticmethod
    def strafe_left():
        """Move left."""
        action = [0] * ACTION_COUNT
        action[ACTION_MOVE_LEFT] = 1
        return action
    
    @staticmethod
    def strafe_right():
        """Move right."""
        action = [0] * ACTION_COUNT
        action[ACTION_MOVE_RIGHT] = 1
        return action
    
    @staticmethod
    def forward_strafe_left():
        """Forward and strafe left."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_MOVE_LEFT] = 1
        return action
    
    @staticmethod
    def forward_strafe_right():
        """Forward and strafe right."""
        action = [0] * ACTION_COUNT
        action[ACTION_FORWARD] = 1
        action[ACTION_MOVE_RIGHT] = 1
        return action
    
    @staticmethod
    def use():
        """Use/activate."""
        action = [0] * ACTION_COUNT
        action[ACTION_USE] = 1
        return action
    
    @staticmethod
    def get_action_names(action_vector):
        """Get readable names for active actions in a vector."""
        return [ACTION_NAMES[i] for i, a in enumerate(action_vector) if a == 1]
