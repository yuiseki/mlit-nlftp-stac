#!/usr/bin/env python3
"""data/links.jsonl (+ data/head.jsonl) -> catalog/.

Offline. Runs in seconds and does not touch the network, so the catalog can be
rebuilt as often as the shape of it changes.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mlit_nlftp_stac.page import spdx_from_terms  # noqa: E402
from mlit_nlftp_stac.stac import (  # noqa: E402
    REDISTRIBUTION,
    build_collection,
    build_item,
    build_license_catalog,
    build_license_status_root,
    build_collections_root,
    build_licenses_root,
    build_region_catalog,
    build_regions_root,
    build_root,
    write_json,
)

DATA = ROOT / "data"


def load(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def collection_id(page: str) -> str:
    """`A31b-2025` -> `A31b`, `P30` -> `P30`, `mesh250r6` -> `mesh250r6`.

    The trailing `-YYYY` is the page's own version, not part of the dataset's
    identity; every year of a dataset belongs in one Collection.
    """
    head, _, tail = page.rpartition("-")
    return head if head and tail.isdigit() and len(tail) == 4 else page


def _count_with_geometry(out: Path) -> int:
    n = 0
    for p in out.glob("collections/*/items/*.json"):
        if json.loads(p.read_text()).get("geometry") is not None:
            n += 1
    return n


def _pages_by_collection(rows: list) -> dict:
    """One page per Collection.

    A dataset can have both `A03` and `A03-2025`. They describe the same thing;
    the versioned page is the current one, so it wins. A page with no
    description loses to one that has it.
    """
    best: dict = {}
    for r in rows:
        cid = collection_id(r["page"])
        version = r["page"].rpartition("-")[2]
        rank = (bool(r.get("description")), int(version) if version.isdigit() else 0)
        if cid not in best or rank > best[cid][0]:
            best[cid] = (rank, r)
    return {k: v[1] for k, v in best.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", help="build just these collections")
    ap.add_argument("--out", default=str(ROOT / "catalog"))
    ap.add_argument(
        "--base-url",
        default="",
        help="where the catalog will be served, e.g. https://stac.yuiseki.net/mlit-nlftp. "
        "Makes the self links absolute; everything else stays relative so the "
        "catalog still works from a local directory.",
    )
    args = ap.parse_args()
    base_url = args.base_url.rstrip("/")

    links = load(DATA / "links.jsonl")
    if not links:
        print("data/links.jsonl is missing. Run scripts/01_fetch_index.py first.", file=sys.stderr)
        return 1
    head = {r["url"]: r for r in load(DATA / "head.jsonl") if r.get("status") == 200}
    pages = _pages_by_collection(load(DATA / "pages.jsonl"))
    regions = {}
    region_file = DATA / "region_bbox.json"
    if region_file.exists():
        regions = json.loads(region_file.read_text())["regions"]
        print(f"{len(regions)} region extents from N03")
    else:
        print("data/region_bbox.json is missing, so only mesh-named items get a "
              "footprint. Run scripts/07_region_bbox.py.", file=sys.stderr)
    if not pages:
        print("data/pages.jsonl is missing, so collections will be named by "
              "identifier only. Re-run scripts/01_fetch_index.py.", file=sys.stderr)
    print(f"{len(links)} links, {len(head)} with a HEAD result "
          f"({len(head) * 100 // max(len(links), 1)}%)")

    groups = defaultdict(list)
    for row in links:
        groups[collection_id(row["page"])].append(row)
    if args.only:
        groups = {k: v for k, v in groups.items() if k in set(args.only)}

    out = Path(args.out)
    collections = []
    by_region: dict = {}
    by_license: dict = {}
    for cid, rows in sorted(groups.items()):
        page_url = rows[0]["page_url"]
        page = pages.get(cid) or {}
        terms = page.get("terms") or ""
        license_ = spdx_from_terms(terms)
        coll_title = f"{page.get('title') or cid} ({cid})"
        items = [
            build_item(
                {**r, **head.get(r["url"], {})}, page_url, cid, regions,
                license_, terms, base_url, coll_title,
            )
            for r in rows
        ]
        for it in items:
            write_json(out / "collections" / cid / "items" / f"{it['id']}.json", it)
        coll = build_collection(cid, page_url, items, page, regions, base_url)
        write_json(out / "collections" / cid / "collection.json", coll)
        (out / "collections" / cid / "README.md").write_text(
            f"# {coll['title']}\n\n{coll['description']}\n\n"
            f"- Identifier: `{coll['ksj:identifier']}`\n"
            f"- Files: {len(items)}\n"
            f"- Source: {page_url}\n"
            f"- Terms of use (as stated upstream): {coll['ksj:terms'] or 'not stated on the page'}\n"
            f"- SPDX: `{coll['license']}`\n", encoding="utf-8")
        for it in items:
            status = it["properties"].get("ksj:redistribution") or "check"
            by_license.setdefault(status, {}).setdefault(
                cid, {"title": coll["title"], "entries": []}
            )["entries"].append(
                {"id": it["id"], "title": it["properties"].get("title") or it["id"]}
            )
            region = it["properties"].get("ksj:region")
            if not region or region not in regions:
                # 整備局, 三大都市圏 and mesh numbers sit in the same column as
                # prefecture names but are not places N03 knows, so they get no
                # region entry rather than a wrong one.
                continue
            by_region.setdefault(region, []).append(
                {
                    "collection": cid,
                    "id": it["id"],
                    "title": it["properties"].get("title") or it["id"],
                }
            )
        collections.append(coll)
        print(f"  {cid:<14} {len(items):>5} items  {coll['license']:<10} {coll['title']}")

    region_index = []
    for name, entries in sorted(
        by_region.items(), key=lambda kv: (regions[kv[0]].get("code") or "")
    ):
        code = regions[name].get("code")
        slug = code or name
        write_json(
            out / "regions" / f"{slug}.json",
            build_region_catalog(code, name, entries, base_url),
        )
        region_index.append(
            {
                "slug": slug,
                "title": f"{name} ({code})" if code else name,
                "count": len(entries),
            }
        )
    if region_index:
        write_json(out / "regions" / "catalog.json", build_regions_root(region_index, base_url))
        print(f"{len(region_index)} regions, "
              f"{sum(r['count'] for r in region_index)} item links -> {out / 'regions'}")

    status_index = []
    for status in ("allowed", "not-allowed", "check"):
        lic_groups = by_license.get(status) or {}
        if not lic_groups:
            continue
        rows = []
        for cid, g in sorted(lic_groups.items()):
            write_json(
                out / "licenses" / status / f"{cid}.json",
                build_license_catalog(status, cid, g["title"], g["entries"], base_url),
            )
            rows.append({"collection": cid, "title": g["title"], "count": len(g["entries"])})
        write_json(
            out / "licenses" / status / "catalog.json",
            build_license_status_root(status, rows, base_url),
        )
        status_index.append({"status": status, "count": sum(r["count"] for r in rows)})
        print(f"  {REDISTRIBUTION[status][0].split(' ')[0]:<14} "
              f"{sum(r['count'] for r in rows):>6} 件 / {len(rows)} コレクション")
    if status_index:
        write_json(out / "licenses" / "catalog.json", build_licenses_root(status_index, base_url))

    write_json(out / "collections" / "catalog.json",
               build_collections_root(collections, base_url))
    write_json(
        out / "catalog.json",
        build_root(collections, base_url, bool(region_index), bool(status_index)),
    )
    for name in ("README.md", "AGENTS.md"):
        (out / name).write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    titled = sum(
        1 for c in collections for link in c["links"] if link["rel"] == "item"
    )
    named = sum(1 for rows_ in groups.values() for r in rows_ if (r.get("cells") or {}))
    print(f"{len(collections)} collections, {titled} items -> {out}")
    print(f"{named} of {titled} items carry the page's own row "
          f"({named * 100 // max(titled, 1)}%)")
    located = sum(
        1
        for c in collections
        for link in c["links"]
        if link["rel"] == "item"
    )
    with_geom = _count_with_geometry(out)
    print(f"{with_geom} of {located} items have a footprint "
          f"({with_geom * 100 // max(located, 1)}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
