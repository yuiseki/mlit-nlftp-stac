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


def test_an_item_carries_the_terms_and_resolves_them_for_its_own_year():
    # Someone can land on an Item page from a search engine, press Download,
    # and never see the Collection, so the terms have to be on the Item. The
    # licence is resolved from the Item's year rather than copied whole: this
    # file is from 2025, which N02 licenses as CC BY 4.0.
    terms = "2020年（令和2年）以降：オープンデータ（CC_BY_4.0）\n上記以外：商用可"
    row = _row("https://x/N02-25_GML.zip", "N02-25_GML.zip")
    row["cells"] = {"地域": "全国", "年度": "2025年（令和7年）"}
    it = build_item(row, PAGE, "N02", None, "other", terms)
    assert it["properties"]["license"] == "CC-BY-4.0"
    assert it["properties"]["ksj:redistribution"] == "allowed"
    assert "CC_BY_4.0" in it["properties"]["ksj:terms"]

    # ... and an older file of the same dataset resolves to the other rule.
    old = _row("https://x/N02-13_GML.zip", "N02-13_GML.zip")
    old["cells"] = {"地域": "全国", "年度": "2013年（平成25年）"}
    older = build_item(old, PAGE, "N02", None, "other", terms)
    assert older["properties"]["license"] == "other"
    assert older["properties"]["ksj:redistribution"] == "allowed"  # 商用可
    assert older["properties"]["ksj:terms_applied"].startswith("上記以外")


def test_no_terms_is_check_rather_than_a_quiet_yes():
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "X")
    assert it["properties"]["license"] == "other"
    assert it["properties"]["ksj:redistribution"] == "check"


def test_every_item_can_reach_the_terms_even_when_its_page_states_none():
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "X", None, "other", "")
    licence = [link for link in it["links"] if link["rel"] == "license"]
    assert licence and licence[0]["href"].startswith("https://nlftp.mlit.go.jp/")


BASE = "https://stac.yuiseki.net/mlit-nlftp"


def test_without_a_base_url_everything_stays_relative():
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "X")
    assert not [link for link in it["links"] if link["rel"] == "self"]
    coll = build_collection("X", PAGE, [it])
    self_link = [link for link in coll["links"] if link["rel"] == "self"][0]
    assert self_link["href"] == "./collection.json"


def test_a_base_url_makes_the_self_links_absolute_and_leaves_the_rest_alone():
    # A catalog served under a path prefix has to keep working when copied to
    # a directory, so only `self` becomes absolute.
    it = build_item(_row("https://x/N02-25_GML.zip", "N02-25_GML.zip"), PAGE, "N02",
                    None, "other", "", BASE)
    self_link = [link for link in it["links"] if link["rel"] == "self"][0]
    assert self_link["href"] == f"{BASE}/collections/N02/items/N02-25_GML.json"
    assert [link for link in it["links"] if link["rel"] == "root"][0]["href"] == "../../../catalog.json"

    coll = build_collection("N02", PAGE, [it], None, None, BASE)
    assert [link for link in coll["links"] if link["rel"] == "self"][0]["href"] == (
        f"{BASE}/collections/N02/collection.json"
    )




def test_an_item_link_carries_the_items_title():
    # Without it, finding 高知 in a collection means knowing that the two
    # digits in P20-12_39_GML are a JIS prefecture code.
    row = _row("https://x/P20-12_39_GML.zip", "P20-12_39_GML.zip")
    row["cells"] = {"地域": "高知", "年度": "2012年（平成24年）"}
    it = build_item(row, PAGE, "P20", REGIONS)
    coll = build_collection("P20", PAGE, [it])
    link = [x for x in coll["links"] if x["rel"] == "item"][0]
    assert link["title"] == "2012_高知（平成24年）"


def test_an_item_title_says_which_dataset_it_is_from():
    # A region catalog lists items from many collections. STAC Browser swaps a
    # link's title for the item's own once it loads it, so a title of
    # "2006_東京（平成18年）" alone leaves fourteen identical rows.
    row = _row("https://x/A09-06_13_GML.zip", "A09-06_13_GML.zip")
    row["cells"] = {"地域": "東京", "年度": "2006年（平成18年）"}
    it = build_item(row, PAGE, "A09", REGIONS, "other", "", "", "都市地域データ (A09)")
    assert it["properties"]["title"] == "2006_東京（平成18年） — 都市地域データ (A09)"


