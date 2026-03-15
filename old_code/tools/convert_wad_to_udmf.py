"""
Convert classic Doom-format maps in a WAD into UDMF maps.

The script preserves non-map lumps and replaces each classic map block with:
  MAPNAME (marker), TEXTMAP, ENDMAP
"""

from __future__ import annotations

import argparse
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple


MAP_NAME_RE = re.compile(r"^(E[1-9]M[1-9]|MAP[0-9][0-9])$", re.IGNORECASE)
CLASSIC_MAP_LUMPS = {
    "THINGS",
    "LINEDEFS",
    "SIDEDEFS",
    "VERTEXES",
    "SEGS",
    "SSECTORS",
    "NODES",
    "SECTORS",
    "REJECT",
    "BLOCKMAP",
    "BEHAVIOR",
    "SCRIPTS",
}


@dataclass
class Lump:
    name: str
    data: bytes


def _clean_name(raw: str) -> str:
    return raw.split("\x00", 1)[0].strip()


def _read_wad(path: Path) -> Tuple[bytes, List[Tuple[str, int, int]]]:
    blob = path.read_bytes()
    if len(blob) < 12:
        raise ValueError(f"Invalid WAD header: {path}")
    ident, count, directory_offset = struct.unpack_from("<4sii", blob, 0)
    if ident not in (b"IWAD", b"PWAD"):
        raise ValueError(f"Unsupported WAD type {ident!r} in {path}")
    if directory_offset < 12 or directory_offset + (count * 16) > len(blob):
        raise ValueError(f"Invalid WAD directory in {path}")

    lumps: List[Tuple[str, int, int]] = []
    for i in range(count):
        off = directory_offset + (i * 16)
        lump_offset, lump_size = struct.unpack_from("<ii", blob, off)
        name = _clean_name(blob[off + 8:off + 16].decode("ascii", errors="replace")).upper()
        if lump_offset < 0 or lump_size < 0 or lump_offset + lump_size > len(blob):
            raise ValueError(f"Invalid lump bounds for {name} in {path}")
        lumps.append((name, lump_offset, lump_size))
    return blob, lumps


def _decode_name(raw8: bytes) -> str:
    return _clean_name(raw8.decode("ascii", errors="replace").upper()) or "-"


def _fmt_bool(value: bool) -> str:
    return "true" if value else "false"


def _parse_vertices(data: bytes) -> List[Tuple[int, int]]:
    if len(data) % 4 != 0:
        raise ValueError("VERTEXES lump has invalid size")
    out: List[Tuple[int, int]] = []
    for i in range(0, len(data), 4):
        x, y = struct.unpack_from("<hh", data, i)
        out.append((int(x), int(y)))
    return out


def _parse_sectors(data: bytes) -> List[dict]:
    if len(data) % 26 != 0:
        raise ValueError("SECTORS lump has invalid size")
    out: List[dict] = []
    for i in range(0, len(data), 26):
        floor_h, ceil_h = struct.unpack_from("<hh", data, i)
        floor_tex = _decode_name(data[i + 4:i + 12])
        ceil_tex = _decode_name(data[i + 12:i + 20])
        light, special, tag = struct.unpack_from("<hHH", data, i + 20)
        out.append(
            {
                "heightfloor": int(floor_h),
                "heightceiling": int(ceil_h),
                "texturefloor": floor_tex,
                "textureceiling": ceil_tex,
                "lightlevel": int(light),
                "special": int(special),
                "id": int(tag),
            }
        )
    return out


def _parse_sidedefs(data: bytes) -> List[dict]:
    if len(data) % 30 != 0:
        raise ValueError("SIDEDEFS lump has invalid size")
    out: List[dict] = []
    for i in range(0, len(data), 30):
        off_x, off_y = struct.unpack_from("<hh", data, i)
        top = _decode_name(data[i + 4:i + 12])
        bottom = _decode_name(data[i + 12:i + 20])
        middle = _decode_name(data[i + 20:i + 28])
        sector = struct.unpack_from("<H", data, i + 28)[0]
        out.append(
            {
                "offsetx": int(off_x),
                "offsety": int(off_y),
                "texturetop": top,
                "texturebottom": bottom,
                "texturemiddle": middle,
                "sector": int(sector),
            }
        )
    return out


