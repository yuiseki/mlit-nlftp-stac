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
from .terms import resolve as resolve_terms

STAC_VERSION = "1.1.0"
ROOT_TITLE = "国土数値情報 (MLIT National Land Numerical Information)"
FILE_EXT = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
TABLE_EXT = "https://stac-extensions.github.io/table/v1.2.0/schema.json"

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
    base_url: str = "",
    collection_title: str = "",
    dataset_identifier: str = "",
    latest_years: Optional[dict] = None,
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

    # The licence belongs to the year, not to the dataset: 鉄道データ is
    # CC BY 4.0 from 2020 and 商用可 before it. Resolving it here is the only
    # place it can be right, because this is the only place a year is known.
    spdx, redistribution, applied = resolve_terms(terms, year, cells.get("地域"))
    props = {
        "datetime": None,
        # Repeated from the Collection. STAC allows `license` on an Item, and
        # an Item page with a download button and no terms on it is a trap.
        "license": spdx,
        "ksj:redistribution": redistribution,
        **({"ksj:terms_applied": applied} if applied else {}),
        **({"ksj:terms": terms} if terms else {}),
        "start_datetime": start,
        "end_datetime": end,
        # The filename yields it for most datasets and not for the mesh ones,
        # whose names start with a digit. The page states it either way.
        "ksj:identifier": parsed.identifier or dataset_identifier or None,
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
    # The dataset's name belongs in the title, not only in the link that
    # points here. STAC Browser replaces a link's title with the Item's own
    # once it loads the Item, so a region page of 356 files was showing
    # "2006_東京（平成18年）" fourteen times over with nothing to tell them
    # apart. A title has to say what the thing is wherever it is read.
    title = title_from_cells(cells)
    if title and collection_title:
        title = f"{title} — {collection_title}"
    if title:
        props["title"] = title
    for label, key in (("地域", "ksj:region"), ("河川", "ksj:river"),
                       ("形式", "ksj:format"), ("測地系", "ksj:crs")):
        if cells.get(label):
            props[key] = cells[label]
    if nendo_of(cells):
        props["ksj:nendo"] = nendo_of(cells)
    # Whether this is the newest year for its region. Without it, finding the
    # current file for 高知 meant listing every Item of the dataset and
    # comparing titles by eye.
    if latest_years is not None and year is not None:
        key = (cells.get("地域") or "", cells.get("形式") or "")
        if key in latest_years:
            props["ksj:is_latest"] = year == latest_years[key]
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
            {"rel": "root", "href": "../../../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "../collection.json", "type": "application/json",
             "title": collection_title or collection_id},
            {"rel": "collection", "href": "../collection.json", "type": "application/json",
             "title": collection_title or collection_id},
            {"rel": "via", "href": page_url, "type": "text/html"},
            # 9 of 135 pages state no terms at all. An Item page with a
            # download button, no terms and no way to reach them is the
            # failure this link exists to prevent.
            {"rel": "license", "href": AGREEMENT, "type": "text/html",
             "title": "国土数値情報 利用約款"},
        ],
        "assets": {"source": asset},
    }
    if base_url:
        item["links"].insert(
            0,
            {
                "rel": "self",
                "href": f"{base_url}/collections/{collection_id}/items/{item['id']}.json",
                "type": "application/geo+json",
            },
        )
    if bbox:
        item["bbox"] = list(bbox)
    return item