def test_a_region_catalog_points_back_at_the_items():
    from mlit_nlftp_stac.stac import build_region_catalog

    entries = [
        {"collection": "P20", "id": "P20-12_39_GML",
         "title": "2012_高知（平成24年） — 避難施設データ (P20)"},
    ]
    cat = build_region_catalog("39", "高知", entries)
    assert cat["id"] == "region-39"
    assert cat["title"] == "高知 (39)"
    link = [x for x in cat["links"] if x["rel"] == "item"][0]
    assert link["href"] == "../collections/P20/items/P20-12_39_GML.json"
    assert "避難施設データ" in link["title"]


def test_the_region_index_is_only_a_child_of_the_root_when_it_exists():
    from mlit_nlftp_stac.stac import build_root

    without = build_root([], "")
    assert not [x for x in without["links"] if x["href"].endswith("regions/catalog.json")]
    with_ = build_root([], "", regions=True)
    assert [x for x in with_["links"] if x["href"].endswith("regions/catalog.json")]


def test_every_link_carries_a_title():
    # The spec asks for a title on item, child, parent and root links "even if
    # it repeats several times", so a client can render a readable tree
    # without opening each destination.
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "N02", None, "other", "", "",
                    "鉄道データ (N02)")
    for link in it["links"]:
        if link["rel"] in ("root", "parent", "collection"):
            assert link.get("title"), link
    assert [x for x in it["links"] if x["rel"] == "parent"][0]["title"] == "鉄道データ (N02)"


def test_an_item_says_whether_it_is_the_newest_for_its_own_region():
    # A40 is current to 2024 for some prefectures and stops at 2016 for 高知.
    # Asking "is this the file to use?" meant listing every item and comparing
    # titles by eye. Keyed on the region alone: 形式 is spelled differently
    # between vintages, and including it made each old spelling its own
    # bucket, so a 2010 file came back as current.
    latest = {"高知": 2016, "東京": 2024}
    old = _row("https://x/A40-16_39_GML.zip", "a.zip")
    old["cells"] = {"地域": "高知", "年度": "2016年（平成28年）"}
    assert build_item(old, PAGE, "A40", None, "other", "", "", "", "A40", latest)[
        "properties"]["ksj:is_latest"] is True

    tokyo_old = _row("https://x/A40-16_13_GML.zip", "b.zip")
    tokyo_old["cells"] = {"地域": "東京", "年度": "2016年（平成28年）"}
    assert build_item(tokyo_old, PAGE, "A40", None, "other", "", "", "", "A40", latest)[
        "properties"]["ksj:is_latest"] is False

    # A different spelling of 形式 in the same region must not create a second
    # "latest": that is how a 2010 file was marked current.
    other_format = _row("https://x/A40-16_13_SHP.zip", "c.zip")
    other_format["cells"] = {"地域": "東京", "形式": "シェープ、geojson形式",
                             "年度": "2016年（平成28年）"}
    assert build_item(other_format, PAGE, "A40", None, "other", "", "", "", "A40", latest)[
        "properties"]["ksj:is_latest"] is False


def test_a_mesh_item_gets_its_identifier_from_the_page():
    # 500m_mesh_2024_32_SHP starts with a digit, so the filename yields no
    # identifier and a script filtering on it saw the population data as empty.
    row = _row("https://x/500m_mesh_2024_32_SHP.zip", "c.zip")
    row["cells"] = {"地域": "島根", "年度": "2024年（令和6年）"}
    it = build_item(row, PAGE, "mesh500r6", None, "other", "", "", "", "mesh500r6")
    assert it["properties"]["ksj:identifier"] == "mesh500r6"


def test_terms_that_were_never_stated_are_absent_rather_than_empty():
    it = build_item(_row("https://x/a.zip", "a.zip"), PAGE, "P05", None, "other", "")
    assert "ksj:terms" not in it["properties"]
    assert it["properties"]["ksj:redistribution"] == "check"