def _parse_linedefs(data: bytes) -> List[dict]:
    if len(data) % 14 != 0:
        raise ValueError("LINEDEFS lump has invalid size")
    out: List[dict] = []
    for i in range(0, len(data), 14):
        v1, v2, flags, special, tag, side_front, side_back = struct.unpack_from("<7H", data, i)
        out.append(
            {
                "v1": int(v1),
                "v2": int(v2),
                "special": int(special),
                "arg0": int(tag),
                "sidefront": int(side_front),
                "sideback": None if side_back == 0xFFFF else int(side_back),
                "blocking": bool(flags & 0x0001),
                "blockmonsters": bool(flags & 0x0002),
                "twosided": bool(flags & 0x0004),
                "dontpegtop": bool(flags & 0x0008),
                "dontpegbottom": bool(flags & 0x0010),
                "secret": bool(flags & 0x0020),
                "blocksound": bool(flags & 0x0040),
                "dontdraw": bool(flags & 0x0080),
                "mapped": bool(flags & 0x0100),
            }
        )
    return out


def _parse_things(data: bytes) -> List[dict]:
    if len(data) % 10 != 0:
        raise ValueError("THINGS lump has invalid size")
    out: List[dict] = []
    for i in range(0, len(data), 10):
        x, y, angle, thing_type, flags = struct.unpack_from("<hhHHH", data, i)
        easy = bool(flags & 0x0001)
        medium = bool(flags & 0x0002)
        hard = bool(flags & 0x0004)
        multiplayer = bool(flags & 0x0010)
        out.append(
            {
                "x": int(x),
                "y": int(y),
                "angle": int(angle),
                "type": int(thing_type),
                "skill1": easy,
                "skill2": easy,
                "skill3": medium,
                "skill4": hard,
                "skill5": hard,
                "ambush": bool(flags & 0x0008),
                "single": not multiplayer,
                "coop": multiplayer,
                "dm": multiplayer,
            }
        )
    return out


def _emit_block(name: str, fields: Sequence[Tuple[str, object]]) -> str:
    lines = [f"{name}", "{"] 
    for key, value in fields:
        if isinstance(value, bool):
            v = _fmt_bool(value)
        elif isinstance(value, str):
            v = f"\"{value}\""
        else:
            v = str(value)
        lines.append(f"    {key} = {v};")
    lines.append("}")
    return "\n".join(lines)


def _build_textmap(map_name: str, map_lumps: dict) -> bytes:
    required = ("VERTEXES", "SECTORS", "SIDEDEFS", "LINEDEFS", "THINGS")
    missing = [name for name in required if name not in map_lumps]
    if missing:
        raise ValueError(f"{map_name}: missing required lump(s): {', '.join(missing)}")

    vertices = _parse_vertices(map_lumps["VERTEXES"])
    sectors = _parse_sectors(map_lumps["SECTORS"])
    sidedefs = _parse_sidedefs(map_lumps["SIDEDEFS"])
    linedefs = _parse_linedefs(map_lumps["LINEDEFS"])
    things = _parse_things(map_lumps["THINGS"])

    chunks: List[str] = ['namespace = "ZDoom";']

    for x, y in vertices:
        chunks.append(_emit_block("vertex", (("x", x), ("y", y))))

    for sec in sectors:
        chunks.append(
            _emit_block(
                "sector",
                (
                    ("heightfloor", sec["heightfloor"]),
                    ("heightceiling", sec["heightceiling"]),
                    ("texturefloor", sec["texturefloor"]),
                    ("textureceiling", sec["textureceiling"]),
                    ("lightlevel", sec["lightlevel"]),
                    ("special", sec["special"]),
                    ("id", sec["id"]),
                ),
            )
        )

    for side in sidedefs:
        chunks.append(
            _emit_block(
                "sidedef",
                (
                    ("offsetx", side["offsetx"]),
                    ("offsety", side["offsety"]),
                    ("texturetop", side["texturetop"]),
                    ("texturebottom", side["texturebottom"]),
                    ("texturemiddle", side["texturemiddle"]),
                    ("sector", side["sector"]),
                ),
            )
        )

    for line in linedefs:
        fields: List[Tuple[str, object]] = [
            ("v1", line["v1"]),
            ("v2", line["v2"]),
            ("sidefront", line["sidefront"]),
            ("special", line["special"]),
            ("arg0", line["arg0"]),
            ("blocking", line["blocking"]),
            ("blockmonsters", line["blockmonsters"]),
            ("twosided", line["twosided"]),
            ("dontpegtop", line["dontpegtop"]),
            ("dontpegbottom", line["dontpegbottom"]),
            ("secret", line["secret"]),
            ("blocksound", line["blocksound"]),
            ("dontdraw", line["dontdraw"]),
            ("mapped", line["mapped"]),
        ]
        if line["sideback"] is not None:
            fields.insert(3, ("sideback", line["sideback"]))
        chunks.append(_emit_block("linedef", fields))

    for thing in things:
        chunks.append(
            _emit_block(
                "thing",
                (
                    ("x", thing["x"]),
                    ("y", thing["y"]),
                    ("angle", thing["angle"]),
                    ("type", thing["type"]),
                    ("skill1", thing["skill1"]),
                    ("skill2", thing["skill2"]),
                    ("skill3", thing["skill3"]),
                    ("skill4", thing["skill4"]),
                    ("skill5", thing["skill5"]),
                    ("ambush", thing["ambush"]),
                    ("single", thing["single"]),
                    ("coop", thing["coop"]),
                    ("dm", thing["dm"]),
                ),
            )
        )

    text = "\n\n".join(chunks) + "\n"
    return text.encode("utf-8")


