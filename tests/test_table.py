from pathlib import Path

from mlit_nlftp_stac.table import parse_download_rows, year_from_nendo

FIXTURE = Path(__file__).parent / "fixtures" / "download-table.html"


def _rows():
    return parse_download_rows(FIXTURE.read_text(encoding="utf-8"))


def test_every_download_link_is_found():
    assert [r["filename"] for r in _rows()] == [
        "A31a-25_81_10_GML.zip",
        "P29-13.zip",
        "A46-21_58_GML.zip",
        "A46-20_36_GML.zip",
    ]


def test_cells_are_keyed_by_the_tables_own_header():
    cells = _rows()[0]["cells"]
    assert cells["地域"] == "北海道開発局"
    assert cells["河川"] == "洪水予報河川･水位周知河川"
    assert cells["年度"] == "2025年（令和7年）"


def test_each_table_uses_its_own_header():
    # The second table has no 形式 or 河川 column; its cells must not inherit
    # the first table's header or everything shifts by two columns.
    cells = _rows()[1]["cells"]
    assert cells["地域"] == "全国"
    assert cells["年度"] == "平成25年"
    assert "河川" not in cells


def test_the_url_is_resolved_from_the_onclick_path():
    assert _rows()[0]["path"] == "../data/A31a/A31a-25/A31a-25_81_10_GML.zip"


def test_sort_arrows_in_a_header_do_not_become_part_of_the_column_name():
    from mlit_nlftp_stac.table import parse_download_rows as parse

    html = """
    <table><tr><th>地域 ▲ ▼</th><th>年度 ▲ ▼</th><th>ファイル名 ▲ ▼</th><th>ダウンロード</th></tr>
    <tr><td>東京</td><td>2026年（令和8年）</td><td>x.zip</td>
    <td><a onclick="javascript:DownLd('1MB','x.zip','../data/x.zip' ,this);"></a></td></tr></table>
    """
    cells = parse(html)[0]["cells"]
    assert cells["地域"] == "東京"
    assert cells["年度"] == "2026年（令和8年）"


def test_western_year_wins_when_both_are_printed():
    assert year_from_nendo("2025年（令和7年）") == 2025


def test_japanese_eras_are_converted():
    assert year_from_nendo("平成25年") == 2013
    assert year_from_nendo("令和6年") == 2024
    assert year_from_nendo("昭和60年") == 1985
    assert year_from_nendo("令和元年") == 2019
    assert year_from_nendo("平成元年") == 1989


def test_an_unreadable_year_is_none_rather_than_a_guess():
    assert year_from_nendo("") is None
    assert year_from_nendo("－") is None


def test_a_row_holding_two_links_keeps_both_and_labels_neither():
    # A46, A47, A48 and N12 each have one row with two download links in it,
    # upstream markup that lost a </tr>. Taking the first link per row drops
    # a file; giving both the row's cells labels one of them with the other's
    # region and year. Both are emitted, and neither gets the cells.
    rows = {r["filename"]: r for r in _rows()}
    assert rows["A46-21_58_GML.zip"]["cells"] == {}
    assert rows["A46-20_36_GML.zip"]["cells"] == {}
