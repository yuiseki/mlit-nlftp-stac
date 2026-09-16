"""The Markdown that sits beside each catalog.json.

Portolan requires a README.md and an AGENTS.md next to every catalog and
every collection, both linked from the STAC document rather than merely
served: `rel: describedby` and `rel: agents`. Six rounds of agent testing
said the same thing from the other side, so the requirement is not a
formality -- the prose was what the readers used, and an unlinked file was
never opened.

These are generated, not hand-written, for the same reason the root
AGENTS.md no longer states per-dataset facts: a hand-written count goes
stale silently and is then repeated to someone who acts on it.
"""

from __future__ import annotations

from typing import Iterable, Optional

AGREEMENT = "https://nlftp.mlit.go.jp/ksj/other/agreement.html"
PROVENANCE = (
    "Generated from the dataset pages under <https://nlftp.mlit.go.jp/ksj/>. "
    "This is a mirror of the metadata only; the files stay on MLIT's servers."
)
LICENCE_LINE = (
    f"Licence: varies by dataset and by year. Each Collection states its own, "
    f"and each Item resolves the licence of its own year. Upstream terms: <{AGREEMENT}>."
)


def _gb(total: int) -> str:
    return f"{total / 1e9:.1f} GB" if total >= 1e8 else f"{total / 1e6:.0f} MB"


def _readme(title: str, description: str, extra: str = "") -> str:
    body = f"# {title}\n\n{description}\n\n"
    if extra:
        body += extra.rstrip() + "\n\n"
    return body + f"{LICENCE_LINE}\n\nProvenance: {PROVENANCE}\n"


# --- the four axes ---------------------------------------------------------

def collections_docs(collections) -> tuple[str, str]:
    collections = list(collections)
    n = len(collections)
    readme = _readme(
        "データセット別 (by dataset)",
        f"国土数値情報の {n} データセット。識別子ごとに 1 Collection、"
        "ダウンロードできる zip ごとに 1 Item。",
        "Each `<id>/` directory holds `collection.json`, a `README.md` describing\n"
        "the dataset, and an `AGENTS.md` with what a reader needs before\n"
        "downloading: the columns, the licence per year, and what it is missing.",
    )
    agents = f"""# AGENTS.md — データセット別

{n} collections. Opening all of them is the wrong move and costs {n} requests.

| You want | Fetch |
|---|---|
| a named dataset | `./<id>/collection.json`, e.g. `./N02/collection.json` |
| the same with its caveats | `./<id>/AGENTS.md` |
| all {n} with their descriptions | `./index.json`, one request |
| everything matching a filter | `../items.parquet` |
| what exists for a prefecture | `../regions/<JIS code>.json` |

`index.json` carries, per dataset, the identifier, title, description,
category, latest year, every year present, item count, and the licence and
redistribution status **of the newest year**, which is the pair people arrive
wanting. The Collection's own `license` is `other` whenever any year in it is.

A Collection's `ksj:variants` lists the columns of each shapefile in the zip,
with the machine name a query has to spell (`N02_001`) beside the readable
one. `table:columns` is emitted only where the dataset ships a single
shapefile, because a dataset with two schemas cannot honestly have one.
"""
    return readme, agents


def regions_docs(regions) -> tuple[str, str]:
    regions = list(regions)
    links = sum(r.get("count", 0) for r in regions)
    readme = _readme(
        "地域別 (by region)",
        f"同じ Item を地域から引くための索引。{len(regions)} 地域、{links} 件のリンク。",
        "Files are named `<JIS prefecture code>.json` where the region is a\n"
        "prefecture (`39.json` = 高知), and by name where upstream publishes per\n"
        "river bureau or metropolitan region instead.",
    )
    agents = f"""# AGENTS.md — 地域別

{len(regions)} catalogs over the same Items, {links} links in total. This axis
exists because answering "what is there for 高知?" from Collections alone
meant opening all 110 of them.

- `./39.json` is 高知; the file name is the JIS prefecture code.
- Every `rel: item` link carries the dataset's name in its title, so the list
  is readable without opening anything.
- A file that covers several prefectures appears under each of them.
- Nationwide files (全国) are not repeated into every prefecture. Check the
  dataset itself when a theme seems absent here.

`ksj:is_latest` on an Item is computed **per region**, not per dataset: a
dataset whose newest national edition is 2024 can still have 2016 as the
newest thing that exists for one prefecture. Do not read the dataset's
`ksj:latest_year` as the year available here.

For counting rather than browsing, `../items.parquet` has a `region` column.
"""
    return readme, agents