def _table_column(col: dict) -> dict:
    """One entry of `table:columns`.

    `name` is the name a query has to spell, which is `N02_001` and not
    鉄道区分; the readable name goes in the description, where a person and an
    agent both still see it. A coded column is a string in the shapefile, so
    that is its type here; which code list it uses is in `ksj:variants`.
    """
    readable = col.get("name") or ""
    desc = col.get("description") or ""
    parts = [p for p in (readable, desc) if p]
    if col.get("codelist"):
        parts.append(f"コードリスト「{col['codelist']}」")
    return {
        "name": col["column"],
        "description": " / ".join(parts),
        "type": "string" if col["type"] in ("codelist", "unknown") else col["type"],
    }


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
    base_url: str = "",
) -> dict:
    """`page` is the parsed dataset page, when one was harvested for this id.

    Without it a Collection can only be called by its identifier, which tells a
    reader nothing. `A31b` means "浸水想定区域データ" and there is no way to
    know that from the code.
    """
    page = page or {}
    title = page.get("title") or collection_id
    variants = page.get("variants") or []
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
        **({"stac_extensions": [TABLE_EXT]} if len(variants) == 1 else {}),
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
        "keywords": [
            k for k in (
                "国土数値情報",
                page.get("identifier") or collection_id,
                page.get("category"),
            ) if k
        ],
        # What the columns are called and what their coded values mean. Two
        # agents could find the right dataset here and not plan the work,
        # because this was the one thing only the upstream page had.
        **({"ksj:variants": variants} if variants else {}),
        # The standard field, but only when it can be right: a dataset that
        # ships several shapefiles has several schemas, and one flat list
        # would describe none of them.
        **(
            {"table:columns": [_table_column(c) for c in variants[0]["columns"]]}
            if len(variants) == 1
            else {}
        ),
        "extent": {
            "spatial": {"bbox": spatial},
            "temporal": {"interval": [[years[0] if years else None, years[-1] if years else None]]},
        },
        "updated": _utc_now(),
        "ksj:identifier": page.get("identifier") or collection_id,
        # Absent rather than empty: 7 pages state no terms, and "" reads as a
        # value. `ksj:redistribution` on each Item says `check` for these.
        **({"ksj:terms": terms} if terms else {}),
        "ksj:source_page": page_url,
        **({"ksj:category": page["category"]} if page.get("category") else {}),
        # The newest year this dataset has, which is the first thing anyone
        # asks and used to mean reading every Item's title.
        **({"ksj:latest_year": max(years_seen)} if (years_seen := sorted({
            int(it["properties"]["start_datetime"][:4])
            for it in items
            if it["properties"].get("start_datetime")
        })) else {}),
        **{
            key: page.get("fields", {})[label]
            for label, key in _EXTRA_FIELDS.items()
            if page.get("fields", {}).get(label)
        },
        "links": [
            {"rel": "root", "href": "../../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json",
             "title": "データセット別 (by dataset)"},
            {
                "rel": "self",
                "href": (
                    f"{base_url}/collections/{collection_id}/collection.json"
                    if base_url
                    else "./collection.json"
                ),
                "type": "application/json",
            },
            {"rel": "license", "href": AGREEMENT, "type": "text/html", "title": "国土数値情報 利用約款"},
            {"rel": "via", "href": page_url, "type": "text/html"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown"},
            {"rel": "agents", "href": "../../AGENTS.md", "type": "text/markdown",
             "title": "AGENTS.md — how to get an answer out of this catalog"},
        ]
        + [
            {
                "rel": "item",
                "href": f"./items/{it['id']}.json",
                "type": "application/geo+json",
                # Without this a reader looking for 高知 has to know that the
                # two digits in P20-12_39_GML are a JIS prefecture code. The
                # title is already on the Item; not repeating it here made the
                # catalog unusable without outside knowledge.
                "title": it["properties"].get("title") or it["id"],
            }
            for it in items
        ],
    }


REGIONS_ID = "regions"

REDISTRIBUTION = {
    "allowed": (
        "再配布できるもの (redistribution allowed)",
        "利用約款が「複製物の再配布を含む」と明記している商用可のデータと、"
        "CC BY 4.0 のデータ。出典と改変の旨を書けば再配布できます。",
    ),
    "not-allowed": (
        "再配布できないもの (redistribution not allowed)",
        "利用約款が非商用と定めるデータ。第1条が「非商用目的のみでの利用"
        "（ただし複製物の再配布を除く）」と書いているので、再配布はできません。",
    ),
    "check": (
        "確認が要るもの (check before redistributing)",
        "「一部制限」で提供者ごとに条件が違うもの、年次が読めず条件を解決"
        "できなかったもの、条件の記載が無いもの。可否は読んで判断してください。",
    ),
}


