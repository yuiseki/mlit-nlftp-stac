from mlit_nlftp_stac.mesh import primary_mesh_bbox


def test_mesh_5439_is_the_tokyo_cell():
    w, s, e, n = primary_mesh_bbox("5439")
    assert (w, s) == (139.0, 36.0)
    assert e == 140.0
    assert round(n, 4) == 36.6667


def test_mesh_6841_is_in_northern_hokkaido():
    w, s, _, _ = primary_mesh_bbox("6841")
    assert w == 141.0
    assert round(s, 4) == 45.3333


def test_mesh_3036_covers_okinotorishima():
    w, s, e, n = primary_mesh_bbox("3036")
    assert w <= 136.08 <= e
    assert s <= 20.42 <= n


def test_a_code_that_is_not_four_digits_is_rejected():
    for bad in ("543", "54390", "abcd", ""):
        assert primary_mesh_bbox(bad) is None
