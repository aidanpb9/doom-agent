"""Manage mission progress and graph state. Own the node graph.
Know which nodes are current, next, and goal.
Decide when a node is reached. Knows about NodeTypes."""
from core.navigation.graph import Node, NodeType, Graph
from core.navigation.navigation_engine import NavigationEngine
from core.execution.game_state import GameState
from core.execution.action_decoder import ActionDecoder
from core.utils import calculate_euclidean_distance
from config.constants import (ACTION_USE, DOOR_USE_COOLDOWN, 
    NODE_PROXIMITY, LOOT_NODE_MAX_DISTANCE, DOOR_USE_DISTANCE, 
    LOOT_PROXIMITY, TICK, HEALTH_KEYWORDS, ARMOR_KEYWORDS, AMMO_KEYWORDS,
    WEAPON_KEYWORDS)
import json
from pathlib import Path
from collections import deque


class PathTracker:

    def __init__(self, graph: Graph, nav_engine: NavigationEngine):
        self.graph = graph
        self.nav_engine = nav_engine
        self.cur_path = deque()
        self.last_node = None
        self.next_node = None
        self.goal_node = None
        self.visited_waypoints = set()
        self.door_use_timer = 0
        #For seeing if stats increase to remove accidentally claimed loot nodes
        self.prev_health = 0 
        self.prev_armor = 0
        self.prev_ammo = 0

    def load_static_nodes(self, map_name: str) -> None:
        """Load nodes from maps/JSON file made by pre-processing tool into self.graph.
        What the json structure should look like:
        {
        "wad": "wads/doom1.wad",
        "map": "E1M1",
        "node_points": [
            {"x": 564.1, "y": 604.5, "type": "waypoint", "special": null},
            {"x": 100.0, "y": 200.0, "type": "door", "special": 1},
            {"x": 300.0, "y": 400.0, "type": "exit", "special": 11}
        ],
        "edges": [
            [0, 1],
            [1, 2]
        ]
        }
        """
        path = Path(f"maps/json/{map_name}.json")
        with open(path) as f:
            data = json.load(f)

            #build nodes first so edges can reference by index
            nodes = []
            for point in data["node_points"]:
                node_type = NodeType[point["type"].upper()]
                node = Node(point["x"], point["y"], node_type, special=point.get("special"), is_static=True)
                self.graph.add_node(node)
                nodes.append(node)
            
            for i, j in data["edges"]:
                self.graph.add_edge(nodes[i], nodes[j])

    def update(self, gamestate: GameState) -> None:
        """Called by StateMachine every tick to update nodes and door_use_timer."""
        #Update door timer
        self.door_use_timer = max(0, self.door_use_timer - TICK)
        
        #Update path if needed
        if self.goal_node and not self.cur_path:
            self._set_cur_path()

        #If we're close to next node in path, update next_node
        if self.next_node and self._has_reached_node(gamestate, self.next_node):
            self._get_next_node(gamestate)
        
        #Place loot nodes, remove accidentally visited ones
        if gamestate.loots_visible:
            self._place_node(gamestate)
        self._cleanup_incidental_node(gamestate)

    def get_next_move(self, x: float, y: float, angle: float) -> list[int]:
        """Handle door_use_timer reset after a USE action.
        StateMachine calls this from TRAVERSE/RECOVER, which calls nav_engine.step_toward()."""
        if not self.next_node:
            return ActionDecoder.null_action()
        
        action = self.nav_engine.step_toward(x, y, angle, self.next_node, self.door_use_timer)

        if action[ACTION_USE]:
            self.door_use_timer = DOOR_USE_COOLDOWN
        return action

    def set_goal_by_type(self, gamestate: GameState, node_type: NodeType, keywords: set[str] | None = None) -> None:
        """Find and set the goal node according to current state."""
        goal_node = None
        if node_type == NodeType.EXIT:
            for node in self.graph.nodes:
                if node.node_type == NodeType.EXIT:
                    goal_node = node
        elif node_type == NodeType.LOOT:
            goal_node = self._nearest_node(gamestate, keywords)

        if not goal_node:
            return
        
        self.goal_node = goal_node
        self._set_cur_path()

    def has_loot_node(self, keywords: set[str]) -> bool:
        """Check if a loot type is known in the graph."""
        for node in self.graph.nodes:
            if node.node_type == NodeType.LOOT and node.name in keywords:
                return True
        return False
    
    def _set_cur_path(self) -> None:
        """Update cur_path by calling nav_engine.make_path()."""
        self.cur_path = self.nav_engine.make_path(self.last_node, self.goal_node)

    def _has_reached_node(self, gamestate: GameState, target_node: Node) -> bool:
        """Return True when a node is close. Different nodes have different thresholds
        which this accounts for, so the function is reusable."""
        distance_to_target = calculate_euclidean_distance(
            gamestate.pos_x, gamestate.pos_y, target_node.x, target_node.y)
        
        #If target_node is DOOR, don't update next_node until we're sure that we used the door.
        if target_node.node_type == NodeType.DOOR:
            if self.door_use_timer > 0 and distance_to_target < DOOR_USE_DISTANCE:
                return True
        elif distance_to_target < NODE_PROXIMITY:
            return True
        return False

    def _get_next_node(self, gamestate: GameState) -> Node:
        """When current next_node is reached, replace it with a new one and update last node."""
        #Loot nodes are only goal nodes in RECOVER. After pickup, SM sets a new goal
        #which triggers _set_cur_path automatically via set_goal_node.
        if self.next_node is None:
            self.next_node = self.cur_path.popleft()
            return self.next_node

        
        if self.next_node.node_type == NodeType.LOOT:
            #handles when goal node is loot and we want to remove it after claiming
            self.graph.remove_node(self.next_node)
            self.last_node = self._nearest_node(gamestate)
            self.next_node = None
        else:
            self.last_node = self.next_node
            if self.last_node and self.last_node.is_static and self.last_node.node_type == NodeType.WAYPOINT:
                if self.last_node not in self.visited_waypoints:
                    self.visited_waypoints.add(self.last_node)
            if self.cur_path:
                self.next_node = self.cur_path.popleft()
        return self.next_node

    def _place_node(self, gamestate: GameState) -> None:
        "Add dynamic LOOT and WAYPOINT nodes to the graph."
        for loot in gamestate.loots_visible:
            #Check if loot is already marked as a node
            is_loot_marked = False
            for node in self.graph.nodes:
                if node.node_type == NodeType.LOOT:
                    distance = calculate_euclidean_distance(loot.pos_x, loot.pos_y, node.x, node.y)
                    if distance < LOOT_PROXIMITY:
                        is_loot_marked = True
                        loot_node = node
                        break
            
            #If loot not marked, add waypoint and loot nodes to graph if in range
            if not is_loot_marked:
                loot_node = Node(loot.pos_x, loot.pos_y, NodeType.LOOT, loot.name)
                #check if loot in max marking range (see GA param)
                is_in_range = calculate_euclidean_distance(gamestate.pos_x, gamestate.pos_y, loot_node.x, loot_node.y) < LOOT_NODE_MAX_DISTANCE
                if is_in_range:
                    self.graph.add_node(loot_node)
                    self._make_anchor(gamestate, loot_node)

            #If loot marked, update its connection if shorter distance exists.
            #But only if that shorter distance doesn't occur while on the way to the loot node.
            #Don't need to check is_in_range here, since we check old_distance which already passes.
            elif loot_node is not self.next_node:
                neighbors = self.graph.get_neighbors(loot_node)
                if not neighbors:
                    continue

                old_anchor = neighbors[0] #loot nodes only have 1 neighbor, its anchor
                old_distance = self.graph.get_edge(loot_node, old_anchor).length
                new_distance = calculate_euclidean_distance(
                    gamestate.pos_x, gamestate.pos_y, loot_node.x, loot_node.y)
                
                if new_distance < old_distance:
                    self.graph.remove_edge(old_anchor, loot_node)
                    self.graph.remove_node(old_anchor)
                    self._make_anchor(gamestate, loot_node)

    def _make_anchor(self, gamestate: GameState, loot_node: Node) -> None:
        """Make an "anchor" node of agent's current position and inserts it into Graph.
        Add edges between this anchor node and last, next, and loot.
        Make this anchor the last_node."""
        waypoint_node = Node(gamestate.pos_x, gamestate.pos_y, NodeType.WAYPOINT)
        if self.next_node is None:
            return
        
        self.graph.add_node(waypoint_node)
        self.graph.remove_edge(self.last_node, self.next_node)
        self.graph.add_edge(loot_node, waypoint_node)
        self.graph.add_edge(self.last_node, waypoint_node)
        self.graph.add_edge(waypoint_node, self.next_node)
        self.last_node = waypoint_node

    def _nearest_node(self, gamestate: GameState, keywords: set[str] | None = None) -> Node:
        """Find the closest node in the graph to agent's position.
        Used when initializing episode to populate self.last_node,
        when removing loot nodes after reaching them to give the
        agent a more accurate node to start its new path, and when finding 
        closest loot nodes for updating the goal node in RECOVER state.
        A limitation is that this could choose unreachable nodes in some cases (thru wall)."""
        best_match = None
        best_match_distance = float('inf')

        for node in self.graph.nodes:
            distance = calculate_euclidean_distance(gamestate.pos_x, gamestate.pos_y, node.x, node.y)
            
            if keywords:
                if node.name in keywords and distance < best_match_distance:
                    best_match = node
                    best_match_distance = distance
            elif distance < best_match_distance:
                best_match = node
                best_match_distance = distance
        return best_match 
    
    def _cleanup_incidental_node(self, gamestate: GameState) -> None:
        """If agent stats increase, it must have picked up loot that wasn't intended 
        by pathtracker. Remove these nodes so agent doesn't think it still exists."""
        health_gained = gamestate.health > self.prev_health
        armor_gained = gamestate.armor > self.prev_armor
        ammo_gained = gamestate.ammo > self.prev_ammo
        
        for node in list(self.graph.nodes): #use list here since we're removing nodes
            if node.node_type != NodeType.LOOT or node is self.next_node:
                continue
            dist = calculate_euclidean_distance(gamestate.pos_x, gamestate.pos_y, node.x, node.y)
            if dist > NODE_PROXIMITY:
                continue
            if ((node.name in HEALTH_KEYWORDS and health_gained) or
                (node.name in ARMOR_KEYWORDS and armor_gained) or
                (node.name in (AMMO_KEYWORDS | WEAPON_KEYWORDS) and ammo_gained)):
                self.graph.remove_node(node)
        
        self.prev_health = gamestate.health
        self.prev_armor = gamestate.armor
        self.prev_ammo = gamestate.ammo

        