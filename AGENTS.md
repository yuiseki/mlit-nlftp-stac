# AGENTS.md

## What this repository produces

A static STAC catalog under `catalog/`. No server, no database. Every file is
JSON on disk, so a build is reproducible offline once `data/` exists.

## Before you change the parsing

`src/mlit_nlftp_stac/ksj.py` turns a filename such as `A33-25_01_GML.zip` into
an identifier, a year, and an area. Upstream filenames are irregular and the
irregularities are load-bearing. Run `make test` before and after; the cases in
`tests/test_ksj.py` were taken from real upstream filenames, not invented.

Known upstream irregularities, all verified against the live site:

- Download links live in `onclick="javascript:DownLd(...)"`, not in `href`.
- The size shown on the page is not reliable. The base of "MB" is 1024^2 on
  most pages and 10^6 on others, `A46` through `A48` use comma separators
  (`7,905KB`), one label reads `48.7.2MB`, and `P29-23_01_GML.zip` is
  advertised as 5.19MB while the file is 0.44MB. Use `data/head.jsonl`.
- `G09-2026` is linked from the index but returns 404.
- Sortable pages write their column headers as `地域 ▲ ▼`. Keying on the raw
  text loses 4,739 rows without any error.
- Four rows, in A46, A47, A48 and N12, hold two download links because a
  `</tr>` is missing.

## Rules that are not negotiable

- Never fabricate a geometry. Two sources are real and both are used: a JIS
  mesh code in the filename, which names the exact cell, and the extent of a
  prefecture as N03 行政区域 states it, for a file published per prefecture.
  Everything else gets `"geometry": null` and no `bbox`. A nationwide bbox on
  a file that is not nationwide makes spatial search wrong in a way nobody
  notices. Files published per river-bureau (北海道開発局 and the rest) or per
  metropolitan region have no administrative boundary to borrow and stay
  without a footprint.
- Never fabricate a size or a checksum either. If `data/head.jsonl` has no
  entry for a URL, the Item omits `file:size` rather than guessing from the
  page label.
- Licenses differ per dataset. Do not copy one Collection's license into
  another.

## Talking to nlftp

Four workers, a random 1 to 10 second pause per request. Do not raise it.
HEAD works and returns `Content-Length`, `Last-Modified` and `ETag`, so
checking for updates costs nothing; there is no reason to re-download.
