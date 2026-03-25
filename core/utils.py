"""Contains resuable functions."""
from math import sqrt
#for geometry, from Thomas interact.py
def closest_point_on_segment(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / denom
    t = max(0.0, min(1.0, t))
    return x1 + t * dx, y1 + t * dy


def normalize_angle(angle_deg: float) -> float:
    """Wraps an angle -180 to 180 deg."""
    return (angle_deg + 180.0) % 360.0 - 180.0


def calculate_euclidean_distance(point1_x, point1_y, point2_x, point2_y) -> float:
    """Distance between 2 points formula."""
    return sqrt((point2_x - point1_x)**2 + (point2_y - point1_y)**2)