"""Manage mission progress and graph state. Own the node graph.
Know which nodes are current, next, and goal.
Decide when a node is reached. Knows about NodeTypes."""
from core.navigation.graph import Node, NodeType, Graph
from core.navigation.navigation_engine import NavigationEngine
from core.execution.game_state import GameState
from core.execution.action_decoder import ActionDecoder
from core.utils import calculate_euclidean_distance, has_clear_world_line, point_to_segment_distance
from config.constants import (DOOR_USE_COOLDOWN, 
    NODE_PROXIMITY, LOOT_NODE_MAX_DISTANCE, DOOR_USE_DISTANCE, 
    LOOT_PROXIMITY, TICK, HEALTH_KEYWORDS, ARMOR_KEYWORDS, AMMO_KEYWORDS,
    WEAPON_KEYWORDS, ANCHOR_MIN_WALL_DISTANCE, STUCK_CHECK_INTERVAL, LOOT_NODE_COOLDOWN,
    STUCK_DISTANCE_THRESHOLD)
import json
from pathlib import Path
from collections import deque


class PathTracker:

    def __init__(
        self, 
        graph: Graph, 
        nav_engine: NavigationEngine, 
        blocking_segments: list[tuple[float, float, float, float]]
    ):
        self.graph = graph
        self.nav_engine = nav_engine
        self.cur_path = deque() #ordered deque of nodes from last_node to goal_node
        self.last_node = None #most recently reached node, A* starts from here
        self.next_node = None #immediate navigation target, the next node in cur_path
        self.goal_node = None #destination node for current state (EXIT or LOOT)
        self.visited_waypoints = set() #static waypoints reached, used for GA fitness
        self.door_use_timer = 0 #cooldown after USE action to prevent door spam
        self.blocking_segments = blocking_segments #improve node placing by adding map objects to geometry
        self.loot_blacklist = {} #(x, y) -> ticks remaining; prevents re-marking loot that was removed as unreachable
        self.stuck_timer = 0 #ticks elapsed since last stuck check
        self.stuck_last_pos = (0.0, 0.0) #agent position at last stuck check, compared against current pos
        self.is_stuck = False #set True when non-LOOT stuck fires, consumed by StateMachine
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
        
        #Expire loot blacklist entries each tick. Position is clear to re-mark once it hits 0.
        active_cooldowns = {}
        for pos, ticks in self.loot_blacklist.items():
            remaining = ticks - TICK
            if remaining > 0:
                active_cooldowns[pos] = remaining
        self.loot_blacklist = active_cooldowns

        #If agent hasn't moved enough, the current goal is likely unreachable. For loot nodes, 
        #remove and cooldown so they can be re-marked from a better position. For other goals, trigger stuck recovery.
        self.stuck_timer += TICK
        if self.stuck_timer >= STUCK_CHECK_INTERVAL:
            dist_moved = calculate_euclidean_distance(
                gamestate.pos_x, gamestate.pos_y,
                self.stuck_last_pos[0], self.stuck_last_pos[1])
            
            if dist_moved < STUCK_DISTANCE_THRESHOLD and self.goal_node:
                if self.goal_node.node_type == NodeType.LOOT:
                    self.loot_blacklist[(self.goal_node.x, self.goal_node.y)] = LOOT_NODE_COOLDOWN
                    self.graph.remove_node(self.goal_node)
                else:
                    self.is_stuck = True
                self.last_node = self._nearest_node(gamestate, static_only=True)
                self.goal_node = None
                self.next_node = None
                self.cur_path = deque()
            self.stuck_timer = 0
            self.stuck_last_pos = (gamestate.pos_x, gamestate.pos_y)

        #Update path if needed
        if self.goal_node and not self.cur_path:
            self._set_cur_path()

        #next_node can be None after loot collection (_get_next_node sets it to None on loot pickup).
        #When that happens, the proximity check below never fires (guarded by self.next_node),
        #so we need to explicitly repopulate next_node from cur_path here.
        if not self.next_node and self.cur_path:
            self._get_next_node(gamestate)
        elif self.next_node and self._has_reached_node(gamestate, self.next_node):
            self._get_next_node(gamestate)
        
        #Place loot nodes, remove accidentally visited ones
        if gamestate.loots_visible:
            self._place_node(gamestate)
        self._cleanup_incidental_node(gamestate)

    def get_next_move(self, x: float, y: float, angle: float) -> list[int]:
        """Return movement action toward next_node. Fires USE on nearby doors and the exit."""
        if not self.next_node:
            return ActionDecoder.null_action()
        
        action = self.nav_engine.step_toward(x, y, angle, self.next_node)

        #Do USE on any nearby door regardless of nav target, handles doors that closed during combat
        #and were already consumed from cur_path. EXIT is intentional only, fire when it's next_node
        #to avoid exiting the level early while collecting loot nearby.
        if not self.door_use_timer:
            for node in self.graph.nodes:
                if node.node_type == NodeType.DOOR:
                    if calculate_euclidean_distance(x, y, node.x, node.y) < DOOR_USE_DISTANCE:
                        action = ActionDecoder.combine(action, ActionDecoder.use())
                        self.door_use_timer = DOOR_USE_COOLDOWN
                        break
                elif node.node_type == NodeType.EXIT and node is self.next_node:
                    if calculate_euclidean_distance(x, y, node.x, node.y) < DOOR_USE_DISTANCE:
                        action = ActionDecoder.combine(action, ActionDecoder.use())
                        self.door_use_timer = DOOR_USE_COOLDOWN
                        break
        return action

    def set_goal_by_type(self, gamestate: GameState, node_type: NodeType, keywords: set[str] | None = None) -> None:
        """Find and set the goal node according to current state."""
        goal_node = None

        #Either set goal as EXIT or LOOT. If exit, we have to do a linear scan
        #here to find it, hence the repeated node_type EXIT check.
        if node_type == NodeType.EXIT:
            for node in self.graph.nodes:
                if node.node_type == NodeType.EXIT:
                    goal_node = node
        elif node_type == NodeType.LOOT:
            goal_node = self._nearest_node(gamestate, keywords, static_only=False)
        
        #Avoid rebuilding cur_path every tick — only replans when goal actually changes.
        #Rebuilding every tick re-inserts the current next_node into cur_path, causing
        #navigation to an already-consumed node.
        if not goal_node or goal_node is self.goal_node:
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
        
        #make_path returns None only if start or goal node has no neighbors
        if self.cur_path is None:
            goal_neighbors = self.graph.get_neighbors(self.goal_node)
            last_neighbors = self.graph.get_neighbors(self.last_node)
            msg = f"make_path failed: ({self.last_node.x:.0f},{self.last_node.y:.0f}) neighbors={len(last_neighbors)} -> ({self.goal_node.x:.0f},{self.goal_node.y:.0f}) neighbors={len(goal_neighbors)}"
            raise RuntimeError(msg)

        #Immediately populate next_node if None to avoid a one-tick gap when
        #_set_cur_path is called from set_goal_by_type after update has already run.
        if not self.next_node:
            if self.cur_path:
                self.next_node = self.cur_path.popleft()
            else:
                self.next_node = self.goal_node

    def _has_reached_node(self, gamestate: GameState, target_node: Node) -> bool:
        """Return True when a node is close. Different nodes have different thresholds
        which this accounts for, so the function is reusable."""
        distance_to_target = calculate_euclidean_distance(
            gamestate.pos_x, gamestate.pos_y, target_node.x, target_node.y)
        
        #If target_node is DOOR, don't update next_node until we're sure that we used the door.
        if target_node.node_type in (NodeType.DOOR, NodeType.EXIT):
            if self.door_use_timer > 0 and distance_to_target < DOOR_USE_DISTANCE:
                return True
        elif distance_to_target < NODE_PROXIMITY:
            return True
        return False

    def _get_next_node(self, gamestate: GameState) -> Node | None:
        """When current next_node is reached, replace it with a new one and update last node."""
        #Loot nodes are only goal nodes in RECOVER. After pickup, SM sets a new goal
        #which triggers _set_cur_path automatically via set_goal_by_type.
        if self.next_node is None:
            self.next_node = self.cur_path.popleft()
            return self.next_node

        if self.next_node.node_type == NodeType.LOOT:
            #After claiming loot, fully reset nav state so StateMachine sets a 
            #fresh goal next tick. Otherwise, goal_node still points to removed loot node,
            #and make_path will fail trying to reach a node no longer in the graph.
            self.graph.remove_node(self.next_node)
            self.last_node = self._nearest_node(gamestate, static_only=True)
            self.next_node = None
            self.goal_node = None
            self.cur_path = deque()
        else:
            self.last_node = self.next_node
            if self.last_node and self.last_node.is_static and self.last_node.node_type == NodeType.WAYPOINT:
                if self.last_node not in self.visited_waypoints:
                    self.visited_waypoints.add(self.last_node)
            if self.cur_path:
                self.next_node = self.cur_path.popleft()
        return self.next_node

    def _place_node(self, gamestate: GameState) -> None:
        """Add dynamic LOOT and WAYPOINT nodes to the graph."""
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
                #next_node is required to anchor the loot node into the graph. Without it,
                #_make_anchor returns early and the loot node is added with no edges (unreachable).
                #It will be picked up on a future tick once next_node is repopulated.
                is_in_range = calculate_euclidean_distance(gamestate.pos_x, gamestate.pos_y, loot_node.x, loot_node.y) < LOOT_NODE_MAX_DISTANCE
                is_clear_path = has_clear_world_line(gamestate.pos_x, gamestate.pos_y, loot_node.x, loot_node.y, self.blocking_segments)
                
                #Don't mark loot if the anchor would be placed too close to a wall.
                #Anchors are created at the agent's current position — if that position is
                #wall-adjacent (e.g. near a candle next to a wall), every future path to
                #this loot routes through that tight spot and the agent gets stuck.
                #The loot will be marked on a future tick from a safer position.
                too_close_to_wall = self.blocking_segments and any(
                    point_to_segment_distance(gamestate.pos_x, gamestate.pos_y, x1, y1, x2, y2) < ANCHOR_MIN_WALL_DISTANCE
                    for x1, y1, x2, y2 in self.blocking_segments
                )

                #Skip loot that was recently removed due to being unreachable, agent will reposition
                in_cooldown = any(
                    calculate_euclidean_distance(loot.pos_x, loot.pos_y, cx, cy) < LOOT_PROXIMITY
                    for cx, cy in self.loot_blacklist) 

                if self.next_node is not None and is_in_range and is_clear_path and not too_close_to_wall and not in_cooldown:
                    self.graph.add_node(loot_node)
                    self._make_anchor(gamestate, loot_node)

            #Anchor update: if agent is now closer to this loot than the existing anchor,
            #replace the anchor with a better one.
            #Don't need to check is_in_range here, since we check old_distance which already passes.
            #Skip anchor update if loot is already the active nav target, about to get it anyways.
            elif loot_node is not self.next_node:
                neighbors = self.graph.get_neighbors(loot_node)
                if not neighbors:
                    continue

                old_anchor = neighbors[0] #loot nodes only have 1 neighbor, its anchor
                old_distance = self.graph.get_edge(loot_node, old_anchor).length
                new_distance = calculate_euclidean_distance(
                    gamestate.pos_x, gamestate.pos_y, loot_node.x, loot_node.y)
                
                #Don't update anchor if next_node is None, _make_anchor returns early without
                #creating a replacement, leaving the loot node isolated with no edges in the graph.
                #Also, skip if old_anchor is actively being navigated. Removing it would corrupt current path.
                if (new_distance < old_distance and self.next_node is not None and 
                    old_anchor is not self.next_node and old_anchor not in self.cur_path):
                    #Reconnect old_anchor's non-loot neighbors before removing it,
                    #so that the chain through old_anchor isn't severed.
                    others = []
                    for n in self.graph.get_neighbors(old_anchor):
                        if n is not loot_node:
                            others.append(n)

                    waypoint_node = Node(gamestate.pos_x, gamestate.pos_y, NodeType.WAYPOINT)
                    self.graph.add_node(waypoint_node)

                    if self.last_node is old_anchor:
                        self.last_node = self._nearest_node(gamestate, static_only=True)

                    self.graph.remove_node(old_anchor) #removes all old_anchor edges
                    self.graph.add_edge(loot_node, waypoint_node)
                    for other in others:
                        self.graph.add_edge(waypoint_node, other)

    def _make_anchor(self, gamestate: GameState, loot_node: Node) -> None:
        """Create a waypoint at the agent's current position and splice it into the graph
        between last_node and next_node, with an edge to loot_node. Updates last_node to this waypoint."""
        waypoint_node = Node(gamestate.pos_x, gamestate.pos_y, NodeType.WAYPOINT)
        if self.next_node is None:
            return
        
        self.graph.add_node(waypoint_node)
        self.graph.add_edge(loot_node, waypoint_node)
        self.graph.add_edge(self.last_node, waypoint_node)
        self.graph.add_edge(waypoint_node, self.next_node)
        self.last_node = waypoint_node

    def _nearest_node(self, gamestate: GameState, keywords: set[str] | None = None, static_only: bool = False) -> Node:
        """Find the closest node in the graph to the agent's position.
        Used when initializing episode to populate self.last_node,
        when removing loot nodes after reaching them to give the
        agent a more accurate node to start its new path, and when finding 
        closest loot nodes for updating the goal node in RECOVER state.
        A limitation is that this could choose unreachable nodes in some cases (thru wall)."""
        best_match = None
        best_match_distance = float('inf')

        for node in self.graph.nodes:
            if static_only and not node.is_static:
                continue

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
            if node.node_type != NodeType.LOOT or node is self.next_node or node is self.goal_node:
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