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
