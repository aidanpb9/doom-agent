#for geometry, from Thomas interact.py
def _closest_point_on_segment(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / denom
    t = max(0.0, min(1.0, t))
    return x1 + t * dx, y1 + t * dy

def _normalize_angle_delta_deg(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0