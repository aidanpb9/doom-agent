import vizdoom as vzd
import numpy as np
import cv2
import time
import logging
import math
import sys
import random
from datetime import datetime
from pathlib import Path
import json

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from agent.nav.mapper import HybridMapper  # type: ignore[import-not-found]
    from agent.nav.navigator import Navigator  # type: ignore[import-not-found]
    from agent.nav.heading_controller import HeadingController  # type: ignore[import-not-found]
    from agent.nav import planner  # type: ignore[import-not-found]
    from agent.utils.progress_tracker import ProgressTracker  # type: ignore[import-not-found]
except ImportError:
    # Fallback: create simple stubs if imports fail
    class HybridMapper:
        def __init__(self):
            self.grid_size = 64
        def update(self, world):
            return None
        def agent_cell(self):
            return None
    class Navigator:
        def __init__(self, grid_size=64):
            self.current_path = None
        def update_path(self, occupancy_grid, agent_pos):
            pass
        def get_next_waypoint(self):
            return None
        def advance_path(self, agent_pos, threshold=2):
            pass
        def clear_path(self):
            pass
    class HeadingController:
        def __init__(self):
            pass
        def set_target(self, dy, dx):
            pass
        def act(self, angle):
            return None
    class ProgressTracker:
        def __init__(self, window=12):
            pass
        def update(self, pos):
            pass
        def is_stuck(self):
            return False
    class planner:
        @staticmethod
        def find_nearest_frontier(grid, start_pos, max_frontiers=10):
            return None

