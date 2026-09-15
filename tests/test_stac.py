import pytest

from mlit_nlftp_stac.stac import build_collection, build_item, item_id

PAGE = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A51-2025.html"


def _row(url, filename, **kw):
    return {"url": url, "filename": filename, "size_label": "1MB", **kw}


def test_id_comes_from_the_url_not_the_printed_name():
    # Both links are printed as A51-25_40_GML.zip on the same page; only one
    # of them actually is.
    a = _row("https://nlftp.mlit.go.jp/ksj/gml/data/A51/A51-25/A51-25_40_GML.zip", "A51-25_40_GML.zip")
    b = _row("https://nlftp.mlit.go.jp/ksj/gml/data/A51/A51-24/A51-24_40_GML.zip", "A51-25_40_GML.zip")
    assert item_id(a) != item_id(b)
    assert item_id(b) == "A51-24_40_GML"


def test_year_follows_the_url_too():
    b = _row("https://nlftp.mlit.go.jp/ksj/gml/data/A51/A51-24/A51-24_40_GML.zip", "A51-25_40_GML.zip")
    assert build_item(b, PAGE, "A51")["properties"]["start_datetime"].startswith("2024")


def test_size_is_only_taken_from_a_head_result():
    row = _row("https://x/A51-25_40_GML.zip", "A51-25_40_GML.zip", size_label="5.19MB")
    assert "file:size" not in build_item(row, PAGE, "A51")["assets"]["source"]
    row["bytes"] = 459964
    assert build_item(row, PAGE, "A51")["assets"]["source"]["file:size"] == 459964


def test_an_item_without_a_derivable_footprint_has_no_bbox():
    it = build_item(_row("https://x/P29-23_01_GML.zip", "P29-23_01_GML.zip"), PAGE, "P29")
    assert it["geometry"] is None
    assert "bbox" not in it


def test_a_mesh_named_item_gets_a_real_footprint():
    it = build_item(_row("https://x/A31-22_10_5439_SHP.zip", "A31-22_10_5439_SHP.zip"), PAGE, "A31b")
    assert it["geometry"]["type"] == "Polygon"
    assert it["bbox"][0] == 139.0


REGIONS = {
    "東京": {"region": "東京", "code": "13", "bbox": [136.0695, 20.4227, 153.9867, 35.8984]},
    "全国": {"region": "全国", "code": None, "bbox": [122.9333, 20.4227, 153.9867, 45.5572]},
}


def test_a_prefecture_file_gets_the_prefectures_extent():
    row = _row("https://x/N03-20260101_13_GML.zip", "N03-20260101_13_GML.zip")
    row["cells"] = {"地域": "東京", "年度": "2026年（令和8年）"}
    it = build_item(row, PAGE, "N03", REGIONS)
    assert it["bbox"][2] == 153.9867  # 南鳥島 is in Tokyo
    assert "N03" in it["properties"]["ksj:extent_source"]


def test_a_region_with_no_known_extent_stays_without_one():
    row = _row("https://x/A31a-25_81_10_GML.zip", "A31a-25_81_10_GML.zip")
    row["cells"] = {"地域": "北海道開発局"}
    it = build_item(row, PAGE, "A31a", REGIONS)
    assert it["geometry"] is None
    assert "bbox" not in it
    assert "ksj:extent_source" not in it["properties"]


def test_a_mesh_code_beats_the_region():
    row = _row("https://x/A31-22_10_5439_SHP.zip", "A31-22_10_5439_SHP.zip")
    row["cells"] = {"地域": "全国"}
    it = build_item(row, PAGE, "A31b", REGIONS)
    assert it["bbox"][0] == 139.0
    assert it["properties"]["ksj:extent_source"].startswith("JIS mesh")


def test_a_collection_extent_is_the_union_not_a_list_of_every_item():
    rows = [
        {**_row("https://x/N03-20260101_13_GML.zip", "a.zip"), "cells": {"地域": "東京"}},
        {**_row("https://x/A31-22_10_5439_SHP.zip", "b.zip"), "cells": {}},
    ]
    items = [build_item(r, PAGE, "X", REGIONS) for r in rows]
    coll = build_collection("X", PAGE, items, None, REGIONS)
    assert len(coll["extent"]["spatial"]["bbox"]) == 1
    assert coll["extent"]["spatial"]["bbox"][0] == pytest.approx(
        [136.0695, 20.4227, 153.9867, 36.6667], abs=1e-4
    )


def test_a_collection_with_no_item_extent_falls_back_to_the_measured_japan_bbox():
    row = {**_row("https://x/P29-23_01_GML.zip", "c.zip"), "cells": {"地域": "北海道開発局"}}
    coll = build_collection("P29", PAGE, [build_item(row, PAGE, "P29", REGIONS)], None, REGIONS)
    assert coll["extent"]["spatial"]["bbox"][0] == REGIONS["全国"]["bbox"]


def test_an_item_carries_the_collections_licence_and_terms():
    # Someone can land on an Item page from a search engine, press Download,
    # and never see the Collection. The terms have to be on the Item too.
    row = _row("https://x/N02-25_GML.zip", "N02-25_GML.zip")
    it = build_item(row, PAGE, "N02", None, "other", "2020年以降：CC_BY_4.0\n上記以外：商用可")
    assert it["properties"]["license"] == "other"
    assert "CC_BY_4.0" in it["properties"]["ksj:terms"]


def test_the_licence_defaults_to_other_rather_than_to_nothing():
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "X")
    assert it["properties"]["license"] == "other"


def test_every_item_can_reach_the_terms_even_when_its_page_states_none():
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "X", None, "other", "")
    licence = [link for link in it["links"] if link["rel"] == "license"]
    assert licence and licence[0]["href"].startswith("https://nlftp.mlit.go.jp/")
