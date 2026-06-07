import json
import zlib

import pytest

from aioafero.v1.conclave import frames


def _drain(decoder, chunk: bytes) -> list[dict]:
    """Collect every frame the decoder yields for ``chunk``."""
    return list(decoder.feed(chunk))


def test_zlib_hello_frame_is_decoded_once():
    decoder = frames.ConclaveFrameDecoder()
    hello = {"hello": {"version": "conclave 2.7.3", "heartbeat": 60}}
    blob = zlib.compress(json.dumps(hello).encode())
    result = _drain(decoder, blob)
    assert result == [hello]
    assert list(decoder.feed(b"")) == []


def test_zlib_hello_followed_by_json_in_same_chunk():
    decoder = frames.ConclaveFrameDecoder()
    hello = {"hello": {"version": "conclave 2.7.3"}}
    tunnel = {"tunnel": {"version": "conclave 2.7.3"}}
    blob = zlib.compress(json.dumps(hello).encode()) + json.dumps(tunnel).encode()
    result = _drain(decoder, blob)
    assert result == [hello, tunnel]


def test_truncated_zlib_prefix_then_plain_hello():
    """Match live server: incomplete zlib blob then newline-framed hello."""
    decoder = frames.ConclaveFrameDecoder()
    chunk1 = b"\x78\x01" + b"\xaa" * 76
    chunk2 = b'\n{"hello":{"version":"conclave 2.7.3","heartbeat":60}}\n'
    assert _drain(decoder, chunk1) == []
    result = _drain(decoder, chunk2)
    hello = {"hello": {"version": "conclave 2.7.3", "heartbeat": 60}}
    assert result[0] is frames.HEARTBEAT_FRAME
    assert hello in result


def test_zlib_hello_split_across_reads():
    decoder = frames.ConclaveFrameDecoder()
    blob = zlib.compress(json.dumps({"hello": {"version": "2.7.3"}}).encode())
    assert _drain(decoder, blob[:5]) == []
    result = _drain(decoder, blob[5:])
    assert result == [{"hello": {"version": "2.7.3"}}]


def test_zlib_prefix_skipped_when_first_byte_is_brace():
    decoder = frames.ConclaveFrameDecoder()
    payload = b'{"login":{"ok":true}}'
    result = _drain(decoder, payload)
    assert result == [{"login": {"ok": True}}]


def test_corrupt_zlib_prefix_is_dropped():
    decoder = frames.ConclaveFrameDecoder()
    # Looks like a zlib header but the body is garbage. The decoder should
    # discard the buffered bytes and fall through to JSON parsing.
    payload = b"\x78\x01garbage-not-zlib"
    result = _drain(decoder, payload)
    assert result == []


def test_zlib_prefix_held_when_only_one_byte_received():
    decoder = frames.ConclaveFrameDecoder()
    # Single 0x78 byte: looks like a zlib header but we have not seen the
    # flag byte yet, so the decoder waits before committing to either mode.
    assert _drain(decoder, b"\x78") == []
    assert decoder._expecting_zlib_prefix is True
    blob = zlib.compress(json.dumps({"hello": {}}).encode())
    assert _drain(decoder, blob[1:]) == [{"hello": {}}]


def test_malformed_zlib_payload_logs_and_discards(caplog):
    decoder = frames.ConclaveFrameDecoder()
    blob = zlib.compress(b"\xff\xfe")
    with caplog.at_level("WARNING"):
        result = _drain(decoder, blob)
    assert result == []
    assert "Discarding malformed zlib-framed" in caplog.text


def test_back_to_back_json_objects():
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    payload = (
        json.dumps({"welcome": {"sessionId": 1}}).encode()
        + json.dumps({"join": {"sessionId": 1}}).encode()
    )
    result = _drain(decoder, payload)
    assert result == [{"welcome": {"sessionId": 1}}, {"join": {"sessionId": 1}}]


def test_newline_delimited_frames_yield_heartbeats():
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    payload = b'\n{"private":{"event":"attr_change"}}\n\n'
    result = _drain(decoder, payload)
    assert result[0] is frames.HEARTBEAT_FRAME
    assert result[1] == {"private": {"event": "attr_change"}}
    assert result[2] is frames.HEARTBEAT_FRAME


def test_non_object_top_level_value_is_dropped(caplog):
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    with caplog.at_level("DEBUG"):
        result = _drain(decoder, b"42")
    assert result == []
    assert "Discarding non-object" in caplog.text


def test_incomplete_json_is_buffered():
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    assert _drain(decoder, b'{"private":') == []
    assert _drain(decoder, b'{"x":1}}') == [{"private": {"x": 1}}]


def test_multibyte_split_across_reads():
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    payload = json.dumps({"name": "café"}, ensure_ascii=False).encode()
    # Split inside the multi-byte UTF-8 sequence for "é" (0xC3 0xA9).
    cut = payload.index(b"\xc3") + 1
    assert _drain(decoder, payload[:cut]) == []
    assert _drain(decoder, payload[cut:]) == [{"name": "café"}]


def test_encode_frame_appends_newline():
    payload = frames.encode_frame({"a": 1})
    assert payload.endswith(b"\n")
    assert json.loads(payload) == {"a": 1}


def test_encode_heartbeat():
    assert frames.encode_heartbeat() == b"\n"


@pytest.mark.parametrize(
    ("ws", "expected"),
    [
        (b"\n", [frames.HEARTBEAT_FRAME]),
        (b" \t", []),
        (b"\r", []),
    ],
)
def test_whitespace_runs_only_yield_heartbeats_for_newlines(ws, expected):
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    assert _drain(decoder, ws) == expected


def test_drop_non_object_json_rejects_partial_utf8():
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    assert _drain(decoder, b"\xc3") == []


def test_drop_non_object_json_accepts_array(caplog):
    decoder = frames.ConclaveFrameDecoder()
    decoder._expecting_zlib_prefix = False
    with caplog.at_level("DEBUG"):
        assert _drain(decoder, b"[1,2]") == []
    assert "Discarding non-object Conclave frame" in caplog.text
