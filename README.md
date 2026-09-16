# mlit-nlftp-stac

A static STAC catalog for 国土数値情報 (National Land Numerical Information),
the geospatial data the Japanese Ministry of Land, Infrastructure, Transport
and Tourism publishes at <https://nlftp.mlit.go.jp/ksj/>.

Upstream has 21,603 downloadable zip files across 135 dataset pages, 228.2 GB
measured by HEAD. The only index it offers is HTML, and the download links are not
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
curl -s https://stac.yuiseki.net/mlit-nlftp/regions/39/catalog.json \
  | jq -r '.links[] | select(.rel=="item") | .title' | grep 津波
# 2016_高知（平成28年） — 津波浸水想定データ (A40)
```

And the download URL for one of them:

```bash
curl -s https://stac.yuiseki.net/mlit-nlftp/collections/A40/items/A40-16_39_GML.json \
  | jq -r '.assets.source.href, .properties.license, .properties["ksj:terms"]'
```

Everything at once, as one table:

```bash
duckdb -c "
  select collection_title, count(*) files, round(sum(file_size)/1e9, 2) gb
    from 'https://stac.yuiseki.net/mlit-nlftp/items.parquet'
   where redistribution = 'allowed' and year >= 2023
   group by 1 order by gb desc limit 5"
# 洪水浸水想定区域データ (A31a)                        795  40.67
# 250mメッシュ別将来推計人口データ（R6国政局推計）       168  12.01
```

1.4 MB for all 21,603 items. See [Query it whole](#query-it-whole).

## Four ways in

```
catalog.json
├── AGENTS.md                  rel: agents, linked from the root and every Collection
├── collections/catalog.json   データセット別   110 datasets
├── regions/catalog.json       地域別           56 regions
├── licenses/catalog.json      ライセンス別     3 statuses
├── categories/catalog.json    分類別           14 categories
└── items.parquet              every Item as one row
```

Four trees over the same 21,603 Items. A reader arriving with a theme takes
分類別, one with a place takes 地域別, one intending to republish takes
ライセンス別, and one that already knows the dataset takes データセット別.
`AGENTS.md` says which to take, and is linked rather than merely served: an
unlinked document is not read.

One node, one directory: `regions/39/catalog.json`, not `regions/39.json`.
Portolan's validator does not recognise a catalog whose file is named anything
else, so 193 of these were invisible to it (PTL-LNK-006) before the move.

Every catalog and every Collection carries its own `README.md` and `AGENTS.md`,
as Portolan requires, each referenced from the STAC document (`rel: describedby`
and `rel: agents`). The per-dataset `AGENTS.md` is generated from that dataset's
own Items: columns, licence split per file, measured size, and the datasets it
is usually used with. `make validate` fails if either file is missing or
unlinked.

**By dataset.** One Collection per KSJ dataset, named as the dataset page
names itself: `鉄道データ (N02)`, not `N02`. One Item per downloadable zip,
titled from its own row of the download table with the year first, so sorting
by title sorts by year, and with the dataset's name after it so the title
still says what it is when read somewhere else:
`2025_全国（令和7年） — 鉄道データ (N02)`.

**By licence.** `licenses/allowed/catalog.json` is every file
whose terms permit redistribution: 11,538 of 21,603, across 47 datasets. 4,288
may not be redistributed and 5,777 need a human to read the conditions. See
below for why this is an Item-level question.

**By region.** `regions/39/catalog.json` is every file that covers 高知 — 356 of them,
each carrying the name of the dataset it came from. 56 such catalogs, 16,613 links.
"What is there for this prefecture?" is the question people actually ask, and
answering it from Collections alone meant opening all 110.

**By category.** `categories/catalog.json` groups the 110 datasets the way the
JPGIS list page does: 施設 20, 交通 16, 災害・防災 15, and eleven more. 133 of
the 135 pages carry one. It is the axis for "what is there about X" when the
dataset's name is not known.

## Query it whole

`items.parquet` is every Item as one row: id, collection, title, year,
licence, redistribution, region, the download URL, the measured size, and the
footprint. 21,603 rows in 1.4 MB, spatially ordered and written with a
covering bbox, so a reader asking about one prefecture skips most of the file.

It answers what a tree cannot: everything matching a filter, across all 110
datasets, in one request. The JSON stays authoritative; this is an index.

```sql
select region, count(*)
  from 'https://stac.yuiseki.net/mlit-nlftp/items.parquet'
 where redistribution = 'allowed' and collection = 'P04'
 group by 1 order by 2 desc;
