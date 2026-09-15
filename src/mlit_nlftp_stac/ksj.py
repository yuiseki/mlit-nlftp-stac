"""Reading meaning out of upstream filenames.

Upstream names look regular until they are not. `N02-25_GML.zip` is the 2025
nationwide file; `A16-85_14_GML.zip` is from 1985; `N03-20260101_GML.zip`
carries a full date; `A31-22_10_5439_GEOJSON.zip` ends in a mesh code.

What this module deliberately does NOT do is decide that a two-digit token is
a prefecture. `A47-21_14` and `A47-21_55` sit in the same slot on the same
page, and only one of them can be a prefecture code. The tokens are reported
as they are; anything that wants to read them as prefectures has to know which
dataset it is looking at.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .mesh import primary_mesh_bbox

# `A31a`, `L03-b-u`, `N02` — letters and digits, then optional -letter groups.
_IDENT = r"[A-Z]\d{2}[a-z]?(?:-[a-z](?:-[a-z])?)?"
_STEM = re.compile(rf"^({_IDENT})-(\d{{2,8}})(.*)$")
_YEAR_ONLY = re.compile(r"(?:^|[_\-])((?:19|20)\d{2})(?:[_\-.]|$)")
_TOKEN = re.compile(r"\d+")


@dataclass
class ParsedName:
    filename: str
    identifier: Optional[str] = None
    year: Optional[int] = None
    area_tokens: List[str] = field(default_factory=list)
    mesh_code: Optional[str] = None


def _year_from(digits: str) -> Optional[int]:
    """`25` -> 2025, `85` -> 1985, `120401` -> 2012, `20260101` -> 2026."""
    if len(digits) == 2:
        v = int(digits)
        # KSJ has nothing later than the current decade and nothing before the
        # 1950s, so 41..99 can only be the 20th century.
        return 2000 + v if v <= 40 else 1900 + v
    if len(digits) == 6:  # yymmdd
        return _year_from(digits[:2])
    if len(digits) == 8:  # yyyymmdd
        return int(digits[:4])
    if len(digits) == 4:
        return int(digits)
    return None


def parse_filename(filename: str) -> ParsedName:
    stem = re.sub(r"\.(zip|ZIP)$", "", filename)
    m = _STEM.match(stem)
    if not m:
        ym = _YEAR_ONLY.search(stem)
        return ParsedName(filename=filename, year=int(ym.group(1)) if ym else None)

    identifier, digits, rest = m.group(1), m.group(2), m.group(3)
    year = _year_from(digits)

    tokens = [t for t in _TOKEN.findall(rest)]
    mesh = next((t for t in tokens if primary_mesh_bbox(t)), None)
    if mesh:
        tokens = [t for t in tokens if t != mesh]

    return ParsedName(
        filename=filename,
        identifier=identifier,
        year=year,
        area_tokens=tokens,
        mesh_code=mesh,
    )