def build_license_catalog(
    status: str,
    collection_id: str,
    collection_title: str,
    entries: Iterable[dict],
    base_url: str = "",
) -> dict:
    """One dataset's Items that share a redistribution status."""
    entries = list(entries)
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": f"license-{status}-{collection_id}",
        "title": f"{collection_title} — {len(entries)} 件",
        "description": f"{collection_title} のうち再配布の可否が「{status}」のファイル。",
        "ksj:redistribution": status,
        "links": [
            {"rel": "root", "href": "../../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "./catalog.json", "type": "application/json",
             "title": REDISTRIBUTION[status][0]},
            {
                "rel": "self",
                "href": (f"{base_url}/licenses/{status}/{collection_id}.json"
                         if base_url else f"./{collection_id}.json"),
                "type": "application/json",
            },
            {"rel": "license", "href": AGREEMENT, "type": "text/html",
             "title": "国土数値情報 利用約款"},
        ]
        + [
            {
                "rel": "item",
                "href": f"../../collections/{collection_id}/items/{e['id']}.json",
                "type": "application/geo+json",
                "title": e["title"],
            }
            for e in entries
        ],
    }


def build_license_status_root(status: str, groups: Iterable[dict], base_url: str = "") -> dict:
    groups = list(groups)
    title, description = REDISTRIBUTION[status]
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": f"license-{status}",
        "title": f"{title} — {sum(g['count'] for g in groups)} 件",
        "description": description,
        "ksj:redistribution": status,
        "links": [
            {"rel": "root", "href": "../../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json",
             "title": "ライセンス別 (by licence)"},
            {
                "rel": "self",
                "href": (f"{base_url}/licenses/{status}/catalog.json"
                         if base_url else "./catalog.json"),
                "type": "application/json",
            },
            {"rel": "license", "href": AGREEMENT, "type": "text/html",
             "title": "国土数値情報 利用約款"},
        ]
        + [
            {
                "rel": "child",
                "href": f"./{g['collection']}.json",
                "type": "application/json",
                "title": f"{g['title']} — {g['count']} 件",
            }
            for g in groups
        ],
    }


def build_licenses_root(statuses: Iterable[dict], base_url: str = "") -> dict:
    statuses = list(statuses)
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": "licenses",
        "title": "ライセンス別 (by licence)",
        "description": (
            "国土数値情報の利用条件は年次ごとに変わります。鉄道データは2020年以降が"
            "CC BY 4.0 で、それ以前は商用可。学校データは2023年度と2021年度が"
            "CC BY 4.0 で、2013年度は非商用。ここでは Item ごとに年次から解決した"
            "結果で引けます。判定の根拠は各 Item の ksj:terms_applied にあります。"
        ),
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {
                "rel": "self",
                "href": f"{base_url}/licenses/catalog.json" if base_url else "./catalog.json",
                "type": "application/json",
            },
            {"rel": "license", "href": AGREEMENT, "type": "text/html",
             "title": "国土数値情報 利用約款"},
        ]
        + [
            {
                "rel": "child",
                "href": f"./{s['status']}/catalog.json",
                "type": "application/json",
                "title": f"{REDISTRIBUTION[s['status']][0]} — {s['count']} 件",
            }
            for s in statuses
        ],
    }


def build_region_catalog(
    code: Optional[str],
    name: str,
    entries: Iterable[dict],
    base_url: str = "",
) -> dict:
    """A browsable list of every Item that covers one region.

    Items live under their Collection, which is the right place for them and
    the wrong one for the question a planner actually asks: "what is there for
    高知?". Answering that from Collections alone means opening all 110 of
    them. This is the same Items, indexed the other way.
    """
    entries = list(entries)
    slug = code or name
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": f"region-{slug}",
        "title": f"{name} ({code})" if code else name,
        "description": (
            f"国土数値情報 のうち {name} を対象とするファイル {len(entries)} 件。"
            "Collection ごとに分かれた Item を地域から引くための索引です。"
        ),
        "ksj:region": name,
        "ksj:region_code": code,
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "./catalog.json", "type": "application/json",
             "title": "地域別 (by region)"},
            {
                "rel": "self",
                "href": f"{base_url}/regions/{slug}.json" if base_url else f"./{slug}.json",
                "type": "application/json",
            },
        ]
        + [
            {
                "rel": "item",
                "href": f"../collections/{e['collection']}/items/{e['id']}.json",
                "type": "application/geo+json",
                "title": e["title"],
            }
            for e in entries
        ],
    }


