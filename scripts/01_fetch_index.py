#!/usr/bin/env python3
"""nlftp's HTML index -> data/links.jsonl.

The download links are not hrefs. They sit in
`onclick="javascript:DownLd('12.1MB','N02-24_GML.zip','../data/...zip',this)"`,
which is why a crawler that follows links finds nothing here.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

BASE = "https://nlftp.mlit.go.jp/ksj/"
DATALIST = BASE + "gml/datalist/"
UA = {"User-Agent": "mlit-nlftp-stac/0.1 (+https://github.com/yuiseki)"}
DOWNLD = re.compile(r"javascript:DownLd(?:_new)?\('([^']*)','([^']*)','([^']*)'")
OUT = Path(__file__).resolve().parents[1] / "data" / "links.jsonl"


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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen, failed, n = set(), [], 0
    with OUT.open("w", encoding="utf-8") as f:
        for i, page in enumerate(pages, 1):
            url = f"{DATALIST}KsjTmplt-{page}.html"
            try:
                html = get(url)
            except Exception as e:  # a page listed in the index may still 404
                failed.append((page, str(e)[:80]))
                continue
            for size, filename, path in DOWNLD.findall(html):
                href = urljoin(DATALIST, path.strip())
                if href in seen:
                    continue
                seen.add(href)
                f.write(json.dumps({"page": page, "page_url": url, "filename": filename,
                                    "size_label": size, "url": href}, ensure_ascii=False) + "\n")
                n += 1
            if i % 20 == 0:
                print(f"  {i}/{len(pages)} pages, {n} links", flush=True)
            time.sleep(0.2)
    print(f"{n} links -> {OUT}")
    for page, err in failed:
        print(f"  page failed: {page}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
