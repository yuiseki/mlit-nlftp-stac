import io
import struct
import zipfile

import pytest

from mlit_nlftp_stac.shpbbox import (
    ZipReadError,
    bbox_from_shp_header,
    looks_like_japan,
    shp_bbox,
)

TOKYO = (136.0695, 20.4227, 153.9867, 35.8984)


def _shp_header(bbox):
    head = bytearray(100)
    struct.pack_into(">I", head, 0, 9994)
    struct.pack_into("<4d", head, 36, *bbox)
    return bytes(head)


def _zip_bytes(members, compression=zipfile.ZIP_DEFLATED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as z:
        for name, payload in members:
            z.writestr(name, payload)
    return buf.getvalue()


def _reader(blob):
    return lambda start, end: blob[start : end + 1]


def _bbox(blob):
    return shp_bbox(_reader(blob), len(blob))[1]


def test_bbox_is_read_without_touching_the_rest_of_the_file():
    body = _shp_header(TOKYO) + b"\x00" * 5_000_000
    blob = _zip_bytes([("N03-20260101_13.dbf", b"x" * 1000), ("N03-20260101_13.shp", body)])
    assert _bbox(blob) == pytest.approx(TOKYO)


def test_a_stored_uncompressed_member_works_too():
    blob = _zip_bytes([("a.shp", _shp_header(TOKYO))], compression=zipfile.ZIP_STORED)
    assert _bbox(blob) == pytest.approx(TOKYO)


def test_the_shp_is_found_whatever_its_position():
    blob = _zip_bytes(
        [("readme.txt", b"hi"), ("a.prj", b"GEOGCS"), ("b.shp", _shp_header(TOKYO))]
    )
    assert _bbox(blob) == pytest.approx(TOKYO)


def test_an_archive_without_a_shapefile_is_an_error_not_an_empty_bbox():
    blob = _zip_bytes([("only.txt", b"hi")])
    with pytest.raises(ZipReadError):
        _bbox(blob)


def test_something_that_is_not_a_shapefile_is_rejected():
    with pytest.raises(ZipReadError):
        bbox_from_shp_header(b"\x00" * 100)


def test_a_bbox_outside_japan_does_not_pass_the_sanity_check():
    assert looks_like_japan(TOKYO)
    assert not looks_like_japan((-74.0, 40.0, -73.0, 41.0))  # New York
    assert not looks_like_japan((140.0, 36.0, 139.0, 35.0))  # east west of west
    assert not looks_like_japan(None)