def licenses_docs(statuses) -> tuple[str, str]:
    counts = {s["status"]: s for s in statuses}
    def n(k: str) -> int:
        return counts.get(k, {}).get("items", 0)
    readme = _readme(
        "ライセンス別 (by licence)",
        "再配布してよいかどうかで Item を分けた索引。"
        f"再配布できるもの {n('allowed')} 件、できないもの {n('not-allowed')} 件、"
        f"人が読んで判断するもの {n('check')} 件。",
        "A licence belongs to a year, not to a dataset, so this axis indexes\n"
        "Items and not Collections.",
    )
    agents = f"""# AGENTS.md — ライセンス別

Redistribution is an Item-level question here, which is why this axis exists.
国土数値情報's terms change between vintages of the same dataset: 鉄道データ is
CC BY 4.0 from 2020 and 商用可 before it.

| Status | Items | Means |
|---|---|---|
| `allowed` | {n('allowed')} | 複製物の再配布を含む, or an explicit CC licence |
| `not-allowed` | {n('not-allowed')} | 非商用, or 再配布を除く |
| `check` | {n('check')} | 一部制限 and the like: a human has to read it |

`check` is never resolved automatically. A40 lists which prefectures may
redistribute and which must telephone first; A27 says the terms differ per
municipality and stops there. Guessing either way would be worse than saying
so.

Each Item carries `ksj:terms_applied`, the sentence that decided its status,
and its Collection keeps `ksj:terms` verbatim. Quote the first when you have
to show your reasoning; read the second when the first is not enough.

Counting is faster in `../items.parquet`, which has a `redistribution` column.
"""
    return readme, agents


def license_status_docs(status: str, label: str, groups) -> tuple[str, str]:
    groups = list(groups)
    items = sum(g.get("count", 0) for g in groups)
    meaning = {
        "allowed": (
            "再配布してよいと上流が明記しているファイル。CC BY 4.0 か、"
            "利用約款で「複製物の再配布を含む」とされているものです。"
        ),
        "not-allowed": (
            "再配布できないファイル。非商用限定か、「複製物の再配布を除く」"
            "と書かれているものです。加工物の公開もできません。"
        ),
        "check": (
            "自動では判断できないファイル。「一部制限」など、都道府県や市区町村ごとに"
            "条件が違うと書かれているものです。人が原文を読む必要があります。"
        ),
    }[status]
    advice = {
        "allowed": (
            "Attribution is still required. Quote the Item's "
            "`ksj:terms_applied` when you publish something derived from it."
        ),
        "not-allowed": (
            "Read these, compute on them, cite them. Do not republish the file "
            "or a copy of its contents."
        ),
        "check": (
            "Treat as not-allowed until someone has read the Collection's "
            "`ksj:terms` for the prefecture or municipality in question. The "
            "catalog will not decide this for you."
        ),
    }[status]
    readme = _readme(
        f"{label}",
        f"{meaning} {items} 件、{len(groups)} データセット。",
    )
    agents = f"""# AGENTS.md — {label}

{items} Items across {len(groups)} datasets, one catalog per dataset.

{advice}

The status was resolved from the Item's own year against the dataset's terms
statement. `ksj:terms_applied` on each Item is the sentence that decided it;
`ksj:terms` on the Collection is the whole statement, unedited. Upstream
terms: <{AGREEMENT}>.
"""
    return readme, agents


