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
AGENT_DIR = ROOT_DIR / "DOOM"
if str(AGENT_DIR) not in sys.path:
    sys.path.append(str(AGENT_DIR))

from agent.nav.mapper import AutomapMapper

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

ENEMY_KEYWORDS = (
    "zombie",
    "zombieman",
    "shotgun",
    "chaingun",
    "imp",
    "demon",
    "caco",
    "baron",
    "lostsoul",
    "lost soul",
    "hellknight",
    "arachno",
    "revenant",
    "mancubus",
    "archvile",
    "pain",
    "spider",
    "cyber",
    "trooper",
    "troop",
    "spectre",
)

PRIORITY_LABELS = {
    "exit": 10,
    "switch": 9,
    "door": 8,
    "key": 7,
    "clip": 6,
    "ammo": 6,
    "stimpack": 5,
    "health": 5,
    "armor": 4,
    "soul": 3,
}


class DoomAgent:
    def __init__(self, wad_path, config_path="DOOM/doom.cfg", episode_timeout=10):
        self.wad_path = wad_path
        self.config_path = config_path
        self.episode_timeout = episode_timeout
        self.game = None
        self.frames_since_enemy = 0
        self.explore_forward_steps = 0
        self.explore_turn_direction = 1
        self.explore_strafe_direction = 1  # For varied exploration
        self.last_kill_count = 0
        self.frames_since_last_kill = 0
        self.stuck_on_enemy_steps = 0
        self.mapper = AutomapMapper()
        self.target_cell = None
        self.explore_path = []
        self.exploration_phase = 0  # 0=forward, 1=strafe, 2=turn sweep
        
    def initialize_game(self):
        self.game = vzd.DoomGame()
        self.game.load_config(self.config_path)

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
        logger.info(f"Game initialized with WAD: {self.wad_path}")
        
    def get_state_info(self, state):
        if state is None:
            return None
            
        game_vars = state.game_variables
        screen = state.screen_buffer
        labels = state.labels if hasattr(state, 'labels') else []
        
        if game_vars is None or len(game_vars) == 0:
            return None

        # doom/doom.cfg game var order:
        # HEALTH, AMMO2, KILLCOUNT, POSITION_X, POSITION_Y, ANGLE
        health = float(game_vars[0]) if len(game_vars) > 0 else 100.0
        ammo = float(game_vars[1]) if len(game_vars) > 1 else 0.0
        kills = int(game_vars[2]) if len(game_vars) > 2 else 0
        pos_x = float(game_vars[3]) if len(game_vars) > 3 else 0.0
        pos_y = float(game_vars[4]) if len(game_vars) > 4 else 0.0
        angle = float(game_vars[5]) if len(game_vars) > 5 else 0.0

        info = {
            "health": health,
            "ammo": ammo,
            "kills": kills,
            "pos_x": pos_x,
            "pos_y": pos_y,
            "angle": angle,
            "screen": screen,
            "labels": labels,
        }
        
        return info
    
    def detect_enemies_from_labels(self, labels):
        if not labels:
            return None
        
        enemies = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            name_lower = name.lower()
            is_enemy = any(k in name_lower for k in ENEMY_KEYWORDS)
            is_not_dead = "dead" not in name_lower and "gibbe" not in name_lower
            
            if is_enemy and is_not_dead:
                cx = lbl.x + lbl.width / 2
                cy = lbl.y + lbl.height / 2
                area = lbl.width * lbl.height
                
                if area > 80:
                    enemies.append({
                        'x': cx,
                        'y': cy,
                        'area': area,
                        'name': lbl.object_name
                    })
        
        if enemies:
            enemies.sort(key=lambda e: e['area'], reverse=True)
            enemy = enemies[0]
            return (int(enemy['x']), int(enemy['y']), min(enemy['area'] / 2000.0, 1.0))
        
        return None

    def count_enemies_from_labels(self, labels):
        if not labels:
            return 0
        count = 0
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            name_lower = name.lower()
            if any(k in name_lower for k in ENEMY_KEYWORDS):
                count += 1
        return count
    
    def find_priority_target_on_screen(self, labels, health, ammo):
        """Find the most important label on screen to navigate toward."""
        if not labels:
            return None
        
        targets = []
        for lbl in labels:
            name = getattr(lbl, "object_name", "") or ""
            name_lower = name.lower()
            
            # Skip player and weapons
            if "player" in name_lower or "weapon" in name_lower:
                continue
            
            # Check priority
            priority = 0
            for keyword, score in PRIORITY_LABELS.items():
                if keyword in name_lower:
                    priority = max(priority, score)
                    break
            
            if priority > 0:
                cx = lbl.x + lbl.width / 2
                cy = lbl.y + lbl.height / 2
                targets.append({
                    "x": cx,
                    "y": cy,
                    "name": name,
                    "priority": priority,
                })
        
        if targets:
            # Sort by priority (higher first)
            targets.sort(key=lambda t: t["priority"], reverse=True)
            target = targets[0]
            return (int(target["x"]), int(target["y"]), target["name"])
        
        return None
    
    def navigate_toward_screen_target(self, target_x, screen_width, screen_center_x):
        """Return action to navigate toward a target on screen."""
        offset = target_x - screen_center_x
        abs_offset = abs(offset)
        
        if abs_offset < 40:
            # Target centered, move toward it
            return [1, 0, 0, 0, 0, 0, 0]
        elif offset > 40:
            # Target on right
            if abs_offset > 100:
                return [0, 0, 1, 0, 0, 0, 0]  # Turn right
            else:
                return [1, 0, 1, 0, 0, 0, 0]  # Forward + turn right
        else:
            # Target on left
            if abs_offset > 100:
                return [0, 1, 0, 0, 0, 0, 0]  # Turn left
            else:
                return [1, 1, 0, 0, 0, 0, 0]  # Forward + turn left
    
    def _find_frontier_cells(self, walkable):
        """Find frontier cells (walkable cells on map edge or near unexplored areas)."""
        if walkable.sum() == 0:
            return None
        
        # Get walkable boundary
        from scipy import ndimage
        edges = ndimage.binary_erosion(walkable, iterations=1)
        frontier = walkable & ~edges
        
        frontier_cells = np.argwhere(frontier)
        return frontier_cells if len(frontier_cells) > 0 else None
    
    def _navigate_to_frontier(self, frontier_cells):
        """Navigate toward frontier. Simple: just turn and move toward frontier."""
        # Frontier cells are mostly at right side = turn right, left side = turn left
        if len(frontier_cells) == 0:
            return [1, 0, 0, 0, 0, 0, 0]
        
        # Get average frontier position
        avg_row, avg_col = frontier_cells.mean(axis=0)
        map_center = frontier_cells.max() // 2
        
        if avg_col > map_center + 10:
            return [1, 0, 1, 0, 0, 0, 0]  # Forward + turn right
        elif avg_col < map_center - 10:
            return [1, 1, 0, 0, 0, 0, 0]  # Forward + turn left
        else:
            return [1, 0, 0, 0, 0, 0, 0]  # Just forward
    
    def decide_action(self, state_info, automap_buffer=None):
        if state_info is None:
            return [1, 0, 0, 0, 0, 0, 0]

        health = state_info['health']
        ammo = state_info['ammo']
        kills = state_info['kills']
        screen = state_info['screen']
        labels = state_info.get('labels', [])
        
        screen_width = screen.shape[1]
        screen_center_x = screen_width // 2
        
        # ===== COMBAT: FIND & KILL ENEMIES =====
        enemy_detection = self.detect_enemies_from_labels(labels)
        
        if enemy_detection is not None:
            self.frames_since_enemy = 0
            
            if len(enemy_detection) == 3:
                enemy_x, enemy_y, confidence = enemy_detection
            else:
                enemy_x, enemy_y = enemy_detection
            
            offset = enemy_x - screen_center_x
            abs_offset = abs(offset)
            
            # PROVEN AIMING - DO NOT CHANGE
            if ammo > 0:
                # CENTERED: Pure attack
                if abs_offset < 25:
                    return [0, 0, 0, 0, 0, 1, 0]
                # RIGHT: Turn right and attack
                elif offset > 25:
                    if abs_offset > 80:
                        return [0, 0, 1, 0, 0, 1, 0]  # Strong turn
                    else:
                        return [1, 0, 1, 0, 0, 1, 0]  # Forward + turn right + attack
                # LEFT: Turn left and attack
                else:
                    if abs_offset > 80:
                        return [0, 1, 0, 0, 0, 1, 0]  # Strong turn
                    else:
                        return [1, 1, 0, 0, 0, 1, 0]  # Forward + turn left + attack
            else:
                # No ammo, just approach
                if offset > 25:
                    return [1, 0, 1, 0, 0, 0, 0]
                elif offset < -25:
                    return [1, 1, 0, 0, 0, 0, 0]
                else:
                    return [1, 0, 0, 0, 0, 0, 0]
        
        self.frames_since_enemy += 1
        
        # ===== SURVIVAL: CRITICAL HEALTH =====
        if health < 30:
            if self.frames_since_enemy % 2 == 0:
                return [0, 0, 0, 1, 0, 0, 0]
            else:
                return [0, 0, 0, 0, 1, 0, 0]
        
        # ===== GRAB ITEMS ON SCREEN =====
        priority_target = self.find_priority_target_on_screen(labels, health, ammo)
        if priority_target is not None:
            target_x, target_y, target_name = priority_target
            return self.navigate_toward_screen_target(target_x, screen_width, screen_center_x)
        
        # ===== DEFAULT: PATHSEEKING WITH AUTOMAP =====
        # Use automap to find unexplored areas and navigate to them
        if automap_buffer is not None:
            # Find frontier (unexplored/unexplored edges)
            automap = automap_buffer[..., :3]  # RGB channels
            
            # Walls are bright, floors are dark
            walkable = np.mean(automap, axis=2) < 150
            explored = np.sum(walkable) > 0
            
            if explored:
                # Find frontier cells (walkable near walls or edges)
                frontier = self._find_frontier_cells(walkable)
                
                if frontier is not None and len(frontier) > 0:
                    # Navigate toward frontier
                    return self._navigate_to_frontier(frontier)
        
        # FALLBACK: Random exploration pattern
        if self.explore_forward_steps <= 0:
            self.explore_forward_steps = 20
            self.explore_turn_direction = 1 if random.random() < 0.5 else -1
        
        self.explore_forward_steps -= 1
        
        # More aggressive turning
        if self.explore_forward_steps % 4 == 0:
            if self.explore_turn_direction > 0:
                return [1, 0, 1, 0, 0, 0, 0]
            else:
                return [1, 1, 0, 0, 0, 0, 0]
        
        return [1, 0, 0, 0, 0, 0, 0]
    
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
        
        self.frames_since_enemy = 0
        self.explore_forward_steps = 0
        self.explore_turn_direction = 1
        self.last_kill_count = 0
        self.frames_since_last_kill = 0
        self.stuck_on_enemy_steps = 0
        self.target_cell = None
        self.explore_path = []
        
        start_time = time.time()
        
        frame_count = 0
        max_steps = int(self.episode_timeout * 35)
        
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
            initial_kills = int(gv0[2]) if len(gv0) > 2 else 0
        else:
            initial_health = 100.0
            initial_ammo = 0.0
            initial_kills = 0
        
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
                
                stats["kills"] = current_kills - initial_kills
                stats["health_lost"] = max(0.0, initial_health - current_health)
                stats["ammo_used"] = max(0.0, initial_ammo - current_ammo)
                
                automap_buffer = state.automap_buffer if hasattr(state, "automap_buffer") else None
                action = self.decide_action(state_info, automap_buffer)
                
                action_names = ["FORWARD", "LEFT_TURN", "RIGHT_TURN", "MOVE_LEFT", "MOVE_RIGHT", "ATTACK", "USE"]
                active_actions = [action_names[i] for i, a in enumerate(action) if a == 1]
                
                if frame_count % 20 == 0:
                    lbls = state_info.get("labels", [])
                    n_enemies = self.count_enemies_from_labels(lbls)
                    
                    # Log all unique label names seen
                    label_names = set()
                    for lbl in lbls:
                        name = getattr(lbl, "object_name", "") or ""
                        if name:
                            label_names.add(name)
                    
                    logger.info(
                        f"Step {stats['actions_taken']}: "
                        f"Health={current_health:.0f} Ammo={current_ammo:.0f} "
                        f"Kills={stats['kills']} "
                        f"Enemies={n_enemies} "
                        f"Labels={sorted(label_names) if label_names else 'None'}"
                    )
                
                reward = self.game.make_action(action, 4)
                stats["episode_reward"] += float(reward)
                stats["actions_taken"] += 1
                frame_count += 1
                
                elapsed = time.time() - start_time
                if elapsed >= self.episode_timeout:
                    break
                
                if frame_count >= max_steps:
                    break
                    
            except Exception as e:
                logger.error(f"Error during episode: {e}")
                break
        
        stats["episode_time"] = time.time() - start_time
        
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
    seconds = 10

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
    agent = DoomAgent(wad_file, episode_timeout=seconds)
    agent.initialize_game()
    stats = agent.run_episode()
    agent.close()

    results_file = log_dir / "last_run.json"
    with open(results_file, "w") as f:
        json.dump(stats, f, indent=2)
