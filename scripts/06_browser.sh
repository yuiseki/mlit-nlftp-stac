#!/usr/bin/env bash
# Browse the generated catalog in STAC Browser.
#
# STAC Browser is a Vue app that upstream expects you to clone and run; it is
# not published to npm. It lands in tmp/, which is ignored, so none of it
# enters this repository and nothing here depends on node except this command.
#
# The catalog is symlinked into STAC Browser's own public/ directory and read
# from a relative URL, so the page and the data share an origin. A second
# server on a second port would work too, but then every file is a
# cross-origin request and the failure mode is a blank catalog with the reason
# only visible in the devtools console.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD

DIR=tmp/stac-browser
REF=${STAC_BROWSER_REF:-v5.1.0}

if ! command -v npm >/dev/null; then
  echo "npm is needed for STAC Browser itself. The catalog does not need it:" >&2
  echo "  make serve    # then point any STAC client at the URL it prints" >&2
  exit 1
fi

if [ ! -f catalog/catalog.json ]; then
  echo "catalog/ is empty. Run 'make build' first." >&2
  exit 1
fi

if [ ! -d "$DIR/.git" ]; then
  echo "fetching STAC Browser $REF into $DIR (first run only)"
  mkdir -p tmp
  git clone --quiet --depth 1 --branch "$REF" https://github.com/radiantearth/stac-browser.git "$DIR"
fi
if [ ! -d "$DIR/node_modules" ]; then
  echo "installing STAC Browser dependencies (first run only, a few minutes)"
  (cd "$DIR" && npm install --no-audit --no-fund --loglevel=error)
fi

ln -sfn "$ROOT/catalog" "$DIR/public/catalog"

echo
echo "  open http://localhost:8080 once vite says ready"
echo
cd "$DIR"
SB_catalogUrl="/catalog/catalog.json" exec npm start
