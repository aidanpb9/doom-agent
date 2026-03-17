"""Core data structure for the navigation node graph.
Node, Edge, and Graph are pure data containers.
No pathfinding or mission logic lives here."""

from enum import Enum
from typing import Optional


class NodeType(Enum):
    """Represents the different node types of the graph.""" 
    
    waypoint = 1
    anchor = 2
    loot = 3
    door = 4
    exit = 5


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
        self.edge_length = 0 #might be sqrt((node2.x - node1.x)^2 + (node2.y - node1.y)^2)


class Graph:
    """Stores the nav node graph as a collection of nodes and edges.
    Pathtracker owns and mutates this. NavigationEngine reads it for pathfinding."""
    
    def __init__(self):
        self.nodes = [] 
        self.edges = [] 
    
    def add_node(self, node):
        pass
    
    def add_edge(self, node1, node2):
        pass