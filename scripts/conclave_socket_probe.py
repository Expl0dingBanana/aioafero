#!/usr/bin/env python3
"""Probe Conclave transport keep-alive: TCP socket options, TLS, app heartbeats.

Conclave is **not** HTTP on the wire — there are no ``Connection: keep-alive``
headers on the push socket. Liveness is application-level ``\\n`` heartbeats
advertised in ``hello`` / ``welcome`` (see mitm captures).

Usage::

    uv run python scripts/conclave_socket_probe.py <username>
    uv run python scripts/conclave_socket_probe.py   # username from .aioafero-session.json
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping
import json
from pathlib import Path
import socket
import ssl
import time

import aiohttp

from aioafero import v1
from aioafero.v1.conclave.frames import encode_frame, encode_heartbeat
from aioafero.v1.conclave.protocol import (
    WELCOME_FRAME_KEY,
    build_login_frame,
    server_heartbeat_seconds,
)

DEFAULT_TOKEN_CACHE = Path(".aioafero-session.json")

# Linux TCP keepalive getsockopt names (when available).
_TCP_KEEPALIVE_OPTS: tuple[tuple[str, int], ...] = (
    ("SO_KEEPALIVE", socket.SOL_SOCKET, socket.SO_KEEPALIVE),
    ("TCP_KEEPIDLE", socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPIDLE", 4)),
    ("TCP_KEEPINTVL", socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPINTVL", 5)),
    ("TCP_KEEPCNT", socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPCNT", 6)),
)


def _load_username(arg: str | None) -> str:
    if arg:
        return arg
    if not DEFAULT_TOKEN_CACHE.is_file():
        raise SystemExit(
            "usage: conclave_socket_probe.py <username>  (or create .aioafero-session.json)"
        )
    data = json.loads(DEFAULT_TOKEN_CACHE.read_text(encoding="utf-8"))
    username = data.get("username")
    if not username:
        raise SystemExit("token cache is missing 'username'")
    return username


def _sockopt(sock: socket.socket, name: str, level: int, option: int) -> str:
    try:
        return str(sock.getsockopt(level, option))
    except OSError as err:
        return f"n/a ({err})"


def _dump_socket(sock: socket.socket, *, label: str) -> None:
    print(f"\n=== {label} (TCP) ===")
    for opt_name, level, option in _TCP_KEEPALIVE_OPTS:
        print(f"  {opt_name}: {_sockopt(sock, opt_name, level, option)}")
    print(f"  SO_REUSEADDR: {_sockopt(sock, 'SO_REUSEADDR', socket.SOL_SOCKET, socket.SO_REUSEADDR)}")
    try:
        print(f"  getsockname: {sock.getsockname()}")
        print(f"  getpeername: {sock.getpeername()}")
    except OSError as err:
        print(f"  peer/name: n/a ({err})")


def _dump_transport(writer: asyncio.StreamWriter) -> None:
    transport = writer.transport
    if transport is None:
        print("\n=== transport ===\n  (none)")
        return
    print("\n=== asyncio transport ===")
    print(f"  closing: {transport.is_closing()}")
    sock = transport.get_extra_info("socket")
    if sock is not None and hasattr(sock, "getsockopt"):
        _dump_socket(sock, label="client socket")  # type: ignore[arg-type]
    else:
        print(f"  socket extra_info: {sock!r}")
    ssl_obj = transport.get_extra_info("ssl_object")
    if ssl_obj is not None:
        print("\n=== TLS ===")
        cipher = ssl_obj.cipher()
        if cipher:
            print(f"  cipher: {cipher[0]} {cipher[1]} {cipher[2]}")
        print(f"  peer cert host: {ssl_obj.getpeercert().get('subject', 'n/a') if ssl_obj.getpeercert() else 'n/a'}")


def _print_http_headers(headers: Mapping[str, str], *, label: str) -> None:
    print(f"\n=== {label} (HTTP response headers) ===")
    if not headers:
        print("  (empty)")
        return
    for key in sorted(headers, key=str.lower):
        if key.lower() in {"connection", "keep-alive", "transfer-encoding", "date", "server"}:
            print(f"  {key}: {headers[key]}")
    connection = headers.get("Connection") or headers.get("connection")
    keep_alive = headers.get("Keep-Alive") or headers.get("keep-alive")
    if connection is None and keep_alive is None:
        print("  (no Connection / Keep-Alive headers in response)")


async def _request_access_with_headers(bridge: v1.AferoBridgeV1):
    """Mint conclaveAccess and return parsed access + raw response headers."""
    endpoint = f"/v1/accounts/{bridge.account_id}/conclaveAccess"
    url = bridge.generate_api_url(endpoint)
    from aioafero.v1 import v1_const

    headers = {
        "host": v1_const.AFERO_CLIENTS[bridge.afero_client]["API_HOST"],
        "content-type": "application/json; charset=utf-8",
    }
    res = await bridge.request(
        "POST",
        url,
        headers=headers,
        json={"user": True, "softHub": False},
    )
    res.raise_for_status()
    data = await res.json()
    from aioafero.v1.conclave.access import _parse_conclave_access

    return _parse_conclave_access(data), res.headers


async def _read_frame_text(reader: asyncio.StreamReader, timeout: float) -> bytes:
    async with asyncio.timeout(timeout):
        return await reader.read(65536)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", nargs="?", help="Hubspace account email")
    parser.add_argument(
        "--listen",
        type=float,
        default=150.0,
        help="Seconds to listen after login for app heartbeats (default: 150)",
    )
    args = parser.parse_args()
    username = _load_username(args.username)

    session = aiohttp.ClientSession()
    try:
        cache = json.loads(DEFAULT_TOKEN_CACHE.read_text(encoding="utf-8"))
        bridge = v1.AferoBridgeV1(
            username,
            cache["refresh_token"],
            session=session,
            enable_conclave=False,
        )
        await bridge.initialize()
        await bridge.async_block_until_done()

        access, http_headers = await _request_access_with_headers(bridge)
        _print_http_headers(http_headers, label="conclaveAccess POST")
        print(f"\nconclave host={access.host} port={access.port}")

        ctx = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            access.host,
            access.port,
            ssl=ctx,
            server_hostname=access.host,
        )
        _dump_transport(writer)

        writer.write(encode_frame({}))
        await writer.drain()
        print("\n=== handshake ===\n  sent {}")

        handshake = None
        welcome = None
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline and welcome is None:
            try:
                chunk = await _read_frame_text(reader, 10.0)
            except TimeoutError:
                print("  waiting for handshake bytes…")
                continue
            if not chunk:
                print("  EOF during handshake")
                break
            print(f"  chunk {len(chunk)} bytes, head={chunk[:32]!r}")
            if handshake is None and chunk[:1] == b"\x78":
                import zlib

                try:
                    text = zlib.decompress(chunk).decode()
                    handshake = json.loads(text)
                    print(f"  zlib hello/tunnel: {text[:200]}")
                except (zlib.error, json.JSONDecodeError) as err:
                    print(f"  zlib parse error: {err}")
            if b"welcome" in chunk:
                for line in chunk.split(b"\n"):
                    line = line.strip()
                    if not line or line == b"\n":
                        continue
                    try:
                        frame = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if WELCOME_FRAME_KEY in frame:
                        welcome = frame
                        break

        if handshake is None:
            print("  (no zlib handshake parsed — may need ConclaveFrameDecoder)")
        if welcome is None:
            # Try login if we have not seen welcome yet
            writer.write(encode_frame(build_login_frame(access)))
            await writer.drain()
            print("  sent login")
            try:
                chunk = await _read_frame_text(reader, 15.0)
                if chunk:
                    print(f"  post-login chunk {len(chunk)} bytes")
                    for line in chunk.split(b"\n"):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            frame = json.loads(line)
                        except json.JSONDecodeError:
                            if line == b"":
                                print("  heartbeat \\n")
                            continue
                        if WELCOME_FRAME_KEY in frame:
                            welcome = frame
                            print(f"  welcome: {json.dumps(frame)[:300]}")
            except TimeoutError:
                print("  post-login read timeout")

        hb = server_heartbeat_seconds(handshake or {}, welcome or {})
        print("\n=== application keep-alive ===")
        print(f"  server advertises heartbeat: {hb}s (reply with bare \\\\n)")
        print("  note: push socket is custom JSON frames, not HTTP — no Connection header")

        print(f"\n=== listening {args.listen:.0f}s for server heartbeats ===")
        last_at = time.monotonic()
        heartbeats = 0
        end = time.monotonic() + args.listen
        while time.monotonic() < end:
            try:
                chunk = await _read_frame_text(reader, min(30.0, end - time.monotonic()))
            except TimeoutError:
                idle = time.monotonic() - last_at
                print(f"  no bytes for 30s (idle {idle:.1f}s since last chunk)")
                continue
            if not chunk:
                print("  EOF — server closed socket")
                break
            last_at = time.monotonic()
            if chunk == b"\n":
                heartbeats += 1
                writer.write(encode_heartbeat())
                await writer.drain()
                print(f"  heartbeat #{heartbeats} (acked)")
            else:
                preview = chunk[:120].decode("utf-8", errors="replace")
                print(f"  data {len(chunk)} bytes: {preview!r}")

        writer.close()
        await writer.wait_closed()
        await bridge.close()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
