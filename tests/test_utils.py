"""Tests for core/utils.py.

Functions tested:
  - calculate_euclidean_distance(x1, y1, x2, y2) -> float
  - normalize_angle(angle_deg) -> float  — wraps to [-180, 180)
  - has_clear_world_line(px, py, ox, oy, segments) -> bool

load_blocking_segments_from_wad is not tested here because it requires a real WAD file.
"""
import pytest
from core.utils import calculate_euclidean_distance, normalize_angle, has_clear_world_line


# ---------------------------------------------------------------------------
# calculate_euclidean_distance
# ---------------------------------------------------------------------------

def test_euclidean_distance_correct_value():
    #3-4-5 right triangle gives exact integer result
    assert calculate_euclidean_distance(0, 0, 3, 4) == pytest.approx(5.0)


def test_euclidean_distance_same_point():
    #distance from a point to itself should be 0
    assert calculate_euclidean_distance(5, 5, 5, 5) == pytest.approx(0.0)


def test_euclidean_distance_negative_coords():
    #Doom maps use negative coordinates so sign should not affect result
    assert calculate_euclidean_distance(-3, 0, 0, 4) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# normalize_angle
# ---------------------------------------------------------------------------

def test_normalize_angle_already_in_range():
    #angle already within (-180, 180) should be unchanged
    assert normalize_angle(90.0) == pytest.approx(90.0)
    assert normalize_angle(-90.0) == pytest.approx(-90.0)
    assert normalize_angle(0.0) == pytest.approx(0.0)


def test_normalize_angle_wraps_at_180():
    #180 sits exactly on the boundary so formula maps it to -180
    assert normalize_angle(180.0) == pytest.approx(-180.0)


def test_normalize_angle_large_positive():
    #540 = 180 + 360 → wraps to -180
    assert normalize_angle(540.0) == pytest.approx(-180.0)


def test_normalize_angle_large_negative():
    #-270 → equivalent to 90
    assert normalize_angle(-270.0) == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# has_clear_world_line
# ---------------------------------------------------------------------------

def test_clear_line_no_segments():
    #empty segment list → always clear regardless of positions
    assert has_clear_world_line(0, 0, 10, 10, []) is True


def test_clear_line_no_obstruction():
    #segment runs parallel above the line of sight so should not block
    #player at (0,0), target at (10,0), wall at y=5 from x=0 to x=10
    segments = [(0, 5, 10, 5)]
    assert has_clear_world_line(0, 0, 10, 0, segments) is True


def test_blocked_line():
    #wall crosses directly across the line of sight
    #player at (0,0), target at (10,0), wall at x=5 from y=-5 to y=5
    segments = [(5, -5, 5, 5)]
    assert has_clear_world_line(0, 0, 10, 0, segments) is False


def test_clear_line_none_target():
    #None object coordinates → no target to check, treated as clear
    segments = [(5, -5, 5, 5)]
    assert has_clear_world_line(0, 0, None, None, segments) is True


def test_clear_line_collinear_touch():
    #segment endpoint touches the line of sight but does not cross it
    #player at (0,0), target at (10,0), wall endpoint sits at (5,0)-(5,5)
    #the wall starts on the line but goes perpendicular away so should block
    #since (5,0) is on the line of sight and _on_segment returns True
    segments = [(5, 0, 5, 5)]
    assert has_clear_world_line(0, 0, 10, 0, segments) is False