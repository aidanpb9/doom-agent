"""
Main Doom Agent orchestrator.
Contains the DoomAgent class that manages the game loop and coordinates behavior.
"""

import vizdoom as vzd
import numpy as np
import time
import logging
import threading
import os
import faulthandler
from datetime import datetime
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    Image = None

from agent.behavior.behavior_selector import BehaviorSelector
from agent.utils.action_decoder import ActionDecoder
from config import ACTION_NAMES

ACTION_VECTORS = [
    [1, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 0],
    [0, 0, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1],
]

logger = logging.getLogger(__name__)


class DoomAgent:
    """Main agent class that orchestrates the Doom game simulation."""
    
    def __init__(
        self,
        wad_path,
        config_path="vizdoom_config.cfg",
        episode_timeout=10,
        step_delay=0.0,
        action_frame_skip=1,
        fast_mode=False,
        log_interval=20,
        save_debug=True,
        map_name=None,
        no_enemies=False,
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
            no_enemies: Disable monster spawning using Doom's -nomonsters flag
        """
        self.wad_path = wad_path
        self.config_path = config_path
        self.episode_timeout = episode_timeout
        self.action_frame_skip = int(action_frame_skip)
        self.step_delay = float(step_delay)
        self.fast_mode = bool(fast_mode)
        self.log_interval = int(log_interval)
        self.save_debug = bool(save_debug)
        self.map_name = map_name
        self.no_enemies = bool(no_enemies)
        self.use_wall_clock = True
        if self.fast_mode:
            self.step_delay = 0.0
            self.action_frame_skip = max(self.action_frame_skip, 8)
            self.log_interval = max(self.log_interval, 100)
            self.save_debug = False
            # Keep wall-clock timeout even in fast mode to avoid hangs.
            self.use_wall_clock = True
            # Fast mode should avoid high-frequency nav/perception info logs.
            logging.getLogger("agent.navigation.navmesh").setLevel(logging.WARNING)
            logging.getLogger("agent.navigation.sector_navigator").setLevel(logging.WARNING)
            logging.getLogger("agent.perception.perception").setLevel(logging.WARNING)
        self.game = None
        self.episode_step = 0
        self.automap_log = []  # Store automap frames
        self.action_log = []   # Store actions taken
        self.last_pos = None
        self.nav_debug_log = []  # Store navigation debug overlays
        self.hang_timeout = 8.0
        self.hang_action_timeout = 6.0
        self._hang_event = None
        self._last_action_time = None
        self._hang_stage = None
        self._hang_stage_time = None
        self._last_action_name = None
        self._frame_count = 0
        
        # Initialize modular behavior system
        self.behavior_selector = BehaviorSelector(
            combat_enabled=True,
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

    def _apply_native_settings(self):
        if self.fast_mode or self.game is None:
            return
        def safe_call(fn, *args):
            try:
                fn(*args)
            except Exception:
                pass
        # Match classic Doom timing and presentation.
        safe_call(self.game.set_ticrate, 35)
        safe_call(self.game.set_render_all_frames, True)
        safe_call(self.game.set_window_visible, True)
        if hasattr(vzd.ScreenResolution, "RES_640X480"):
            safe_call(self.game.set_screen_resolution, vzd.ScreenResolution.RES_640X480)
        safe_call(self.game.set_render_hud, True)
        safe_call(self.game.set_render_weapon, True)
        safe_call(self.game.set_render_crosshair, True)
        safe_call(self.game.set_render_decals, True)
        safe_call(self.game.set_render_particles, True)
        safe_call(self.game.set_render_messages, True)
        safe_call(self.game.set_render_corpses, True)
        safe_call(self.game.set_render_screen_flashes, True)
        safe_call(self.game.set_render_effects_sprites, True)
        safe_call(self.game.set_render_minimal_hud, False)
        
    def initialize_game(self):
        """Initialize the Doom game environment."""
        self.game = vzd.DoomGame()
        self.game.load_config(self.config_path)
        self._apply_fast_settings()
        self._apply_native_settings()

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
        if self.no_enemies:
            try:
                self.game.add_game_args("-nomonsters")
            except Exception:
                pass

        wad_name = Path(wad_path).name.lower()
        if self.map_name:
            doom_map = str(self.map_name).upper()
        else:
            doom_map = "E1M1" if "doom" in wad_name else "MAP01"
        try:
            self.game.set_doom_map(doom_map)
        except Exception:
            pass
        self.behavior_selector.set_map_name(doom_map)
        self.behavior_selector.set_wad_path(wad_path)

        timeout_ticks = max(int(self.episode_timeout * 35), 2100)
        self.game.set_episode_timeout(timeout_ticks)
        self.game.init()

        # Enable cheats for navigation focus
        for cmd in ("am_cheat 3", "iddqd", "notarget"):
            try:
                self.game.send_game_command(cmd)
            except Exception:
                pass

        logger.info(
            "Game initialized with WAD: %s (no_enemies=%s)",
            self.wad_path,
            self.no_enemies,
        )

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
        last_move_time = start_time
        last_move_pos = None
        frame_count = 0
        max_steps = max(1, int(self.episode_timeout * 35 / max(1, self.action_frame_skip)))
        hang_detected = False
        timeout_hit = False
        max_steps_hit = False
        state_none = False
        error_during_episode = None
        last_state_info = None
        self._hang_event = threading.Event()
        self._last_action_time = time.time()
        self._hang_stage = "start"
        self._hang_stage_time = time.time()
        self._frame_count = 0

        def hang_watchdog():
            while self._hang_event is not None and not self._hang_event.is_set():
                time.sleep(0.5)
                last_ts = self._last_action_time
                if last_ts is None:
                    continue
                if time.time() - last_ts > self.hang_action_timeout:
                    stage = self._hang_stage or "unknown"
                    stage_age = 0.0
                    if self._hang_stage_time is not None:
                        stage_age = time.time() - self._hang_stage_time
                    dump_name = datetime.now().strftime("logs/hang_dump_%Y%m%d_%H%M%S.txt")
                    try:
                        with open(dump_name, "w") as f:
                            f.write(
                                f"stage={stage} stage_age={stage_age:.2f}s "
                                f"last_action_age={(time.time() - last_ts):.2f}s "
                                f"episode_step={self.episode_step} frame_count={self._frame_count} "
                                f"last_pos={self.last_pos} last_action={self._last_action_name}\n"
                            )
                            faulthandler.dump_traceback(file=f, all_threads=True)
                    except Exception:
                        pass
                    logger.error(
                        "Hang detected: no action completed for %.1fs, forcing shutdown.",
                        self.hang_action_timeout,
                    )
                    try:
                        if self.game is not None:
                            self.game.close()
                    except Exception:
                        pass
                    try:
                        logging.shutdown()
                    except Exception:
                        pass
                    os._exit(2)

        threading.Thread(target=hang_watchdog, daemon=True).start()
        
        logger.info("=" * 60)
        logger.info("Starting new episode")
        logger.info("=" * 60)
        
        try:
            self.game.new_episode()
            logger.info("Episode started successfully")
        except Exception as e:
            logger.error(f"Failed to start episode: {e}")
            stats["end_reason"] = "start_failed"
            if self._hang_event is not None:
                self._hang_event.set()
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
                self._hang_stage = "get_state"
                self._hang_stage_time = time.time()
                state = self.game.get_state()
                self._hang_stage = "get_state_done"
                self._hang_stage_time = time.time()
                
                if state is None:
                    state_none = True
                    break
                
                state_info = self.get_state_info(state)
                if state_info is None:
                    # Skip frames where state info isn't ready yet
                    reward = self.game.make_action(
                        [1, 0, 0, 0, 0, 0, 0], self.action_frame_skip
                    )
                    self._last_action_time = time.time()
                    self._hang_stage = "make_action_done"
                    self._hang_stage_time = time.time()
                    frame_count += 1
                    self._frame_count = frame_count
                    continue

                last_state_info = state_info
                
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
                if last_move_pos is None:
                    last_move_pos = (pos_x, pos_y)
                    last_move_time = time.time()
                else:
                    dxm = pos_x - last_move_pos[0]
                    dym = pos_y - last_move_pos[1]
                    if (dxm * dxm + dym * dym) > 16.0:
                        last_move_pos = (pos_x, pos_y)
                        last_move_time = time.time()
                
                # Use modular behavior selector
                self._hang_stage = "decide_action"
                self._hang_stage_time = time.time()
                action = self.behavior_selector.decide_action(state_info, angle)
                self._hang_stage = "decide_action_done"
                self._hang_stage_time = time.time()
                
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
                    action_idx = None
                    for i, a in enumerate(ACTION_VECTORS):
                        if action == a:
                            action_idx = i
                            break
                    if action_idx is not None:
                        if 0 <= action_idx < len(ACTION_NAMES):
                            action_name = ACTION_NAMES[action_idx]
                        else:
                            action_name = f"Action_{action_idx}"
                    else:
                        active_names = ActionDecoder.get_action_names(action)
                        if active_names:
                            action_name = "+".join(active_names)
                self._last_action_name = action_name
                
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
                
                self._hang_stage = "make_action"
                self._hang_stage_time = time.time()
                reward = self.game.make_action(action, self.action_frame_skip)
                self._last_action_time = time.time()
                self._hang_stage = "make_action_done"
                self._hang_stage_time = time.time()
                stats["episode_reward"] += float(reward)
                stats["actions_taken"] += 1
                frame_count += 1
                self._frame_count = frame_count
                self.episode_step += 1

                if time.time() - last_move_time > self.hang_timeout:
                    nav = getattr(self.behavior_selector, "sector_navigator", None)
                    if not getattr(nav, "exit_focus_active", False):
                        logger.error("Hang detected: no movement for %.1fs, ending episode.", self.hang_timeout)
                        hang_detected = True
                        break
                
                if self.step_delay > 0:
                    time.sleep(self.step_delay)
                
                if self.use_wall_clock:
                    elapsed = time.time() - start_time
                    if elapsed >= self.episode_timeout:
                        timeout_hit = True
                        break
                
                if frame_count >= max_steps:
                    max_steps_hit = True
                    break
                    
            except Exception as e:
                logger.error(f"Error during episode: {e}")
                error_during_episode = str(e)
                break
        
        stats["episode_time"] = time.time() - start_time
        if self._hang_event is not None:
            self._hang_event.set()
        
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
        
        def safe_is_player_dead():
            try:
                return bool(self.game.is_player_dead())
            except Exception:
                return False

        def safe_is_episode_finished():
            try:
                return bool(self.game.is_episode_finished())
            except Exception:
                return False

        end_reason = "unknown"
        episode_finished = safe_is_episode_finished()
        if error_during_episode:
            end_reason = f"error:{error_during_episode}"
        elif hang_detected:
            end_reason = "hang_no_movement"
        elif safe_is_player_dead():
            end_reason = "player_dead"
        elif timeout_hit:
            end_reason = "timeout"
        elif episode_finished:
            end_reason = "exit"
        elif max_steps_hit:
            end_reason = "max_steps"
        elif state_none:
            end_reason = "state_none"

        end_pos = None
        end_nav_node_id = None
        end_sector_ids = []
        if last_state_info is not None:
            try:
                end_pos = (float(last_state_info.get("pos_x", 0.0)), float(last_state_info.get("pos_y", 0.0)))
            except Exception:
                end_pos = None
            sectors = last_state_info.get("sectors") if isinstance(last_state_info, dict) else None
            if sectors:
                for sec in sectors:
                    inside = False
                    sec_id = None
                    try:
                        if isinstance(sec, dict):
                            sec_id = sec.get("id", None) or sec.get("sector_id", None)
                            inside = bool(
                                sec.get("is_inside", False)
                                or sec.get("inside", False)
                                or sec.get("is_inside_player", False)
                                or sec.get("contains_player", False)
                            )
                        else:
                            for attr in ("id", "sector_id"):
                                if hasattr(sec, attr):
                                    sec_id = getattr(sec, attr)
                                    break
                            for attr in ("is_inside", "inside", "is_inside_player", "contains_player"):
                                if hasattr(sec, attr):
                                    try:
                                        inside = bool(getattr(sec, attr))
                                    except Exception:
                                        inside = False
                                    break
                    except Exception:
                        inside = False
                    if inside:
                        end_sector_ids.append(sec_id if sec_id is not None else "unknown")
            nav = getattr(self.behavior_selector, "sector_navigator", None)
            if nav is not None and getattr(nav, "mesh", None) is not None and end_pos is not None:
                try:
                    node = nav.mesh.get_closest_node_in((end_pos[0], end_pos[1], 0.0), nav.mesh.nodes, use_poly=True)
                    if node is not None:
                        end_nav_node_id = node.node_id
                except Exception:
                    end_nav_node_id = None

        stats["end_reason"] = end_reason
        stats["end_pos"] = end_pos
        stats["end_nav_node_id"] = end_nav_node_id
        stats["end_sector_ids"] = end_sector_ids

        logger.info("=" * 60)
        logger.info("Episode finished")
        logger.info(f"Episode end reason: {end_reason}")
        if end_pos is not None:
            logger.info(
                "Episode end location: pos=(%.1f,%.1f) nav_node=%s sectors=%s",
                end_pos[0],
                end_pos[1],
                end_nav_node_id,
                end_sector_ids if end_sector_ids else "unknown",
            )
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
