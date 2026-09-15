from pathlib import Path

from mlit_nlftp_stac.page import parse_page, spdx_from_terms

FIXTURE = Path(__file__).parent / "fixtures" / "ksjtmplt-n02-2024.html"


def _page():
    return parse_page(FIXTURE.read_text(encoding="utf-8"))


def test_title_drops_the_site_name():
    assert _page()["title"] == "鉄道データ"


def test_description_comes_from_the_naiyou_row():
    assert _page()["description"].startswith("全国の旅客鉄道・軌道の路線や駅について")


def test_identifier_is_read_from_the_page_not_guessed_from_a_filename():
    assert _page()["identifier"] == "N02"


def test_line_breaks_in_a_cell_survive():
    assert "\n" in _page()["fields"]["原典資料"]


def test_terms_are_kept_verbatim():
    assert "CC_BY_4.0" in _page()["terms"]


def test_mixed_terms_are_not_flattened_into_one_spdx_id():
    # N02 is CC BY 4.0 from 2020 onward and merely commercial-use-allowed
    # before that. Calling the whole collection CC-BY-4.0 would tell a user
    # they may do things with the older files that the terms do not allow.
    assert spdx_from_terms(_page()["terms"]) == "other"


def test_terms_that_say_only_cc_by_get_the_spdx_id():
    assert spdx_from_terms("オープンデータ（CC_BY_4.0）") == "CC-BY-4.0"
    assert spdx_from_terms("CC BY 4.0") == "CC-BY-4.0"


def test_unreadable_or_missing_terms_are_other():
    assert spdx_from_terms("") == "other"
    assert spdx_from_terms("非商用") == "other"


OLD = Path(__file__).parent / "fixtures" / "ksjtmplt-a09-old-layout.html"


def test_older_pages_use_a_bold_td_instead_of_a_th():
    # A09, A53-2025 and A55-2024 still use the pre-<th> layout. Reading only
    # <th> silently gives those three collections no description at all.
    page = parse_page(OLD.read_text(encoding="utf-8"))
    assert page["identifier"] == "A09"
    assert page["description"].startswith("土地利用基本計画に基づき指定された都市地域")
    assert page["terms"] == "商用可"
