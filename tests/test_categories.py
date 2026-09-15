from pathlib import Path

from mlit_nlftp_stac.categories import parse_categories

FIXTURE = Path(__file__).parent / "fixtures" / "datalist.html"


def _cats():
    return parse_categories(FIXTURE.read_text(encoding="utf-8"))


def test_a_dataset_gets_the_heading_it_sits_under():
    cats = _cats()
    assert cats["C23"] == "水域"
    assert cats["N02-2024"] == "交通"


def test_every_dataset_row_is_picked_up_not_just_the_first():
    assert set(_cats()) == {"C23", "W09-2005", "N02-2024"}


def test_a_dataset_before_any_heading_is_not_given_one():
    html = '<table><tr><td><a href="KsjTmplt-X01.html">x</a></td></tr></table>'
    assert parse_categories(html) == {}


def test_a_page_with_no_categories_yields_nothing():
    assert parse_categories("<html><body><p>hi</p></body></html>") == {}
