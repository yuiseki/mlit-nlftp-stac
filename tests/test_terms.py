"""Every terms string here was copied from a live dataset page."""

from mlit_nlftp_stac.terms import resolve

CC = "オープンデータ（CC_BY_4.0）"
NC = "非商用"
OK = "商用可"


def test_one_licence_for_every_year():
    assert resolve(CC, 2024) == ("CC-BY-4.0", "allowed", CC)
    assert resolve(OK, 1970) == ("other", "allowed", OK)
    assert resolve(NC, 2024) == ("other", "not-allowed", NC)


def test_from_a_year_onwards():
    # N02: 2020年（令和2年）以降：オープンデータ（CC_BY_4.0） / 上記以外：商用可
    terms = "2020年（令和2年）以降：オープンデータ（CC_BY_4.0）\n上記以外：商用可"
    assert resolve(terms, 2025)[0] == "CC-BY-4.0"
    assert resolve(terms, 2020)[0] == "CC-BY-4.0"
    assert resolve(terms, 2019)[:2] == ("other", "allowed")


def test_a_list_of_specific_years():
    # P29: 2023年度、2021年度 are CC BY; 2013年度 is not.
    terms = ("2023年度（令和5年度）、2021年度（令和3年度）：オープンデータ（CC_BY_4.0）\n"
             "2013年度（平成25年度）：非商用")
    assert resolve(terms, 2023)[0] == "CC-BY-4.0"
    assert resolve(terms, 2021)[0] == "CC-BY-4.0"
    assert resolve(terms, 2013)[:2] == ("other", "not-allowed")


def test_the_did_split_that_makes_old_years_unpublishable():
    terms = "1995年（平成7年）以降：商用可\n上記以外：非商用"
    assert resolve(terms, 2020)[1] == "allowed"
    assert resolve(terms, 1990)[1] == "not-allowed"


def test_angle_bracket_headings():
    # P14 puts the scope in ＜＞ on its own line, with the licence below it.
    terms = ("＜2023年度（令和5年度）、2021年度（令和3年度）＞\n"
             "オープンデータ（CC_BY_4.0（一部制限））\n"
             "【重要：データ利用時の注意事項】\n"
             "・一部、利用規約とは異なる利用条件が付されたデータがあります\n"
             "＜2015年度（平成27年度）、2011年度（平成23年度）＞\n"
             "非商用")
    assert resolve(terms, 2023)[1] == "check"      # 一部制限
    assert resolve(terms, 2015)[1] == "not-allowed"


def test_partially_restricted_needs_a_human():
    terms = "オープンデータ（CC_BY_4.0（一部制限））\n【重要】・都道府県毎に定められた利用条件"
    assert resolve(terms, 2024)[:2] == ("other", "check")


def test_a_caveat_that_is_not_a_year_rule_does_not_split_anything():
    # N03 is CC BY 4.0 throughout, with a warning about 国土地理院.
    terms = "オープンデータ（CC_BY_4.0）\n※本データを二次利用する場合には、国土地理院に申請等必要な場合があります。"
    assert resolve(terms, 2026)[:2] == ("other", "check")


def test_no_terms_at_all_is_not_a_yes():
    assert resolve("", 2024)[:2] == ("other", "check")
    assert resolve("", None)[:2] == ("other", "check")


def test_an_unknown_year_against_split_terms_cannot_be_resolved():
    terms = "2020年（令和2年）以降：オープンデータ（CC_BY_4.0）\n上記以外：商用可"
    assert resolve(terms, None)[:2] == ("other", "check")
