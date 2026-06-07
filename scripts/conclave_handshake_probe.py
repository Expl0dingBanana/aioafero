#!/usr/bin/env python3
"""Minimal Conclave TLS handshake probe — prints raw server bytes after ``{}``."""

from __future__ import annotations

import asyncio
import json
import ssl
import sys
import zlib

import aiohttp

from aioafero import v1
from aioafero.v1.conclave.access import request_conclave_access
from aioafero.v1.conclave.frames import encode_frame


async def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else None
    if not username:
        raise SystemExit("usage: conclave_handshake_probe.py <username>")

    session = aiohttp.ClientSession()
    try:
        from pathlib import Path

        cache_path = Path(".aioafero-session.json")
        refresh_token = json.loads(cache_path.read_text())["refresh_token"]
        bridge = v1.AferoBridgeV1(
            username,
            refresh_token,
            session=session,
            enable_conclave=False,
        )
        await bridge.initialize()
        await bridge.async_block_until_done()

        access = await request_conclave_access(bridge)
        print(f"host={access.host} port={access.port} channel={access.channel_id}")
        print(f"token_len={len(access.token)}")

        ctx = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            access.host,
            access.port,
            ssl=ctx,
            server_hostname=access.host,
        )
        print("TLS connected")

        writer.write(encode_frame({}))
        await writer.drain()
        print("sent {}")

        for attempt in range(5):
            try:
                async with asyncio.timeout(15.0):
                    chunk = await reader.read(65536)
            except TimeoutError:
                print(f"read {attempt}: TIMEOUT (no bytes in 15s)")
                continue
            if not chunk:
                print(f"read {attempt}: EOF")
                break
            print(f"read {attempt}: {len(chunk)} bytes")
            print(f"  hex head: {chunk[:64].hex()}")
            if chunk[:1] == b"\x78":
                try:
                    payload = zlib.decompress(chunk)
                    print(f"  zlib JSON: {payload.decode('utf-8')[:500]}")
                except zlib.error as err:
                    print(f"  zlib error: {err}")
            else:
                print(f"  text head: {chunk[:500]!r}")

        writer.close()
        await writer.wait_closed()
        await bridge.close()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
