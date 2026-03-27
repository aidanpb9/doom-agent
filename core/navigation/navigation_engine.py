"""Pure pathfinding and movement. Find paths with A* and produce actions.
Know nothing about mission state, node types, or progress."""
from core.navigation.graph import Node, NodeType, Graph
from core.utils import calculate_euclidean_distance, normalize_angle
from core.execution.action_decoder import ActionDecoder
from config.constants import TURN_DEAD_ZONE, DOOR_USE_DISTANCE, FORWARD_ANGLE_THRESHOLD
from math import atan2, degrees
import heapq
from collections import deque


class NavigationEngine:

    def __init__(self, graph: Graph):
        self.graph = graph

    def make_path(self, start_node: Node, end_node: Node) -> deque[Node]:
        """Given a graph and 2 points, find the shortest path. Path guaranteed to exist.
        This is A* implementation. g=actual cost from start, h=straight-line estimate to goal."""
        heap = [] #use priority q to get best scoring neighbor
        closed = set() #to avoid processing nodes we've already seen
        parent = {} #dict to reconstruct path at the end
        g = {start_node: 0} #each node is given a cost so far (sum of edges traversed)
        h = {} #each node has an estimated cost to goal using Euclidean distance 
        counter = 0 #a tiebreaker if node scores are equal so we don't ever compare Node objects

        heapq.heappush(heap, (0.0, counter, start_node)) #push (priority, counter, item)
        while heap:
            _, _, current = heapq.heappop(heap)
            if current is end_node: #reconstruct path and return
                path = []
                cur = end_node
                while cur is not start_node:
                    path.append(cur)
                    cur = parent[cur]
                path.reverse()
                return deque(path)
            
            if current in closed:
                continue
            closed.add(current)

            for neighbor in self.graph.get_neighbors(current):
                if neighbor in closed:
                    continue
                new_g = g[current] + calculate_euclidean_distance(current.x, current.y, neighbor.x, neighbor.y)
                #only update if this is first time we've seen neighbor, or found a cheaper route to neighbor
                if neighbor not in g or new_g < g[neighbor]:
                    g[neighbor] = new_g
                    parent[neighbor] = current
                    h[neighbor] = calculate_euclidean_distance(neighbor.x, neighbor.y, end_node.x, end_node.y)
                    counter += 1
                    f = new_g + h[neighbor]
                    heapq.heappush(heap, (f, counter, neighbor))

    def step_toward(self, x: float, y: float, angle: float, target_node: Node, door_use_timer: int) -> list[int]:
        """Given current pos and target point, produce an action.
        Only use forward, turn left, tur right, or USE."""
        actions = []

        #VizDoom angles: 0=East, 90=North, 180=West, 270=South (tested with temporary script)
        desired = degrees(atan2(target_node.y - y, target_node.x - x)) #where the target is in relation to us
        angle_delta = normalize_angle(desired - angle) #-180 to 180

        if abs(angle_delta) < FORWARD_ANGLE_THRESHOLD:
            actions.append(ActionDecoder.forward()) #always go forward

        if abs(angle_delta) > TURN_DEAD_ZONE:
            if angle_delta > 0:
                actions.append(ActionDecoder.turn_left())
            else:
                actions.append(ActionDecoder.turn_right())
        
        #handling doors
        if not door_use_timer and target_node.node_type in (NodeType.DOOR, NodeType.EXIT):
            distance = calculate_euclidean_distance(x, y, target_node.x, target_node.y)
            if distance < DOOR_USE_DISTANCE:
                actions.append(ActionDecoder.use())

        action = ActionDecoder.combine(*actions)
        return action