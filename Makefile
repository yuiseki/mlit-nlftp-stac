PY := PYTHONPATH=src python3

.PHONY: help index links head build validate test serve start install-catalog clean

help:
	@echo "make index     fetch the upstream index and measure every file (hours)"
	@echo "make links     just the index (minutes)"
	@echo "make head      just the HEAD sweep; resumable"
	@echo "make build     data/ -> catalog/  (offline, seconds)"
	@echo "make validate  check catalog/"
	@echo "make serve     serve catalog/ on :8765 with CORS, for other clients"
	@echo "make start     browse catalog/ in STAC Browser on :8080"
	@echo "make test      unit tests"
	@echo "make install-catalog   rsync catalog/ to \$$(CATALOG_ROOT) (needs sudo)"

index: links head

links:
	$(PY) scripts/01_fetch_index.py

head:
	$(PY) scripts/02_head_sizes.py

build:
	$(PY) scripts/03_build_stac.py

validate:
	$(PY) scripts/04_validate.py

serve:
	$(PY) scripts/05_serve.py

start:
	bash scripts/06_browser.sh

test:
	$(PY) -m pytest tests -q

CATALOG_ROOT ?= /srv/mlit-nlftp-stac

install-catalog: 
	@test -f catalog/catalog.json || { echo "catalog/ is empty; run make build" >&2; exit 1; }
	mkdir -p $(CATALOG_ROOT)
	rsync -a --delete catalog/ $(CATALOG_ROOT)/
	@echo "$(CATALOG_ROOT) updated"

clean:
	rm -rf catalog
