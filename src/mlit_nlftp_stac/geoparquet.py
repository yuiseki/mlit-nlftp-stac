"""The whole catalog as one table, so it can be queried without a server.

A static catalog answers "what is in this dataset" by being read, and "which
files cover this place, from this year, that I may redistribute" only by being
read in its entirety: 21,603 files. Two agents given this catalog both named
that as their largest cost. One GeoParquet file answers it in a query.

This follows the stac-geoparquet convention: one row per Item, the STAC fields
that are worth filtering on promoted to columns, and the geometry written so
that a reader can skip row groups it does not need.
"""

from typing import Dict, Iterable, List, Optional

# Item fields worth filtering on. Everything else stays in the JSON, which is
# still the authoritative copy; this is an index, not a replacement.
COLUMNS = [
    "id",
    "collection",
    "collection_title",
    "title",
    "year",
    "start_datetime",
    "end_datetime",
    "license",
    "redistribution",
    "terms_applied",
    "identifier",
    "region",
    "river",
    "format",
    "crs",
    "nendo",
    "mesh_code",
    "extent_source",
    "href",
    "file_size",
    "declared_size",
    "last_modified",
    "etag",
    "item_href",
]


def item_row(item: Dict, collection_title: str = "", base_url: str = "") -> Dict:
    """One Item as a flat row."""
    p = item.get("properties", {})
    asset = (item.get("assets") or {}).get("source", {})
    start = p.get("start_datetime")
    return {
        "id": item["id"],
        "collection": item.get("collection"),
        "collection_title": collection_title or None,
        "title": p.get("title"),
        # The year is what people filter on, and deriving it here means a
        # reader does not have to parse a timestamp to ask for 2025.
        "year": int(start[:4]) if start else None,
        "start_datetime": start,
        "end_datetime": p.get("end_datetime"),
        "license": p.get("license"),
        "redistribution": p.get("ksj:redistribution"),
        "terms_applied": p.get("ksj:terms_applied"),
        "identifier": p.get("ksj:identifier"),
        "region": p.get("ksj:region"),
        "river": p.get("ksj:river"),
        "format": p.get("ksj:format"),
        "crs": p.get("ksj:crs"),
        "nendo": p.get("ksj:nendo"),
        "mesh_code": p.get("ksj:mesh_code"),
        "extent_source": p.get("ksj:extent_source"),
        "href": asset.get("href"),
        "file_size": asset.get("file:size"),
        "declared_size": p.get("ksj:declared_size"),
        "last_modified": asset.get("ksj:last_modified"),
        "etag": asset.get("ksj:etag"),
        "item_href": (
            f"{base_url}/collections/{item.get('collection')}/items/{item['id']}.json"
            if base_url
            else f"./collections/{item.get('collection')}/items/{item['id']}.json"
        ),
    }


def rows_from(items: Iterable[Dict], titles: Optional[Dict[str, str]] = None,
              base_url: str = "") -> List[Dict]:
    titles = titles or {}
    return [item_row(it, titles.get(it.get("collection"), ""), base_url) for it in items]
