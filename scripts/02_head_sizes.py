#!/usr/bin/env python3
"""data/links.jsonl -> data/head.jsonl.

HEAD gives Content-Length, Last-Modified and ETag, which is everything needed
to size a download and to notice when upstream changes. The page's own size
label is not usable for either.

Four workers, a random 1 to 10 second pause per request. The output is
appended one line at a time, so an interrupted run resumes where it stopped.
"""
import argparse
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
UA = {"User-Agent": "mlit-nlftp-stac/0.1 (+https://github.com/yuiseki)"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-sleep", type=float, default=1.0)
    ap.add_argument("--max-sleep", type=float, default=10.0)
    ap.add_argument("--limit", type=int, default=0, help="stop after N requests (for a smoke test)")
    args = ap.parse_args()

    rows = [json.loads(line) for line in (DATA / "links.jsonl").read_text().splitlines() if line]
    out = DATA / "head.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line:
                done.add(json.loads(line)["url"])
    todo = [r for r in rows if r["url"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    pace = (args.min_sleep + args.max_sleep) / 2
    print(f"{len(rows)} known, {len(done)} done, {len(todo)} to go "
          f"(~{len(todo) * pace / args.workers / 3600:.1f} h)", flush=True)

    lock, n, t0 = threading.Lock(), 0, time.time()
    f = out.open("a", encoding="utf-8")

    def head(row: dict) -> None:
        nonlocal n
        time.sleep(random.uniform(args.min_sleep, args.max_sleep))
        req = urllib.request.Request(row["url"], headers=UA, method="HEAD")
        rec = {"url": row["url"], "filename": row["filename"]}
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                h = resp.headers
                rec.update(status=resp.status, bytes=int(h.get("Content-Length") or 0),
                           last_modified=h.get("Last-Modified"), etag=h.get("ETag"))
        except urllib.error.HTTPError as e:
            rec.update(status=e.code, bytes=0, last_modified=None, etag=None)
        except Exception as e:
            rec.update(status=type(e).__name__, bytes=0, last_modified=None, etag=None)
        with lock:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if n % 200 == 0:
                el = time.time() - t0
                print(f"  {n}/{len(todo)}  {el/60:.0f} min, ~{(len(todo)-n)*el/n/60:.0f} min left", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(head, todo))
    f.close()
    print(f"{n} done in {(time.time()-t0)/60:.0f} min -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
