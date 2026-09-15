# AGENTS.md

## What this repository produces

A static STAC catalog under `catalog/`. No server, no database. Every file is
JSON on disk, so a build is reproducible offline once `data/` exists.

Two views of the same Items:

- `collections/<id>/` — one Collection per KSJ dataset, Items inside it.
- `regions/<code>.json` — the same Items indexed by 地域, one Catalog per
  prefecture and per 地方, plus 全国. This is a view, which is why it is a
  Catalog and not a Collection: an Item's `collection` field points at its
  dataset, and the Item files live in one place and are linked from both.

## Before you change the parsing

`src/mlit_nlftp_stac/ksj.py` and `table.py` turn upstream HTML into an
identifier, a year, an area and a title. Upstream is irregular and the
irregularities are load-bearing. Run `make test` before and after; the cases in
`tests/` were taken from real upstream pages, not invented.

Known upstream irregularities, all verified against the live site:

- Download links live in `onclick="javascript:DownLd(...)"`, not in `href`.
- The size shown on the page is not reliable. The base of "MB" is 1024^2 on
  most pages and 10^6 on others, `A46` through `A48` use comma separators
  (`7,905KB`), one label reads `48.7.2MB`, and `P29-23_01_GML.zip` is
  advertised as 5.19MB while the file is 0.44MB. Use `data/head.jsonl`.
- The vintage column is headed `年度` on most pages and `年` on others, N03
  among them.
- Sortable pages write their column headers as `地域 ▲ ▼`. Keying on the raw
  text loses 4,739 rows without any error.
- Two page layouts exist for the description table: `<th>key</th>` on newer
  pages, `<td><b>key</b></td>` on A09, A53-2025 and A55-2024.
- Four rows, in A46, A47, A48 and N12, hold two download links because a
  `</tr>` is missing.
- The A51-2025 page prints `A51-25_40_GML.zip` twice, for two different files.
  Item ids come from the URL path, which is unique, not from the printed name.
- `G09-2026` is linked from the index but returns 404.
- Some upstream prose is simply wrong: mesh500r6 describes itself as
  「250mメッシュ別の将来人口」. That is quoted faithfully, not fixed here.

## Rules that are not negotiable

- **Never fabricate a geometry.** Two sources are real and both are used: a JIS
  mesh code in the filename, which names the exact cell, and the extent of a
  prefecture as N03 行政区域 states it, for a file published per prefecture.
  Everything else gets `"geometry": null` and no `bbox`. A nationwide bbox on
  a file that is not nationwide makes spatial search wrong in a way nobody
  notices. Files published per river-bureau (北海道開発局 and the rest) or per
  metropolitan region have no administrative boundary to borrow and stay
  without a footprint. `ksj:extent_source` says which source was used.
- **Never fabricate a size or a checksum either.** If `data/head.jsonl` has no
  entry for a URL, the Item omits `file:size` rather than guessing from the
  page label. What the page claims stays in `ksj:declared_size`, labelled as a
  claim.
- **Licenses differ per dataset.** Do not copy one Collection's license into
  another. Do promote it to an SPDX identifier only when the whole statement
  is that one licence; most KSJ terms split by year and stay `other` with the
  wording quoted in `ksj:terms`.
- **Every Item repeats its Collection's licence and terms and carries its own
  `license` link.** Someone can arrive at an Item from a search engine, see a
  Download button, and never open the Collection.
- **A title has to say what the thing is wherever it is read.** An Item title
  of `2006_東京（平成18年）` is fine inside its Collection and useless in a
  region catalog, where fourteen of them sit together. STAC Browser replaces a
  link's title with the Item's own once it loads the Item, so the Item title
  carries the dataset name too. The year stays first so that sorting by title
  sorts by year.
- **Put a `title` on every link.** The STAC best practices ask for it on
  `item`, `child`, `parent` and `root` links "even if it repeats several
  times", so a client can draw a readable tree without opening each
  destination. `make validate` fails on an item link without one.

## Talking to nlftp

Four workers, a random 1 to 10 second pause per request. Do not raise it.
HEAD works and returns `Content-Length`, `Last-Modified` and `ETag`, so
checking for updates costs nothing; there is no reason to re-download.

A zip's shapefile extent can be read without downloading the zip:
`src/mlit_nlftp_stac/shpbbox.py` walks the central directory and inflates the
first 100 bytes of the `.shp`. 1 GB of N03 archives costs 4 MB of range
requests.

## After deploying

Cloudflare caches a 404. A check that fails right after a deploy proves
nothing until the edge is ruled out:

```bash
curl -sI "https://stac.yuiseki.net/mlit-nlftp/catalog.json?cb=$(date +%s)"
```
