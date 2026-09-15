# mlit-nlftp-stac

A static STAC catalog for 国土数値情報 (National Land Numerical Information),
the geospatial data the Japanese Ministry of Land, Infrastructure, Transport
and Tourism publishes at <https://nlftp.mlit.go.jp/ksj/>.

Upstream has 21,603 downloadable zip files across 136 dataset pages, about
214 GB. The only index it offers is HTML, and the download links are not
`href` attributes but `onclick` handlers, so nothing crawls it by accident.
This turns that into a catalog a person or an agent can read.

It is a mirror, not a source. The files stay on MLIT's servers; only the
metadata lives here.

## Use it

<https://stac.yuiseki.net/mlit-nlftp/catalog.json>

Browsable with nothing installed, in STAC Browser's hosted demo:
<https://browser.moregeo.it/external/stac.yuiseki.net/mlit-nlftp/catalog.json>

Everything a dataset covering 高知 offers, in one request:

```bash
curl -s https://stac.yuiseki.net/mlit-nlftp/regions/39.json \
  | jq -r '.links[] | select(.rel=="item") | .title' | grep 津波
# 津波浸水想定データ (A40) — 2016_高知（平成28年）
```

And the download URL for one of them:

```bash
curl -s https://stac.yuiseki.net/mlit-nlftp/collections/A40/items/A40-16_39_GML.json \
  | jq -r '.assets.source.href, .properties.license, .properties["ksj:terms"]'
```

## Three ways in

```
catalog.json
├── collections/catalog.json   データセット別   110 datasets
├── regions/catalog.json       地域別           56 regions
└── licenses/catalog.json      ライセンス別     3 statuses
```

**By dataset.** One Collection per KSJ dataset, named as the dataset page
names itself: `鉄道データ (N02)`, not `N02`. One Item per downloadable zip,
titled from its own row of the download table with the year first, so sorting
by title sorts by year, and with the dataset's name after it so the title
still says what it is when read somewhere else:
`2025_全国（令和7年） — 鉄道データ (N02)`.

**By licence.** `licenses/allowed/catalog.json` is every file
whose terms permit redistribution: 9,943 of 21,603, across 41 datasets. 4,146
may not be redistributed and 7,514 need a human to read the conditions. See
below for why this is an Item-level question.

**By region.** `regions/39.json` is every file that covers 高知 — 356 of them,
each carrying the name of the dataset it came from. 56 such catalogs, 16,613 links.
"What is there for this prefecture?" is the question people actually ask, and
answering it from Collections alone meant opening all 110.

## What an Item tells you

| | |
|---|---|
| `assets.source.href` | the zip on nlftp |
| `assets.source.file:size` | measured by HEAD, where it has been measured |
| `properties.license` | resolved from the Item's own year, not the Collection's |
| `properties.ksj:redistribution` | `allowed`, `not-allowed` or `check` |
| `properties.ksj:terms_applied` | the sentence that decided it |
| `properties.ksj:terms` | the Collection's full statement, verbatim |
| `geometry` / `bbox` | a JIS mesh cell, or the prefecture's extent from N03 行政区域 |
| `properties.ksj:extent_source` | which of those two, in words |
| `start_datetime` / `end_datetime` | from the page's 年度 column, not guessed from the filename |
| `properties.ksj:declared_size` | what the page claims, which is not always what the file weighs |

## What it does not tell you

Worth knowing before you plan work around it:

- **No attribute schemas.** Which column holds バス区分, which years a
  population projection has as fields: not here. Follow `ksj:source_page`.
- **No search.** A static catalog has no `/search`. The region index covers
  the common case; anything else means reading `catalog.json` and choosing.
- **Footprints are administrative, not measured.** A prefecture file gets the
  prefecture's extent, so spatial search works at prefecture granularity and
  no finer. 98% of Items have one; files published per river-bureau or per
  metropolitan region have no boundary to borrow and carry `"geometry": null`.
- **`file:size` is 4% covered** while the HEAD sweep runs. `make head` is
  resumable and fills the rest.
- **A licence belongs to a year, not to a dataset.** 鉄道データ is CC BY 4.0
  from 2020 and 商用可 before it; 学校データ is CC BY 4.0 for 2023 and 2021 and
  非商用 for 2013. Each Item resolves its own, and `ksj:terms_applied` quotes
  the sentence that decided it. The Collection keeps the whole statement.
  「一部制限」 is never resolved automatically: A40 lists which prefectures may
  redistribute and which must telephone first, and A27 says the terms differ
  per municipality and stops there. Those are `check`.
- **Upstream staleness is not flagged.** 避難施設 (P20) stopped in 2012. The
  catalog says when a file is from without saying that nothing newer exists.

## Where things are

```
scripts/01_fetch_index.py     nlftp HTML -> data/links.jsonl + data/pages.jsonl
scripts/02_head_sizes.py      -> data/head.jsonl (real bytes, Last-Modified, ETag)
scripts/03_build_stac.py      data/*.jsonl -> catalog/
scripts/04_validate.py        catalog/ -> pass or fail
scripts/05_serve.py           serve catalog/ with CORS, for other STAC clients
scripts/06_browser.sh         browse catalog/ in STAC Browser
scripts/07_region_bbox.py     N03 行政区域 -> data/region_bbox.json

src/mlit_nlftp_stac/ksj.py     filename -> identifier, year, area (the risky part)
src/mlit_nlftp_stac/page.py    a dataset page -> its own name, description, terms
src/mlit_nlftp_stac/table.py   a download row -> the region, river, format, year
src/mlit_nlftp_stac/mesh.py    JIS mesh code -> bounding box
src/mlit_nlftp_stac/shpbbox.py a zip's shapefile extent, read by range request
src/mlit_nlftp_stac/stac.py    all of the above -> STAC

docs/design.md                 the decisions, and where upstream fights back
deploy/                        how it is served
```

## Building

```bash
make index      # 01 and 02. Hits nlftp; takes hours, and is resumable.
make build      # 03. Offline, seconds.
make validate   # 04.
make start      # browse the result in STAC Browser on :8080
make test       # unit tests
```

`make index` is deliberately slow: four workers with a random 1 to 10 second
pause between requests. The upstream server belongs to a government agency and
there is no reason to hurry it. `scripts/07_region_bbox.py` is separate and
rarely needed; it reads 1 GB of N03 archives as 4 MB of range requests.

`make start` clones STAC Browser into `tmp/` on first run, symlinks `catalog/`
into its `public/` directory, and serves both from one origin. `make serve` is
for pointing some other STAC client at the catalog over HTTP.

## License

The code is MIT. The data it describes is not: each KSJ dataset carries its
own terms, from CC BY 4.0 to non-commercial-only, and every generated
Collection states which. See <https://nlftp.mlit.go.jp/ksj/other/agreement.html>.
