"""Every case here is a real upstream filename, copied from the live index."""

from mlit_nlftp_stac.ksj import parse_filename


def test_national_file_has_no_area_token():
    p = parse_filename("N02-25_GML.zip")
    assert p.identifier == "N02"
    assert p.year == 2025
    assert p.area_tokens == []


def test_two_digit_year_before_1990_is_last_century():
    # A16-85 is the 1985 survey, still linked from the A16-2020 page.
    assert parse_filename("A16-85_14_GML.zip").year == 1985


def test_eight_digit_date_keeps_only_the_year():
    p = parse_filename("N03-20260101_GML.zip")
    assert p.identifier == "N03"
    assert p.year == 2026


def test_six_digit_date_keeps_only_the_year():
    p = parse_filename("N03-120401_01_GML.zip")
    assert p.identifier == "N03"
    assert p.year == 2012
    assert p.area_tokens == ["01"]


def test_identifier_may_carry_letter_suffixes():
    assert parse_filename("A31a-25_83_10_SHP.zip").identifier == "A31a"
    assert parse_filename("L03-b-u-16_6841-tky_GML.zip").identifier == "L03-b-u"


def test_mesh_code_is_recognised():
    p = parse_filename("A31-22_10_5439_GEOJSON.zip")
    assert p.mesh_code == "5439"


def test_mesh_code_is_recognised_with_a_trailing_word():
    assert parse_filename("L03-b-u-16_6841-tky_GML.zip").mesh_code == "6841"


def test_year_only_filenames_still_parse():
    p = parse_filename("250m_mesh_2024_GML.zip")
    assert p.year == 2024
    assert p.identifier is None


def test_area_tokens_are_not_called_prefectures():
    # A47 uses this slot for both prefecture codes (14) and something else
    # entirely (55). Anything that turns the token into a prefecture without
    # knowing the dataset is guessing.
    p = parse_filename("A47-21_55_GML.zip")
    assert p.area_tokens == ["55"]
    assert not hasattr(p, "prefecture_code")
