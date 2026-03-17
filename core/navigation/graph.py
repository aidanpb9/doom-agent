"""Docstring here.
"""

from enum import Enum
from typing import Optional


class NodeType(Enum):
    waypoint = 1
    anchor = 2
    loot = 3
    door = 4
    exit = 5


class Node:
    def __init__(self, x, y, node_type, name=None, special=None):
        self.x = x
        self.y = y
        self.node_type = node_type
        self.name = name
        self.special = special      


class Edge:
    def __init__(self, node1, node2):
        self.node1 = node1
        self.node2 = node2
        self.edge_length = 0 #might be sqrt((node2.x - node1.x)^2 + (node2.y - node1.y)^2)


class Graph:
    def __init__(self):
        self.nodes = [] 
        self.edges = [] 
    
    def add_node(self, node):
        pass
    
    def add_edge(self, node1, node2):
        pass