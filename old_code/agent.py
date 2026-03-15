"""
DoomAgent — VizDoom setup and episode loop.
Delegates action decisions to the StateMachine.
"""

import time
import logging
import vizdoom as vzd
from pathlib import Path

from config.constants import DEFAULT_WAD_PATH, DEFAULT_MAP_NAME, DEFAULT_EPISODE_TIMEOUT, DEFAULT_ACTION_FRAME_SKIP

logger = logging.getLogger(__name__)


class DoomAgent:

    def __init__(self, fast_mode=False):
        self.fast_mode = fast_mode
        self.game = None
        self.state_machine = None  # set in Phase 3

    def _apply_fast_settings(self):
        """Headless, minimal rendering for evolve mode."""
        def safe(fn, *args):
            try: fn(*args)
            except Exception: pass

        safe(self.game.set_window_visible, False)
        safe(self.game.set_render_hud, False)
        safe(self.game.set_render_weapon, False)
        safe(self.game.set_render_crosshair, False)
        safe(self.game.set_render_decals, False)
        safe(self.game.set_render_particles, False)
        safe(self.game.set_render_messages, False)
        safe(self.game.set_render_corpses, False)
        safe(self.game.set_render_all_frames, False)
        safe(self.game.set_audio_buffer_enabled, False)
        safe(self.game.set_depth_buffer_enabled, False)
        safe(self.game.set_automap_buffer_enabled, False)
        if hasattr(vzd.ScreenResolution, "RES_320X240"):
            safe(self.game.set_screen_resolution, vzd.ScreenResolution.RES_320X240)
        safe(self.game.set_screen_format, vzd.ScreenFormat.GRAY8)

    def _apply_native_settings(self):
        """Windowed, full rendering for run mode."""
        def safe(fn, *args):
            try: fn(*args)
            except Exception: pass

        safe(self.game.set_window_visible, True)
        safe(self.game.set_render_all_frames, True)
        safe(self.game.set_render_hud, True)
        safe(self.game.set_render_weapon, True)
        safe(self.game.set_render_crosshair, True)
        safe(self.game.set_render_decals, True)
        safe(self.game.set_render_particles, True)
        safe(self.game.set_render_messages, True)
        safe(self.game.set_render_corpses, True)
        if hasattr(vzd.ScreenResolution, "RES_640X480"):
            safe(self.game.set_screen_resolution, vzd.ScreenResolution.RES_640X480)

    def initialize_game(self):
        self.game = vzd.DoomGame()
        self.game.load_config("config/vizdoom.cfg")

        if self.fast_mode:
            self._apply_fast_settings()
        else:
            self._apply_native_settings()

        try: self.game.set_sectors_info_enabled(True)
        except Exception: pass
        try: self.game.set_lines_info_enabled(True)
        except Exception: pass

        self.game.set_doom_scenario_path(str(Path(DEFAULT_WAD_PATH).resolve()))
        self.game.set_doom_map(DEFAULT_MAP_NAME)
        self.game.set_episode_timeout(DEFAULT_EPISODE_TIMEOUT)
        self.game.init()
        logger.info("Game initialized — map=%s fast=%s", DEFAULT_MAP_NAME, self.fast_mode)

    def run_episode(self):
        """Run one episode, return stats dict."""
        stats = {
            "kills": 0,
            "health": 100,
            "armor": 0,
            "ammo": 0,
            "end_reason": "unknown",
            "episode_time": 0.0,
        }

        self.game.new_episode()
        start_time = time.time()

        while not self.game.is_episode_finished():
            state = self.game.get_state()
            if state is None:
                break

            # TODO Phase 3: action = self.state_machine.decide(state)
            action = [1, 0, 0, 0, 0, 0, 0, 0]  # placeholder: always forward

            self.game.make_action(action, DEFAULT_ACTION_FRAME_SKIP)

        stats["episode_time"] = time.time() - start_time
        stats["end_reason"] = "exit" if self.game.is_episode_finished() else "timeout"
        logger.info("Episode done — reason=%s time=%.1fs", stats["end_reason"], stats["episode_time"])
        return stats

    def close(self):
        if self.game:
            self.game.close()