def categories_docs(categories) -> tuple[str, str]:
    categories = list(categories)
    rows = "\n".join(
        f"| {c['name']} | {c['count']} |" for c in categories
    )
    readme = _readme(
        "分類別 (by category)",
        f"国土数値情報のデータセットを、JPGIS 一覧ページ自身の分類で並べた索引。"
        f"{len(categories)} 分類。",
        "The categories are upstream's own headings, not a taxonomy invented here.",
    )
    agents = f"""# AGENTS.md — 分類別

The axis for "what is there about X" when the dataset's identifier is not
known. The {len(categories)} headings are upstream's own, taken from the JPGIS
list page, not a taxonomy invented here.

| 分類 | データセット |
|---|---|
{rows}

Two of the 135 dataset pages carry no category upstream and are absent from
this axis; they are still reachable from `../collections/catalog.json`.

A category is a shelf, not an answer. 避難施設 sits under 施設 and 津波浸水想定
under 災害・防災, so a question about evacuation in a flood needs both. The
Collections carry `rel: related` links for the pairs that are actually used
together, each with a `ksj:reason`.
"""
    return readme, agents


# --- one dataset -----------------------------------------------------------

def collection_readme(coll: dict, item_count: int, page_url: str) -> str:
    terms = coll.get("ksj:terms") or "not stated on the page"
    return (
        f"# {coll['title']}\n\n{coll['description']}\n\n"
        f"- Identifier: `{coll['ksj:identifier']}`\n"
        f"- Files: {item_count}\n"
        f"- Years: {', '.join(str(y) for y in coll.get('ksj:years') or []) or 'unknown'}\n"
        f"- Category: {coll.get('ksj:category') or 'none upstream'}\n"
        f"- Source: {page_url}\n"
        f"- SPDX: `{coll['license']}`\n"
        f"- Terms of use (as stated upstream): {terms}\n\n"
        f"Provenance: {PROVENANCE}\n"
    )


