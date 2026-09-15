"""JIS X 0410 mesh codes.

Only the primary (first-order) mesh is handled. Its code is four digits:
the first two are latitude times 1.5, the last two are longitude minus 100.
A cell spans 40 minutes of latitude and one degree of longitude.

This is the one footprint in the whole catalog that can be computed rather
than looked up, so it is the one place an Item gets a real geometry for free.
"""

from typing import Optional, Tuple

BBox = Tuple[float, float, float, float]

LAT_SPAN = 2.0 / 3.0  # 40 minutes
LON_SPAN = 1.0


def primary_mesh_bbox(code: str) -> Optional[BBox]:
    """Return (west, south, east, north), or None if `code` is not a mesh code."""
    if not code or len(code) != 4 or not code.isdigit():
        return None
    south = int(code[:2]) / 1.5
    west = int(code[2:]) + 100.0
    # Japan only. A four-digit number outside this box is some other kind of
    # code that happens to have four digits, and guessing at it would put an
    # Item somewhere it does not belong.
    if not (20.0 <= south <= 46.0 and 122.0 <= west <= 154.0):
        return None
    return (west, south, west + LON_SPAN, south + LAT_SPAN)


def bbox_to_polygon(bbox: BBox) -> dict:
    w, s, e, n = bbox
    return {
        "type": "Polygon",
        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }
