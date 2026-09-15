"""Reading a Shapefile's bounding box out of a zip without downloading it.

A .shp file states its own extent in the first 100 bytes of its header. The
zip holding it says where that file starts. nlftp honours Range requests, so
the extent of a 66 MB prefecture archive costs a few kilobytes instead of the
whole file: 1 GB of N03 becomes about 6 MB of reads.

The functions here take a `reader(start, end) -> bytes` so they can be tested
against an in-memory zip, with no network involved.
"""

import struct
import zlib
from typing import Callable, Dict, List, Optional, Tuple

Reader = Callable[[int, int], bytes]
BBox = Tuple[float, float, float, float]

_EOCD = b"PK\x05\x06"
_CD_ENTRY = b"PK\x01\x02"
_MAX_EOCD = 65557  # 22 byte record plus the largest possible comment


class ZipReadError(Exception):
    pass


def central_directory(reader: Reader, total: int) -> List[Dict]:
    """Every entry in the zip, with where its data starts."""
    tail = reader(max(0, total - _MAX_EOCD), total - 1)
    i = tail.rfind(_EOCD)
    if i < 0:
        raise ZipReadError("no end-of-central-directory record")
    cd_size, cd_off = struct.unpack("<II", tail[i + 12 : i + 20])
    if cd_off == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
        raise ZipReadError("zip64 central directory is not handled")

    cd = reader(cd_off, cd_off + cd_size - 1)
    entries, p = [], 0
    while p + 46 <= len(cd) and cd[p : p + 4] == _CD_ENTRY:
        (method,) = struct.unpack("<H", cd[p + 10 : p + 12])
        csize, usize = struct.unpack("<II", cd[p + 20 : p + 28])
        nlen, elen, clen = struct.unpack("<HHH", cd[p + 28 : p + 34])
        (local_header,) = struct.unpack("<I", cd[p + 42 : p + 46])
        name = cd[p + 46 : p + 46 + nlen].decode("cp932", "replace")
        entries.append(
            {
                "name": name,
                "method": method,
                "compressed_size": csize,
                "size": usize,
                "local_header": local_header,
            }
        )
        p += 46 + nlen + elen + clen
    if not entries:
        raise ZipReadError("central directory holds no entries")
    return entries


def read_member_head(reader: Reader, entry: Dict, want: int = 100) -> bytes:
    """The first `want` bytes of one member, inflating only as far as needed."""
    head = reader(entry["local_header"], entry["local_header"] + 29)
    if head[:4] != b"PK\x03\x04":
        raise ZipReadError(f"{entry['name']}: no local file header")
    nlen, elen = struct.unpack("<HH", head[26:30])
    start = entry["local_header"] + 30 + nlen + elen

    if entry["method"] == 0:  # stored
        return reader(start, start + want - 1)
    if entry["method"] != 8:
        raise ZipReadError(f"{entry['name']}: compression method {entry['method']}")

    # Deflate needs the start of the stream and nothing more; 8 KiB of input
    # yields far more than 100 bytes out for any real shapefile header.
    chunk = min(entry["compressed_size"], 8192)
    blob = reader(start, start + chunk - 1)
    out = zlib.decompressobj(-15).decompress(blob, want)
    if len(out) < want:
        raise ZipReadError(f"{entry['name']}: only {len(out)} bytes inflated")
    return out


def bbox_from_shp_header(head: bytes) -> BBox:
    """(west, south, east, north) from the .shp header's bytes 36..68."""
    if len(head) < 100:
        raise ZipReadError("shapefile header is shorter than 100 bytes")
    if struct.unpack(">I", head[0:4])[0] != 9994:
        raise ZipReadError("not a shapefile: bad magic")
    xmin, ymin, xmax, ymax = struct.unpack("<4d", head[36:68])
    return (xmin, ymin, xmax, ymax)


def shp_bbox(reader: Reader, total: int) -> Tuple[str, BBox]:
    """The name and extent of the first .shp in the archive."""
    entries = central_directory(reader, total)
    shps = [e for e in entries if e["name"].lower().endswith(".shp")]
    if not shps:
        raise ZipReadError(f"no .shp among {len(entries)} entries")
    entry = shps[0]
    return entry["name"], bbox_from_shp_header(read_member_head(reader, entry))


def looks_like_japan(bbox: Optional[BBox]) -> bool:
    """A sanity check on a derived extent, so a misread cannot pass silently."""
    if not bbox:
        return False
    w, s, e, n = bbox
    return 122.0 <= w <= 154.0 and 20.0 <= s <= 46.0 and w < e and s < n and e <= 154.5 and n <= 46.5
