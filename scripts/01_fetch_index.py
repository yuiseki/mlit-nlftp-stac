#!/usr/bin/env python3
"""nlftp's HTML index -> data/links.jsonl and data/pages.jsonl.

The download links are not hrefs. They sit in
`onclick="javascript:DownLd('12.1MB','N02-24_GML.zip','../data/...zip',this)"`,
which is why a crawler that follows links finds nothing here.

The same fetch also yields each dataset's own words about itself: its name,
what it contains, its identifier and its terms of use all sit in a table on
the page. Taking them here means the catalog needs no third-party API to
explain what `A31b` is.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mlit_nlftp_stac.page import parse_page  # noqa: E402
from mlit_nlftp_stac.categories import LIST_URL, parse_categories  # noqa: E402
from mlit_nlftp_stac.table import parse_download_rows  # noqa: E402

BASE = "https://nlftp.mlit.go.jp/ksj/"
DATALIST = BASE + "gml/datalist/"
UA = {"User-Agent": "mlit-nlftp-stac/0.1 (+https://github.com/yuiseki)"}
DOWNLD = re.compile(r"javascript:DownLd(?:_new)?\('([^']*)','([^']*)','([^']*)'")
DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "links.jsonl"
OUT_PAGES = DATA / "pages.jsonl"


def get(url: str, tries: int = 3) -> str:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise AssertionError("unreachable")


def main() -> int:
    pages = sorted(set(re.findall(r"datalist/KsjTmplt-([A-Za-z0-9_.\-]+?)\.html", get(BASE + "index.html"))))
    print(f"{len(pages)} dataset pages", flush=True)

    # Which shelf each dataset sits on. Only the JPGIS list page says.
    try:
        categories = parse_categories(get(LIST_URL))
        print(f"{len(categories)} datasets carry a category", flush=True)
    except Exception as e:  # noqa: BLE001
        categories = {}
        print(f"  category list unavailable: {e}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen, failed, missed, n = set(), [], [], 0
    with OUT.open("w", encoding="utf-8") as f, OUT_PAGES.open("w", encoding="utf-8") as fp:
        for i, page in enumerate(pages, 1):
            url = f"{DATALIST}KsjTmplt-{page}.html"
            try:
                html = get(url)
            except Exception as e:  # a page listed in the index may still 404
                failed.append((page, str(e)[:80]))
                continue
            meta = parse_page(html, url)
            fp.write(json.dumps(
                {"page": page, "page_url": url, **meta,
                 **({"category": categories[page]} if page in categories else {})},
                ensure_ascii=False) + "\n")

            rows = parse_download_rows(html)
            # The row parser only sees links inside a table. Anything outside
            # one would be dropped silently, so count against the raw match.
            raw = len(DOWNLD.findall(html))
            if len(rows) != raw:
                missed.append((page, raw - len(rows)))
            for row in rows:
                href = urljoin(DATALIST, row["path"])
                if href in seen:
                    continue
                seen.add(href)
                f.write(json.dumps({"page": page, "page_url": url, "filename": row["filename"],
                                    "size_label": row["size_label"], "cells": row["cells"],
                                    "url": href}, ensure_ascii=False) + "\n")
                n += 1
            if i % 20 == 0:
                print(f"  {i}/{len(pages)} pages, {n} links", flush=True)
            time.sleep(0.2)
    print(f"{n} links -> {OUT}")
    print(f"{len(pages) - len(failed)} pages -> {OUT_PAGES}")
    for page, err in failed:
        print(f"  page failed: {page}: {err}")
    for page, count in missed:
        print(f"  {page}: {count} link(s) outside a table, not captured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
