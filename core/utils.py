"""Contains resuable functions."""
from math import sqrt

def calculate_euclidean_distance(point1_x, point1_y, point2_x, point2_y) -> float:
    """Distance between 2 points formula."""
    return sqrt((point2_x - point1_x)**2 + (point2_y - point1_y)**2)

def normalize_angle(angle_deg: float) -> float:
    """Wraps an angle -180 to 180 deg."""
    return (angle_deg + 180.0) % 360.0 - 180.0