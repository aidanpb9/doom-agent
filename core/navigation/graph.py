"""Core data structure for the navigation node graph.
Node, Edge, and Graph are pure data containers.
No pathfinding or mission logic lives here."""
from enum import Enum
from core.utils import calculate_euclidean_distance


class NodeType(Enum):
    """Represents the different node types of the graph.""" 
    WAYPOINT = 1
    ANCHOR = 2
    LOOT = 3
    DOOR = 4
    EXIT = 5


class Node:
    """A point in the navigation graph with a position, type and optional metadata."""
    def __init__(self, x, y, node_type, name=None, special=None):
        self.x = x
        self.y = y
        self.node_type = node_type
        self.name = name
        self.special = special      


class Edge:
    """An undirected connection between two nodes with a precomputed length."""
    def __init__(self, node1, node2):
        self.node1 = node1
        self.node2 = node2
        self.edge_length = calculate_euclidean_distance(node1.x, node1.y, node2.x, node2.y)


class Graph:
    """Stores the nav node graph as a collection of nodes and edges.
    Pathtracker owns and mutates this. NavigationEngine reads it for pathfinding."""
    def __init__(self):
        self.nodes = [] 
        self.edges = [] 
    
    def add_node(self, node) -> None:
        """Register this node as part of Graph so pathfinding can reach it.
        We simply append it to the list since the list order doesn't determine
        the Graph, the node & edge connection does."""
        self.nodes.append(node)
    
    def add_edge(self, node1, node2) -> None:
        """Record that two nodes are connected."""
        self.edges.append(Edge(node1, node2))

    def get_neighbors(self, node) -> list[Node]:
        """Loop through all edges in the graph. Each edge has 2 nodes.
        If one of those nodes is the input node, we know the other is a neighbor.
        Function used by NavEngine.make_path()."""
        neighbors = []
        for edge in self.edges:
            if edge.node1 is node:
                neighbors.append(edge.node2)
            elif edge.node2 is node:
                neighbors.append(edge.node1)
        return neighbors