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
from mlit_nlftp_stac.table import nendo_of, year_from_nendo  # noqa: E402
from mlit_nlftp_stac.stac import _slug  # noqa: E402
from mlit_nlftp_stac import docs  # noqa: E402
from mlit_nlftp_stac.stac import (  # noqa: E402
    REDISTRIBUTION,
    REGION_GROUP_MIN,
    YEAR_GROUP_MIN,
    build_year_catalog,
    build_year_region_catalog,
    build_collection,
    build_item,
    build_license_catalog,
    build_license_status_root,
    build_categories_root,
    build_category_catalog,
    build_collections_root,
    build_licenses_root,
    build_region_catalog,
    build_regions_root,
    build_root,
    write_json,
)

def write_docs(path, readme: str, agents: str) -> None:
    """The pair Portolan requires beside every catalog.json."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text(readme, encoding="utf-8")
    (path / "AGENTS.md").write_text(agents, encoding="utf-8")


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
    codelists = {}
    cl_path = DATA / "codelists.json"
    if cl_path.exists():
        codelists = json.loads(cl_path.read_text())
        print(f"{len(codelists)} code lists, "
              f"{sum(len(v) for v in codelists.values())} values")
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
    items_by_cid: dict = {}
    page_url_by_cid: dict = {}
    by_region: dict = {}
    by_license: dict = {}
    by_category: dict = {}
    latest_license: dict = {}
    latest_redistribution: dict = {}
    for cid, rows in sorted(groups.items()):
        page_url = rows[0]["page_url"]
        page = pages.get(cid) or {}
        terms = page.get("terms") or ""
        license_ = spdx_from_terms(terms)
        coll_title = f"{page.get('title') or cid} ({cid})"
        identifier = page.get("identifier") or cid
        crs = (page.get("fields") or {}).get("座標系", "")
        # The newest year per 地域, so an Item can say whether it is the
        # current file for its own prefecture rather than for the dataset.
        # Keyed on the region alone: 形式 is written inconsistently between
        # vintages -- P11 calls it 「GML、シェープ形式」 in 2010 and
        # 「シェープ、geojson形式」 in 2022 -- so including it made each old
        # spelling its own bucket and marked a 12-year-old file as current.
        latest_years: dict = {}
        for r in rows:
            cells = r.get("cells") or {}
            y = year_from_nendo(nendo_of(cells))
            if y is None:
                continue
            key = cells.get("地域") or ""
            latest_years[key] = max(latest_years.get(key, 0), y)
        items = [
            build_item(
                {**r, **head.get(r["url"], {})}, page_url, cid, regions,
                license_, terms, base_url, coll_title, identifier, latest_years, crs,
            )
            for r in rows
        ]
        for it in items:
            write_json(out / "collections" / cid / "items" / f"{it['id']}.json", it)
        coll = build_collection(cid, page_url, items, page, regions, base_url)
        # Every year this dataset has, so "is it still being updated" is a
        # thing a reader can see rather than infer from one number. Stating
        # that a dataset is discontinued would be a guess; stating that its
        # newest edition is from 2012 is not.
        years = sorted({
            int(it["properties"]["start_datetime"][:4]) for it in items
            if it["properties"].get("start_datetime")
        })
        if years:
            coll["ksj:years"] = years
        for v in coll.get("ksj:variants") or []:
            for c in v["columns"]:
                url = c.get("codelist_url")
                if url and url in codelists:
                    slug = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    c["ksj:codelist_href"] = f"../../codelists/{slug}.json"
        # PTL-CAT-001, and the same thing a person hits: 603 Item links in one
        # array is a list nobody scrolls. Above YEAR_GROUP_MIN the Items move
        # under a year, and a year longer than REGION_GROUP_MIN moves again
        # under its region. Small datasets keep the flat list, which is easier
        # than a tree of one.
        if len(items) > YEAR_GROUP_MIN:
            by_year: dict = defaultdict(list)
            for it in items:
                y = (it["properties"].get("start_datetime") or "")[:4]
                entry = {"id": it["id"], "title": it["properties"].get("title") or it["id"],
                         "region": it["properties"].get("ksj:region") or ""}
                by_year[int(y) if y else 0].append(entry)
            # The Item links stay on the Collection: STAC expects a Collection
            # to list its Items, and Portolan PTL-LNK-002 makes it an error not
            # to (21,426 of them when they were removed). The year children are
            # navigation added beside them, not instead of them. PTL-CAT-001
            # then still warns that the flat list is long, so the two rules
            # cannot both be satisfied by a dataset this size; the warning is
            # the one worth living with.
            for year in sorted(by_year, reverse=True):
                rows = sorted(by_year[year], key=lambda e: (e["region"], e["title"]))
                ydir = out / "collections" / cid / "years" / str(year)
                region_rows = []
                if len(rows) > REGION_GROUP_MIN:
                    grouped: dict = defaultdict(list)
                    for e in rows:
                        grouped[e["region"] or "その他"].append(e)
                    for rname in sorted(grouped):
                        rslug = _slug(rname)
                        write_json(
                            ydir / rslug / "catalog.json",
                            build_year_region_catalog(
                                cid, coll_title, year, rname, grouped[rname], base_url),
                        )
                        write_docs(
                            ydir / rslug,
                            *docs.year_region_docs(coll_title, year, rname, len(grouped[rname])),
                        )
                        region_rows.append(
                            {"slug": rslug, "name": rname, "count": len(grouped[rname])})
                write_json(
                    ydir / "catalog.json",
                    build_year_catalog(cid, coll_title, year, rows, region_rows, base_url),
                )
                write_docs(ydir, *docs.year_docs(coll_title, year, len(rows), region_rows))
                coll["links"].append({
                    "rel": "child",
                    "href": f"./years/{year}/catalog.json",
                    "type": "application/json",
                    "title": f"{year} — {len(rows)} 件"
                             + (f" / {len(region_rows)} 地域" if region_rows else ""),
                })
        write_json(out / "collections" / cid / "collection.json", coll)
        # The docs are written after the link post-processing below, once the
        # series and editorial links exist: an AGENTS.md that omits "often used
        # with" would be describing a Collection that no longer matches it.
        items_by_cid[cid] = items
        page_url_by_cid[cid] = page_url
        newest = max(
            (int(it["properties"]["start_datetime"][:4]) for it in items
             if it["properties"].get("start_datetime")), default=None)
        if newest is not None:
            for it in items:
                if (it["properties"].get("start_datetime") or "")[:4] == str(newest):
                    latest_license[cid] = it["properties"]["license"]
                    latest_redistribution[cid] = it["properties"].get("ksj:redistribution")
                    break
        if page.get("category"):
            by_category.setdefault(page["category"], []).append(
                {"id": cid, "title": coll_title, "count": len(items)})

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
            out / "regions" / slug / "catalog.json",
            build_region_catalog(code, name, entries, base_url),
        )
        write_docs(out / "regions" / slug, *docs.region_docs(code, name, entries))
        region_index.append(
            {
                "slug": slug,
                "title": f"{name} ({code})" if code else name,
                "count": len(entries),
            }
        )
    if region_index:
        write_json(out / "regions" / "catalog.json", build_regions_root(region_index, base_url))
        write_docs(out / "regions", *docs.regions_docs(region_index))
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
                out / "licenses" / status / cid / "catalog.json",
                build_license_catalog(status, cid, g["title"], g["entries"], base_url),
            )
            write_docs(
                out / "licenses" / status / cid,
                *docs.license_collection_docs(
                    status, REDISTRIBUTION[status][0], g["title"], g["entries"]),
            )
            rows.append({"collection": cid, "title": g["title"], "count": len(g["entries"])})
        write_json(
            out / "licenses" / status / "catalog.json",
            build_license_status_root(status, rows, base_url),
        )
        write_docs(
            out / "licenses" / status,
            *docs.license_status_docs(status, REDISTRIBUTION[status][0], rows),
        )
        status_index.append({"status": status, "count": sum(r["count"] for r in rows)})
        print(f"  {REDISTRIBUTION[status][0].split(' ')[0]:<14} "
              f"{sum(r['count'] for r in rows):>6} 件 / {len(rows)} コレクション")
    if status_index:
        write_json(out / "licenses" / "catalog.json", build_licenses_root(status_index, base_url))
        write_docs(
            out / "licenses",
            *docs.licenses_docs(
                [{"status": s["status"], "items": s["count"]} for s in status_index]
            ),
        )

    # One file per code list, referenced from the columns that use it. Kept
    # out of the collections so that a dataset using RiverCodeCd does not
    # carry its 35,450 rows.
    slugs = {}
    for url, values in sorted(codelists.items()):
        slug = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        slugs[url] = slug
        write_json(out / "codelists" / f"{slug}.json",
                   {"source": url, "values": values})
    if slugs:
        print(f"{len(slugs)} code lists -> {out / 'codelists'}")

    # Editions of the same thing, linked to each other. Derived from the
    # titles, which is where the difference is written: 500mメッシュ別将来推計
    # 人口データ exists as （H29国政局推計）, （H30国政局推計） and （R6国政局推計）
    # and nothing else says they are the same series.
    import re as _re

    def series_of(title: str) -> str:
        base = title.rsplit(" (", 1)[0]
        base = _re.sub(r"（[^（）]*推計[^（）]*）", "", base)
        return _re.sub(r"（shape形式版）", "", base).strip()

    series: dict = {}
    for c in collections:
        series.setdefault(series_of(c["title"]), []).append(c)
    for name, members in series.items():
        if len(members) < 2:
            continue
        for c in members:
            c["ksj:series"] = name
            c["links"] += [
                {
                    "rel": "related",
                    "href": f"../{o['id']}/collection.json",
                    "type": "application/json",
                    "title": f"同じ系列: {o['title']}"
                             + (f" — 最新 {o['ksj:latest_year']}" if o.get("ksj:latest_year") else ""),
                }
                for o in members
                if o["id"] != c["id"]
            ]
            write_json(out / "collections" / c["id"] / "collection.json", c)
    if series:
        n = sum(len(m) for m in series.values() if len(m) > 1)
        print(f"{n} collections belong to a series of {sum(1 for m in series.values() if len(m) > 1)}")

    # A small index for choosing a dataset by reading. collections/catalog.json
    # is links only, and a description is what tells 津波浸水想定 from 高潮浸水
    # 想定; fetching 110 collection.json files to read them is the scan this
    # catalog exists to avoid.
    # Datasets that are typically used together. This is editorial: the
    # upstream data states no such relation, and two agents in a row asked for
    # it after finding the advice in prose and not in links. Marked
    # ksj:editorial so a reader can tell it from the series links, which are
    # derived from the titles.
    combos_path = DATA / "combinations.json"
    if combos_path.exists():
        combos = json.loads(combos_path.read_text())
        by_id = {c["id"]: c for c in collections}
        unknown = [c for c in combos["combinations"]
                   if c[0] not in by_id or c[1] not in by_id]
        if unknown:
            print(f"  combinations naming a dataset that does not exist: {unknown}",
                  file=sys.stderr)
        n = 0
        for a, b, why in combos["combinations"]:
            if a not in by_id or b not in by_id:
                continue
            crs_a = (by_id[a].get("ksj:coordinate_system") or "").split("/")[0].strip()
            crs_b = (by_id[b].get("ksj:coordinate_system") or "").split("/")[0].strip()
            # A pair this catalog recommends overlaying should say when the two
            # are on different datums. A40 is JGD2011 and P20 is JGD2000, and a
            # reader found that only by opening both Items.
            warn = (f"（測地系が違います: {crs_a} と {crs_b}。重ねる前に変換が要ります）"
                    if crs_a and crs_b and crs_a != crs_b else "")
            for x, y in ((a, b), (b, a)):
                by_id[x]["links"].append({
                    "rel": "related",
                    "href": f"../{y}/collection.json",
                    "type": "application/json",
                    "title": f"よく一緒に使う: {by_id[y]['title']} — {why}{warn}",
                    "ksj:editorial": True,
                    "ksj:reason": why,
                    **({"ksj:crs_mismatch": [crs_a, crs_b]} if warn else {}),
                })
                n += 1
        for c in collections:
            if any(l.get("ksj:editorial") for l in c["links"]):
                write_json(out / "collections" / c["id"] / "collection.json", c)
        print(f"{n} editorial links over {len(combos['combinations'])} pairs")

    # Every Collection gets its own README.md and AGENTS.md, now that its links
    # are final. Portolan requires both beside every collection.json; the
    # AGENTS.md is the one that carries the dataset's own caveats, which the
    # catalog-wide one deliberately no longer states.
    for c in collections:
        cid = c["id"]
        write_docs(
            out / "collections" / cid,
            docs.collection_readme(c, len(items_by_cid.get(cid) or []),
                                   page_url_by_cid.get(cid, "")),
            docs.collection_agents(c, items_by_cid.get(cid) or [], base_url),
        )

    cat_index = []
    for name, members in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        write_json(out / "categories" / _slug(name) / "catalog.json",
                   build_category_catalog(name, members, base_url))
        write_docs(out / "categories" / _slug(name), *docs.category_docs(name, members))
        cat_index.append({"name": name, "count": len(members)})
    if cat_index:
        write_json(out / "categories" / "catalog.json",
                   build_categories_root(cat_index, base_url))
        write_docs(out / "categories", *docs.categories_docs(cat_index))
        print(f"{len(cat_index)} categories -> {out / 'categories'}")

    write_json(out / "collections" / "index.json", {
        "description": "全 Collection の説明文つき一覧。語句で選ぶための索引です。",
        "collections": [
            {
                "id": c["id"],
                "title": c["title"],
                "description": c.get("description", ""),
                "category": c.get("ksj:category"),
                "keywords": c.get("keywords", []),
                "geometry_type": c.get("ksj:geometry_type"),
                "coordinate_system": c.get("ksj:coordinate_system"),
                "latest_year": c.get("ksj:latest_year"),
                "years": c.get("ksj:years"),
                "item_count": sum(1 for x in c["links"] if x["rel"] == "item"),
                # The Collection's own `license` is `other` whenever any year
                # in it is, which reads as "not open" for a dataset whose
                # current year is CC BY 4.0. This is the newest year's.
                "license": c["license"],
                "latest_license": latest_license.get(c["id"]),
                # Whether the newest edition may be republished, which is the
                # question people arrive with and could only be answered by
                # opening an Item.
                "latest_redistribution": latest_redistribution.get(c["id"]),
                "series": c.get("ksj:series"),
            }
            for c in collections
        ],
    })

    write_json(out / "collections" / "catalog.json",
               build_collections_root(collections, base_url))
    write_docs(out / "collections", *docs.collections_docs(collections))
    write_json(
        out / "catalog.json",
        build_root(collections, base_url, bool(region_index), bool(status_index),
                   bool(cat_index)),
    )
    # The repository's own AGENTS.md is for someone changing this code. What
    # the catalog publishes is for whatever is reading the catalog.
    (out / "README.md").write_text((ROOT / "README.md").read_text(encoding="utf-8"),
                                   encoding="utf-8")
    (out / "AGENTS.md").write_text(
        (ROOT / "docs" / "catalog-AGENTS.md").read_text(encoding="utf-8"), encoding="utf-8")
    # Items are counted from the files, not from the Collections' item links:
    # a grouped Collection links years, not Items, and counting links reported
    # 21,246 of 177.
    titled = sum(1 for _ in (out / "collections").glob("*/items/*.json"))
    named = sum(1 for rows_ in groups.values() for r in rows_ if (r.get("cells") or {}))
    print(f"{len(collections)} collections, {titled} items -> {out}")
    print(f"{named} of {titled} items carry the page's own row "
          f"({named * 100 // max(titled, 1)}%)")
    located = titled
    with_geom = _count_with_geometry(out)
    print(f"{with_geom} of {located} items have a footprint "
          f"({with_geom * 100 // max(located, 1)}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
