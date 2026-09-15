# mlit-nlftp-stac

A static STAC catalog for 国土数値情報 (National Land Numerical Information),
the geospatial data the Japanese Ministry of Land, Infrastructure, Transport
and Tourism publishes at <https://nlftp.mlit.go.jp/ksj/>.

The upstream site has 21,603 downloadable zip files across 136 dataset pages,
about 214 GB in total. The only index it offers is HTML, and the download
links are not `href` attributes but `onclick` handlers, so nothing can crawl
it by accident. This repository turns that into a catalog a person or an agent
can read: one STAC Collection per KSJ dataset, one Item per zip, with the
download URL, its real byte count, and its last-modified time.

This is a mirror, not a source. The data stays on MLIT's servers; only the
metadata lives here.

## Where things are

```
scripts/01_fetch_index.py     nlftp HTML -> data/links.jsonl (URL, declared size)
                                          + data/pages.jsonl (name, description, terms)
scripts/02_head_sizes.py      data/links.jsonl -> data/head.jsonl (real bytes, ETag)
scripts/03_build_stac.py      data/*.jsonl -> catalog/
scripts/04_validate.py        catalog/ -> pass or fail
scripts/05_serve.py           serve catalog/ with CORS, for other STAC clients
scripts/06_browser.sh         browse catalog/ in STAC Browser
scripts/07_region_bbox.py     N03 行政区域 -> data/region_bbox.json

src/mlit_nlftp_stac/ksj.py    filename -> identifier, year, area (the risky part)
src/mlit_nlftp_stac/page.py   a dataset page -> its own name, description, terms
src/mlit_nlftp_stac/table.py  a download row -> the region, river, format, year
src/mlit_nlftp_stac/stac.py   a parsed row -> a STAC Item
src/mlit_nlftp_stac/mesh.py   JIS mesh code -> bounding box
src/mlit_nlftp_stac/shpbbox.py a zip's shapefile extent, read by range request

docs/design.md                what is borrowed from Portolan, and what is not
```

## Building

```bash
make index      # 01 and 02. Hits nlftp; takes hours, and is resumable.
make build      # 03. Offline, seconds.
make validate   # 04.
make start      # browse the result in STAC Browser on :8080
make test       # unit tests
```

`make start` clones STAC Browser into `tmp/` on first run, symlinks `catalog/`
into its `public/` directory, and serves both from one origin. `make serve`
exists separately for pointing some other STAC client at the catalog over
HTTP; it adds CORS headers and runs on :8765, away from the tileserver that
usually holds :8000.

`make index` is deliberately slow: four workers with a random 1 to 10 second
pause between requests. The upstream server belongs to a government agency and
there is no reason to hurry it.

## Published at

<https://stac.yuiseki.net/mlit-nlftp/>

Browsable without installing anything:
<https://radiantearth.github.io/stac-browser/#/external/stac.yuiseki.net/mlit-nlftp/catalog.json>

One host, one directory per catalog. `make build` bakes that into the
absolute `self` links; every other link stays relative, so the same build
works from a local directory too. See [`deploy/`](deploy/).

## Status

110 Collections, 21,603 Items. Every Collection carries the name and the
description the dataset page gives itself, so the catalog reads as
`鉄道データ (N02)` rather than `N02`. 24 Collections state CC BY 4.0 outright
and get that SPDX identifier; the rest say something a single identifier
cannot express and are `other` with their terms quoted verbatim.

Items are titled with the words in their own row of the download table, with
the year first so that sorting by title sorts by year: `2025_全国（令和7年）`,
`2025_北海道開発局 GML形式 洪水予報河川･水位周知河川（令和7年）`. 99% of them;
the rest sit in malformed upstream rows.

Each Item repeats its Collection's licence and terms and carries its own
licence link, because an Item page has a download button on it and whoever
lands there may never see the Collection.

98% of Items carry a footprint, taken either from a mesh code in the filename
or from the extent of the matching prefecture in N03 行政区域. The remainder
are published per river-bureau or per metropolitan region, which no
administrative boundary matches, and are left without one.

Items have one asset, the upstream zip. No format conversion yet.

## License

The code here is MIT. The data it describes is not: each KSJ dataset carries
its own terms, from CC BY 4.0 to non-commercial-only, and every generated
Collection states which. See <https://nlftp.mlit.go.jp/ksj/other/agreement.html>.
