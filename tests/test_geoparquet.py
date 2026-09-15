from mlit_nlftp_stac.geoparquet import COLUMNS, item_row

ITEM = {
    "id": "N02-25_GML",
    "collection": "N02",
    "geometry": None,
    "properties": {
        "title": "2025_全国（令和7年） — 鉄道データ (N02)",
        "start_datetime": "2025-01-01T00:00:00Z",
        "end_datetime": "2025-12-31T23:59:59Z",
        "license": "CC-BY-4.0",
        "ksj:redistribution": "allowed",
        "ksj:terms_applied": "2020年（令和2年）以降：オープンデータ（CC_BY_4.0）",
        "ksj:region": "全国",
        "ksj:declared_size": "14.2MB",
    },
    "assets": {"source": {"href": "https://nlftp.mlit.go.jp/x.zip", "file:size": 14903774}},
}


def test_a_row_has_every_declared_column():
    assert set(item_row(ITEM)) == set(COLUMNS)


def test_the_year_is_a_number_so_it_can_be_filtered_on():
    # Without it a reader has to parse a timestamp to ask for 2025.
    assert item_row(ITEM)["year"] == 2025


def test_the_fields_a_query_would_filter_on_survive():
    row = item_row(ITEM, "鉄道データ (N02)")
    assert row["redistribution"] == "allowed"
    assert row["license"] == "CC-BY-4.0"
    assert row["region"] == "全国"
    assert row["file_size"] == 14903774
    assert row["collection_title"] == "鉄道データ (N02)"


def test_an_item_with_nothing_measured_still_makes_a_row():
    bare = {"id": "x", "collection": "Y", "properties": {}, "assets": {}}
    row = item_row(bare)
    assert row["id"] == "x"
    assert row["year"] is None
    assert row["file_size"] is None


def test_the_row_points_back_at_its_item():
    assert item_row(ITEM)["item_href"].endswith("collections/N02/items/N02-25_GML.json")
    assert item_row(ITEM, "", "https://x/y")["item_href"].startswith("https://x/y/collections/")
