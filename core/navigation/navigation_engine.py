"""Pure pathfinding and movement. Find paths with A* and produce actions.
Knows nothing about mission state, node types, or progress."""

from core.navigation.graph import Node

class NavigationEngine:

    def __init__(self, graph):
        self.graph = graph
        self.door_use_timer = 0

    def make_path(self, start_node, end_node) -> list[Node]:
        """Given a graph and 2 points, find a path"""
        pass #do A* here (and with helpers ofc)

    def step_toward(self, x, y, angle, target_node) -> list[int]:
        """Given current pos and target point, produce an action"""
        #do update door time logic here
        #do use logic on doors here
        pass