"""
Build navmesh JSON files using the sector-topology generator.

This is the single supported build path:
  zdoom-navmesh-generator-master/tools/build_navmesh_sector.js
"""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


MAP_NAME_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$", re.IGNORECASE)


class WadError(RuntimeError):
    pass


def _read_wad_directory(path: Path) -> Tuple[bytes, List[Tuple[str, int, int]]]:
    data = path.read_bytes()
    if len(data) < 12:
        raise WadError(f"Invalid WAD header: {path}")
    ident, num_lumps, dir_offset = struct.unpack_from("<4sii", data, 0)
    if ident not in (b"IWAD", b"PWAD"):
        raise WadError(f"Unknown WAD type {ident!r}: {path}")
    if dir_offset < 12 or dir_offset + num_lumps * 16 > len(data):
        raise WadError(f"Invalid directory offset in {path}")

    lumps: List[Tuple[str, int, int]] = []
    for i in range(num_lumps):
        off = dir_offset + i * 16
        lump_offset, lump_size = struct.unpack_from("<ii", data, off)
        name_raw = data[off + 8 : off + 16]
        name = name_raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").upper()
        if lump_offset + lump_size > len(data):
            raise WadError(f"Invalid lump bounds for {name} in {path}")
        lumps.append((name, lump_offset, lump_size))
    return data, lumps


def _discover_maps(source_wad: Path) -> List[str]:
    _, lumps = _read_wad_directory(source_wad)
    maps: List[str] = []
    for name, _, _ in lumps:
        if MAP_NAME_RE.match(name):
            maps.append(name)
    if not maps:
        raise WadError(f"No map markers found in {source_wad}")
    return maps


def _extract_udmf_map(source_wad: Path, map_name: str, out_wad: Path) -> None:
    data, lumps = _read_wad_directory(source_wad)
    map_upper = map_name.upper()

    start_idx = None
    for i, (name, _, _) in enumerate(lumps):
        if name == map_upper:
            start_idx = i
            break
    if start_idx is None:
        raise WadError(f"Map {map_upper} not found in {source_wad}")

    end_idx = None
    for i in range(start_idx + 1, len(lumps)):
        if lumps[i][0] == "ENDMAP":
            end_idx = i
            break
    if end_idx is None:
        raise WadError(f"ENDMAP not found for {map_upper} in {source_wad}")

    subset = lumps[start_idx : end_idx + 1]
    out_wad.parent.mkdir(parents=True, exist_ok=True)

    blob = bytearray()
    dir_entries: List[Tuple[int, int, str]] = []
    offset = 12
    for name, lump_offset, lump_size in subset:
        lump_data = data[lump_offset : lump_offset + lump_size]
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


def _run_sector_builder(generator_root: Path, map_wad: Path, map_name: str, out_json: Path) -> None:
    builder = generator_root / "tools" / "build_navmesh_sector.js"
    if not builder.exists():
        raise WadError(f"Sector builder not found: {builder}")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", str(builder), str(map_wad), map_name.upper(), str(out_json)],
        cwd=str(generator_root),
        check=True,
    )


def _parse_map_targets(args: argparse.Namespace, source_wad: Path) -> Sequence[str]:
    if args.map and args.all:
        raise WadError("Use either --map or --all, not both.")
    if not args.map and not args.all:
        raise WadError("Specify --map <NAME> or --all.")
    if args.map:
        target = args.map.upper()
        if not MAP_NAME_RE.match(target):
            raise WadError(f"Invalid map name: {args.map}")
        return [target]
    return _discover_maps(source_wad)


def _print_summary(done: Iterable[str]) -> None:
    maps = list(done)
    print(f"Built {len(maps)} navmeshes:")
    print(" ".join(maps))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build navmesh JSON from a UDMF WAD.")
    parser.add_argument("--map", help="Map name, e.g. E1M1")
    parser.add_argument("--all", action="store_true", help="Build all maps found in --udmf-wad")
    parser.add_argument("--udmf-wad", default="wads/doom-udmf.wad", help="Source UDMF WAD")
    parser.add_argument(
        "--maps-wad",
        default="wads/DOOM.WAD",
        help="WAD used to discover map names for --all",
    )
    parser.add_argument(
        "--generator-root",
        default="zdoom-navmesh-generator-master",
        help="Path to zdoom-navmesh-generator source",
    )
    parser.add_argument("--output-dir", default="models/nav", help="Output navmesh directory")
    parser.add_argument("--work-wads", default="logs/navmesh_wads", help="Per-map extracted WAD directory")
    parser.add_argument(
        "--refresh-extract",
        action="store_true",
        help="Force re-extraction from --udmf-wad even if a per-map work WAD exists",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source_wad = (repo_root / args.udmf_wad).resolve()
    maps_wad = (repo_root / args.maps_wad).resolve()
    generator_root = (repo_root / args.generator_root).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    work_wads = (repo_root / args.work_wads).resolve()

    if not source_wad.exists():
        raise WadError(f"UDMF WAD not found: {source_wad}")
    if not generator_root.exists():
        raise WadError(f"Generator root not found: {generator_root}")

    # For --all, prefer map discovery from DOOM.WAD (or user-provided maps wad).
    # This keeps the target list stable even if the UDMF conversion WAD is partial.
    discover_wad = maps_wad if maps_wad.exists() else source_wad
    maps = list(_parse_map_targets(args, discover_wad))
    built: List[str] = []
    for map_name in maps:
        map_wad = work_wads / f"{map_name}.wad"
        out_json = output_dir / f"{map_name}.json"
        should_extract = args.refresh_extract or not map_wad.exists()
        if should_extract:
            try:
                _extract_udmf_map(source_wad, map_name, map_wad)
            except WadError:
                if not map_wad.exists():
                    raise
        _run_sector_builder(generator_root, map_wad, map_name, out_json)
        built.append(map_name)

    _print_summary(built)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
