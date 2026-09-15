# Design

## What this is

A static STAC catalog describing 国土数値情報. It holds metadata only. Every
asset href points at nlftp; nothing is rehosted and nothing is converted.

That single decision settles most of the rest. A catalog that owns no bytes
cannot promise range requests, cannot compute checksums for files it has not
downloaded, and has nothing to keep in sync beyond its own metadata.

## Shape

```
catalog.json                                  Catalog   1
collections/<id>/collection.json              Collection 110
collections/<id>/items/<file>.json            Item     21,603
```

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

**Footprints.** Only mesh-coded filenames yield a footprint that can be
computed (`src/mlit_nlftp_stac/mesh.py`). Everything else would need the zip
opened or a prefecture lookup that the filename does not reliably support, so
those Items carry `"geometry": null` and no `bbox`. Filling them with a
nationwide box would make every spatial query match everything.

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

## Dates

A KSJ year may be a calendar year or a fiscal one and the page does not always
say which. Items set `datetime` to null and span the calendar year with
`start_datetime` and `end_datetime`, which is the least wrong reading. Where
no year can be parsed at all, `ksj:datetime_is_unknown` marks it rather than a
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

## Open

- A53-2025 has no description upstream. Nothing to do but notice it.
- Prefecture footprints, which need a per-dataset decision about what the
  two-digit token in a filename means.
- Whether to emit stac-geoparquet alongside the JSON for bulk querying.
