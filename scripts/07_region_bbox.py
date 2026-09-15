#!/usr/bin/env python3
"""N03 行政区域 -> data/region_bbox.json.

The extent of each prefecture comes from 国土数値情報 itself rather than from
some other country-boundary dataset, so the footprints in this catalog agree
with the data they describe.

N03's prefecture archives total about 1 GB, and all this needs from each is
the 100-byte header of the shapefile inside. Range requests get exactly that:
around 6 MB of reads for the whole country.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mlit_nlftp_stac.shpbbox import ZipReadError, looks_like_japan, shp_bbox  # noqa: E402

DATA = ROOT / "data"
UA = {"User-Agent": "mlit-nlftp-stac/0.1 (+https://github.com/yuiseki)"}


def http_reader(url: str):
    def read(start: int, end: int) -> bytes:
        req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()

    return read


def content_length(url: str) -> int:
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


def pick_n03(links: list) -> list:
    """The newest N03 vintage, one file per region."""
    n03 = [r for r in links if r["page"].startswith("N03")]
    dates = {m.group(1) for r in n03 if (m := re.search(r"N03-(\d{8})", r["filename"]))}
    if not dates:
        return []
    newest = max(dates)
    return [r for r in n03 if f"N03-{newest}" in r["filename"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sleep", type=float, default=1.0)
    ap.add_argument("--max-sleep", type=float, default=4.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    links = [json.loads(line) for line in (DATA / "links.jsonl").read_text().splitlines() if line]
    targets = pick_n03(links)
    if not targets:
        print("no N03 links in data/links.jsonl", file=sys.stderr)
        return 1
    if args.limit:
        targets = targets[: args.limit]
    print(f"{len(targets)} N03 archives")

    out, failed, bytes_read = {}, [], 0
    for i, row in enumerate(targets, 1):
        region = (row.get("cells") or {}).get("地域") or ""
        code = m.group(1) if (m := re.search(r"_(\d{2})_", row["filename"])) else None
        try:
            total = content_length(row["url"])
            reader = http_reader(row["url"])
            counted = {"n": 0}

            def counting(start: int, end: int) -> bytes:
                counted["n"] += end - start + 1
                return reader(start, end)

            name, bbox = shp_bbox(counting, total)
            if not looks_like_japan(bbox):
                raise ZipReadError(f"bbox outside Japan: {bbox}")
            bytes_read += counted["n"]
            out[region] = {
                "region": region,
                "code": code,
                "bbox": [round(v, 6) for v in bbox],
                "source_file": row["filename"],
                "source_url": row["url"],
                "shapefile": name,
            }
            print(f"  {i:>3}/{len(targets)} {region:<14} {[round(v, 3) for v in bbox]}"
                  f"  ({counted['n'] / 1024:.0f} KB of {total / 1024**2:.0f} MB)", flush=True)
        except Exception as e:
            failed.append((region or row["filename"], f"{type(e).__name__}: {e}"))
            print(f"  {i:>3}/{len(targets)} {region:<14} FAILED {e}", flush=True)
        time.sleep(random.uniform(args.min_sleep, args.max_sleep))

    path = DATA / "region_bbox.json"
    path.write_text(
        json.dumps(
            {
                "note": "Extents read from the shapefile headers inside 国土数値情報 N03 行政区域.",
                "source_page": targets[0]["page_url"],
                "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "regions": out,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(out)} regions, {bytes_read / 1024**2:.1f} MB read -> {path}")
    for region, err in failed:
        print(f"  failed: {region}: {err}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
