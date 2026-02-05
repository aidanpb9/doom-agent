"""
Main Doom Agent orchestrator.
Contains the DoomAgent class that manages the game loop and coordinates behavior.
"""

import vizdoom as vzd
import numpy as np
import time
import logging
from pathlib import Path
import json
try:
    from PIL import Image
except ImportError:
    Image = None

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

from agent.control.behavior_selector import BehaviorSelector

logger = logging.getLogger(__name__)


class DoomAgent:
    """Main agent class that orchestrates the Doom game simulation."""
    
    def __init__(
        self,
        wad_path,
        config_path="vizdoom_config.cfg",
        episode_timeout=10,
        step_delay=0.12,
        action_frame_skip=4,
        fast_mode=False,
        log_interval=20,
        save_debug=True,
    ):
        """Initialize the Doom agent.
        
        Args:
            wad_path: Path to the WAD file
            config_path: Path to vizdoom config file
            episode_timeout: Time limit for episode in seconds
            step_delay: Sleep time between actions (slows real-time playback)
            action_frame_skip: Frames to skip per action
            fast_mode: Disable rendering/buffers + reduce logging for speed
            log_interval: Steps between info logs (0 disables)
            save_debug: Save debug logs/images to disk
        """
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
        self.episode_step = 0
        self.automap_log = []  # Store automap frames
        self.action_log = []   # Store actions taken
        self.last_pos = None
        self.nav_debug_log = []  # Store navigation debug overlays
        
        # Initialize navigation components
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
            combat_enabled=True,
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
        """Initialize the Doom game environment."""
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

        # Enable cheats for navigation focus
        try:
            self.game.send_game_command("am_cheat 3")
        except Exception:
            pass
        try:
            self.game.send_game_command("iddqd")
        except Exception:
            pass
        logger.info("Cheats enabled: am_cheat 3, invincibility (iddqd)")
        
    def get_state_info(self, state):
        """Parse game state using perception manager."""
        return self.behavior_selector.perception.get_state_info(state)
    
    def save_automap_log(self):
        """Save automap frames and action log to files."""
        if not self.save_debug:
            return
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Save automap images if PIL is available
        if Image is not None and self.automap_log:
            automap_dir = logs_dir / "automap_frames"
            automap_dir.mkdir(exist_ok=True)
            
            for step_num, automap_data in self.automap_log:
                if automap_data is not None:
                    try:
                        img = Image.fromarray(automap_data.astype(np.uint8))
                        img.save(automap_dir / f"step_{step_num:04d}.png")
                    except Exception:
                        pass

        # Save navigation debug overlays if available
        if Image is not None and self.nav_debug_log:
            nav_dir = logs_dir / "nav_debug_frames"
            nav_dir.mkdir(exist_ok=True)
            for step_num, nav_data in self.nav_debug_log:
                if nav_data is not None:
                    try:
                        img = Image.fromarray(nav_data.astype(np.uint8))
                        img.save(nav_dir / f"step_{step_num:04d}.png")
                    except Exception:
                        pass
        
        # Save action log as text
        if self.action_log:
            action_log_path = logs_dir / "action_log.txt"
            with open(action_log_path, 'w') as f:
                f.write("Step\tHealth\tAmmo\tPos_X\tPos_Y\tAngle\tAction\tEnemy_Detected\tLabels\n")
                for entry in self.action_log:
                    f.write(
                        f"{entry['step']}\t"
                        f"{entry['health']:.0f}\t"
                        f"{entry['ammo']:.0f}\t"
                        f"{entry['pos_x']:.1f}\t"
                        f"{entry['pos_y']:.1f}\t"
                        f"{entry['angle']:.1f}\t"
                        f"{entry['action']}\t"
                        f"{entry['enemy_detected']}\t"
                        f"{entry['labels']}\n"
                    )
            logger.info(f"Action log saved to {action_log_path}")

    def run_episode(self):
        """Run a single episode and return statistics."""
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
        self.automap_log = []
        self.action_log = []
        self.nav_debug_log = []
        self.episode_step = 0
        
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
                    # Skip frames where state info isn't ready yet
                    reward = self.game.make_action(
                        [1, 0, 0, 0, 0, 0, 0], self.action_frame_skip
                    )
                    frame_count += 1
                    continue
                
                current_health = state_info['health']
                current_ammo = state_info['ammo']
                current_kills = state_info['kills']
                
                stats["kills"] = current_kills
                stats["health_lost"] = max(0.0, initial_health - current_health)
                stats["ammo_used"] = max(0.0, initial_ammo - current_ammo)
                
                automap_buffer = state.automap_buffer if hasattr(state, "automap_buffer") else None
                angle = state_info.get('angle', None)
                pos_x = state_info.get('pos_x', 0)
                pos_y = state_info.get('pos_y', 0)
                self.last_pos = (pos_x, pos_y)
                
                # Use modular behavior selector with full state for sector navigator
                action = self.behavior_selector.decide_action(state_info, automap_buffer, angle, state=state)
                
                # Log automap every 20 steps
                if self.save_debug and frame_count % 20 == 0 and automap_buffer is not None:
                    self.automap_log.append((self.episode_step, automap_buffer.copy()))
                    debug_frame = self.behavior_selector.get_navigation_debug_frame(automap_buffer)
                    if debug_frame is not None:
                        self.nav_debug_log.append((self.episode_step, debug_frame))
                
                do_log = self.log_interval > 0 and frame_count % self.log_interval == 0
                do_action_log = self.save_debug and frame_count % 10 == 0
                need_labels = do_log or do_action_log
                if need_labels:
                    lbls = state_info.get("labels", [])
                    n_enemies = self.behavior_selector.perception.count_enemies_from_labels(lbls)
                    label_names = set()
                    for lbl in lbls:
                        name = getattr(lbl, "object_name", "") or ""
                        if name:
                            label_names.add(name)
                else:
                    lbls = []
                    n_enemies = 0
                    label_names = set()

                action_name = "Unknown"
                if do_log or do_action_log:
                    from agent.config import ACTION_NAMES
                    try:
                        action_idx = None
                        for i, a in enumerate([
                            [1,0,0,0,0,0,0], [0,1,0,0,0,0,0], [0,0,1,0,0,0,0],
                            [0,0,0,1,0,0,0], [0,0,0,0,1,0,0], [0,0,0,0,0,1,0],
                            [0,0,0,0,0,0,1]
                        ]):
                            if action == a:
                                action_idx = i
                                break
                        if action_idx is not None:
                            action_name = ACTION_NAMES.get(action_idx, f"Action_{action_idx}")
                    except Exception:
                        pass
                
                # Store action log entry
                if do_action_log:  # Log every 10 actions
                    self.action_log.append({
                        'step': self.episode_step,
                        'health': current_health,
                        'ammo': current_ammo,
                        'pos_x': pos_x,
                        'pos_y': pos_y,
                        'angle': angle if angle is not None else 0,
                        'action': action_name,
                        'enemy_detected': n_enemies > 0,
                        'labels': ', '.join(sorted(label_names)) if label_names else 'None'
                    })
                
                if do_log:
                    logger.info(
                        f"Step {stats['actions_taken']}: "
                        f"Health={current_health:.0f} Ammo={current_ammo:.0f} "
                        f"Pos({pos_x:.0f},{pos_y:.0f}) Action={action_name} "
                        f"Kills={stats['kills']} Enemies={n_enemies} "
                        f"Labels={sorted(label_names) if label_names else 'None'}"
                    )
                
                reward = self.game.make_action(action, self.action_frame_skip)
                stats["episode_reward"] += float(reward)
                stats["actions_taken"] += 1
                frame_count += 1
                self.episode_step += 1
                
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
        
        # Save logs
        if self.save_debug:
            self.save_automap_log()
            try:
                debug_path = Path("logs") / "sector_map.png"
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
        """Close the game and cleanup."""
        if self.game:
            self.game.close()