# Import new modular components
from agent.control.behavior_selector import BehaviorSelector
from agent.core.perception import PerceptionManager

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"doom_agent_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DoomAgent:
    def __init__(
        self,
        wad_path,
        config_path="vizdoom_config.cfg",
        episode_timeout=10,
        step_delay=0.05,
        action_frame_skip=4,
        fast_mode=False,
        log_interval=20,
        save_debug=True,
    ):
        self.wad_path = wad_path
        self.config_path = config_path
        self.episode_timeout = episode_timeout
        self.action_frame_skip = int(action_frame_skip)
        self.step_delay = float(step_delay)
        self.fast_mode = bool(fast_mode)
        self.log_interval = int(log_interval)
        self.save_debug = bool(save_debug)
        self.use_wall_clock = True
        if self.fast_mode:
            self.step_delay = 0.0
            self.action_frame_skip = max(self.action_frame_skip, 8)
            self.log_interval = max(self.log_interval, 100)
            self.save_debug = False
            self.use_wall_clock = False
        self.game = None
        self.frames_since_enemy = 0
        self.explore_forward_steps = 0
        self.explore_turn_direction = 1
        self.explore_strafe_direction = 1  # For varied exploration
        self.last_kill_count = 0
        self.frames_since_last_kill = 0
        self.stuck_on_enemy_steps = 0
        self.last_pos = None
        self.mapper = HybridMapper()
        self.navigator = Navigator(grid_size=getattr(self.mapper, "grid_size", 64))
        self.heading_controller = HeadingController()
        self.progress = ProgressTracker(window=12)
        
        # Initialize modular behavior system
        self.behavior_selector = BehaviorSelector(
            mapper=self.mapper,
            navigator=self.navigator,
            heading_controller=self.heading_controller,
            progress_tracker=self.progress,
            combat_enabled=False,
            items_enabled=False,
        )

    def _apply_fast_settings(self):
        if not self.fast_mode or self.game is None:
            return
        def safe_call(fn, *args):
            try:
                fn(*args)
            except Exception:
                pass
        safe_call(self.game.set_window_visible, False)
        safe_call(self.game.set_audio_buffer_enabled, False)
        safe_call(self.game.set_render_all_frames, False)
        safe_call(self.game.set_render_hud, False)
        safe_call(self.game.set_render_weapon, False)
        safe_call(self.game.set_render_crosshair, False)
        safe_call(self.game.set_render_decals, False)
        safe_call(self.game.set_render_particles, False)
        safe_call(self.game.set_render_messages, False)
        safe_call(self.game.set_render_corpses, False)
        safe_call(self.game.set_render_screen_flashes, False)
        safe_call(self.game.set_render_effects_sprites, False)
        safe_call(self.game.set_render_minimal_hud, False)
        if hasattr(vzd.ScreenResolution, "RES_320X240"):
            safe_call(self.game.set_screen_resolution, vzd.ScreenResolution.RES_320X240)
        safe_call(self.game.set_screen_format, vzd.ScreenFormat.GRAY8)
        safe_call(self.game.set_depth_buffer_enabled, False)
        safe_call(self.game.set_automap_buffer_enabled, False)
        safe_call(self.game.set_automap_render_textures, False)
        logger.info(
            "Fast mode enabled: headless render, reduced buffers, minimal logging."
        )
        
    def initialize_game(self):
        self.game = vzd.DoomGame()
        self.game.load_config(self.config_path)
        self._apply_fast_settings()

        # Enable world geometry info when available
        try:
            self.game.set_sectors_info_enabled(True)
        except Exception:
            pass
        try:
            self.game.set_lines_info_enabled(True)
        except Exception:
            pass

        wad_path = str(Path(self.wad_path).resolve())
        self.game.set_doom_scenario_path(wad_path)

        wad_name = Path(wad_path).name.lower()
        doom_map = "E1M1" if "doom1" in wad_name else "MAP01"
        try:
            self.game.set_doom_map(doom_map)
        except Exception:
            pass

        timeout_ticks = max(int(self.episode_timeout * 35), 2100)
        self.game.set_episode_timeout(timeout_ticks)
        self.game.init()

        # Enable cheats for navigation focus
        for cmd in ("am_cheat 3", "iddqd", "notarget"):
            try:
                self.game.send_game_command(cmd)
            except Exception:
                pass

        logger.info(f"Game initialized with WAD: {self.wad_path}")
        logger.info("Cheats enabled: am_cheat 3, iddqd, notarget")
        
    def get_state_info(self, state):
        """Parse game state using perception manager."""
        return self.behavior_selector.perception.get_state_info(state)
    
    def run_episode(self):
        if self.game is None:
            self.initialize_game()
        
        stats = {
            "kills": 0,
            "ammo_used": 0.0,
            "health_lost": 0.0,
            "actions_taken": 0,
            "episode_reward": 0.0,
            "episode_time": 0.0,
        }
        
        # Reset behavior state for new episode
        self.behavior_selector.reset_episode()
        
        start_time = time.time()
        frame_count = 0
        max_steps = max(1, int(self.episode_timeout * 35 / max(1, self.action_frame_skip)))
        
        logger.info("=" * 60)
        logger.info("Starting new episode")
        logger.info("=" * 60)
        
        try:
            self.game.new_episode()
            logger.info("Episode started successfully")
        except Exception as e:
            logger.error(f"Failed to start episode: {e}")
            return stats
        
        initial_state = self.game.get_state()
        if (
            initial_state is not None
            and initial_state.game_variables is not None
            and len(initial_state.game_variables) > 0
        ):
            gv0 = initial_state.game_variables
            initial_health = float(gv0[0]) if len(gv0) > 0 else 100.0
            initial_ammo = float(gv0[1]) if len(gv0) > 1 else 0.0
        else:
            initial_health = 100.0
            initial_ammo = 0.0
        
        while not self.game.is_episode_finished():
            try:
                state = self.game.get_state()
                
                if state is None:
                    break
                
                state_info = self.get_state_info(state)
                if state_info is None:
                    break
                
                current_health = state_info['health']
                current_ammo = state_info['ammo']
                current_kills = state_info['kills']
                
                stats["kills"] = current_kills
                stats["health_lost"] = max(0.0, initial_health - current_health)
                stats["ammo_used"] = max(0.0, initial_ammo - current_ammo)
                
                automap_buffer = state.automap_buffer if hasattr(state, "automap_buffer") else None
                angle = state_info.get('angle', None)
                pos_x = state_info.get('pos_x', 0.0)
                pos_y = state_info.get('pos_y', 0.0)
                self.last_pos = (pos_x, pos_y)
                
                # Use modular behavior selector
                action = self.behavior_selector.decide_action(state_info, automap_buffer, angle)
                
                if self.log_interval > 0 and frame_count % self.log_interval == 0:
                    lbls = state_info.get("labels", [])
                    n_enemies = self.behavior_selector.perception.count_enemies_from_labels(lbls)
                    
                    # Log all unique label names seen
                    label_names = set()
                    for lbl in lbls:
                        name = getattr(lbl, "object_name", "") or ""
                        if name:
                            label_names.add(name)
                    
                    logger.info(
                        f"Step {stats['actions_taken']}: "
                        f"Health={current_health:.0f} Ammo={current_ammo:.0f} "
                        f"Pos({pos_x:.0f},{pos_y:.0f}) "
                        f"Kills={stats['kills']} "
                        f"Enemies={n_enemies} "
                        f"Labels={sorted(label_names) if label_names else 'None'}"
                    )
                
                reward = self.game.make_action(action, self.action_frame_skip)
                stats["episode_reward"] += float(reward)
                stats["actions_taken"] += 1
                frame_count += 1
                
                if self.step_delay > 0:
                    time.sleep(self.step_delay)
                
                if self.use_wall_clock:
                    elapsed = time.time() - start_time
                    if elapsed >= self.episode_timeout:
                        break
                
                if frame_count >= max_steps:
                    break
                    
            except Exception as e:
                logger.error(f"Error during episode: {e}")
                break
        
        stats["episode_time"] = time.time() - start_time

        if self.save_debug:
            try:
                debug_path = log_dir / "sector_map.png"
                self.behavior_selector.sector_navigator.render_debug_map(
                    str(debug_path), self.last_pos
                )
                logger.info(f"Sector debug map saved to {debug_path}")
            except Exception:
                pass
        
        logger.info("=" * 60)
        logger.info("Episode finished")
        logger.info(f"Total reward: {stats['episode_reward']:.2f}")
        logger.info(f"Kills: {stats['kills']}")
        logger.info(f"Health lost: {stats['health_lost']:.2f}")
        logger.info(f"Actions taken: {stats['actions_taken']}")
        logger.info(f"Episode time: {stats['episode_time']:.2f}s")
        logger.info("=" * 60)
        
        return stats
    
    def close(self):
        if self.game:
            self.game.close()


