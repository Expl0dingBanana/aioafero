"""Shared fakes and wire helpers for Conclave unit tests."""

from __future__ import annotations

import asyncio
import json
import zlib

from aioafero.v1.conclave.access import ConclaveAccess

ACCESS = ConclaveAccess(
    host="conclave-stream1.afero.net",
    port=443,
    ssl=True,
    compression=True,
    token="conclave-token",
    channel_id="account-uuid",
)


class FakeWriter:
    """Minimal ``asyncio.StreamWriter`` substitute for handshake tests."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:  # pragma: no cover - trivial
        await asyncio.sleep(0)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:  # pragma: no cover - trivial
        await asyncio.sleep(0)


class ScriptedReader:
    """``asyncio.StreamReader``-shaped reader replaying canned chunks.

    After ``chunks`` is exhausted, ``read`` resolves with ``b""`` so the
    connection loop sees a graceful close.
    """

    def __init__(self, chunks: list[bytes], *, hold_open: bool = False) -> None:
        self._chunks = list(chunks)
        self._hold_open = hold_open

    def at_eof(self) -> bool:
        """Match ``asyncio.StreamReader.at_eof`` for scripted replay."""
        return not self._chunks and not self._hold_open

    async def read(self, _size: int) -> bytes:
        if self._chunks:
            await asyncio.sleep(0)
            return self._chunks.pop(0)
        if self._hold_open:
            await asyncio.Event().wait()
        return b""


def zlib_hello() -> bytes:
    return zlib.compress(
        json.dumps({"hello": {"version": "conclave 2.7.3", "heartbeat": 60}}).encode()
    )


def wire_frame(payload: dict) -> bytes:
    return json.dumps(payload).encode() + b"\n"