def _is_map_start(lumps: Sequence[Tuple[str, int, int]], idx: int) -> bool:
    name = lumps[idx][0]
    if not MAP_NAME_RE.match(name):
        return False
    if idx + 1 >= len(lumps):
        return False
    return lumps[idx + 1][0] in CLASSIC_MAP_LUMPS


def _collect_map_lumps(
    blob: bytes,
    lumps: Sequence[Tuple[str, int, int]],
    start_idx: int,
) -> Tuple[int, dict]:
    out = {}
    i = start_idx + 1
    while i < len(lumps):
        name, off, size = lumps[i]
        if MAP_NAME_RE.match(name):
            break
        if name not in CLASSIC_MAP_LUMPS:
            break
        out[name] = blob[off:off + size]
        i += 1
    return i, out


def _write_wad(path: Path, lumps: Sequence[Lump]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray()
    entries = bytearray()
    offset = 12
    for lump in lumps:
        payload = lump.data or b""
        data.extend(payload)
        name = lump.name.upper().encode("ascii", errors="replace")[:8].ljust(8, b"\x00")
        entries.extend(struct.pack("<ii8s", offset, len(payload), name))
        offset += len(payload)

    directory_offset = 12 + len(data)
    header = struct.pack("<4sii", b"PWAD", len(lumps), directory_offset)
    path.write_bytes(header + data + entries)


def convert_wad(input_wad: Path, output_wad: Path) -> Tuple[int, int]:
    blob, lumps = _read_wad(input_wad)

    out_lumps: List[Lump] = []
    converted = 0
    i = 0
    while i < len(lumps):
        name, off, size = lumps[i]
        if _is_map_start(lumps, i):
            next_i, map_lumps = _collect_map_lumps(blob, lumps, i)
            textmap = _build_textmap(name, map_lumps)
            out_lumps.append(Lump(name=name, data=b""))
            out_lumps.append(Lump(name="TEXTMAP", data=textmap))
            out_lumps.append(Lump(name="ENDMAP", data=b""))
            converted += 1
            i = next_i
            continue

        out_lumps.append(Lump(name=name, data=blob[off:off + size]))
        i += 1

    _write_wad(output_wad, out_lumps)
    return converted, len(out_lumps)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert classic Doom-format maps to UDMF.")
    parser.add_argument("--input", required=True, help="Input WAD path (e.g., wads/DOOM.WAD)")
    parser.add_argument("--output", required=True, help="Output WAD path (e.g., wads/DOOM-udmf.wad)")
    args = parser.parse_args()

    in_path = Path(args.input).resolve()
    out_path = Path(args.output).resolve()
    if not in_path.exists():
        raise SystemExit(f"error: input WAD not found: {in_path}")

    converted, total_lumps = convert_wad(in_path, out_path)
    print(f"Converted maps: {converted}")
    print(f"Wrote: {out_path}")
    print(f"Total output lumps: {total_lumps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
