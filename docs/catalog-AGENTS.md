# AGENTS.md

For whatever is reading this catalog: how to get an answer out of it, and
which of its answers not to trust.

This is a mirror of 国土数値情報 (National Land Numerical Information). It holds
metadata; the files stay on MLIT's servers. Base URL:
`https://stac.yuiseki.net/mlit-nlftp/`

## Fetch with a User-Agent

Cloudflare fronts this host and answers **403 to `Python-urllib/3.12`**, the
default the Python standard library sends. `curl` and `requests` are fine.

```python
urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "you"}))
```

## Four ways in, and which to use

| You want | Fetch |
|---|---|
| everything matching a filter | `items.parquet` (1.1 MB, all 21,603 items) |
| what exists for a prefecture | `regions/<JIS code>.json` |
| what you may republish | `licenses/allowed/catalog.json` |
| one dataset in detail | `collections/<id>/collection.json` |

`collections/catalog.json` lists all 110 datasets by Japanese name in one
request. Start there if you are choosing a dataset by reading.

**Do not scan 110 collections.** Every question of the form "which files
cover X" or "which files are Y" is one query against `items.parquet`:

```sql
select collection_title, region, title, href, file_size
  from 'https://stac.yuiseki.net/mlit-nlftp/items.parquet'
 where region = '高知' and is_latest and redistribution = 'allowed';
```

Columns: `id collection collection_title title year start_datetime
end_datetime license redistribution terms_applied identifier region river
format crs nendo mesh_code is_latest category extent_source href file_size
declared_size last_modified etag item_href geometry`.

Spatial predicates need DuckDB's spatial extension, version 1.5.5 or later.
1.3.2 crashes on it.

**A stale copy will lie to you.** The CDN in front of this host has served a
`items.parquet` two columns out of date, and a 404 for a path that existed,
long after the origin was right. If a column the list above names is missing,
or a licence disagrees with the Item's own JSON, you have an old copy. Add a
query string to get past it:

```bash
curl -s "https://stac.yuiseki.net/mlit-nlftp/items.parquet?cb=$(date +%s)" -o items.parquet
```

The Item JSON is authoritative. `items.parquet` is built from it.

## Picking the right file

A dataset's newest year is not the same in every prefecture. 津波浸水想定 (A40)
is current to 2024 in most places and stops at 2016 in 高知 and 徳島. So:

- `ksj:is_latest` on an Item is computed **per region**, not per dataset.
  Filter on it.
- `ksj:latest_year` on a Collection is the newest year anywhere in it, which
  is not a promise about your prefecture.
- Item titles start with the year (`2016_高知（平成28年） — 津波浸水想定データ
  (A40)`), so sorting by title sorts by year.

Many datasets publish the same year in several formats. `ksj:format` says
which; GML, シェープ形式 and GeoJSON形式 are the usual three, and some zips
contain two at once ("シェープ、geojson形式").

## Before you redistribute anything

The licence belongs to the **year**, not to the dataset. 鉄道データ is CC BY 4.0
from 2020 and 商用可 before it; バス停留所データ is CC BY 4.0 for 2022 and
非商用 for 2010.

- `properties.license` — resolved for that Item's year.
- `properties.ksj:redistribution` — `allowed`, `not-allowed`, `check`.
- `properties.ksj:terms_applied` — the sentence that decided it.
- `properties.ksj:terms` — the dataset's full statement. Absent when the page
  states none, which is why those Items are `check`.

The terms of use define the two words that matter
(<https://nlftp.mlit.go.jp/ksj/other/agreement_02.html>, 第1条): 商用可 is
「複製物の再配布を含む」 and 非商用 is 「ただし複製物の再配布を除く」. So
`not-allowed` means redistribution is excluded in as many words.

`check` is not a soft yes. It covers 「一部制限」, where the conditions belong
to a prefecture or a municipality, and Items whose year could not be read.
Read `ksj:terms` yourself.

Attribution, when you do use it: 出典 the dataset and its page URL, and say if
you edited it.

## Reading the data you download

A Collection carries `ksj:variants`: one entry per shapefile in the zip, each
with its columns.

```json
{"name": "鉄道区分", "column": "N02_001", "description": "鉄道路線の種類による区別",
 "type": "codelist", "codelist": "鉄道区分コード",
 "ksj:codelist_href": "../../codelists/RailwayClassCd.json"}
```

`column` is the name the shapefile actually uses and the one a query has to
spell. Coded columns hold values like `13`; the code list says what they mean.

```bash
curl -s .../codelists/RailwayClassCd.json | jq '.values[] | select(.value=="13")'
# {"value":"13","label":"鋼索鉄道","description":"車両にロープを緊結して…"}
```

A dataset can have more than one variant, and the page does not always say
which vintage each belongs to: P11 has two tables in which `P11_002` is
バス事業者名 in one and バス区分 in the other, and neither names a shapefile.
When two variants disagree about a column, open the file to see which you got.

`table:columns` is also emitted, but only for the 80 datasets that ship a
single shapefile. 105 of 110 datasets have schemas; five state none upstream.
Nine code lists are spreadsheets rather than pages and are not read.

Shapefiles are Shift-JIS in older vintages and both encodings in newer ones.
`ksj:crs` says the CRS, usually JGD2011.

## What this catalog gets wrong, and where it is thin

- **Footprints are administrative, not measured.** A prefecture file gets the
  prefecture's extent from N03 行政区域, so spatial search works at prefecture
  granularity and no finer. `ksj:extent_source` says which source was used;
  files published per river-bureau or per metropolitan region have no boundary
  to borrow and carry `"geometry": null`. Mesh-named files get their real cell.
- **`file:size` is measured, `ksj:declared_size` is claimed.** The page's own
  figure disagrees with the file often enough not to plan a download on it:
  one file advertised at 5.19MB is 0.44MB. Coverage of the measured value is
  still growing; when it is absent, the size is unknown rather than zero.
- **Staleness is not flagged.** 避難施設 (P20) stopped in 2012 and nothing here
  says so beyond the dates. Check `ksj:latest_year` against the year you need.
- **Old and new editions of the same idea are not linked.** There are seven
  future-population collections (mesh250r6 / mesh500r6 / mesh1000r6 are the
  2024 R6 estimates; mesh500h30 and mesh1000h30 are H30; mesh500 and mesh1000
  are H29). Read their descriptions: the newer ones say 令和2年の国勢調査 and
  2070年まで, the older ones 平成27年の国勢調査 and 2050年まで.
- **Upstream prose is quoted, not corrected.** mesh500r6 describes itself as
  「250mメッシュ別の将来人口」. That is what the page says.
- **Column names can be placeholders.** The population meshes list
  `PT00_20XX` and `RTC_20XX`; which years are actually present is in the file,
  not here.
- **Nothing links related datasets.** Overlaying 浸水想定 with 避難施設 is a
  normal thing to want and there is no link from one to the other, nor from an
  old edition of a dataset to its replacement.

## Quirks of the upstream site, if you go there

- Download links are `onclick="javascript:DownLd(...)"`, not `href`. Nothing
  crawls that site by accident.
- The zips are directly fetchable: no Referer, no cookie, Range supported.
- The A51-2025 page prints one filename for two different files; Item ids here
  come from the URL path for that reason.
