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

from mlit_nlftp_stac.stac import build_collection, build_item, build_root, write_json  # noqa: E402

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", help="build just these collections")
    ap.add_argument("--out", default=str(ROOT / "catalog"))
    args = ap.parse_args()

    links = load(DATA / "links.jsonl")
    if not links:
        print("data/links.jsonl is missing. Run scripts/01_fetch_index.py first.", file=sys.stderr)
        return 1
    head = {r["url"]: r for r in load(DATA / "head.jsonl") if r.get("status") == 200}
    print(f"{len(links)} links, {len(head)} with a HEAD result "
          f"({len(head) * 100 // max(len(links), 1)}%)")

    groups = defaultdict(list)
    for row in links:
        groups[collection_id(row["page"])].append(row)
    if args.only:
        groups = {k: v for k, v in groups.items() if k in set(args.only)}

    out = Path(args.out)
    collections = []
    for cid, rows in sorted(groups.items()):
        page_url = rows[0]["page_url"]
        items = [build_item({**r, **head.get(r["url"], {})}, page_url, cid) for r in rows]
        for it in items:
            write_json(out / "collections" / cid / "items" / f"{it['id']}.json", it)
        coll = build_collection(cid, cid, page_url, items)
        write_json(out / "collections" / cid / "collection.json", coll)
        (out / "collections" / cid / "README.md").write_text(
            f"# {cid}\n\n国土数値情報 {cid}. {len(items)} files mirrored from {page_url}\n\n"
            "Terms of use are stated per dataset upstream; see the `license` link in\n"
            "`collection.json`.\n", encoding="utf-8")
        collections.append(coll)
        print(f"  {cid:<14} {len(items):>5} items")

    write_json(out / "catalog.json", build_root(collections))
    for name in ("README.md", "AGENTS.md"):
        (out / name).write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    print(f"{len(collections)} collections, "
          f"{sum(len(v) for v in groups.values())} items -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
