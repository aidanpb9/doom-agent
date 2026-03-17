"""Manages mission progress and graph state. Owns the node graph.
Knows which nodes are current, next, and goal.
Decides when a node is reached. Knows about NodeTypes."""

from core.navigation.graph import Node

class PathTracker:

    def __init__(self, graph, nav_engine):
        self.graph = graph
        self.nav_engine = nav_engine
        self.cur_path = []
        self.last_node = None
        self.next_node = None
        self.visited_waypoints = []

    def set_cur_path(self) -> None:
        """Updates cur_path by calling nav_engine.make_path()."""
        pass

    def _get_next_node(self) -> Node:
        """When current next_node is reached, replace it with a new one."""
        pass
    
    def _has_reached_node(self) -> bool:
        """When next_node is close, return True."""
        pass

    def place_node(self) -> None:
        "Adds dynamic nodes to the graph."
        #anchor nodes, loot node logic, duplicate checks, distance threshold
        #creates Node objects, then call graph.add_node()
        pass
    
    def _place_edge(self) -> None:
        """Helper for place_node, private to seperate logic."""
        #creates Edge objects, then call graph.add_edge()
        pass

    def load_static_nodes(self, ) -> None:
        "Load nodes from maps/JSON file made by pre-processing tool into self.graph."
        pass
    
    def update(self, gamestate) -> None:
        """For 1 tic, this is used to update dynamic nodes and last/next nodes. 
        gamestate is passed in from StateMachine. """
        pass
        
    