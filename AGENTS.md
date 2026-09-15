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

## Rules that are not negotiable

- Never fabricate a geometry. An Item whose footprint cannot be derived gets
  `"geometry": null` and no `bbox`. A nationwide bbox on a file that is not
  nationwide makes spatial search wrong in a way nobody notices.
- Never fabricate a size or a checksum either. If `data/head.jsonl` has no
  entry for a URL, the Item omits `file:size` rather than guessing from the
  page label.
- Licenses differ per dataset. Do not copy one Collection's license into
  another.

## Talking to nlftp

Four workers, a random 1 to 10 second pause per request. Do not raise it.
HEAD works and returns `Content-Length`, `Last-Modified` and `ETag`, so
checking for updates costs nothing; there is no reason to re-download.
