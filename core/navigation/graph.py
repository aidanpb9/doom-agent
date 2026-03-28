"""Core data structure for the navigation node graph.
Node, Edge, and Graph are pure data containers.
No pathfinding or mission logic lives here."""
from enum import Enum
from core.utils import calculate_euclidean_distance


class NodeType(Enum):
    """Represent the different node types of the graph."""
    WAYPOINT = 1
    LOOT = 2
    DOOR = 3
    EXIT = 4


class Node:
    """A point in the navigation graph with a position, type and optional metadata."""
    def __init__(
        self, 
        x: float, 
        y: float, 
        node_type: NodeType, 
        name: str | None = None, 
        special: int | None = None, 
        is_static: bool = False
    ):
        self.x = x
        self.y = y
        self.node_type = node_type
        self.name = name
        self.special = special   
        self.is_static = is_static


class Edge:
    """An undirected connection between two nodes with a precomputed length."""
    def __init__(self, node1: Node, node2: Node):
        self.node1 = node1
        self.node2 = node2
        self.length = calculate_euclidean_distance(node1.x, node1.y, node2.x, node2.y)


class Graph:
    """Store the nav node graph as a collection of nodes and edges.
    Pathtracker owns and mutates this. NavigationEngine reads it for pathfinding."""
    def __init__(self):
        self.nodes = []
        self.edges = []
    
    def add_node(self, node: Node) -> None:
        """Register this node as part of Graph so pathfinding can reach it.
        We simply append it to the list since the list order doesn't determine
        the Graph, the node & edge connection does."""
        self.nodes.append(node)

    def remove_node(self, node: Node) -> None:
        """Remove a node and all its edges from the graph."""
        self.nodes.remove(node)
        for neighbor in self.get_neighbors(node):
            self.remove_edge(node, neighbor)

    def add_edge(self, node1: Node, node2: Node) -> None:
        """Record that two nodes are connected."""
        self.edges.append(Edge(node1, node2))
    
    def remove_edge(self, node1: Node, node2: Node) -> None:
        """Remove the edge connecting node1 and node2."""
        for edge in self.edges:
            if edge.node1 is node1 and edge.node2 is node2:
                self.edges.remove(edge)
                return
            if edge.node1 is node2 and edge.node2 is node1:
                self.edges.remove(edge)
                return
            
    def get_edge(self, node1: Node, node2: Node) -> Edge | None:
        """Return the edge connecting node1 and node2, or None if not found."""
        for edge in self.edges:
            if edge.node1 is node1 and edge.node2 is node2:
                return edge
            if edge.node1 is node2 and edge.node2 is node1:
                return edge
        return None

    def get_neighbors(self, node: Node) -> list[Node]:
        """Loop through all edges in the graph. Each edge has 2 nodes.
        If one of those nodes is the input node, we know the other is a neighbor."""
        neighbors = []
        for edge in self.edges:
            if edge.node1 is node:
                neighbors.append(edge.node2)
            elif edge.node2 is node:
                neighbors.append(edge.node1)
        return neighbors