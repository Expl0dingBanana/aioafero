r"""Conclave wire-frame decoder.

Server frames arrive as a zlib ``hello`` blob, then newline-delimited or
concatenated JSON objects, with bare ``\n`` heartbeats mixed in.

Pure helpers (:func:`try_parse_zlib_prefix`, :func:`index_json_object_start`)
are module-level for unit tests; :class:`ConclaveFrameDecoder` is the
incremental buffer used by the TLS client.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import json
import logging
import zlib

logger = logging.getLogger(__name__)

HEARTBEAT_FRAME: dict = {"__heartbeat__": True}
_NEWLINE = ord("\n")
_WS_ORDS = frozenset({ord(c) for c in "\n\r \t"})
_NON_OBJECT_JSON = object()


@dataclass(frozen=True)
class ZlibPrefixResult:
    """Result of :func:`try_parse_zlib_prefix`."""

    frame: dict | None
    consumed: int
    decided: bool


def index_json_object_start(data: bytes) -> int | None:
    """Return the byte offset of the first ``{`` in ``data``, if any."""
    index = data.find(b"{")
    return index if index >= 0 else None


def try_parse_zlib_prefix(data: bytes) -> ZlibPrefixResult:
    """Attempt to decompress a leading zlib envelope from ``data``."""
    if not data:
        return ZlibPrefixResult(None, 0, False)
    if data[0] != 0x78:
        return ZlibPrefixResult(None, 0, True)
    if len(data) < 2:
        return ZlibPrefixResult(None, 0, False)
    decompressor = zlib.decompressobj()
    try:
        decompressed = decompressor.decompress(data)
    except zlib.error:
        return ZlibPrefixResult(None, 0, True)
    if not decompressor.eof:
        if index_json_object_start(data) is not None:
            return ZlibPrefixResult(None, 0, True)
        return ZlibPrefixResult(None, 0, False)
    consumed = len(data) - len(decompressor.unused_data)
    try:
        frame = json.loads(decompressed.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Discarding malformed zlib-framed Conclave hello frame")
        return ZlibPrefixResult(None, consumed, True)
    if not isinstance(frame, dict):
        logger.debug("Discarding non-object zlib-framed Conclave frame: %r", frame)
        return ZlibPrefixResult(None, consumed, True)
    return ZlibPrefixResult(frame, consumed, True)


def _heartbeats_from_bytes(data: bytes) -> Iterator[dict]:
    """Yield :data:`HEARTBEAT_FRAME` for each newline byte in ``data``."""
    for byte in data:
        if byte == _NEWLINE:
            yield HEARTBEAT_FRAME


class ConclaveFrameDecoder:
    """Incremental decoder for the Conclave server-to-client stream."""

    def __init__(self) -> None:
        """Start decoding a fresh Conclave connection."""
        self._buffer = bytearray()
        self._expecting_zlib_prefix = True

    def feed(self, chunk: bytes) -> Iterator[dict]:
        """Feed bytes and yield each complete frame."""
        if chunk:
            self._buffer.extend(chunk)
        yield from self._drain()

    def _drain(self) -> Iterator[dict]:
        if self._expecting_zlib_prefix:
            result = try_parse_zlib_prefix(bytes(self._buffer))
            if not result.decided:
                return
            self._expecting_zlib_prefix = False
            if result.consumed:
                del self._buffer[: result.consumed]
            if result.frame is not None:
                yield result.frame
        yield from self._drain_json()

    def _drain_json(self) -> Iterator[dict]:
        decoder = json.JSONDecoder()
        while self._buffer:
            yield from self._yield_ws_heartbeats()
            if not self._buffer:
                break
            if self._buffer[0] != ord("{"):
                json_start = index_json_object_start(self._buffer)
                if json_start is None:
                    if self._consume_json_value(decoder) is _NON_OBJECT_JSON:
                        continue
                    return
                yield from self._heartbeats_before(json_start)
            result = self._consume_json_value(decoder)
            if result is None:
                return
            if result is not _NON_OBJECT_JSON:
                yield result

    def _yield_ws_heartbeats(self) -> Iterator[dict]:
        while self._buffer and self._buffer[0] in _WS_ORDS:
            heartbeat = self._buffer[0] == _NEWLINE
            del self._buffer[:1]
            if heartbeat:
                yield HEARTBEAT_FRAME

    def _heartbeats_before(self, json_start: int) -> Iterator[dict]:
        prefix = bytes(self._buffer[:json_start])
        del self._buffer[:json_start]
        yield from _heartbeats_from_bytes(prefix)

    def _consume_json_value(self, decoder: json.JSONDecoder) -> dict | object | None:
        """Parse one JSON value from the front of the buffer.

        :returns: A frame dict, ``_NON_OBJECT_JSON`` when a scalar/array was
            dropped, or ``None`` when more bytes are needed.
        """
        try:
            text = self._buffer.decode("utf-8")
        except UnicodeDecodeError:
            return None
        try:
            obj, end_index = decoder.raw_decode(text)
        except json.JSONDecodeError:
            return None
        byte_end = len(text[:end_index].encode("utf-8"))
        del self._buffer[:byte_end]
        if isinstance(obj, dict):
            return obj
        logger.debug("Discarding non-object Conclave frame: %r", obj)
        return _NON_OBJECT_JSON


def encode_frame(payload: dict) -> bytes:
    """Encode a client-to-server JSON frame."""
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


def encode_heartbeat() -> bytes:
    """Return the client heartbeat byte sequence."""
    return b"\n"
