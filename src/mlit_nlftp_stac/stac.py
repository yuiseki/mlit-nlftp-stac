"""Turning a harvested link into STAC.

One Collection per upstream dataset page, one Item per downloadable zip, one
asset per Item pointing at the file on nlftp. Nothing is copied or converted
here, so nothing in the catalog can go stale except the metadata itself.
"""

import json
import posixpath
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .ksj import parse_filename
from .mesh import bbox_to_polygon, primary_mesh_bbox
from .page import spdx_from_terms
from .table import nendo_of, title_from_cells, year_from_nendo

STAC_VERSION = "1.1.0"
FILE_EXT = "https://stac-extensions.github.io/file/v2.1.0/schema.json"

# Last resort only, for a Collection with no Item extent and no
# data/region_bbox.json to fall back on. The real value comes from N03's own
# nationwide shapefile header; this copy is rounded outward so it can only be
# too large, never too small.
JAPAN_BBOX = [122.9, 20.4, 154.0, 45.6]
AGREEMENT = "https://nlftp.mlit.go.jp/ksj/other/agreement.html"

MLIT = {
    "name": "国土交通省 国土政策局 (MLIT, National Spatial Planning and Regional Policy Bureau)",
    "roles": ["producer", "licensor"],
    "url": "https://nlftp.mlit.go.jp/ksj/",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _temporal(year: Optional[int]):
    """A KSJ year may be a calendar year or a fiscal one and the page does not
    always say which. Spanning the calendar year is the least wrong reading, so
    `datetime` is null and the interval carries the meaning."""
    if year is None:
        return None, None
    return f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"


def item_id(row: dict) -> str:
    """The id comes from the URL, not from the name printed on the page.

    On the A51-2025 page two links are both labelled `A51-25_40_GML.zip`, but
    one of them points at `A51-24/A51-24_40_GML.zip`. They are different files
    (12,520,868 and 11,506,692 bytes, measured). Keying on the printed name
    loses one of them; the path is what is actually unique.
    """
    base = posixpath.basename(row["url"]) or row["filename"]
    return base.rsplit(".", 1)[0]


def build_item(
    row: dict,
    page_url: str,
    collection_id: str,
    regions: Optional[dict] = None,
    license: str = "other",
    terms: str = "",
) -> dict:
    """`row` is one harvested link, optionally carrying HEAD results.

    `regions` maps a 地域 name to its extent, read from N03 行政区域 by
    `scripts/07_region_bbox.py`.

    `license` and `terms` are the Collection's, repeated here on purpose: a
    person who lands on an Item page and downloads the zip from it never sees
    the Collection, and the terms are the one thing they must not miss.
    """
    parsed = parse_filename(posixpath.basename(row["url"]) or row["filename"])
    cells = row.get("cells") or {}

    # The page states the year in its own 年度 column. Reading it from the
    # filename works most of the time and is wrong the rest of it, as with the
    # two A51 links that print the same name for different years.
    year = year_from_nendo(nendo_of(cells)) or parsed.year
    start, end = _temporal(year)

    # A mesh code names the exact cell the file covers, so it wins. Failing
    # that, a file published per prefecture covers that prefecture, and N03
    # says how far that reaches. Both are real extents; neither is invented.
    bbox = primary_mesh_bbox(parsed.mesh_code) if parsed.mesh_code else None
    extent_source = "mesh" if bbox else None
    if bbox is None and regions:
        region = regions.get(cells.get("地域", ""))
        if region:
            bbox = tuple(region["bbox"])
            extent_source = "n03"
    geometry = bbox_to_polygon(bbox) if bbox else None

    props = {
        "datetime": None,
        # Repeated from the Collection. STAC allows `license` on an Item, and
        # an Item page with a download button and no terms on it is a trap.
        "license": license,
        "ksj:terms": terms,
        "start_datetime": start,
        "end_datetime": end,
        "ksj:identifier": parsed.identifier,
        "ksj:area_tokens": parsed.area_tokens,
        "ksj:mesh_code": parsed.mesh_code,
        "ksj:declared_size": row.get("size_label"),
    }
    if extent_source:
        # The footprint of a prefecture file is the prefecture, not the
        # measured extent of what is inside the zip. Say which it is.
        props["ksj:extent_source"] = (
            "JIS mesh code in the filename" if extent_source == "mesh"
            else "国土数値情報 N03 行政区域 (administrative extent, not the file's own)"
        )
    title = title_from_cells(cells)
    if title:
        props["title"] = title
    for label, key in (("地域", "ksj:region"), ("河川", "ksj:river"),
                       ("形式", "ksj:format"), ("測地系", "ksj:crs")):
        if cells.get(label):
            props[key] = cells[label]
    if nendo_of(cells):
        props["ksj:nendo"] = nendo_of(cells)
    if start is None:
        # STAC allows a null datetime only when both ends are present.
        props["datetime"] = "1970-01-01T00:00:00Z"
        props["ksj:datetime_is_unknown"] = True
        del props["start_datetime"], props["end_datetime"]

    asset = {
        "href": row["url"],
        "type": "application/zip",
        "title": row["filename"],
        # Not `data`: this is the upstream original, not a cloud-native copy
        # produced here. A `data` asset appears only once a conversion exists.
        "roles": ["source"],
    }
    # Only from a HEAD response. The size printed on the page disagrees with
    # the file often enough that copying it here would be a lie with a number.
    if row.get("bytes"):
        asset["file:size"] = row["bytes"]
    if row.get("last_modified"):
        asset["ksj:last_modified"] = row["last_modified"]
    if row.get("etag"):
        asset["ksj:etag"] = row["etag"]

    item = {
        "type": "Feature",
        "stac_version": STAC_VERSION,
        "stac_extensions": [FILE_EXT],
        "id": item_id(row),
        "geometry": geometry,
        "properties": props,
        "collection": collection_id,
        "links": [
            {"rel": "root", "href": "../../../catalog.json", "type": "application/json"},
            {"rel": "parent", "href": "../collection.json", "type": "application/json"},
            {"rel": "collection", "href": "../collection.json", "type": "application/json"},
            {"rel": "via", "href": page_url, "type": "text/html"},
            # 9 of 135 pages state no terms at all. An Item page with a
            # download button, no terms and no way to reach them is the
            # failure this link exists to prevent.
            {"rel": "license", "href": AGREEMENT, "type": "text/html",
             "title": "国土数値情報 利用約款"},
        ],
        "assets": {"source": asset},
    }
    if bbox:
        item["bbox"] = list(bbox)
    return item


# Rows of the page's own table that say something a catalogue user wants and
# that fit in a field. The rest stays on the page.
_EXTRA_FIELDS = {
    "座標系": "ksj:coordinate_system",
    "データ形状": "ksj:geometry_type",
    "データ基準年月日": "ksj:reference_date",
    "原典資料": "ksj:source_material",
    "関連する法律": "ksj:related_law",
}


def build_collection(
    collection_id: str,
    page_url: str,
    items: Iterable[dict],
    page: Optional[dict] = None,
    regions: Optional[dict] = None,
) -> dict:
    """`page` is the parsed dataset page, when one was harvested for this id.

    Without it a Collection can only be called by its identifier, which tells a
    reader nothing. `A31b` means "浸水想定区域データ" and there is no way to
    know that from the code.
    """
    page = page or {}
    title = page.get("title") or collection_id
    description = page.get("description") or ""
    terms = page.get("terms") or ""
    items = list(items)
    years = sorted(
        {
            p
            for it in items
            for p in (it["properties"].get("start_datetime"), it["properties"].get("end_datetime"))
            if p
        }
    )
    # The union of what the Items actually cover, not a list of every Item's
    # box: A31b alone would contribute 2,007 of them and say no more than one.
    boxes = [it["bbox"] for it in items if "bbox" in it]
    if boxes:
        spatial = [[
            min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes),
        ]]
    else:
        nationwide = (regions or {}).get("全国", {}).get("bbox")
        spatial = [list(nationwide) if nationwide else JAPAN_BBOX]

    return {
        "type": "Collection",
        "stac_version": STAC_VERSION,
        "id": collection_id,
        "title": f"{title} ({collection_id})",
        "description": description or (
            f"国土数値情報 {collection_id}. The dataset page states no description; "
            f"see {page_url}."
        ),
        # Read from the page's 使用許諾条件 row, and only promoted to an SPDX id
        # when the whole statement is that one licence. Most KSJ datasets split
        # their terms by year, which no single identifier can express.
        "license": spdx_from_terms(terms),
        "providers": [MLIT],
        "keywords": [k for k in ("国土数値情報", page.get("identifier") or collection_id) if k],
        "extent": {
            "spatial": {"bbox": spatial},
            "temporal": {"interval": [[years[0] if years else None, years[-1] if years else None]]},
        },
        "updated": _utc_now(),
        "ksj:identifier": page.get("identifier") or collection_id,
        "ksj:terms": terms,
        "ksj:source_page": page_url,
        **{
            key: page.get("fields", {})[label]
            for label, key in _EXTRA_FIELDS.items()
            if page.get("fields", {}).get(label)
        },
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json"},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
            {"rel": "self", "href": "./collection.json", "type": "application/json"},
            {"rel": "license", "href": AGREEMENT, "type": "text/html", "title": "国土数値情報 利用約款"},
            {"rel": "via", "href": page_url, "type": "text/html"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown"},
        ]
        + [
            {"rel": "item", "href": f"./items/{it['id']}.json", "type": "application/geo+json"}
            for it in items
        ],
    }


def build_root(collections: Iterable[dict]) -> dict:
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": "mlit-nlftp",
        "title": "国土数値情報 (MLIT National Land Numerical Information)",
        "description": (
            "A mirror of the download index at https://nlftp.mlit.go.jp/ksj/. "
            "One Collection per dataset, one Item per downloadable file. "
            "The files themselves remain on MLIT's servers."
        ),
        "updated": _utc_now(),
        "links": [
            {"rel": "root", "href": "./catalog.json", "type": "application/json"},
            {"rel": "self", "href": "./catalog.json", "type": "application/json"},
            {"rel": "via", "href": "https://nlftp.mlit.go.jp/ksj/", "type": "text/html"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown"},
        ]
        + [
            {
                "rel": "child",
                "href": f"./collections/{c['id']}/collection.json",
                "type": "application/json",
                "title": c.get("title"),
            }
            for c in collections
        ],
    }


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
