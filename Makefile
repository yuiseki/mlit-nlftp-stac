PY := PYTHONPATH=src python3

.PHONY: help index links head build validate test serve start install-catalog clean

help:
	@echo "make index     fetch the upstream index and measure every file (hours)"
	@echo "make links     just the index (minutes)"
	@echo "make head      just the HEAD sweep; resumable"
	@echo "make build     data/ -> catalog/  (offline, seconds)"
	@echo "               BASE_URL=... sets the absolute self links"
	@echo "               also writes catalog/items.parquet, the whole catalog as one table"
	@echo "make validate  check catalog/"
	@echo "make serve     serve catalog/ on :8765 with CORS, for other clients"
	@echo "make start     browse catalog/ in STAC Browser on :8080"
	@echo "make test      unit tests"
	@echo "make install-catalog   rsync catalog/ to \$$(CATALOG_ROOT)"

index: links head

links:
	$(PY) scripts/01_fetch_index.py

head:
	$(PY) scripts/02_head_sizes.py

BASE_URL ?= https://stac.yuiseki.net/mlit-nlftp

build:
	$(PY) scripts/03_build_stac.py --base-url "$(BASE_URL)"
	$(PY) scripts/09_geoparquet.py --base-url "$(BASE_URL)"

validate:
	$(PY) scripts/04_validate.py

serve:
	$(PY) scripts/05_serve.py

start:
	bash scripts/06_browser.sh

test:
	$(PY) -m pytest tests -q

# stac.yuiseki.net serves /data/www/html/stac, so a second catalog is another
# directory next to this one rather than another hostname.
CATALOG_ROOT ?= /data/www/html/stac/mlit-nlftp

install-catalog:
	@test -f catalog/catalog.json || { echo "catalog/ is empty; run make build" >&2; exit 1; }
	mkdir -p $(CATALOG_ROOT)
	rsync -a --delete catalog/ $(CATALOG_ROOT)/
	@echo "$(CATALOG_ROOT) updated"

clean:
	rm -rf catalog