if __name__ == "__main__":
    import sys
    
    wad_file = "wads/doom1.wad"
    seconds = 30
    fast_mode = "--fast" in sys.argv
    slow_mode = "--slow" in sys.argv
    if "--fast" in sys.argv:
        sys.argv.remove("--fast")
    if "--slow" in sys.argv:
        sys.argv.remove("--slow")

    step_delay = 0.0
    action_frame_skip = 6
    if slow_mode:
        step_delay = 0.05
        action_frame_skip = 4
        fast_mode = False

    if len(sys.argv) > 1:
        wad_file = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            seconds = int(sys.argv[2])
        except Exception:
            seconds = 10
    
    if not Path(wad_file).exists():
        logger.error(f"WAD file not found: {wad_file}")
        sys.exit(1)
    
    logger.info(f"Starting Doom Agent with WAD: {wad_file}")
    if fast_mode:
        logger.info("Fast mode: headless render + reduced buffers")
    else:
        logger.info(
            f"Screen mode: frame_skip={action_frame_skip} step_delay={step_delay:.2f}s"
        )
    agent = DoomAgent(
        wad_file,
        episode_timeout=seconds,
        fast_mode=fast_mode,
        step_delay=step_delay,
        action_frame_skip=action_frame_skip,
    )
    agent.initialize_game()
    stats = agent.run_episode()
    agent.close()

    results_file = log_dir / "last_run.json"
    with open(results_file, "w") as f:
        json.dump(stats, f, indent=2)
