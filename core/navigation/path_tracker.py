"""Manages mission progress and graph state. Owns the node graph.
Knows which nodes are current, next, and goal.
Decides when a node is reached. Knows about NodeTypes."""
from core.navigation.graph import Node, NodeType
from core.utils import calculate_euclidean_distance
from config.constants import (ACTION_USE, DOOR_USE_COOLDOWN, 
    NODE_PROXIMITY, DOOR_USE_DISTANCE, LOOT_PROXIMITY, TICK)
import json
from pathlib import Path
from collections import deque


class PathTracker:

    def __init__(self, graph, nav_engine):
        self.graph = graph
        self.nav_engine = nav_engine
        self.cur_path = deque()
        self.last_node = None
        self.next_node = None
        self.goal_node = None
        self.visited_waypoints = set()
        self.door_use_timer = 0

    def update(self, gamestate) -> None:
        """Called by StateMachine every tick to update nodes and door_use_timer."""
        if self.goal_node and not self.cur_path:
            self.set_cur_path()
        
        self.door_use_timer = max(0, self.door_use_timer - TICK)

        #If we're close to next node in path, update next_node
        if self.next_node and self._has_reached_node(gamestate, self.next_node):
            self._get_next_node()
        
        if gamestate.loots_visible:
            self._place_node(gamestate)

    def get_next_move(self, x, y, angle) -> list[int]:
        """StateMachine calls this, which calls nav_engine.step_toward().
        Handles door_use_timer after a USE action."""
        action = self.nav_engine.step_toward(x, y, angle, self.next_node, self.door_use_timer)
        if action[ACTION_USE]:
            self.door_use_timer = DOOR_USE_COOLDOWN
        return action

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
        path = Path(f"maps/{map_name}.json")
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

    def set_goal_node(self, node: Node) -> None:
        """Called by StateMachine."""
        self.goal_node = node

    def _set_cur_path(self) -> None:
        """Updates cur_path by calling nav_engine.make_path()."""
        self.cur_path = self.nav_engine.make_path(self.last_node, self.goal_node)

    def _has_reached_node(self, gamestate, target_node) -> bool:
        """When a node is close, return True. Different nodes have different thresholds
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

    def _get_next_node(self) -> Node:
        """When current next_node is reached, replace it with a new one. Update last node."""
        if (self.next_node not in self.visited_waypoints and 
            self.next_node.is_static and 
            self.next_node.node_type == NodeType.WAYPOINT
        ):
            self.visited_waypoints.add(self.next_node)
            
        self.last_node = self.next_node
        if self.cur_path:
            self.next_node = self.cur_path.popleft()
        return self.next_node

    def _place_node(self, gamestate) -> None:
        "Adds dynamic LOOT and WAYPOINT nodes to the graph."
        for loot in gamestate.loots_visible:
            #Check if loot is already marked as a node
            is_loot_marked = False
            for node in self.graph.nodes:
                if node.node_type == NodeType.LOOT:
                    distance = calculate_euclidean_distance(loot.x, loot.y, node.x, node.y)
                    if distance < LOOT_PROXIMITY:
                        is_loot_marked = True
                        loot_node = node
                        break
            
            #If loot not marked, add waypoint and loot nodes to graph
            if not is_loot_marked:
                loot_node = Node(loot.x, loot.y, NodeType.LOOT, name=loot.name)
                self.graph.add_node(loot_node)
                self._make_anchor(gamestate, loot_node)

            #If loot marked, update its connection if shorter distance exists.
            #Only do update if on the main path (next_node is not loot), this avoids errors where
            #we get an unfairly close edge between waypoint and loot that won't ever be taken from main path.
            elif self.next_node.node_type != NodeType.LOOT:
                old_anchor = self.graph.get_neighbors(loot_node)[0] #loot nodes only have 1 neighbor, its anchor
                old_distance = self.graph.get_edge(loot_node, old_anchor).length
                new_distance = calculate_euclidean_distance(
                    gamestate.pos_x, gamestate.pos_y, loot_node.x, loot_node.y)
                
                if new_distance < old_distance:
                    self.graph.remove_edge(old_anchor, loot_node)
                    self._make_anchor(gamestate, loot_node)

    def _make_anchor(self, gamestate, loot_node) -> None:
        """Makes an "anchor" node of agent's current position and inserts it into Graph.
        Adds edges between this anchor node and last, next, and loot.
        Makes this anchor the last_node."""
        waypoint_node = Node(gamestate.pos_x, gamestate.pos_y, NodeType.WAYPOINT)
        self.graph.add_node(waypoint_node)
        self.graph.remove_edge(self.last_node, self.next_node)
        self.graph.add_edge(loot_node, waypoint_node)
        self.graph.add_edge(self.last_node, waypoint_node)
        self.graph.add_edge(waypoint_node, self.next_node)
        self.last_node = waypoint_node


