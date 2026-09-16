# Design

## What this is

A static STAC catalog describing 国土数値情報. It holds metadata only. Every
asset href points at nlftp; nothing is rehosted and nothing is converted.

That single decision settles most of the rest. A catalog that owns no bytes
cannot promise range requests, cannot compute checksums for files it has not
downloaded, and has nothing to keep in sync beyond its own metadata.

## Shape

Three views of the same Items, and nothing else at the top:

```
catalog.json                                  Catalog        1
collections/catalog.json                        by dataset
collections/<id>/collection.json                Collection 110
collections/<id>/items/<file>.json              Item    21,603
regions/catalog.json                            by region
regions/<code>/catalog.json                     Catalog     56
licenses/catalog.json                           by licence
licenses/<status>/<id>.json                     Catalog    120
```

The root used to link straight to the 110 Collections, with the two other
views sitting among them, so one level of the tree held two kinds of thing.
The best practices ask for the opposite ("use structural elements consistently
across each level"), and the asymmetry had a bug hiding in it: every
Collection's root and parent pointed at `../catalog.json`, which from
`collections/N02/` is `collections/catalog.json`, a file that did not exist.
110 dangling links. `make validate` now resolves every relative link in every
document rather than only the item links, which is what would have caught it.

One Collection per dataset, not per dataset-version: the `-2025` on a page
name such as `A31b-2025` is the page's own version, and every year of A31b
belongs together. One Item per downloadable file.

## What is borrowed from Portolan

[Portolan](https://github.com/portolan-sdi/portolan-spec) is an opinionated
profile over STAC for cloud-native catalogs. Conforming to it would mean
converting 214 GB of zipped Shapefiles to GeoParquet and PMTiles, which is not
what this repository is for. Its reasoning is worth taking anyway:

- **The `source` role.** Portolan exempts an upstream original from its format
  rules when it carries `source`. That is exactly what these assets are, so
  they are `source` and not `data`. A `data` asset would claim a cloud-native
  copy exists.
- **Mirror, not official.** Producer and host differ, so this is a mirror. It
  carries a `via` link to the upstream page at every level and records the
  sync time in `updated`.
- **Explicit licensing.** A Collection must state a license. Each dataset page
  states its own terms in a 使用許諾条件 row, so those are read and promoted to
  an SPDX identifier when the whole statement is that one licence. Most are
  not: `N02` is CC BY 4.0 from 2020 onward and merely "commercial use allowed"
  before, and a Collection holds every year. Those stay `other`, with the
  upstream wording kept verbatim in `ksj:terms`. `proprietary` is never used.
- **A fabricated value is worse than an absent one.** Portolan says this about
  `file:size` and `file:checksum`. It is applied here to footprints too.
- **README.md and AGENTS.md as links.** They describe the data, so they are
  `describedby` and `agents` links rather than assets.

What is not taken: the format requirements, the storage requirements (there is
no hosted asset to range-request), the styling and thumbnail requirements, and
conformance itself.

## Three places where the upstream data fights back

**Footprints.** Two sources are real. A mesh code in the filename names the
exact cell and can be computed (`src/mlit_nlftp_stac/mesh.py`). A file
published per prefecture covers that prefecture, and 国土数値情報 says how far
that reaches: N03 行政区域 is in this catalog already, so the extents come from
the data itself rather than from some other country-boundary dataset.

Reading them is cheap. N03's prefecture archives total about 1 GB, and all
that is needed from each is the 100-byte header of the shapefile inside, which
states its own bounding box. The zip's central directory says where that file
starts, nlftp honours Range requests, and deflate only needs the start of its
stream, so 1 GB of archives becomes 4 MB of reads
(`scripts/07_region_bbox.py`, `src/mlit_nlftp_stac/shpbbox.py`). The same pass
yields the 8 regional aggregates N03 carries as codes 52 to 59, which also
settles what the two-digit tokens in A46, A47 and A48 filenames are: 地方, not
prefectures.

A prefecture footprint is the administrative extent, not the measured extent
of what is inside the zip. It is a superset, so it can only cause a spatial
query to match something it did not need, never to miss something it did.
`ksj:extent_source` says which of the two an Item's footprint came from.

98% of Items have one. The rest are published per river-bureau
(北海道開発局 and the other eight) or per metropolitan region, and no
administrative boundary matches those, so they stay null.

**Sizes.** The size printed on the page is unusable: the base of "MB" is
1024^2 on most pages and 10^6 on others, `A46` to `A48` use comma separators,
one label reads `48.7.2MB`, and `P29-23_01_GML.zip` is advertised at 5.19MB
against a measured 0.44MB. `file:size` therefore appears only where a HEAD
response measured it. The page's own string is kept as `ksj:declared_size`,
clearly labelled as what the page claims.

**Identity.** The A51-2025 page prints `A51-25_40_GML.zip` twice, once for a
link whose path is `A51-24/A51-24_40_GML.zip`. They are different files
(12,520,868 and 11,506,692 bytes). Item ids come from the URL path, which is
unique, not from the printed name.

## Item titles

Each download link sits in a table row whose other cells say what the file is,
and the table's header names those columns: 地域, 形式, 河川, 測地系, 年度.
Taking the row gives an Item a title a person can read, and gives the year
from the page rather than from a guess at the filename.

The title leads with the year, as `2026_東京（令和8年）`, because STAC Browser
sorts on the title and a list of files that sorts by year is the one a person
wants. The era is kept because that is how the page names a vintage, and
someone looking for 令和6年度版 should find it by eye.

The vintage column is headed 年度 on most pages and 年 on others, N03 among
them. Looking only for 年度 leaves those pages taking the year from the
filename and printing it twice in the title.

Sortable pages write their headers as `地域 ▲ ▼`, so the arrows are stripped
before the label is used as a key; without that, 4,739 rows lose every cell
and no error is raised.

Four upstream rows (in A46, A47, A48 and N12) hold two download links because
a `</tr>` is missing. The cells then describe one of the two and there is no
way to tell which. Both links are kept and neither gets the cells, so eight
Items have no title. Taking the first link per row instead would drop four
files; giving both rows the cells would label four files with another file's
region and year.

## Licensing on Items, not only Collections

STAC puts `license` on a Collection, and a reader who walks down from the
catalog sees it there. A reader who arrives at an Item from a search engine
does not: they see a title, a map and a download button. So each Item repeats
its Collection's `license` and `ksj:terms`, and carries a `license` link of its
own. Nine of 135 pages state no terms at all; those Items still have the link.

## One table beside the tree

A catalog of 21,603 files answers "what is in this dataset" by being read, and
"which files cover this place, from this year, that I may redistribute" only
by being read whole. Both agents named that as their largest cost, and it is
the one thing a static tree genuinely cannot do.

`items.parquet` is the same Items as one row each, following the
stac-geoparquet convention: the fields worth filtering on promoted to columns,
the geometry written with a covering bbox, and the rows in Hilbert order so a
reader asking about one prefecture skips most of the row groups. Items with no
footprint sort last, since they have no place in that order.

The whole catalog is 1.1 MB, which is small enough that the question of
whether to host a search API does not arise. The JSON remains authoritative;
this is an index built from it by `09_geoparquet.py`, offline, from the files
`03_build_stac.py` just wrote, so the two cannot disagree except by being run
at different times.

## The columns, and what their values mean

Two agents were given a research question and this catalog. Both found the
right dataset, and both said the same thing about what stopped them next:
nothing here said which column held バス区分, or what the value 13 meant, so
the only way to plan the work was to open the MLIT page.

The page has it. Each dataset states its columns in a 属性情報 table -- the
readable name, the name the shapefile actually uses, a description, and either
a type or a link to a code list -- and each code list is a table of value,
label and definition. `attributes.py` reads both. 105 of 110 datasets, 1,565
columns over 153 shapefiles, 117 code lists, 46,040 values.

Three decisions worth stating:

**A dataset can have several schemas.** N02 ships RailroadSection.shp and
Station.shp with different columns. `ksj:variants` is a list, one per
shapefile. `table:columns`, which is flat, is emitted only for the 80 datasets
that ship one shapefile; for the others it would describe none of them.

**`name` is the name a query has to spell.** That is `N02_001`, not 鉄道区分.
The readable name goes in the description, where both a person and an agent
still see it.

**Code lists are files, not fields.** RiverCodeCd has 35,450 values. Inlining
it into every dataset that references a river would be absurd, so each list is
`codelists/<name>.json` and a column points at it. Nine lists are spreadsheets
rather than pages; those are left unread rather than guessed at.

## A licence belongs to a year

The terms of use (agreement_02.html, 第1条) define the two labels that matter:

    （ａ）「商用可」＝ ... 商用目的での利用（複製物の再配布を含む）が可能
    （ｂ）「非商用」＝ ... 非商用目的のみでの利用（ただし複製物の再配布を除く）

So 商用可 permits redistribution and 非商用 excludes it, in as many words, and
the question "may I republish this file?" has an answer written down.

What the answer is not is a property of the dataset. 鉄道データ is CC BY 4.0
from 2020 and 商用可 before it. 学校データ is CC BY 4.0 for 2023 and 2021 and
非商用 for 2013. 人口集中地区データ is 商用可 from 1995 and 非商用 before. A
Collection holds every year, so one answer for the Collection is either wrong
or useless; an Item has a year, so an Item can be right.

`src/mlit_nlftp_stac/terms.py` resolves it, and `ksj:terms_applied` on each
Item quotes the sentence that decided. Anything it cannot resolve is `check`,
never a guess: the cost of a wrong "allowed" is someone republishing data they
were not licensed to. That covers 「一部制限」, where the conditions are the
provider's and not the page's, and Items whose year could not be read.

Counted this way, 9,943 of 21,603 files may be redistributed, 4,146 may not,
and 7,514 need a person. Counted per Collection it looked like 15 datasets;
the difference is entirely the recent years of datasets whose old years are
not open.

`licenses/<status>/<dataset>.json` makes that browsable, which is the point:
someone building a derived dataset needs to find what they may lawfully use
before they need anything else.

## One judgement, marked as one

Everything else in this catalog is taken from what upstream says. The
cross-theme `rel: related` links are not: 浸水想定 and 避難施設 are a pair
because someone decided they are, and the data says nothing of the kind.

Two rounds of agents asked for them after finding the advice in AGENTS.md's
prose and not in any link they could follow. So they exist, in
`data/combinations.json`, 18 pairs with a reason each, and every generated
link carries `ksj:editorial: true` and `ksj:reason`. A reader can therefore
tell a judgement from a fact, which is the only condition on which a judgement
belongs in a catalog whose whole discipline is not inventing things.

The links are bidirectional and `make validate` fails if one direction is
missing, because a reader arriving at either end should find the other.

## Indexed by region as well as by dataset

An Item belongs to one Collection, which is the right home for it and the
wrong answer to the question a planner actually asks: what is there for 高知?
Answering that from Collections alone means opening all 110 of them, and two
agents asked to use this catalog both said so unprompted.

`regions/<code>/catalog.json` is a Catalog of the same Items seen the other way, one
per prefecture, per 地方, and one for 全国. 56 of them, 16,613 item links. Each
link carries the collection's name alongside the item's title, so the list
reads as 避難施設データ (P20) — 2012_高知（平成24年）.

Items whose 地域 is not a place N03 knows get no region entry rather than a
wrong one. That covers the 地方整備局, the 三大都市圏, and the pages whose
地域 column holds a mesh number.

An Item's own title carries the dataset name as well, because a title has to
say what the thing is wherever it is read. STAC Browser replaces a link's
title with the Item's own as soon as it loads the Item, so a region catalog of
339 files was rendering as `2006_東京（平成18年）` fourteen times over with
nothing to tell the rows apart. The year stays first, so sorting by title
still sorts by year; within a Collection the suffix is constant and changes
nothing.

Item links inside a Collection carry the Item's title too. Without it,
finding 高知 in P20 meant knowing that the two digits in `P20-12_39_GML` are a
JIS prefecture code, which is exactly the outside knowledge a catalog exists
to remove.

## Dates

The year now comes from the 年度 column, falling back to the filename only
when the row was unreadable. The column is written as 2025年（令和7年） or as
平成25年, so both the western year and the era form are read; 令和元年 is 2019,
not 令和0年.

A KSJ year may still be a calendar year or a fiscal one and the page does not
say which. Items set `datetime` to null and span the calendar year with
`start_datetime` and `end_datetime`, which is the least wrong reading. Where
no year can be read at all, `ksj:datetime_is_unknown` marks it rather than a
plausible-looking date being invented.

## Naming

A Collection called `A31b` tells a reader nothing. Every dataset page carries
its own name in `<title>`, its own prose in a 内容 row, and its identifier in
a 識別子 row, so `01_fetch_index.py` takes all three from the same fetch that
harvests the links. No third-party API sits between the source and the words
that describe it.

Two page layouts exist. Newer pages use `<th>key</th><td>value</td>`; A09,
A53-2025 and A55-2024 still use `<td><b>key</b></td><td>value</td>`. Reading
only the first gives those three no description at all, which is the kind of
gap that looks like missing upstream data rather than a parser that stopped
early. Both are read. 134 of 135 pages yield a description; A53-2025 genuinely
has no 内容 row.

Where a dataset has both an unversioned and a versioned page (`A03` and
`A03-2025`), the versioned one is the current description and wins.

## Where it is served

`https://stac.yuiseki.net/mlit-nlftp/`. A path under one host, not a host per
catalog, for two reasons. Cloudflare's Universal SSL covers the apex and
first-level subdomains only, so `mlit-nlftp.stac.yuiseki.net` would need Total
TLS on the zone while `stac.yuiseki.net` needs nothing. And the next catalog
then costs a directory rather than a DNS record and a tunnel rule.

Only the `self` links are absolute. `root`, `parent` and `item` stay relative,
so a copy of `catalog/` works from a local directory, from a different prefix,
or from a USB stick, which is most of the point of a static catalog.

## Browsing it

`make start` runs STAC Browser against the catalog. The catalog is symlinked
into STAC Browser's own `public/` directory and read from a relative URL, so
the page and the data share an origin. Two servers on two ports also works,
and `05_serve.py` sends the CORS headers for it, but then every catalog file
is a cross-origin request: when something is wrong the page shows an empty
catalog and blames CORS, whatever the actual cause was. One origin removes
that whole class of confusion from a dev loop.

## Open

- A53-2025 has no description upstream. Nothing to do but notice it.
- Prefecture footprints, which need a per-dataset decision about what the
  two-digit token in a filename means.
- Whether to emit stac-geoparquet alongside the JSON for bulk querying.

## Portolan conformance, and where this catalog stops

`portolan check --metadata --no-data` (portolan-cli, rashid rules) is run
against the built catalog. Two of its findings were bugs and are fixed; four
are deliberate, and they are listed here so that a later reader does not
mistake them for oversights.

Fixed:

- **PTL-PRV-002** — every Collection now carries exactly one provider with the
  `host` role, last in the list, with a URL to reach the maintainer. The data
  is MLIT's; this copy is not, and nothing here said who to tell about a wrong
  footprint.
- **PTL-LNK-006** — 193 leaf catalogs were named `39.json`, `交通.json`,
  `allowed/A09.json`. A generic Portolan client does not recognise a catalog
  whose file is not `catalog.json`, so a third of this catalog was invisible to
  it. Each now sits in its own directory. The old URLs are gone rather than
  redirected.
- **PTL-CAT-001** — 96 Collections listed every Item in one flat array, 603 of
  them in the worst case. Now grouped by year, and by region within a year
  where the year is still long.

Not fixed, on purpose:

- **PTL-CNF-001** (no Portolan schema URI in `stac_extensions`). The spec is
  explicit that declaring the extension is a claim of conformance, not proof of
  it, and that an object conforms only by passing the validator. This catalog
  cannot pass PTL-VIZ-001, so declaring would be a false claim. The URI goes in
  when the claim is true.
- **PTL-VIZ-001** (no `thumbnail` asset). A thumbnail is supposed to be
  generated from the data's default styling. We hold no data: the zips stay on
  MLIT's servers, 228 GB of them, and a third may not be redistributed. A
  picture of a prefecture outline would not be a preview of the data, it would
  be a picture of the bbox we already publish.
- **PTL-AST-003** (no `file:checksum`, 21,603 warnings). Portolan's own text
  answers this: a catalog that describes data it does not host cannot always
  produce them, and a fabricated value is worse than an absent one. We would
  have to download 228 GB to compute them and re-download to keep them true.
  `file:size` is measured by HEAD, which is honest and cheap; a checksum is
  neither.
- **PTL-COL-003** (Collection ids are not lowercase). The ids are KSJ's own
  identifiers: `A40`, `N02`, `mesh500r6`. They are how every MLIT page, every
  filename and every existing tool names these datasets. A lowercase rename
  would be a private spelling of a public identifier.