def build_regions_root(regions: Iterable[dict], base_url: str = "") -> dict:
    regions = list(regions)
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": REGIONS_ID,
        "title": "地域別 (by region)",
        "description": (
            "同じ Item を地域から引くための索引。Collection を 110 件開かずに "
            "「この県には何があるか」に答えるためのものです。"
        ),
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {
                "rel": "self",
                "href": f"{base_url}/regions/catalog.json" if base_url else "./catalog.json",
                "type": "application/json",
            },
        ]
        + [
            {
                "rel": "child",
                "href": f"./{r['slug']}.json",
                "type": "application/json",
                "title": f"{r['title']} — {r['count']} 件",
            }
            for r in regions
        ],
    }


def build_collections_root(collections: Iterable[dict], base_url: str = "") -> dict:
    """The dataset view, as a Catalog of its own.

    Without it the root linked straight to 110 Collections and the two other
    views sat among them, so the levels of the tree held different kinds of
    thing. Worse, every Collection's own root and parent links pointed at
    `../catalog.json`, which from `collections/N02/` is
    `collections/catalog.json`: a file that did not exist. 110 dangling links,
    and nothing noticed because the validator only followed item links.
    """
    collections = list(collections)
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": "collections",
        "title": "データセット別 (by dataset)",
        "description": (
            f"国土数値情報の {len(collections)} データセット。"
            "識別子ごとに 1 Collection、ダウンロードできる zip ごとに 1 Item。"
        ),
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {
                "rel": "self",
                "href": f"{base_url}/collections/catalog.json" if base_url else "./catalog.json",
                "type": "application/json",
            },
        ]
        + [
            {
                "rel": "child",
                "href": f"./{c['id']}/collection.json",
                "type": "application/json",
                "title": c.get("title"),
            }
            for c in collections
        ],
    }


def build_root(
    collections: Iterable[dict],
    base_url: str = "",
    regions: bool = False,
    licenses: bool = False,
) -> dict:
    return {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": "mlit-nlftp",
        "title": ROOT_TITLE,
        "description": (
            "A mirror of the download index at https://nlftp.mlit.go.jp/ksj/. "
            "One Collection per dataset, one Item per downloadable file. "
            "The files themselves remain on MLIT's servers."
        ),
        "updated": _utc_now(),
        "links": [
            {"rel": "root", "href": "./catalog.json", "type": "application/json",
             "title": ROOT_TITLE},
            {
                "rel": "self",
                "href": f"{base_url}/catalog.json" if base_url else "./catalog.json",
                "type": "application/json",
            },
            {"rel": "via", "href": "https://nlftp.mlit.go.jp/ksj/", "type": "text/html",
             "title": "国土数値情報ダウンロードサイト"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown",
             "title": "README"},
            # Published and, until now, linked from nowhere: two agents given
            # this catalog never saw it.
            {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown",
             "title": "AGENTS.md — how to get an answer out of this catalog"},
            # The same Items as one table, for the question a tree cannot
            # answer: everything matching a filter, across all 110 datasets.
            {"rel": "alternate", "href": "./items.parquet",
             "type": "application/vnd.apache.parquet",
             "title": "items.parquet — 全 Item を 1 つの GeoParquet に"},
            {
                "rel": "child",
                "href": "./collections/catalog.json",
                "type": "application/json",
                "title": "データセット別 (by dataset)",
            },
        ]
        + (
            [
                {
                    "rel": "child",
                    "href": "./regions/catalog.json",
                    "type": "application/json",
                    "title": "地域別 (by region)",
                }
            ]
            if regions
            else []
        )
        + (
            [
                {
                    "rel": "child",
                    "href": "./licenses/catalog.json",
                    "type": "application/json",
                    "title": "ライセンス別 (by licence)",
                }
            ]
            if licenses
            else []
        )
        ,
    }


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