def collection_agents(
    coll: dict,
    items: Iterable[dict],
    base_url: str = "",
    redistribution: Optional[dict] = None,
) -> str:
    items = list(items)
    cid = coll["ksj:identifier"]
    counts: dict[str, int] = {}
    formats: dict[str, int] = {}
    total = 0
    for it in items:
        p = it.get("properties", {})
        counts[p.get("ksj:redistribution") or "unknown"] = (
            counts.get(p.get("ksj:redistribution") or "unknown", 0) + 1
        )
        if p.get("ksj:file_format"):
            formats[p["ksj:file_format"]] = formats.get(p["ksj:file_format"], 0) + 1
        size = (it.get("assets", {}).get("source") or {}).get("file:size")
        if size:
            total += size

    years = coll.get("ksj:years") or []
    parts = [f"# AGENTS.md — {coll['title']}\n"]
    parts.append(
        f"{len(items)} files, {_gb(total) if total else 'size unmeasured'}"
        + (f", {years[0]}" if len(years) == 1
           else f", {years[0]}–{years[-1]}" if years else "")
        + ".\n"
    )

    parts.append("\n## Before you download\n")
    rows = [f"| Files | {len(items)} |", f"| Measured total | {_gb(total) if total else 'unknown'} |"]
    if years:
        rows.append(f"| Years present | {', '.join(str(y) for y in years)} |")
    if coll.get("ksj:latest_year"):
        rows.append(f"| Newest edition | {coll['ksj:latest_year']} |")
    if coll.get("ksj:coordinate_system"):
        rows.append(f"| Coordinate system | {coll['ksj:coordinate_system']} |")
    if coll.get("ksj:geometry_type"):
        rows.append(f"| Geometry | {coll['ksj:geometry_type']} |")
    if formats:
        rows.append("| Formats | " + ", ".join(
            f"{k} ({v})" for k, v in sorted(formats.items(), key=lambda x: -x[1])) + " |")
    parts.append("| | |\n|---|---|\n" + "\n".join(rows) + "\n")

    order = [("allowed", "再配布できる"), ("not-allowed", "再配布できない"), ("check", "要確認")]
    split = ", ".join(f"{label} {counts[k]}" for k, label in order if counts.get(k))
    parts.append("\n## Licence\n")
    parts.append(
        f"Per file, resolved from the file's own year: {split or 'unknown'}.\n"
        f"The Collection's own `license` is `{coll['license']}`; it falls back to "
        "`other` whenever any single year in the dataset does. Read the Item's "
        "`license` and its `ksj:terms_applied`, the sentence that decided it.\n"
    )
    if counts.get("check"):
        parts.append(
            f"{counts['check']} of these need a human: upstream states the terms "
            "per prefecture or per municipality. Treat them as not redistributable "
            "until someone has read `ksj:terms` on the Collection.\n"
        )

    variants = coll.get("ksj:variants") or []
    if variants:
        parts.append("\n## Columns\n")
        for v in variants:
            cols = v.get("columns") or []
            head = v.get("shapefile") or v.get("label") or "属性情報"
            named = ", ".join(
                f"`{c['column']}` {c['name']}" for c in cols[:6] if c.get("column")
            )
            parts.append(
                f"- **{head}** — {len(cols)} columns"
                + (f": {named}" + (" …" if len(cols) > 6 else "") if named else "")
                + "\n"
            )
        coded = [
            c for v in variants for c in (v.get("columns") or [])
            if c.get("ksj:codelist_href")
        ]
        if coded:
            one = len(coded) == 1
            parts.append(
                f"\n{len(coded)} column{'' if one else 's'} "
                f"{'is' if one else 'are'} coded, carrying a `ksj:codelist_href` "
                "into `../../codelists/`, where every value has a label.\n"
            )
        parts.append(
            "\nColumn names are what a query has to spell; the readable name is "
            "beside it. These come from the dataset page, which keeps superseded "
            "schemas as HTML comments -- those are stripped, so what is listed "
            "here is the current edition's.\n"
        )
    else:
        parts.append("\n## Columns\n")
        parts.append(
            "The dataset page states no 属性情報 table, so the columns are not "
            "described here. Open the zip to see them.\n"
        )

    related = [
        l for l in coll.get("links", []) if l.get("rel") == "related" and l.get("ksj:reason")
    ]
    if related:
        parts.append("\n## Often used with\n")
        for l in related:
            warn = " (測地系が違います)" if l.get("ksj:crs_mismatch") else ""
            parts.append(f"- `{l['href']}` — {l['ksj:reason']}{warn}\n")
        parts.append(
            "\nThese pairs are an editorial judgement, not upstream metadata: "
            "they carry `ksj:editorial: true`. The list is not exhaustive, and a "
            "combination missing from it is not a combination that was rejected.\n"
        )

    url = f"{base_url}/items.parquet" if base_url else "../../items.parquet"
    parts.append("\n## Count it, do not trust this file\n")
    parts.append(
        "Every number above is generated from the catalog, but a fact stated in "
        "prose goes stale silently. The Items are the record:\n\n"
        "```sql\n"
        "select year, region, redistribution, file_size\n"
        f"  from '{url}'\n"
        f" where collection = '{cid}'\n"
        " order by year desc;\n"
        "```\n\n"
        "`ksj:is_latest` on an Item is computed per region, so the newest year "
        "for the country is not the newest year everywhere.\n"
    )
    return "\n".join(part.rstrip("\n") for part in parts) + "\n"


# --- one leaf --------------------------------------------------------------

def region_docs(code: Optional[str], name: str, entries) -> tuple[str, str]:
    entries = list(entries)
    by_coll: dict[str, int] = {}
    for e in entries:
        by_coll[e.get("collection", "")] = by_coll.get(e.get("collection", ""), 0) + 1
    top = sorted(by_coll.items(), key=lambda kv: -kv[1])[:5]
    readme = _readme(
        f"{name} ({code})" if code else name,
        f"国土数値情報のうち {name} を対象とするファイル {len(entries)} 件、"
        f"{len(by_coll)} データセット。",
    )
    agents = f"""# AGENTS.md — {name}

{len(entries)} Items from {len(by_coll)} datasets, indexed by the region they
cover rather than by the dataset they belong to.

Largest here: """ + ", ".join(f"`{c}` ({n})" for c, n in top) + f""".

Each `rel: item` link carries the dataset's name in its title, so this list
can be read without opening anything.

- A file covering several prefectures appears under each of them.
- Nationwide files are not repeated into this catalog. A theme that looks
  absent here may exist as a 全国 file.
- `ksj:is_latest` on an Item is computed per region, so the newest year here
  can be older than the dataset's own `ksj:latest_year`.

To count rather than browse, `../../items.parquet` has a `region` column:

```sql
select collection_title, count(*)
  from 'items.parquet' where region = '{name}' group by 1 order by 2 desc;
```
"""
    return readme, agents


