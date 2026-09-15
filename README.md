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

src/mlit_nlftp_stac/ksj.py    filename -> identifier, year, area (the risky part)
src/mlit_nlftp_stac/page.py   a dataset page -> its own name, description, terms
src/mlit_nlftp_stac/stac.py   a parsed row -> a STAC Item
src/mlit_nlftp_stac/mesh.py   JIS mesh code -> bounding box

docs/design.md                what is borrowed from Portolan, and what is not
```

## Building

```bash
make index      # 01 and 02. Hits nlftp; takes hours, and is resumable.
make build      # 03. Offline, seconds.
make validate   # 04.
make test       # unit tests
```

`make index` is deliberately slow: four workers with a random 1 to 10 second
pause between requests. The upstream server belongs to a government agency and
there is no reason to hurry it.

## Status

110 Collections, 21,603 Items. Every Collection carries the name and the
description the dataset page gives itself, so the catalog reads as
`鉄道データ (N02)` rather than `N02`. 24 Collections state CC BY 4.0 outright
and get that SPDX identifier; the rest say something a single identifier
cannot express and are `other` with their terms quoted verbatim.

Items have one asset, the upstream zip. No format conversion yet.

## License

The code here is MIT. The data it describes is not: each KSJ dataset carries
its own terms, from CC BY 4.0 to non-commercial-only, and every generated
Collection states which. See <https://nlftp.mlit.go.jp/ksj/other/agreement.html>.
