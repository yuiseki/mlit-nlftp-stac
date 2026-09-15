#!/usr/bin/env python3
"""The code lists the attribute tables point at -> data/codelists.json.

A column typed `codelist` is useless without the list: `N02_001 = 13` means
nothing until something says 鋼索鉄道. Each list is a page of its own, shared
between datasets, so they are fetched once each and keyed by URL.
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mlit_nlftp_stac.attributes import parse_codelist  # noqa: E402

DATA = ROOT / "data"
UA = {"User-Agent": "mlit-nlftp-stac/0.1 (+https://github.com/yuiseki)"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sleep", type=float, default=1.0)
    ap.add_argument("--max-sleep", type=float, default=4.0)
    args = ap.parse_args()

    pages = [json.loads(line) for line in (DATA / "pages.jsonl").read_text().splitlines() if line]
    urls = sorted({
        c["codelist_url"]
        for p in pages
        for v in (p.get("variants") or [])
        for c in v["columns"]
        if c.get("codelist_url")
    })
    out_path = DATA / "codelists.json"
    known = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [u for u in urls if u not in known]
    print(f"{len(urls)} code lists, {len(known)} known, {len(todo)} to fetch")

    failed = []
    for i, url in enumerate(todo, 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                values = parse_codelist(r.read().decode("utf-8", "replace"))
            # An empty list is not a code list: some links go to a spreadsheet
            # or to a page that explains rather than enumerates. Recording it
            # as an empty enum would claim the column has no valid values.
            if values:
                known[url] = values
            else:
                failed.append((url, "no rows parsed"))
            print(f"  {i:>3}/{len(todo)} {len(values):>4} 値  {url.rsplit('/', 1)[-1]}", flush=True)
        except urllib.error.HTTPError as e:
            failed.append((url, f"HTTP {e.code}"))
        except Exception as e:  # noqa: BLE001
            failed.append((url, f"{type(e).__name__}: {e}"))
        time.sleep(random.uniform(args.min_sleep, args.max_sleep))

    out_path.write_text(json.dumps(known, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    total = sum(len(v) for v in known.values())
    print(f"{len(known)} lists, {total} values -> {out_path}")
    for url, why in failed:
        print(f"  failed: {url}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
