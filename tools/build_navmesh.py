"""
Build a navmesh JSON for a specific UDMF map using the local
zdoom-navmesh-generator source.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple
import re


class WadError(RuntimeError):
    pass


def _read_wad_directory(path: Path) -> Tuple[bytes, List[Tuple[str, int, int, int]]]:
    data = path.read_bytes()
    if len(data) < 12:
        raise WadError(f"Invalid WAD header: {path}")
    ident, num_lumps, dir_offset = struct.unpack_from("<4sii", data, 0)
    if ident not in (b"IWAD", b"PWAD"):
        raise WadError(f"Unknown WAD type {ident!r}: {path}")
    if dir_offset < 12 or dir_offset + num_lumps * 16 > len(data):
        raise WadError(f"Invalid directory offset in {path}")

    lumps: List[Tuple[str, int, int, int]] = []
    for i in range(num_lumps):
        off = dir_offset + i * 16
        lump_offset, lump_size = struct.unpack_from("<ii", data, off)
        name_raw = data[off + 8: off + 16]
        name = name_raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
        if lump_offset + lump_size > len(data):
            raise WadError(f"Invalid lump bounds for {name} in {path}")
        lumps.append((name, lump_offset, lump_size, off))
    return data, lumps


def _extract_udmf_map(source_wad: Path, map_name: str, out_wad: Path) -> None:
    data, lumps = _read_wad_directory(source_wad)
    map_upper = map_name.upper()

    start_idx = None
    end_idx = None
    for i, (name, _, _, _) in enumerate(lumps):
        if name.upper() == map_upper:
            start_idx = i
            break
    if start_idx is None:
        raise WadError(f"Map {map_name} not found in {source_wad}")

    for i in range(start_idx + 1, len(lumps)):
        if lumps[i][0].upper() == "ENDMAP":
            end_idx = i
            break
    if end_idx is None:
        raise WadError(f"ENDMAP not found for {map_name} in {source_wad}")

    subset = lumps[start_idx:end_idx + 1]
    out_wad.parent.mkdir(parents=True, exist_ok=True)

    blob = bytearray()
    dir_entries = []
    offset = 12
    for name, lump_offset, lump_size, _ in subset:
        lump_data = data[lump_offset:lump_offset + lump_size]
        blob.extend(lump_data)
        dir_entries.append((offset, lump_size, name))
        offset += lump_size

    dir_offset = 12 + len(blob)
    header = struct.pack("<4sii", b"PWAD", len(subset), dir_offset)
    dir_blob = bytearray()
    for lump_offset, lump_size, name in dir_entries:
        name_bytes = name.encode("ascii", errors="replace")[:8].ljust(8, b"\x00")
        dir_blob.extend(struct.pack("<ii8s", lump_offset, lump_size, name_bytes))

    out_wad.write_bytes(header + blob + dir_blob)


def _write_master_config(generator_root: Path, wad_dir: Path, config_dir: Path, mesh_dir: Path) -> Path:
    config_path = generator_root / "config.json"
    payload = {
        "wadspath": str(wad_dir),
        "configspath": str(config_dir),
        "meshpath": str(mesh_dir),
    }
    config_path.write_text(json.dumps(payload, indent=2))
    return config_path


def _write_map_config(config_dir: Path, map_name: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "triangulation_algorithms": ["libtess", "earcut", "delaunay", "smallest"],
        "triangulation": "earcut",
        "options": {
            "cellSize": 2.0,
            "cellHeight": 1.0,
            "agentHeight": 1.0,
            "agentRadius": 0.5,
            "agentMaxClimb": 0.3,
            "agentMaxSlope": 40.0,
            "regionMinSize": 4.0,
            "regionMergeSize": 10.0,
            "edgeMaxLen": 48.0,
            "edgeMaxError": 4.0,
        },
        "merge_distance": 1.0,
        "solo": True,
    }
    cfg_path = config_dir / f"{map_name.upper()}.json"
    cfg_path.write_text(json.dumps(cfg, indent=2))
    return cfg_path


def _run_generator(generator_root: Path, map_name: str) -> None:
    runner = generator_root / "tools_run_build_navmesh.js"
    runner.write_text(
        "\n".join(
            [
                "const fs = require('fs');",
                "const path = require('path');",
                "const strip = require('strip-comments');",
                "const build = require('./build');",
                "const master = JSON.parse(fs.readFileSync('./config.json', 'utf8'));",
                f"const mapName = '{map_name.upper()}';",
                "const cfgPath = path.join(master.configspath, `${mapName}.json`);",
                "const cfg = JSON.parse(strip(fs.readFileSync(cfgPath, 'utf8')));",
                "build.buildNavMesh(mapName, cfg, master)",
                "  .then(() => { console.log('navmesh:ok'); })",
                "  .catch((err) => { console.error(err); process.exit(1); });",
            ]
        )
    )
    try:
        env = os.environ.copy()
        env.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")
        subprocess.run(
            ["node", str(runner)],
            cwd=str(generator_root),
            env=env,
            check=True,
        )
    finally:
        try:
            runner.unlink()
        except OSError:
            pass


def _run_zshapes_generator(generator_root: Path, wad_path: Path, map_name: str, out_path: Path) -> None:
    script = generator_root / "tools" / "build_navmesh_zshapes.js"
    if not script.exists():
        raise WadError(f"ZShapes builder not found: {script}")
    subprocess.run(
        ["node", str(script), str(wad_path), map_name, str(out_path)],
        cwd=str(generator_root),
        check=True,
    )


def _extract_textmap(wad_path: Path) -> str:
    data, lumps = _read_wad_directory(wad_path)
    for name, offset, size, _ in lumps:
        if name.upper() == "TEXTMAP":
            blob = data[offset:offset + size]
            return blob.decode("utf-8", errors="replace")
    raise WadError(f"TEXTMAP not found in {wad_path}")


def _parse_udmf_vertices(textmap: str) -> List[Tuple[float, float]]:
    vertices: List[Tuple[float, float]] = []
    for block in re.finditer(r"vertex\b[^{]*\{.*?\}", textmap, re.DOTALL | re.IGNORECASE):
        chunk = block.group(0)
        mx = re.search(r"\bx\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", chunk)
        my = re.search(r"\by\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", chunk)
        if not mx or not my:
            continue
        try:
            x = float(mx.group(1))
            y = float(my.group(1))
        except ValueError:
            continue
        vertices.append((x, y))
    return vertices


def _write_simple_navmesh(mesh_path: Path, bounds: Tuple[float, float, float, float], cell_size: float = 256.0) -> None:
    min_x, min_y, max_x, max_y = bounds
    pad = cell_size
    min_x -= pad
    min_y -= pad
    max_x += pad
    max_y += pad

    cols = max(1, int((max_x - min_x) // cell_size))
    rows = max(1, int((max_y - min_y) // cell_size))

    vertices: List[float] = []
    nodes = []

    def add_vertex(x: float, y: float) -> int:
        idx = len(vertices) // 3
        vertices.extend([x, y, 0.0])
        return idx

    def node_index(r: int, c: int) -> int:
        return r * cols + c

    for r in range(rows):
        for c in range(cols):
            x0 = min_x + c * cell_size
            y0 = min_y + r * cell_size
            x1 = x0 + cell_size
            y1 = y0 + cell_size
            v0 = add_vertex(x0, y0)
            v1 = add_vertex(x1, y0)
            v2 = add_vertex(x1, y1)
            v3 = add_vertex(x0, y1)
            centroid = [(x0 + x1) * 0.5, (y0 + y1) * 0.5, 0.0]

            neighbors = []
            if r > 0:
                neighbors.append(node_index(r - 1, c))
            if r + 1 < rows:
                neighbors.append(node_index(r + 1, c))
            if c > 0:
                neighbors.append(node_index(r, c - 1))
            if c + 1 < cols:
                neighbors.append(node_index(r, c + 1))

            nodes.append(
                {
                    "c": centroid,
                    "p": [],
                    "v": [v0, v1, v2, v3],
                    "n": neighbors,
                    "g": 0,
                    "b": [],
                }
            )

    payload = {
        "vertices": vertices,
        "nodes": nodes,
        "groups": 1,
        "length": 0,
        "sizex": 0,
        "sizey": 0,
        "originx": 0,
        "originy": 0,
        "res": int(cell_size),
    }
    mesh_path.write_text(json.dumps(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a navmesh JSON for a UDMF map.")
    parser.add_argument("--map", required=True, help="Map name (e.g., E1M2)")
    parser.add_argument(
        "--udmf-wad",
        default="wads/doom1-udmf.wad",
        help="Source UDMF WAD containing the map",
    )
    parser.add_argument(
        "--generator-root",
        default="zdoom-navmesh-generator-master",
        help="Path to zdoom-navmesh-generator source",
    )
    parser.add_argument(
        "--output-dir",
        default="models/nav",
        help="Directory for generated navmesh JSON",
    )
    parser.add_argument(
        "--work-wads",
        default="logs/navmesh_wads",
        help="Directory for extracted per-map WADs",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    generator_root = (repo_root / args.generator_root).resolve()
    if not generator_root.exists():
        raise WadError(f"Generator root not found: {generator_root}")

    udmf_wad = (repo_root / args.udmf_wad).resolve()
    if not udmf_wad.exists():
        raise WadError(f"UDMF WAD not found: {udmf_wad}")

    work_wads = (repo_root / args.work_wads).resolve()
    out_wad = work_wads / f"{args.map.upper()}.wad"
    _extract_udmf_map(udmf_wad, args.map, out_wad)

    config_dir = generator_root / "configs"
    mesh_dir = (repo_root / args.output_dir).resolve()
    mesh_dir.mkdir(parents=True, exist_ok=True)
    _write_master_config(generator_root, work_wads, config_dir, mesh_dir)
    _write_map_config(config_dir, args.map)

    node_modules = generator_root / "node_modules"
    if not node_modules.exists():
        raise WadError(
            "node_modules not found. Run `npm install` in "
            f"{generator_root} before running this script."
        )

    try:
        _run_generator(generator_root, args.map)
    except Exception as exc:
        print(f"warn: recastjs generator failed ({exc}); using ZShapes fallback", file=sys.stderr)
        mesh_path = mesh_dir / f"{args.map.upper()}.json"
        _run_zshapes_generator(generator_root, out_wad, args.map, mesh_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
