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


A33 = """オープンデータ（CC_BY_4.0（一部制限））
【重要：データ利用時の注意事項】
・本データの利用時には利用規約のほか、都道府県毎に定められた利用条件を必ず確認してください。
＜オープンデータとしての利用可（商用利用可・再配信可）＞
北海道、青森県、岩手県、東京都、島根県、高知県、沖縄県
＜条件付公開＞
■神奈川県、京都府、広島県
（公開の条件は「データの公開条件」を必ず確認してください。）
"""

A52 = """オープンデータ（CC_BY_4.0）
ただし、利用にあたっては、以下の「データ利用時の注意事項」および各都道府県別のデータ時点を必ず確認してください。
【重要：データ利用時の注意事項】
・本データは縮尺1/25,000～1/50,000相当の精度で作成されており、法定図書ではありません。
・データ欠損、誤り等を発見した場合は、断り無く修正することがあります。
"""


def test_a_caveat_about_accuracy_is_not_a_caveat_about_permission():
    # A52 is CC BY 4.0. Everything after it is about precision and legal
    # standing, not about who may copy it. 「確認してください」 appears in
    # almost every KSJ disclaimer, so treating it as a licence condition
    # withholds permission the page actually grants.
    assert resolve(A52, 2023)[:2] == ("CC-BY-4.0", "allowed")


def test_a_prohibition_is_not_a_permission_caveat():
    # A52 says 「申請資料や根拠を示す必要がある資料への利用はできません」: that
    # is a limit on use, not a requirement to ask first. Matching the bare
    # word 申請 read it as the latter and withheld CC BY 4.0.
    assert resolve(A52 + "\n・申請資料や根拠を示す資料への利用はできません。", 2023)[1] == "allowed"


def test_a_caveat_about_permission_still_withholds_it():
    # N03: 「二次利用する場合には、国土地理院に申請等必要な場合があります」
    terms = "オープンデータ（CC_BY_4.0）\n※二次利用する場合には、国土地理院に申請等必要な場合があります。"
    assert resolve(terms, 2026)[1] == "check"


def test_a_prefecture_named_as_redistributable_resolves():
    # 一部制限 is per-prefecture, and the page lists which.
    assert resolve(A33, 2025, "東京")[:2] == ("CC-BY-4.0", "allowed")
    assert resolve(A33, 2025, "高知")[1] == "allowed"


def test_a_prefecture_under_conditions_does_not():
    assert resolve(A33, 2025, "神奈川")[1] == "check"
    assert resolve(A33, 2025, "広島")[1] == "check"


def test_a_prefecture_not_named_at_all_does_not():
    assert resolve(A33, 2025, "山形")[1] == "check"


def test_without_a_region_a_per_prefecture_rule_stays_unresolved():
    assert resolve(A33, 2025)[1] == "check"


A31A = """国土数値情報ダウンロードサイトコンテンツ利用規約のほか、都道府県毎に定められた利用条件を必ず遵守するようにしてください。
■2025年度、2024年度、2023年度、2022年度、2021年度（令和7年度、令和6年度、令和5年度、令和4年度、令和3年度）
オープンデータ（CC_BY_4.0）
■2020年度、2019年度（令和2年度、令和元年度）
＜オープンデータ（CC_BY_4.0）＞
北海道、岩手県、山形県
＜オープンデータ（CC_BY_4.0（一部制限）原則として商用利用化・再配信可）＞
島根県：利用にあたり、規約を遵守すること
"""


def test_a_black_square_heading_scopes_its_years_too():
    # A31a heads year groups with ■2025年度、2024年度… and puts the licence on
    # the line below. Reading only ＜＞ and scope：licence left the whole
    # dataset unresolved, and 2021 onwards is plain CC BY 4.0.
    assert resolve(A31A, 2025)[:2] == ("CC-BY-4.0", "allowed")
    assert resolve(A31A, 2021)[:2] == ("CC-BY-4.0", "allowed")


def test_a_black_square_that_names_no_year_is_not_a_scope():
    # A40 uses ■宮城県 for per-prefecture conditions, not for years.
    terms = "オープンデータ（CC_BY_4.0（一部制限））\n＜オープンデータとして利用可（商用利用可・再配信可）＞\n東京都\n■宮城県\n規約を遵守すること"
    assert resolve(terms, 2024, "東京")[1] == "allowed"
    assert resolve(terms, 2024, "宮城")[1] == "check"
