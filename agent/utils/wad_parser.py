"""
Minimal WAD parser for extracting secret sectors from classic Doom maps.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple


def _is_map_marker(name: str) -> bool:
    return bool(re.match(r"^E\\dM\\d$", name) or re.match(r"^MAP\\d\\d$", name))


def _read_directory(data: bytes, num_lumps: int, dir_offset: int) -> List[Tuple[int, int, str]]:
    entries = []
    for i in range(num_lumps):
        offset = dir_offset + i * 16
        lump_off, lump_size = struct.unpack_from("<ii", data, offset)
        name_bytes = data[offset + 8 : offset + 16]
        name = name_bytes.split(b"\x00", 1)[0].decode("ascii", errors="ignore").upper()
        entries.append((lump_off, lump_size, name))
    return entries


def find_secret_sectors(wad_path: str, map_name: str) -> Set[int]:
    wad_file = Path(wad_path)
    if not wad_file.exists():
        return set()

    data = wad_file.read_bytes()
    if len(data) < 12:
        return set()

    _, num_lumps, dir_offset = struct.unpack_from("<4sii", data, 0)
    entries = _read_directory(data, num_lumps, dir_offset)

    map_name = map_name.upper()
    map_idx: Optional[int] = None
    for i, (_, _, name) in enumerate(entries):
        if name == map_name:
            map_idx = i
            break

    if map_idx is None:
        return set()

    next_map_idx = None
    for j in range(map_idx + 1, len(entries)):
        if _is_map_marker(entries[j][2]):
            next_map_idx = j
            break

    end_idx = next_map_idx if next_map_idx is not None else len(entries)

    sectors_entry = None
    for j in range(map_idx + 1, end_idx):
        if entries[j][2] == "SECTORS":
            sectors_entry = entries[j]
            break

    if sectors_entry is None:
        return set()

    sec_off, sec_size, _ = sectors_entry
    if sec_size % 26 != 0:
        return set()

    secrets: Set[int] = set()
    count = sec_size // 26
    for i in range(count):
        base = sec_off + i * 26
        # floor(2), ceiling(2), floor_tex(8), ceil_tex(8), light(2), special(2), tag(2)
        special = struct.unpack_from("<h", data, base + 22)[0]
        # Classic secret = 9, generalized/extended secrets often use 1024+ (0x400)
        if special == 9 or (special & 0x400) == 0x400:
            secrets.add(i)

    return secrets
