"""The attribute table, taken from the live N02 page."""

from pathlib import Path

from mlit_nlftp_stac.attributes import parse_attributes, parse_codelist

FIXTURE = Path(__file__).parent / "fixtures" / "attributes-n02.html"


def _variants():
    return parse_attributes(FIXTURE.read_text(encoding="utf-8"))


def test_a_variant_per_shapefile():
    # N02 ships two shapefiles with different columns. One flat column list
    # for the dataset would describe neither.
    assert [v["shapefile"] for v in _variants()] == [
        "RailroadSection.shp",
        "Station.shp",
    ]


def test_a_variant_keeps_the_label_the_page_gave_it():
    # When there is no .shp in the label the page still says something, and
    # with two tables per dataset that wording is all a reader has.
    assert _variants()[0]["label"].startswith("属性情報")


def test_a_column_carries_its_human_name_and_its_shp_name():
    col = _variants()[0]["columns"][0]
    assert col["name"] == "鉄道区分"
    assert col["column"] == "N02_001"
    assert col["description"] == "鉄道路線の種類による区別"


def test_a_coded_column_says_which_code_list():
    col = _variants()[0]["columns"][0]
    assert col["type"] == "codelist"
    assert col["codelist"] == "鉄道区分コード"
    assert col["codelist_url"].endswith("/ksj/gml/codelist/RailwayClassCd.html")


def test_a_plain_column_has_no_code_list():
    col = [c for c in _variants()[0]["columns"] if c["column"] == "N02_003"][0]
    assert col["type"] == "string"
    assert "codelist_url" not in col


def test_the_feature_tables_between_them_are_not_columns():
    # 地物情報 and 関連役割名 tables sit in the same markup. Only rows whose
    # first cell names a column like （N02_001） are attributes.
    cols = [c["column"] for v in _variants() for c in v["columns"]]
    assert all(c.startswith("N02_") for c in cols)


CODELIST = """<html><body><table>
<tr><th>コード</th><th>対応する内容</th><th>定義</th></tr>
<tr><td>11</td><td>普通鉄道JR</td><td></td></tr>
<tr><td>13</td><td>鋼索鉄道</td><td>車両にロープを緊結して巻上げて運転するもの。</td></tr>
</table></body></html>"""


def test_a_code_list_is_a_value_a_label_and_sometimes_a_definition():
    values = parse_codelist(CODELIST)
    assert values[0] == {"value": "11", "label": "普通鉄道JR"}
    assert values[1]["value"] == "13"
    assert values[1]["description"].startswith("車両にロープ")


def test_a_page_that_is_not_a_code_list_yields_nothing():
    assert parse_codelist("<html><body><p>not a table</p></body></html>") == []


INDENTED = """<html><body><table>
<tr><th>保護林コード</th></tr>
<tr><td></td><td>コード</td><td>内容</td></tr>
<tr><td></td><td>2010</td><td>森林生態系保護地域保存地区</td></tr>
</table></body></html>"""


def test_a_list_indented_by_an_empty_column_still_parses():
    # hogorinCd and midorinokairoCd indent their table, which put the code in
    # the second cell and made the page look like it had no rows at all.
    assert parse_codelist(INDENTED) == [{"value": "2010", "label": "森林生態系保護地域保存地区"}]


TWO_CELL = """<html><body><table>
<tr><th rowspan="3">属性情報</th><th>属性名<br>（かっこ内はshp属性名）</th><th>説明</th><th>属性の型</th></tr>
<tr><td>収容人数（P20_005）</td><td>避難施設の収容可能人数</td><td>整数値型</td></tr>
<tr><td>津波災害（P20_008）</td><td>真偽値型</td></tr>
</table></body></html>"""


def test_a_row_with_no_description_does_not_put_the_type_in_it():
    # P20 omits the description for 津波災害（P20_008） and the four after it.
    cols = {c["column"]: c for c in parse_attributes(TWO_CELL)[0]["columns"]}
    assert cols["P20_005"]["description"] == "避難施設の収容可能人数"
    assert cols["P20_005"]["type"] == "integer"
    assert cols["P20_008"]["description"] == ""
    assert cols["P20_008"]["type"] == "boolean"


SPANNED = """<html><body><table>
<tr><th rowspan="3">属性情報</th><th>属性名<br>（かっこ内はshp属性名）</th><th>説明</th><th>属性の型</th></tr>
<tr><td>施設規模（P20_006）</td><td>避難施設の面積</td><td>文字列型</td></tr>
<tr><td></td><td>地震災害（P20_007）</td><td>真偽値型</td></tr>
</table></body></html>"""


def test_a_row_indented_by_a_spanned_cell_is_still_a_column():
    # P20_007 sat behind an empty first cell and vanished, which left a gap in
    # the numbering and a column in the data that the catalog could not name.
    cols = [c["column"] for c in parse_attributes(SPANNED)[0]["columns"]]
    assert cols == ["P20_006", "P20_007"]


COMMENTED = """<html><body><table>
<tr><th rowspan="2">属性情報</th><th>属性名<br>（かっこ内はshp属性名）</th><th>説明</th><th>属性の型</th></tr>
<tr><td>バス区分（P11_002）</td><td>運行形態による区分</td><td>コードリスト「バス区分コード」</td></tr>
</table>
<!--
<table>
<tr><th rowspan="2">属性情報</th><th>属性名<br>（かっこ内はshp属性名）</th><th>説明</th><th>属性の型</th></tr>
<tr><td>バス事業者名（P11_002）</td><td>事業者の名称</td><td>文字列型</td></tr>
</table>
-->
</body></html>"""


def test_a_superseded_table_left_in_a_comment_is_not_a_variant():
    # P11 keeps its pre-2022 schema commented out, in which P11_002 means
    # バス事業者名 rather than バス区分. Reading it produced two variants that
    # contradicted each other with nothing to say which was current.
    variants = parse_attributes(COMMENTED)
    assert len(variants) == 1
    assert variants[0]["columns"][0]["name"] == "バス区分"


RANGE = """<html><body><table>
<tr><th rowspan="3">属性情報</th><th>属性名<br>（かっこ内はshp属性名）</th><th>説明</th><th>属性の型</th></tr>
<tr><td>バス系統（P11_003_01～35）</td><td>系統番号</td><td>文字列型</td></tr>
<tr><td>バス区分コード（P11_004_01～35）</td><td>運行形態による区分</td><td>コードリスト「バス区分コード」</td></tr>
</table></body></html>"""


def test_a_column_that_repeats_35_times_is_still_a_column():
    # P11 writes バス区分コード（P11_004_01～35）, naming 35 columns in one row.
    # Skipping it as unparseable dropped the two columns the dataset exists
    # for: the route number and the service class.
    cols = {c["column"]: c for c in parse_attributes(RANGE)[0]["columns"]}
    assert set(cols) == {"P11_003_01～35", "P11_004_01～35"}
    assert cols["P11_004_01～35"]["type"] == "codelist"
