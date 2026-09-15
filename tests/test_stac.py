from mlit_nlftp_stac.stac import build_item, item_id

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
