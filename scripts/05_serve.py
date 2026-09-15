#!/usr/bin/env python3
"""Serve catalog/ over HTTP with CORS.

STAC Browser runs on its own port, so every request it makes for a catalog
file is cross-origin. Without the CORS headers the browser shows an empty
catalog and the reason is only visible in the devtools console.
"""
import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CORSHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, If-None-Match, If-Modified-Since")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges, ETag")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        if not self.path.endswith(".json"):
            return
        sys.stderr.write(f"  {self.command} {self.path}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dir", default=str(ROOT / "catalog"))
    args = ap.parse_args()

    root = Path(args.dir)
    if not (root / "catalog.json").exists():
        print(f"no catalog at {root}. Run `make build` first.", file=sys.stderr)
        return 1

    handler = partial(CORSHandler, directory=str(root))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"catalog at http://localhost:{args.port}/catalog.json", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