def license_collection_docs(
    status: str, label: str, collection_title: str, entries
) -> tuple[str, str]:
    entries = list(entries)
    readme = _readme(
        f"{collection_title} — {label}",
        f"{collection_title} のうち、再配布の可否が「{status}」と判定された "
        f"{len(entries)} 件。判定は各 Item の年次から解決しています。",
    )
    agents = f"""# AGENTS.md — {collection_title} / {label}

{len(entries)} Items of this dataset resolved to `{status}`. The rest of the
dataset may have resolved differently: the licence belongs to the year, not to
the dataset, so one dataset can appear under two or three statuses.

Read `ksj:terms_applied` on an Item for the sentence that decided it, and
`ksj:terms` on `../../../collections/` for the full statement. The dataset as a
whole is described in `../../../collections/`'s own README and AGENTS.

Upstream terms: <{AGREEMENT}>.
"""
    return readme, agents


def category_docs(name: str, members) -> tuple[str, str]:
    members = list(members)
    rows = "\n".join(
        f"| `{m['id']}` | {m['title']} | {m['count']} |" for m in members
    )
    readme = _readme(
        name,
        f"国土数値情報のうち「{name}」に分類される {len(members)} データセット。"
        "分類は JPGIS 一覧ページ自身の見出しです。",
    )
    agents = f"""# AGENTS.md — {name}

{len(members)} datasets on this shelf.

| id | dataset | files |
|---|---|---|
{rows}

A category is a shelf, not an answer: a question that crosses two shelves needs
both. Each Collection carries `rel: related` links for the pairs actually used
together, with a `ksj:reason` on each.

Open `../../collections/<id>/AGENTS.md` before downloading; it states that
dataset's columns, the licence per file and the measured size.
"""
    return readme, agents


def year_docs(collection_title: str, year: int, count: int, regions=None) -> tuple[str, str]:
    regions = list(regions or [])
    readme = _readme(
        f"{year} — {collection_title}",
        f"{collection_title} のうち {year} 年のファイル {count} 件。"
        + (f"{len(regions)} 地域に分かれています。" if regions else ""),
    )
    where = (
        "Children are regions; open the one you need."
        if regions
        else "Items are listed directly, titled with their region."
    )
    agents = f"""# AGENTS.md — {collection_title} / {year}

{count} files from one vintage. {where}

A year is a browsing convenience, not a claim that the whole country was
surveyed that year: a dataset can have 2024 for one prefecture and 2016 for
the next, which is why `ksj:is_latest` on an Item is per region.

The licence is resolved per year, so every Item here shares one: read
`ksj:terms_applied` on any of them. Counting across years is a query, not a
walk: `../../../../items.parquet` has `collection`, `year` and `region`.
"""
    return readme, agents


def year_region_docs(collection_title: str, year: int, region: str, count: int) -> tuple[str, str]:
    readme = _readme(
        f"{region} — {year} — {collection_title}",
        f"{collection_title} {year} 年のうち {region} のファイル {count} 件。",
    )
    agents = f"""# AGENTS.md — {collection_title} / {year} / {region}

{count} files. The region here is the label upstream prints in the download
table: a prefecture for most datasets, a river basin or a bureau for some, so
it is not always a JIS prefecture code.

Every Item carries the same year and therefore the same licence. For the same
region across datasets, use `../../../../../regions/`.
"""
    return readme, agents
