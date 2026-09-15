#!/usr/bin/env python3
"""Open an Afero bridge using afero.yaml + a session cache file.

Does not perform password login — run ``scripts/afero_login.py`` first.

Example::

    uv run --extra cli python scripts/afero_bridge.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
import sys

import aiohttp

from aioafero import v1
from aioafero.v1 import TokenData
from aioafero.v1.conclave import (
    FRAME_LOGGER,
    ConclaveFrameFileHandler,
    attach_frame_capture,
)

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from afero_local import (  # noqa: E402
    DEFAULT_CONFIG,
    config_username,
    load_config,
    load_session,
    save_session,
    session_path,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start AferoBridgeV1 from afero.yaml + session file.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"YAML config path (default: {DEFAULT_CONFIG}).",
    )
    return parser.parse_args()


def _maybe_attach_capture(config: dict) -> ConclaveFrameFileHandler | None:
    raw = config.get("capture_frames")
    if not raw:
        return None
    buffer_size = int(config.get("capture_buffer") or 32)
    handler = attach_frame_capture(
        Path(raw),
        buffer_size=buffer_size,
        propagate=False,
    )
    print(f"Capturing Conclave frames to {handler.path} (buffer={buffer_size})")
    return handler


async def _run(config: dict) -> None:
    cfg_user = config_username(config)
    path = session_path(config)
    username, tokens = load_session(path)
    if username != cfg_user:
        raise SystemExit(
            f"Session file username ({username}) does not match "
            f"config username ({cfg_user})."
        )

    afero_client = str(config.get("afero_client") or "hubspace")
    enable_conclave = bool(config.get("enable_conclave", False))
    polling_interval = int(config.get("polling_interval") or 120)
    capture = _maybe_attach_capture(config)

    session = aiohttp.ClientSession()
    bridge: v1.AferoBridgeV1 | None = None
    try:
        bridge = v1.AferoBridgeV1(
            username,
            tokens.refresh_token,
            session=session,
            token=tokens.token,
            token_expiration=tokens.expiration,
            afero_client=afero_client,
            enable_conclave=enable_conclave,
            polling_interval=polling_interval,
        )
        print(
            f"Initializing bridge for {username} "
            f"(conclave={enable_conclave}, poll={polling_interval}s)…"
        )
        await bridge.initialize()
        await bridge.async_block_until_done()
        if enable_conclave and bridge.conclave is not None:
            if await bridge.conclave.wait_until_logged_in(timeout=90.0):
                print("Conclave logged in.")
            else:
                print("WARNING: Conclave did not log in within 90s.")
        print("Bridge running (Ctrl+C to stop).")
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        if capture is not None:
            n = len(capture.read_frames())
            print(f"Flushed Conclave capture ({n} frame(s)) to {capture.path}")
            FRAME_LOGGER.removeHandler(capture)
            capture.close()
        if bridge is not None:
            live = bridge.token_data
            rotated = (
                TokenData(
                    token=live.token,
                    access_token=live.access_token,
                    refresh_token=live.refresh_token,
                    expiration=live.expiration,
                )
                if live is not None
                else TokenData(
                    token=tokens.token,
                    access_token=tokens.access_token,
                    refresh_token=bridge.refresh_token or tokens.refresh_token,
                    expiration=tokens.expiration,
                )
            )
            save_session(path, username, rotated)
            await bridge.close()
        await session.close()


def main() -> None:
    args = _parse_args()
    config = load_config(args.config)
    level = str(config.get("log_level") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("aioafero").setLevel(getattr(logging, level, logging.INFO))
    asyncio.run(_run(config))


if __name__ == "__main__":
    main()
