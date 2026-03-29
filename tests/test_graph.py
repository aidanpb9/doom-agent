"""Tests for core/navigation/graph.py.

Classes tested:
  - Graph: add_node, remove_node, add_edge, remove_edge, get_edge, get_neighbors
  - Edge:  length precomputed correctly on construction

Node and NodeType are simple data containers with no logic, no point in testing.
"""
import pytest
from core.navigation.graph import Graph, Node, NodeType


# ---------------------------------------------------------------------------
# Helpers — reusable node factory to keep tests concise
# ---------------------------------------------------------------------------

def make_node(x=0.0, y=0.0, node_type=NodeType.WAYPOINT) -> Node:
    return Node(x, y, node_type)


# ---------------------------------------------------------------------------
# add_node / remove_node
# ---------------------------------------------------------------------------

def test_add_node():
    g = Graph()
    n = make_node()
    g.add_node(n)
    assert n in g.nodes


def test_remove_node():
    g = Graph()
    n = make_node()
    g.add_node(n)
    g.remove_node(n)
    assert n not in g.nodes


def test_remove_node_also_removes_edges():
    g = Graph()
    a, b, c = make_node(0, 0), make_node(1, 0), make_node(2, 0)
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(a, b)
    g.add_edge(b, c)
    g.remove_node(b)
    #all edges involving b should be gone
    assert g.get_edge(a, b) is None
    assert g.get_edge(b, c) is None
    assert len(g.edges) == 0


# ---------------------------------------------------------------------------
# add_edge / remove_edge / get_edge
# ---------------------------------------------------------------------------

def test_add_edge():
    g = Graph()
    a, b = make_node(0, 0), make_node(3, 4)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(a, b)
    assert len(g.edges) == 1


def test_remove_edge():
    g = Graph()
    a, b = make_node(), make_node(1, 0)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(a, b)
    g.remove_edge(a, b)
    assert len(g.edges) == 0


def test_get_edge_returns_correct_edge():
    g = Graph()
    a, b = make_node(0, 0), make_node(3, 4)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(a, b)
    edge = g.get_edge(a, b)
    assert edge is not None
    assert edge.node1 is a and edge.node2 is b or edge.node1 is b and edge.node2 is a


def test_get_edge_is_undirected():
    # adding edge (a, b) should be findable in both directions
    g = Graph()
    a, b = make_node(), make_node(1, 0)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(a, b)
    assert g.get_edge(a, b) is not None
    assert g.get_edge(b, a) is not None


def test_get_edge_returns_none_when_not_found():
    g = Graph()
    a, b = make_node(), make_node(1, 0)
    g.add_node(a)
    g.add_node(b)
    assert g.get_edge(a, b) is None


def test_edge_length_precomputed():
    #3-4-5 triangle, edge length should be 5.0
    g = Graph()
    a, b = make_node(0, 0), make_node(3, 4)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(a, b)
    assert g.get_edge(a, b).length == pytest.approx(5.0)


def test_add_edge_duplicate_is_ignored():
    #add_edge silently ignores duplicate edges, graph stays at one edge
    g = Graph()
    a, b = make_node(), make_node(1, 0)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(a, b)
    g.add_edge(a, b)
    assert len(g.edges) == 1


# ---------------------------------------------------------------------------
# get_neighbors
# ---------------------------------------------------------------------------

def test_get_neighbors_correct():
    g = Graph()
    a, b, c = make_node(0, 0), make_node(1, 0), make_node(2, 0)
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(a, b)
    g.add_edge(a, c)
    neighbors = g.get_neighbors(a)
    assert b in neighbors
    assert c in neighbors
    assert len(neighbors) == 2


def test_get_neighbors_empty():
    # node with no edges should return empty list, not crash
    g = Graph()
    a = make_node()
    g.add_node(a)
    assert g.get_neighbors(a) == []