import json
import zlib

from aioafero.v1.conclave.frames import index_json_object_start, try_parse_zlib_prefix


def test_index_json_object_start():
    assert index_json_object_start(b'prefix{"a":1}') == 6
    assert index_json_object_start(b"no-json") is None


def test_try_parse_zlib_prefix_empty():
    result = try_parse_zlib_prefix(b"")
    assert result.decided is False
    assert result.frame is None
    assert result.consumed == 0


def test_try_parse_zlib_prefix_complete():
    hello = {"hello": {"version": "2.7.3"}}
    blob = zlib.compress(json.dumps(hello).encode())
    result = try_parse_zlib_prefix(blob)
    assert result.decided is True
    assert result.frame == hello
    assert result.consumed == len(blob)


def test_try_parse_zlib_prefix_incomplete_without_json():
    chunk = b"\x78\x01" + b"\xaa" * 10
    result = try_parse_zlib_prefix(chunk)
    assert result.decided is False
    assert result.frame is None


def test_try_parse_zlib_prefix_waits_when_incomplete_even_if_brace_present():
    chunk = b"\x78\x01" + bytes([0x7B]) + b"\xaa" * 9
    result = try_parse_zlib_prefix(chunk)
    assert result.decided is False
    assert result.frame is None
    assert result.consumed == 0


def test_try_parse_zlib_prefix_abandons_truncated_prefix_with_plain_json_suffix():
    prefix = b"\x78\x01" + b"\xaa" * 76
    suffix = b'\n{"hello":{"version":"2.7.3"}}\n'
    assert try_parse_zlib_prefix(prefix).decided is False
    result = try_parse_zlib_prefix(prefix + suffix)
    assert result.decided is True
    assert result.frame is None
    assert result.consumed == 0


def test_try_parse_zlib_prefix_non_object(caplog):
    blob = zlib.compress(b"42")
    with caplog.at_level("DEBUG"):
        result = try_parse_zlib_prefix(blob)
    assert result.decided is True
    assert result.frame is None
    assert "Discarding non-object zlib-framed" in caplog.text
