"""Tests for core/navigation/navigation_engine.py.

Functions tested:
  - make_path(start, end) -> deque[Node] (A* pathfinding)
  - step_toward(x, y, angle, target) -> list[int] (movement action producer)

VizDoom angle convention: 0=East, 90=North, 180/-180=West, -90=South.
TURN_DEAD_ZONE = 10 deg, FORWARD_ANGLE_THRESHOLD = 10 deg (from constants.py).
Relevant action vector indices: FORWARD=0, TURN_LEFT=2, TURN_RIGHT=3.

Note: step_toward threshold tests are designed around TURN_DEAD_ZONE and
FORWARD_ANGLE_THRESHOLD values in constants.py. If those constants change,
these tests may pass while the actual behavior is still wrong. The geometry
and A* correctness tests are independent of constants and safe from this.
"""
import pytest
from collections import deque
from core.navigation.graph import Graph, Node, NodeType
from core.navigation.navigation_engine import NavigationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_node(x=0.0, y=0.0) -> Node:
    return Node(x, y, NodeType.WAYPOINT)


def make_graph(*nodes, edges=None) -> tuple[Graph, NavigationEngine]:
    """Build a graph with the given nodes and edge pairs, return (graph, engine)."""
    g = Graph()
    for n in nodes:
        g.add_node(n)
    for a, b in (edges or []):
        g.add_edge(a, b)
    return g, NavigationEngine(g)


# ---------------------------------------------------------------------------
# make_path — A* pathfinding
# ---------------------------------------------------------------------------

def test_astar_finds_direct_path():
    #Two nodes connected by one edge. Path should just contain the end node.
    a, b = make_node(0, 0), make_node(10, 0)
    _, engine = make_graph(a, b, edges=[(a, b)])
    path = engine.make_path(a, b)
    assert list(path) == [b]


def test_astar_finds_path_through_intermediate():
    #A → B → C with no direct A-C edge. Path must go through B.
    a, b, c = make_node(0, 0), make_node(5, 0), make_node(10, 0)
    _, engine = make_graph(a, b, c, edges=[(a, b), (b, c)])
    path = engine.make_path(a, c)
    assert list(path) == [b, c]


def test_astar_prefers_shorter_path():
    #Two routes A→C: direct (cost=10) and via B (cost=5+8=13). A* should pick direct
    a = make_node(0, 0)
    b = make_node(5, 0)
    c = make_node(10, 0)
    d = make_node(0, 8) #indirect detour node
    _, engine = make_graph(a, b, c, d, edges=[(a, c), (a, d), (d, c)])
    path = engine.make_path(a, c)
    assert list(path) == [c] #direct, not through d


def test_astar_start_equals_goal():
    #Start is same object as goal so should return empty deque.
    a = make_node(0, 0)
    _, engine = make_graph(a)
    path = engine.make_path(a, a)
    assert path == deque()


def test_astar_returns_none_when_disconnected():
    #No path between start and end. make_path returns None implicitly.
    a, b = make_node(0, 0), make_node(10, 0)
    _, engine = make_graph(a, b) #no edges
    path = engine.make_path(a, b)
    assert path is None


# ---------------------------------------------------------------------------
# step_toward — movement action producer
# ---------------------------------------------------------------------------

def test_step_toward_forward_when_aligned():
    #Player at (0,0) facing East (0 deg), target due East at (10,0)
    #delta=0 should produce forward only.
    a, b = make_node(0, 0), make_node(10, 0)
    _, engine = make_graph(a, b)
    action = engine.step_toward(0, 0, 0, b)
    assert action[0] == 1  #FORWARD
    assert action[2] == 0  #no TURN_LEFT
    assert action[3] == 0  #no TURN_RIGHT


def test_step_toward_turn_left_when_target_left():
    #Player at (0,0) facing East (0 deg), target due North at (0,10)
    #delta=+90 should turn left, no forward since |delta| > threshold
    a, b = make_node(0, 0), make_node(0, 10)
    _, engine = make_graph(a, b)
    action = engine.step_toward(0, 0, 0, b)
    assert action[2] == 1 #TURN_LEFT
    assert action[0] == 0 #no FORWARD


def test_step_toward_turn_right_when_target_right():
    #Player at (0,0) facing East (0 deg), target due South at (0,-10)
    #delta=-90 should turn right, no forward
    a, b = make_node(0, 0), make_node(0, -10)
    _, engine = make_graph(a, b)
    action = engine.step_toward(0, 0, 0, b)
    assert action[3] == 1 #TURN_RIGHT
    assert action[0] == 0 #no FORWARD


def test_step_toward_boundary_behavior():
    #TURN_DEAD_ZONE == FORWARD_ANGLE_THRESHOLD == 10 deg, so the two conditions
    #never overlap. You get forward-only (delta < 10) or turn-only (delta > 10),
    #never both at once. If constants diverge this test should be revisited.
    a = make_node(0, 0)

    #9 deg offset is within threshold, forward only.
    target_close = make_node(10, 1.58)  #tan(9 deg) * 10 = 1.584
    _, engine = make_graph(a, target_close)
    action = engine.step_toward(0, 0, 0, target_close)
    assert action[0] == 1 #FORWARD
    assert action[2] == 0 #no TURN_LEFT

    #11 deg offset is outside dead zone, turn only.
    target_far = make_node(10, 1.94) #tan(11 deg) * 10 = 1.944
    action = engine.step_toward(0, 0, 0, target_far)
    assert action[0] == 0 #no FORWARD
    assert action[2] == 1 #TURN_LEFT