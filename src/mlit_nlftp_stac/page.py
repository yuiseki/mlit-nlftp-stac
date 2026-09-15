"""Reading a dataset page's own description of itself.

Each `KsjTmplt-*.html` page carries a `<th>key</th><td>value</td>` table that
states, among other things, what the dataset contains, which identifier it
uses, and what the terms of use are. Taking those from the page keeps the
catalog self-contained: no third-party API sits between the source and the
metadata that describes it.
"""

import html as _html
import re
from typing import Dict, Optional

from .attributes import parse_attributes

_ROW = re.compile(r"<tr>\s*<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.S)
# Pages written before the <th> layout put the key in a bold <td> instead.
_ROW_OLD = re.compile(
    r"<tr>\s*<td[^>]*>\s*<b>(.*?)</b>\s*</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.S
)
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BR = re.compile(r"<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")

# The one row that is not prose: a diagram-laden schema table that runs to
# thousands of characters. Its 属性情報 tables are read by `parse_attributes`
# instead of being kept as text.
_SKIP = "データ構造"

ATTRS_BASE = "https://nlftp.mlit.go.jp/ksj/gml/datalist/"


def _text(fragment: str) -> str:
    s = _COMMENT.sub("", fragment)
    s = _BR.sub("\n", s)
    s = _TAG.sub("", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t　]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return "\n".join(line.strip() for line in s.splitlines()).strip()


def parse_page(page_html: str, page_url: str = "") -> Dict:
    fields = {}
    for raw_key, raw_val in _ROW.findall(page_html) + _ROW_OLD.findall(page_html):
        key = _text(raw_key)
        if not key or key.startswith(_SKIP):
            continue
        fields[key] = _text(raw_val)

    title = ""
    m = _TITLE.search(page_html)
    if m:
        title = _text(m.group(1))
        # "国土数値情報 | 鉄道データ" -> "鉄道データ"
        if "|" in title:
            title = title.split("|", 1)[1].strip()

    return {
        "title": title,
        "description": fields.get("内容", ""),
        "identifier": fields.get("識別子", ""),
        "terms": fields.get("このデータの使用許諾条件", ""),
        "fields": fields,
        # The 属性情報 tables live inside the データ構造 cell that `fields`
        # deliberately skips, so they are read from the whole page instead.
        "variants": parse_attributes(page_html, page_url or ATTRS_BASE),
    }


_CC_BY_4 = re.compile(r"CC[_ ]?BY[_ ]?4\.0", re.I)
# Any of these means the terms are not one blanket licence.
# 「一部制限」 is the upstream's own word for "CC BY 4.0, except where it is
# not": A40 lists which prefectures may redistribute and which must ask first,
# and A27 says the terms differ per municipality and cannot be resolved at all.
# A Collection holding all of them is not CC BY 4.0.
_QUALIFIERS = ("一部制限", "上記以外", "以前", "非商用", "商用不可", "申請", "承諾", "問い合わせ")


def spdx_from_terms(terms: str) -> str:
    """An SPDX id only when the whole statement is unambiguously that licence.

    KSJ terms are often split by year: CC BY 4.0 for recent files and merely
    "commercial use allowed" for older ones. A Collection holds every year, so
    labelling it CC-BY-4.0 would tell a user they may do things with the older
    files that the terms do not allow.
    """
    if not terms or not _CC_BY_4.search(terms):
        return "other"
    if any(q in terms for q in _QUALIFIERS):
        return "other"
    return "CC-BY-4.0"
