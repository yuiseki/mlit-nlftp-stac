"""What the columns of a dataset are called, and what their values mean.

Two agents given this catalog and a research question both said the same
thing: they could find the right dataset and could not plan the work, because
nothing said which column held バス区分 or what the value 13 meant. Both had
to open the MLIT page.

The page has it. Each dataset states its columns in a 属性情報 table -- the
human name, the name the shapefile actually uses, a description, and either a
type or a link to a code list -- and each code list is a plain table of value,
label and definition. This reads both.
"""

import html as _html
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

BASE = "https://nlftp.mlit.go.jp/ksj/gml/datalist/"

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t([dh])[^>]*>(.*?)</t\1>", re.S | re.I)
_HREF = re.compile(r'href="([^"]+)"')
_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.I)

# 鉄道区分（N02_001） / 500m_mesh（MESH_ID） — the parenthesised part is the
# name the data actually uses, which is the one a query has to spell.
_COLUMN = re.compile(r"^(.*?)[（(]\s*([A-Za-z][A-Za-z0-9_]*)\s*[)）]\s*$", re.S)
_SHAPEFILE = re.compile(r"[（(]\s*([^（）()]+\.shp)\s*[)）]", re.I)
_CODELIST = re.compile(r"コードリスト[「『](.+?)[」』]")

_TYPES = (
    ("文字列", "string"),
    ("整数", "integer"),
    ("実数", "number"),
    ("日付", "date"),
    ("時間", "datetime"),
    ("真偽", "boolean"),
)


def _text(fragment: str) -> str:
    s = _BR.sub(" ", fragment)
    s = _TAG.sub("", s)
    s = _html.unescape(s)
    return re.sub(r"[\s　]+", " ", s).strip()


def _type_of(cell_text: str) -> str:
    if "コードリスト" in cell_text:
        return "codelist"
    for needle, name in _TYPES:
        if needle in cell_text:
            return name
    return "unknown"


def parse_attributes(page_html: str, page_url: str = BASE) -> List[Dict]:
    """[{shapefile, columns: [{name, column, description, type, ...}]}].

    A dataset can ship several shapefiles with different columns -- N02 has
    RailroadSection and Station -- so one flat list for the dataset would
    describe neither.
    """
    variants: List[Dict] = []
    current: Optional[Dict] = None

    for row in _ROW.findall(page_html):
        cells = _CELL.findall(row)
        texts = [_text(body) for _, body in cells]
        # A row whose variant cell is spanned from above starts with an empty
        # one: P20 does it for 地震災害（P20_007）, which was dropped entirely,
        # leaving a gap in the numbering and a column nobody could explain.
        while texts and not texts[0]:
            texts.pop(0)
        if not texts:
            continue

        if any("属性名" in t for t in texts):  # a header that opens a variant
            label = next((t for t in texts if "属性情報" in t), "")
            m = _SHAPEFILE.search(label)
            # Several datasets publish more than one attribute table and the
            # only thing telling them apart is the page's own wording, which
            # names a shapefile for some and a vintage for others. Keeping the
            # label is the difference between two variants a reader can tell
            # apart and two they cannot.
            current = {
                "shapefile": m.group(1) if m else None,
                "label": label or None,
                "columns": [],
            }
            variants.append(current)
            continue

        if current is None or len(texts) < 2:
            continue

        m = _COLUMN.match(texts[0])
        if not m:  # 地物情報 and 関連役割名 rows land here
            continue
        name, column = m.group(1).strip(), m.group(2)
        # Some rows omit the description and give only name and type: P20
        # does it for 津波災害（P20_008） and the four after it. Reading the
        # second cell as a description put 真偽値型 there and left the type
        # unknown, which is the two fields swapped.
        rest = texts[1:]
        if len(rest) == 1 and _type_of(rest[0]) != "unknown":
            description, type_cell = "", rest[0]
        else:
            description = rest[0] if rest else ""
            type_cell = rest[1] if len(rest) > 1 else ""
        col: Dict[str, object] = {
            "name": name,
            "column": column,
            "description": description,
        }
        col["type"] = _type_of(type_cell)
        cl = _CODELIST.search(type_cell)
        if cl:
            col["codelist"] = cl.group(1).strip()
            href = _HREF.search(row)
            if href:
                col["codelist_url"] = urljoin(page_url, href.group(1))
        current["columns"].append(col)

    return [v for v in variants if v["columns"]]


def parse_codelist(page_html: str) -> List[Dict]:
    """[{value, label, description?}] from a code list page."""
    out: List[Dict] = []
    for row in _ROW.findall(page_html):
        texts = [_text(body) for _, body in _CELL.findall(row)]
        # Some lists indent their table with an empty first column, which put
        # the code in texts[1] and made the whole page parse as nothing.
        while texts and not texts[0]:
            texts.pop(0)
        if len(texts) < 2 or texts[0] in ("コード", "code"):
            continue
        entry: Dict[str, str] = {"value": texts[0], "label": texts[1]}
        if len(texts) > 2 and texts[2]:
            entry["description"] = texts[2]
        out.append(entry)
    return out
