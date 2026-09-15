"""Which shelf each dataset sits on.

The JPGIS list page groups every dataset under a heading: 水域, 地形, 土地利用,
地価, 行政地域, 都市計画決定情報, 大都市圏・条件不利地域, 災害・防災, 施設,
地域資源・観光, 保護保全, 交通, パーソントリップ, 各種統計. Nothing on a
dataset's own page says which, and an agent looking for a theme has nothing to
match on when a Collection's keywords are just its own identifier.

The page also carries one numbered heading, 1.国土, and only one, so there is
no second level to read: every dataset would take the same value and the field
would say nothing.
"""

import html as _html
import re
from typing import Dict

LIST_URL = "https://nlftp.mlit.go.jp/ksj/gml/gml_datalist.html"

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_LINK = re.compile(r"KsjTmplt-([A-Za-z0-9_.\-]+)\.html")
_TAG = re.compile(r"<[^>]+>")
# 【水域】 / ＜水域＞
_HEADING = re.compile(r"^[＜<【\[](.+?)[＞>】\]]$")


def _text(fragment: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", fragment)
    s = _TAG.sub("", s)
    return re.sub(r"[\s　]+", " ", _html.unescape(s)).strip()


def parse_categories(page_html: str) -> Dict[str, str]:
    """{page id: category} for every dataset on the list page."""
    out: Dict[str, str] = {}
    heading = ""
    for row in _ROW.findall(page_html):
        texts = [_text(c) for c in _CELL.findall(row)]
        if not texts:
            continue

        link = _LINK.search(row)
        if link:
            if heading:
                out[link.group(1)] = heading
            continue

        for t in texts[:2]:
            m = _HEADING.match(t)
            if m:
                heading = m.group(1)
                break
    return out
