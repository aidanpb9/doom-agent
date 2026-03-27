"""Manages the episode details. Acts as the interface between VizDoom and StateMachine.
Contains game initialization, telemetry outputs, perception."""
from core.navigation.graph import Graph
from core.navigation.navigation_engine import NavigationEngine
from core.navigation.path_tracker import PathTracker
from core.execution.perception import Perception
from core.execution.state_machine import StateMachine
from core.execution.telemetry_writer import TelemetryWriter
from core.utils import load_blocking_segments_from_wad
from config.constants import DEFAULT_WAD_PATH, DEFAULT_MAP_NAME, DEFAULT_EPISODE_TIMEOUT

import vizdoom as vzd
from pathlib import Path


class Agent:

    def __init__(self, game):
        self.game = None
        self.perception = None
        self.state_machine = None
        self.path_tracker = None #for loading static nodes
        self.telemetry_writer = None
        self.blocking_segments = None #useful for combat
    
    def initialize_game(self) -> None:
        """Does VizDoom setup, loads configs, and creates runtime objects."""

        #VizDoom setup
        self.game = vzd.DoomGame()
        self.game.load_config("config/vizdoom.cfg")
        self._apply_native_settings()

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
        graph = Graph() #one Graph instance shared between NavEngine and PathTracker
        nav_engine = NavigationEngine(graph)
        self.path_tracker = PathTracker(graph, nav_engine)
        self.path_tracker.load_static_nodes(DEFAULT_MAP_NAME)
        self.state_machine = StateMachine(self.path_tracker, self.blocking_segments)
        self.perception = Perception()
        self.telemetry_writer = TelemetryWriter() #TODO: after cleaning TM

    def run_episode(self, params: dict) -> dict:
        """calls Perception and StateMachine each tick.
        Uses params as inputs from the GA.
        Returns stats for the genetic algorithm."""
        self.game.new_episode()
        state = self.game.get_state()
        gamestate = self.perception.parse(state)
        self.path_tracker.last_node = self.path_tracker._nearest_node(gamestate)


    def close(self) -> None:
        if self.game:
            self.game.close()
    

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
        safe(self.game.set_screen_resolution, vzd.ScreenResolution.RES_640X480)