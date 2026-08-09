"""Tests for Conclave frame file capture handler."""

import logging
from pathlib import Path

import pytest

from aioafero.v1.conclave import FRAME_LOGGER, attach_frame_capture
from aioafero.v1.conclave.client import ConclaveClient
from aioafero.v1.conclave.frame_capture import ConclaveFrameFileHandler


@pytest.mark.asyncio
async def test_handler_buffers_then_flushes(tmp_path: Path, conclave_bridge):
    path = tmp_path / "frames.ndjson"
    handler = attach_frame_capture(path, buffer_size=2, propagate=False)
    try:
        bridge, _, _ = conclave_bridge
        client = ConclaveClient(bridge)
        await client._handle_frame({"private": {"event": "a", "data": {"id": "1"}}})
        assert handler.buffered_count == 1
        assert not path.exists()
        await client._handle_frame({"private": {"event": "b", "data": {"id": "2"}}})
        assert handler.buffered_count == 0
        frames = handler.read_frames()
        assert [f["private"]["event"] for f in frames] == ["a", "b"]
    finally:
        FRAME_LOGGER.removeHandler(handler)
        handler.close()


@pytest.mark.asyncio
async def test_handler_close_flushes_partial_buffer(tmp_path: Path, conclave_bridge):
    path = tmp_path / "frames.ndjson"
    handler = attach_frame_capture(path, buffer_size=10, propagate=False)
    bridge, _, _ = conclave_bridge
    client = ConclaveClient(bridge)
    await client._handle_frame({"private": {"event": "x", "data": {}}})
    FRAME_LOGGER.removeHandler(handler)
    handler.close()
    assert handler.read_frames() == [{"private": {"data": {}, "event": "x"}}]


def test_handler_rejects_bad_capacity(tmp_path: Path):
    with pytest.raises(ValueError):
        ConclaveFrameFileHandler(tmp_path / "x", capacity=0)


def test_handler_direct_emit_and_read(tmp_path: Path):
    path = tmp_path / "frames.ndjson"
    handler = ConclaveFrameFileHandler(path, capacity=1)
    FRAME_LOGGER.addHandler(handler)
    FRAME_LOGGER.setLevel("DEBUG")
    try:
        FRAME_LOGGER.debug("%s", '{"ok":true}')
        assert handler.read_frames() == [{"ok": True}]
    finally:
        FRAME_LOGGER.removeHandler(handler)
        handler.close()


def test_handler_read_empty_missing_file(tmp_path: Path):
    handler = ConclaveFrameFileHandler(tmp_path / "missing.ndjson", capacity=1)
    assert handler.read_frames() == []


def test_handler_read_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "frames.ndjson"
    path.write_text('\n{"a": 1}\n\n', encoding="utf-8")
    handler = ConclaveFrameFileHandler(path, capacity=1)
    assert handler.read_frames() == [{"a": 1}]


def test_handler_emit_uses_handle_error_on_failure(tmp_path: Path, mocker):
    handler = ConclaveFrameFileHandler(tmp_path / "frames.ndjson", capacity=10)
    mocker.patch.object(handler, "format", side_effect=RuntimeError("boom"))
    handle_error = mocker.patch.object(handler, "handleError")
    record = logging.LogRecord(
        name="aioafero.v1.conclave.frames",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg="%s",
        args=('{"x":1}',),
        exc_info=None,
    )
    handler.emit(record)
    handle_error.assert_called_once_with(record)
