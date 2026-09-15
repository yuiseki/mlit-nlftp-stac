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
| what there is on a theme | `categories/交通.json` and its 13 siblings |
| what you may republish | `licenses/allowed/catalog.json` |
| one dataset in detail | `collections/<id>/collection.json` |

Do not take a per-dataset fact from this file on trust; count it. An earlier
version of this page said A40 was "current to 2024 in most places", which was
wrong, and a reader repeated it to a planner.

```sql
select region, max(year) from 'items.parquet' where collection = 'A40' group by 1;
```

`collections/index.json` (32 KB) is every dataset with its **description**,
category, keywords, latest year and item count. Start there when you are
choosing by what a dataset contains rather than by its name: the word that
tells 津波浸水想定 from 高潮浸水想定 is in the description, not the title.
`collections/catalog.json` is the same 110 datasets as links only.

```bash
curl -s .../collections/index.json \
  | jq -r '.collections[] | select(.description | test("津波")) | "\(.id) \(.title)"'
```

**Do not scan 110 collections.** Every question of the form "which files
cover X" or "which files are Y" is one query against `items.parquet`:

```sql
select collection_title, region, title, href, file_size
  from 'https://stac.yuiseki.net/mlit-nlftp/items.parquet'
 where region = '高知' and is_latest and redistribution = 'allowed';
```

**Fetch it with a cache-buster. This is not optional.**

```bash
curl -s "https://stac.yuiseki.net/mlit-nlftp/items.parquet?cb=$(date +%s)" -o items.parquet
```

The CDN in front of this host has served a copy two columns out of date for
hours. Four separate readers have hit it, all four concluded the file was
built wrong, and all four were reading an old copy. If a column named below is
missing, that is what happened. The Item JSON is authoritative; the Parquet is
built from it.

Columns: `id collection collection_title title year start_datetime
end_datetime license redistribution terms_applied identifier region river
format file_format crs coordinate_system nendo mesh_code is_latest category
extent_source href file_size declared_size last_modified etag item_href
geometry bbox`.

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

A dataset's newest year is not the same in every prefecture. 津波浸水想定
(A40) covers 39 prefectures, and their newest years are: 2016 for sixteen of
them, 2023 for eight, 2022 for five, 2020 and 2018 for three each, 2017 for
two, and 2024 and 2021 for one each. So:

- `ksj:is_latest` on an Item is computed **per region**, not per dataset.
  Filter on it.
- `ksj:latest_year` on a Collection is the newest year anywhere in it, which
  is not a promise about your prefecture.
- Item titles start with the year (`2016_高知（平成28年） — 津波浸水想定データ
  (A40)`), so sorting by title sorts by year.

Many datasets publish the same year in several formats. Use
`ksj:file_format`, which is `GML`, `Shapefile` or `GeoJSON`, derived from the
filename and present for 96% of files. `ksj:format` is the page's own word for
the same thing: absent for three quarters of them and spelled four ways where
it is present, so it is kept for reference and not for filtering.

## Combining datasets

Datasets that are typically used together **are** linked, as `rel: related`
with `ksj:editorial: true` and a `ksj:reason` saying what the pair is for.
That flag matters: the upstream data states no such relation, so those links
are a judgement made here, unlike the `rel: related` links between editions of
one dataset, which are derived from the titles. 18 pairs, listed in
`data/combinations.json` in the repository.

The ones worth knowing without looking:

- 浸水想定 (A31a 洪水, A40 津波, A49 高潮, A51 内水) against facilities
  (P04 医療機関, P29 学校, P11 バス停留所). Note that 避難施設 (P20) is 非商用
  and cannot be redistributed, so a published map cannot carry its points.
- Population (mesh500r6 and its siblings) against anything reachable on foot.
  The mesh is 500 m; bus-stop catchments are 300 to 500 m.
- 駅別乗降客数 (S12) joins to 鉄道 (N02) by station name and operator.

Editions of the same dataset **are** linked: a Collection in a series carries
`ksj:series` and `rel: related` links to its other editions, with each one's
latest year in the link title. The seven population meshes are three series of
one resolution each.

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
spell. Where it contains `～`, as in `P11_004_01～35`, the page is naming a
numbered family rather than one column; `repeats` then gives the prefix, the
range and an example of a real name (`P11_004_01`). Coded columns hold values like `13`; the code list says what they mean.

```bash
curl -s .../codelists/RailwayClassCd.json | jq '.values[] | select(.value=="13")'
# {"value":"13","label":"鋼索鉄道","description":"車両にロープを緊結して…"}
```

A dataset can have more than one variant when its zip holds several
shapefiles; N02 ships RailroadSection.shp and Station.shp with different
columns.

Only the current schema is listed. Superseded tables are left on the upstream
page as HTML comments, and reading them once made this catalog advertise
columns the data does not have: N07 バスルート was published here with
平日運行頻度 and 土曜日運行頻度, which exist in the pre-2022 schema and not in
the 2022 files anyone would download.

`table:columns` is also emitted, but only for the 80 datasets that ship a
single shapefile. 105 of 110 datasets have schemas; five state none upstream.
Nine code lists are spreadsheets rather than pages and are not read.

Shapefiles are Shift-JIS in older vintages and both encodings in newer ones.
`ksj:coordinate_system` is the dataset's CRS as its page states it: JGD2011 or
JGD2000, and they differ between datasets you might overlay (A40 is JGD2011,
P20 is JGD2000). `ksj:crs` is the download table's own word, usually the
family name 世界測地系, which is not enough to transform with. Neither is
per-vintage: a dataset that changed datum lists both, and some datasets state
the CRS inside their terms of use instead, where this does not find it.

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
- **The cross-theme links are editorial, and thin.** 18 pairs, chosen by hand;
  a pair that is not there is not a statement that it is a bad idea. Editions
  of the same dataset are linked, where more than one edition exists: mesh250r6
  has no `ksj:series` because there is no 250 m edition of the older estimates.
- **A Collection's `license` is `other` if any year in it is.** A40's items
  resolve to CC-BY-4.0 for the prefectures its terms name, while the Collection
  stays `other`, because a Collection has no prefecture. Read the Item.

## Quirks of the upstream site, if you go there

- Download links are `onclick="javascript:DownLd(...)"`, not `href`. Nothing
  crawls that site by accident.
- The zips are directly fetchable: no Referer, no cookie, Range supported.
- The A51-2025 page prints one filename for two different files; Item ids here
  come from the URL path for that reason.
