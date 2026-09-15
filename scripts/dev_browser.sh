#!/usr/bin/env bash
# Fetch STAC Browser on first use and point it at the local catalog.
#
# STAC Browser is not published to npm; upstream expects you to clone it and
# run its own dev server. It lands in tmp/, which is ignored, so nothing about
# it enters this repository.
set -euo pipefail

cd "$(dirname "$0")/.."
DIR=tmp/stac-browser
REF=${STAC_BROWSER_REF:-v5.1.0}
CATALOG_URL=${CATALOG_URL:-http://localhost:8000/catalog.json}

if [ ! -d "$DIR/.git" ]; then
  echo "fetching STAC Browser $REF into $DIR (first run only)"
  mkdir -p tmp
  git clone --depth 1 --branch "$REF" https://github.com/radiantearth/stac-browser.git "$DIR"
fi

if [ ! -d "$DIR/node_modules" ]; then
  echo "installing STAC Browser dependencies (first run only; takes a few minutes)"
  (cd "$DIR" && npm install --no-audit --no-fund)
fi

if [ "${1:-}" = "--setup-only" ]; then
  echo "ready. run: npm run dev"
  exit 0
fi

if [ ! -f catalog/catalog.json ]; then
  echo "catalog/ is empty. Run 'make build' first." >&2
  exit 1
fi

echo "STAC Browser -> $CATALOG_URL"
cd "$DIR"
SB_catalogUrl="$CATALOG_URL" exec npm start
