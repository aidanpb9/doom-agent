#Reference
'''def _parse_state(state) -> Optional[Dict[str, object]]:
        if state is None or state.game_variables is None:
            return None
        game_vars = state.game_variables
        return {
            "health": float(game_vars[0]) if len(game_vars) > 0 else 0.0,
            "ammo": float(game_vars[1]) if len(game_vars) > 1 else 0.0,
            "x": float(game_vars[2]) if len(game_vars) > 2 else 0.0,
            "y": float(game_vars[3]) if len(game_vars) > 3 else 0.0,
            "z": float(game_vars[4]) if len(game_vars) > 4 else 0.0,
            "angle": float(game_vars[5]) if len(game_vars) > 5 else 0.0,
            "kills": int(game_vars[6]) if len(game_vars) > 6 else 0,
            "screen": state.screen_buffer,
            "labels": getattr(state, "labels", []) or [],
        }'''