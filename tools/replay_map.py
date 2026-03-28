"""Render an SVG map showing agent path from a Tier 2 action stream.
Called automatically by TelemetryWriter.finalize_episode() at the end of every episode.

Usage (CLI):
    python tools/replay_map.py <tier2_csv> <map_json> <output_svg> [wad_path] [map_name] [end_reason]

Usage (programmatic):
    from tools.replay_map import render
    render(tier2_path, map_json_path, output_path, end_reason="death")
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.utils import load_blocking_segments_from_wad
from config.constants import DEFAULT_WAD_PATH, DEFAULT_MAP_NAME

SVG_WIDTH = 1400.0
SVG_HEIGHT = 1000.0
SVG_PAD = 30.0

STATE_COLORS = {
    "STUCK":    "#ff4444",
    "COMBAT":   "#ff8800",
    "RECOVER":  "#44cc44",
    "SCAN":     "#4488ff",
    "TRAVERSE": "#888888",
}
NODE_COLORS = {
    "waypoint": "#ffffff",
    "door":     "#00ff88",
    "exit":     "#ff00ff",  #magenta, distinct from death marker
    "loot":     "#ffdd00",
}
END_COLORS = {
    "completion": "#00ff88",
    "death":      "#ff2222",
    "timeout":    "#ffaa00",
}


def _make_transform(segments: list[tuple[float, float, float, float]]):
    """Derive SVG coordinate transform from blocking segment bounding box.
    Same math as navigation_planner._svg_transform but without a ParsedMap."""
    all_x = [x for x1, y1, x2, y2 in segments for x in (x1, x2)]
    all_y = [y for x1, y1, x2, y2 in segments for y in (y1, y2)]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    sx = (SVG_WIDTH - 2 * SVG_PAD) / max(1.0, max_x - min_x)
    sy = (SVG_HEIGHT - 2 * SVG_PAD) / max(1.0, max_y - min_y)
    s = min(sx, sy)

    def tx(x: float) -> float:
        return SVG_PAD + (x - min_x) * s

    def ty(y: float) -> float:
        #flip y: Doom y increases upward, SVG y increases downward
        return SVG_HEIGHT - (SVG_PAD + (y - min_y) * s)

    return tx, ty


def render(
    tier2_path: Path,
    map_json_path: Path,
    output_path: Path,
    wad_path: str = DEFAULT_WAD_PATH,
    map_name: str = DEFAULT_MAP_NAME,
    end_reason: str = "unknown",
) -> None:
    """Read Tier 2 CSV + map JSON + WAD segments, write SVG to output_path."""
    segments = load_blocking_segments_from_wad(wad_path, map_name)
    if not segments:
        print(f"replay_map: no blocking segments loaded from {wad_path} {map_name}")
        return

    tx, ty = _make_transform(segments)

    #Read Tier 2 positions and states
    rows: list[dict] = []
    with open(tier2_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    #Load static nodes from map JSON
    nodes: list[dict] = []
    exit_node: dict | None = None
    if map_json_path.exists():
        data = json.loads(map_json_path.read_text(encoding="utf-8"))
        nodes = data.get("node_points", [])
        for n in nodes:
            if n.get("type") == "exit":
                exit_node = n
                break

    #--- SVG elements ---

    #Map walls
    walls = []
    for x1, y1, x2, y2 in segments:
        walls.append(
            f'<line x1="{tx(x1):.1f}" y1="{ty(y1):.1f}" '
            f'x2="{tx(x2):.1f}" y2="{ty(y2):.1f}" '
            f'stroke="#444444" stroke-width="0.8" />'
        )

    #Agent path: group consecutive rows by sm_state into polylines
    path_lines = []
    if rows:
        run_state = rows[0].get("sm_state", "TRAVERSE")
        run_pts = []
        for row in rows:
            state = row.get("sm_state", "TRAVERSE")
            try:
                px, py = float(row["pos_x"]), float(row["pos_y"])
            except (KeyError, ValueError):
                continue
            if state != run_state:
                if len(run_pts) >= 2:
                    pts_str = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in run_pts)
                    color = STATE_COLORS.get(run_state, "#888888")
                    path_lines.append(
                        f'<polyline points="{pts_str}" stroke="{color}" '
                        f'stroke-width="1.5" fill="none" opacity="0.85" />'
                    )
                run_state = state
                run_pts = [(px, py)]
            else:
                run_pts.append((px, py))
        #flush last run
        if len(run_pts) >= 2:
            pts_str = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in run_pts)
            color = STATE_COLORS.get(run_state, "#888888")
            path_lines.append(
                f'<polyline points="{pts_str}" stroke="{color}" '
                f'stroke-width="1.5" fill="none" opacity="0.85" />'
            )

    #Static nodes
    node_dots = []
    for node in nodes:
        try:
            nx, ny = float(node["x"]), float(node["y"])
        except (KeyError, ValueError):
            continue
        ntype = node.get("type", "waypoint")
        color = NODE_COLORS.get(ntype, "#ffffff")
        node_dots.append(
            f'<circle cx="{tx(nx):.1f}" cy="{ty(ny):.1f}" r="3" fill="{color}" opacity="0.7" />'
        )

    #Markers: level start (first CSV pos), agent end (last CSV pos), level exit (from map JSON)
    markers = []
    if rows:
        try:
            sx0, sy0 = float(rows[0]["pos_x"]), float(rows[0]["pos_y"])
            markers.append(f'<circle cx="{tx(sx0):.1f}" cy="{ty(sy0):.1f}" r="7" fill="#ffffff" opacity="0.9" />')
        except (KeyError, ValueError):
            pass
        try:
            ex0, ey0 = float(rows[-1]["pos_x"]), float(rows[-1]["pos_y"])
            end_color = END_COLORS.get(end_reason, "#aaaaaa")
            markers.append(f'<circle cx="{tx(ex0):.1f}" cy="{ty(ey0):.1f}" r="7" fill="{end_color}" opacity="0.9" />')
        except (KeyError, ValueError):
            pass

    if exit_node:
        try:
            lx, ly = float(exit_node["x"]), float(exit_node["y"])
            markers.append(
                f'<circle cx="{tx(lx):.1f}" cy="{ty(ly):.1f}" r="7" '
                f'fill="none" stroke="#ff00ff" stroke-width="2.5" />'
            )
        except (KeyError, ValueError):
            pass

    #Legend
    end_label = {"completion": "Completion", "death": "Death", "timeout": "Timeout"}.get(end_reason, "End")
    legend_y = 30
    legend = [
        f'<text x="20" y="{legend_y}" fill="#ffffff" font-family="monospace" font-size="16">'
        f'{map_name} Agent Path — {end_label}</text>'
    ]
    legend_y += 24
    for state_name, color in STATE_COLORS.items():
        legend.append(
            f'<rect x="20" y="{legend_y - 10}" width="16" height="10" fill="{color}" />'
            f'<text x="42" y="{legend_y}" fill="#cccccc" font-family="monospace" font-size="12">{state_name}</text>'
        )
        legend_y += 18
    legend.append(
        f'<circle cx="28" cy="{legend_y - 5}" r="5" fill="#ffffff" />'
        f'<text x="42" y="{legend_y}" fill="#cccccc" font-family="monospace" font-size="12">Level start</text>'
    )
    legend_y += 18
    end_color = END_COLORS.get(end_reason, "#aaaaaa")
    legend.append(
        f'<circle cx="28" cy="{legend_y - 5}" r="5" fill="{end_color}" />'
        f'<text x="42" y="{legend_y}" fill="#cccccc" font-family="monospace" font-size="12">Agent end ({end_reason})</text>'
    )
    legend_y += 18
    legend.append(
        f'<circle cx="28" cy="{legend_y - 5}" r="5" fill="none" stroke="#ff00ff" stroke-width="2" />'
        f'<text x="42" y="{legend_y}" fill="#cccccc" font-family="monospace" font-size="12">Level exit</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(SVG_WIDTH)}" height="{int(SVG_HEIGHT)}">\n'
        f'<rect width="100%" height="100%" fill="#121212" />\n'
        + "\n".join(walls) + "\n"
        + "\n".join(path_lines) + "\n"
        + "\n".join(node_dots) + "\n"
        + "\n".join(markers) + "\n"
        + "\n".join(legend) + "\n"
        + "</svg>"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(f"replay_map: wrote {output_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3:
        print("Usage: replay_map.py <tier2_csv> <map_json> <output_svg> [wad_path] [map_name] [end_reason]")
        sys.exit(1)
    render(
        tier2_path=Path(args[0]),
        map_json_path=Path(args[1]),
        output_path=Path(args[2]),
        wad_path=args[3] if len(args) > 3 else DEFAULT_WAD_PATH,
        map_name=args[4] if len(args) > 4 else DEFAULT_MAP_NAME,
        end_reason=args[5] if len(args) > 5 else "unknown",
    )