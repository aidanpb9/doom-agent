NAV:
curr location is A. goal node starts/ is updated to C. do A* to give us a path of nodes to go through (A B C for example). one function handles just going from A to B, such as turning and going forwards. need last node and next node vars. when we get to B, update last node and next node.

see loot, check if its already marked. if it is, calculate distance from current position to loot and compare to length of current edge from loot to its anchor. If shorter (or if loot not marked), place node, add anchor node in between last and next node, update last node to be current node position, add edge between current node and loot.


class Graph: is the node graph. nodes are objects with position and labels
nodes, edges objects
door and exit info
add_node()
add_edge()


class Navigation Engine: 
pure pathfinding and movement. Given a graph and two points, find a path. Given a current position and a target point, produce an action. Knows nothing about mission state, node types, or progress.

get_next_node()
step_toward() (angle + action to reach next node)
TODO: handle doors and exits, smoothing


class PathTracker: 
mission progress and graph state. Owns the node graph. Knows which node is current, which is next, which is the goal. Decides when a node is "reached." Knows about node types (static, anchor, loot). NavigationEngine asks PathTracker for the graph; PathTracker asks NavigationEngine to plan paths.
current_path

has_reached_node()
plan_path() (do A* here, return list of nodes to traverse)
place_node()
TODO: clear nodes on level reset


