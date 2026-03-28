"""Manages the episode details. Acts as the interface between VizDoom and StateMachine.
Contains game initialization, telemetry outputs, perception."""
from core.navigation.graph import Graph, NodeType
from core.navigation.navigation_engine import NavigationEngine
from core.navigation.path_tracker import PathTracker
from core.execution.perception import Perception
from core.execution.state_machine import StateMachine
from core.execution.telemetry_writer import TelemetryWriter
from core.utils import load_blocking_segments_from_wad
from config.constants import (DEFAULT_WAD_PATH, DEFAULT_MAP_NAME, 
    DEFAULT_EPISODE_TIMEOUT, TICK, DEFAULT_TICKRATE, HEADLESS_TICKRATE)
import vizdoom as vzd
from pathlib import Path
import random


class Agent:

    def __init__(self, game: vzd.DoomGame):
        self.game = None
        self.perception = None
        self.state_machine = None
        self.path_tracker = None #for loading static nodes
        self.telemetry_writer = None
        self.blocking_segments = None #useful for combat
    
    def initialize_game(self, headless=False) -> None:
        """Does VizDoom setup, loads configs, and creates runtime objects."""
        self.game = vzd.DoomGame()
        self.game.load_config("config/vizdoom.cfg")
        self._apply_fast_settings() if headless else self._apply_native_settings()

        try: self.game.set_sectors_info_enabled(True)
        except Exception: pass
        try: self.game.set_lines_info_enabled(True)
        except Exception: pass

        self.game.set_doom_scenario_path(str(Path(DEFAULT_WAD_PATH).resolve()))
        self.game.set_doom_map(DEFAULT_MAP_NAME)
        self.game.set_episode_timeout(DEFAULT_EPISODE_TIMEOUT)
        self.game.init()
        self.blocking_segments = load_blocking_segments_from_wad(DEFAULT_WAD_PATH, DEFAULT_MAP_NAME)

        #Create all runtime objects
        graph = Graph() #one Graph instance shared between classes
        nav_engine = NavigationEngine(graph)
        self.path_tracker = PathTracker(graph, nav_engine, self.blocking_segments)
        self.path_tracker.load_static_nodes(DEFAULT_MAP_NAME)
        self.state_machine = StateMachine(self.path_tracker, self.blocking_segments)
        self.perception = Perception()
        self.telemetry_writer = TelemetryWriter() #TODO: after cleaning TM

    def run_episode(self, params: dict | None = None) -> dict:
        """calls Perception and StateMachine each tick.
        Uses params as inputs from the GA.
        Returns stats for the genetic algorithm."""
        stats = {
            "finish_level": False,
            "ticks": 0,
            "health": 0,
            "armor": 0,
            "ammo": 0,
            "enemies_killed": 0,
            "waypoints_reached": 0,
            "end_reason": "timeout"
        }

        #Setup
        self.game.new_episode()
        state = self.game.get_state()
        gamestate = self.perception.parse(state)
        self.path_tracker.last_node = self.path_tracker._nearest_node(gamestate)
        self.path_tracker.set_goal_by_type(gamestate, NodeType.EXIT)
        self.path_tracker._get_next_node(gamestate)

        #Run loop
        while not self.game.is_episode_finished():
            state = self.game.get_state()
            if state is None:
                break
            gamestate = self.perception.parse(state)
            action = self.state_machine.update(gamestate)
            self.game.make_action(action, TICK) #decide action every tic
            
        #Derive how the level ended
        is_dead = self.game.is_player_dead()
        is_timeout = self.game.get_episode_time() >= DEFAULT_EPISODE_TIMEOUT
        level_completed = self.game.is_episode_finished() and not is_dead and not is_timeout
        if is_dead:
            end_reason = "death"
        elif is_timeout:
            end_reason = "timeout"
        elif level_completed:
            end_reason = "completion"
        else:
            end_reason = "unknown"

        #Fill in final stats 
        stats["finish_level"] = end_reason == "completion"
        stats["ticks"] = self.game.get_episode_time()
        stats["health"] = gamestate.health
        stats["armor"] = gamestate.armor
        stats["ammo"] = gamestate.ammo
        stats["enemies_killed"] = gamestate.enemies_killed
        stats["waypoints_reached"] = len(self.path_tracker.visited_waypoints)
        stats["end_reason"] = end_reason
        return stats

    def close(self) -> None:
        if self.game:
            self.game.close()
    
    def _apply_native_settings(self):
        """Windowed, full rendering for run mode."""
        def safe(fn, *args):
            try: fn(*args)
            except Exception: pass

        safe(self.game.set_ticrate, DEFAULT_TICKRATE)
        safe(self.game.set_window_visible, True)
        safe(self.game.set_render_all_frames, True)
        safe(self.game.set_render_hud, True)
        safe(self.game.set_render_weapon, True)
        safe(self.game.set_render_crosshair, True)
        safe(self.game.set_render_decals, True)
        safe(self.game.set_render_particles, True)
        safe(self.game.set_render_messages, True)
        safe(self.game.set_render_corpses, True)
        safe(self.game.set_screen_resolution, vzd.ScreenResolution.RES_640X480)

    def _apply_fast_settings(self):
        """Headless, minimal rendering for evolve mode."""
        def safe(fn, *args):
            try: fn(*args)
            except Exception: pass

        safe(self.game.set_ticrate, HEADLESS_TICKRATE)
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