```

Spatial predicates need DuckDB's spatial extension. Use 1.5.5 or later: 1.3.2
crashes on it.

**Set a User-Agent.** Cloudflare sits in front of this host and answers 403 to
`Python-urllib/3.12`, the default the Python standard library sends. `curl`
and `requests` are fine. Until that rule is changed, `urllib` callers need
`Request(url, headers={"User-Agent": "..."})`.

## What an Item tells you

| | |
|---|---|
| `assets.source.href` | the zip on nlftp |
| `assets.source.file:size` | the real byte count, measured by HEAD for every file |
| `properties.license` | resolved from the Item's own year, not the Collection's |
| `properties.ksj:redistribution` | `allowed`, `not-allowed` or `check` |
| `properties.ksj:terms_applied` | the sentence that decided it |
| `properties.ksj:terms` | the Collection's full statement, verbatim |
| `geometry` / `bbox` | a JIS mesh cell, or the prefecture's extent from N03 行政区域 |
| `properties.ksj:extent_source` | which of those two, in words |
| `start_datetime` / `end_datetime` | from the page's 年度 column, not guessed from the filename |
| `properties.ksj:is_latest` | whether this is the newest year **for its own region** |
| `properties.ksj:file_format` | SHAPE, GEOJSON, GML, from the filename |
| `properties.ksj:coordinate_system` | JGD2011, JGD2000, Tokyo, as the page states it |
| `properties.ksj:declared_size` | what the page claims, which is not always what the file weighs |

And a Collection carries `ksj:variants`: one entry per shapefile in the zip,
each with its columns, the name a query has to spell (`N02_001`), the readable
name (鉄道区分), a description, and for a coded column a link to the code list.
`table:columns` is emitted too, but only for the 82 datasets that ship a single
shapefile, because a dataset with two schemas cannot honestly have one. A
Collection also carries `ksj:years`, every year it holds, so "is there anything
recent here" is answerable without opening an Item.

Eighteen pairs of datasets are linked to each other with `rel: related`, for
combinations someone has to decide rather than derive: 津波浸水想定 with 避難施設,
バス停留所 with 将来推計人口. Those links carry `ksj:editorial: true` and a
`ksj:reason` in Japanese, so a reader can tell an opinion from a fact, and
`ksj:crs_mismatch` when the two sides use different datums.

```bash
curl -s https://stac.yuiseki.net/mlit-nlftp/codelists/RailwayClassCd.json | jq '.values[1]'
# { "value": "13", "label": "鋼索鉄道",
#   "description": "車両にロープを緊結して山上の巻上機により巻上げて運転する…" }
```

## What it does not tell you

Worth knowing before you plan work around it:

- **Attribute schemas cover 105 of 110 datasets**, 1,580 columns across 151
  shapefiles, with 117 code lists and 46,040 coded values beside them. The
  five without are datasets whose page states no 属性情報 table. Nine code
  lists are spreadsheets rather than pages and are not read.
- **No search.** A static catalog has no `/search`. `items.parquet` answers
  most of it, the region index covers "what is here", and Collections carry a
  `ksj:category` (施設, 交通, 災害・防災 …) and keywords to filter on. Nothing
  here can answer "there is no dataset for this theme"; absence is invisible.
- **Footprints are administrative, not measured.** A prefecture file gets the
  prefecture's extent, so spatial search works at prefecture granularity and
  no finer. 98% of Items have one; files published per river-bureau or per
  metropolitan region have no boundary to borrow and carry `"geometry": null`.
- **`file:size` is measured for every file**, all 21,603 of them, by HEAD:
  228.2 GB in total, of which 93.2 GB is redistributable. `ksj:declared_size`
  is the figure the page prints, which disagrees with the file often enough
  not to trust. `make head` is resumable and re-runs against new vintages.
- **A licence belongs to a year, not to a dataset.** 鉄道データ is CC BY 4.0
  from 2020 and 商用可 before it; 学校データ is CC BY 4.0 for 2023 and 2021 and
  非商用 for 2013. Each Item resolves its own, and `ksj:terms_applied` quotes
  the sentence that decided it. The Collection keeps the whole statement.
  「一部制限」 is never resolved automatically: A40 lists which prefectures may
  redistribute and which must telephone first, and A27 says the terms differ
  per municipality and stops there. Those are `check`.
- **Datasets with more than 20 files are browsed by year.** A Collection that
  listed 603 Items in one array is readable by a query and not by a person, so
  the Items sit under `years/<year>/`, and a year longer than 60 files splits
  again by region. The Items themselves stay at `collections/<id>/items/`, so
  every other link into them is unchanged.
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
scripts/08_codelists.py       KSJ code list pages -> data/codelists.json
scripts/09_geoparquet.py      catalog/ -> catalog/items.parquet

src/mlit_nlftp_stac/ksj.py     filename -> identifier, year, area (the risky part)
src/mlit_nlftp_stac/page.py    a dataset page -> its own name, description, terms
src/mlit_nlftp_stac/table.py   a download row -> the region, river, format, year
src/mlit_nlftp_stac/terms.py   a terms statement -> a licence, per year and prefecture
src/mlit_nlftp_stac/attributes.py a 属性情報 table -> the columns of each shapefile
src/mlit_nlftp_stac/categories.py the JPGIS list page -> one category per dataset
src/mlit_nlftp_stac/mesh.py    JIS mesh code -> bounding box
src/mlit_nlftp_stac/shpbbox.py a zip's shapefile extent, read by range request
src/mlit_nlftp_stac/stac.py    all of the above -> STAC
src/mlit_nlftp_stac/geoparquet.py the Items -> one row each

docs/design.md                 the decisions, and where upstream fights back
docs/catalog-AGENTS.md         published as catalog/AGENTS.md, for the reader
data/combinations.json         the 18 editorial pairs, and why each one is there
deploy/                        how it is served
```

## Building

```bash
make index      # 01 and 02. Hits nlftp; takes hours, and is resumable.
make head       # 02 alone, to measure files a new vintage added.
make build      # 03 and 09. Offline, a minute.
make validate   # 04. Resolves every relative link in every document.
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
