"""Reading the download table, not just the download link.

Every download link sits in a table row whose other cells say what the file
is: which region, which river category, which format, and which year. The
table's own header row names those columns. Taking the row gives an Item a
title a person can read, and gives the year from the page rather than from a
guess at the filename.
"""

import html as _html
import re
from typing import Dict, List, Optional

_TABLE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S | re.I)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_DOWNLD = re.compile(r"javascript:DownLd(?:_new)?\('([^']*)','([^']*)','([^']*)'")
_TAG = re.compile(r"<[^>]+>")

# Cells that describe the download mechanism rather than the data.
_NOT_TITLE = {"測地系", "ファイル容量", "ファイル名", "ダウンロード", "一括DL", "容量"}

# The vintage column is called 年度 on most pages and 年 on others (N03 among
# them). Looking only for 年度 leaves those pages taking the year from the
# filename and printing it twice in the title.
_NENDO_KEYS = ("年度", "年")


def nendo_of(cells: Dict[str, str]) -> str:
    for key in _NENDO_KEYS:
        if cells.get(key):
            return cells[key]
    return ""

_ERAS = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911, "明治": 1867}

# Sortable tables put arrows in the header cell, so the same column is called
# "地域" on one page and "地域 ▲ ▼" on another. Keying on the raw text loses
# every row on the sortable pages, quietly: 4,739 of them.
_SORT_ARROWS = re.compile(r"[\s\u3000]*[▲▼△▽↑↓]+[\s\u3000]*")


def _header_label(text: str) -> str:
    return _SORT_ARROWS.sub("", text).strip()


def _text(fragment: str) -> str:
    s = _TAG.sub(" ", fragment)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_download_rows(page_html: str) -> List[Dict]:
    """One entry per download link, with its row's cells keyed by the header.

    Each table is read with its own header. Pages mix table shapes: A31a has
    形式 and 河川 columns that N02 does not, and reusing one header across
    tables shifts every value by however many columns differ.
    """
    out: List[Dict] = []
    for table in _TABLE.findall(page_html):
        header: List[str] = []
        for row in _ROW.findall(table):
            ths = _TH.findall(row)
            if ths:
                header = [_header_label(_text(t)) for t in ths]
                continue
            links = _DOWNLD.findall(row)
            if not links:
                continue
            values = [_text(t) for t in _TD.findall(row)]
            cells = {
                key: val
                for key, val in zip(header, values)
                if key and val and key not in ("ダウンロード", "一括DL")
            }
            # A handful of upstream rows hold two download links because a
            # </tr> is missing. The cells then describe only one of the two and
            # there is no way to tell which, so neither gets them. Dropping the
            # extra link instead would lose a file.
            if len(links) > 1:
                cells = {}
            for size, filename, path in links:
                out.append(
                    {
                        "filename": filename,
                        "path": path.strip(),
                        "size_label": size,
                        "cells": dict(cells),
                    }
                )
    return out


def year_from_nendo(nendo: str) -> Optional[int]:
    """`2025年（令和7年）` -> 2025, `平成25年` -> 2013, `令和元年` -> 2019."""
    if not nendo:
        return None
    m = re.search(r"((?:19|20)\d{2})\s*年", nendo)
    if m:
        return int(m.group(1))
    for era, base in _ERAS.items():
        m = re.search(rf"{era}\s*(元|\d+)\s*年", nendo)
        if m:
            n = 1 if m.group(1) == "元" else int(m.group(1))
            return base + n
    return None


def wareki_from_nendo(nendo: str) -> str:
    """`2025年（令和7年）` -> `令和7年`, `平成25年` -> `平成25年`, else ``."""
    if not nendo:
        return ""
    for era in _ERAS:
        m = re.search(rf"{era}\s*(?:元|\d+)\s*年", nendo)
        if m:
            return m.group(0).replace(" ", "")
    return ""


def title_from_cells(cells: Dict[str, str]) -> str:
    """`2026_東京（令和8年）`.

    The year leads because STAC Browser sorts on the title, and a list of
    files that sorts by year is the one a person wants. The era is kept
    because that is how the page names the vintage, and someone looking for
    「令和6年度版」 should be able to find it by eye.
    """
    year = year_from_nendo(nendo_of(cells))
    parts = [v for k, v in cells.items() if k not in _NOT_TITLE and k not in _NENDO_KEYS]
    seen, rest = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            rest.append(p)
    body = " ".join(rest)
    if year is None:
        return body
    wareki = wareki_from_nendo(nendo_of(cells))
    head = f"{year}_{body}" if body else str(year)
    return f"{head}（{wareki}）" if wareki else head
