#!/usr/bin/env python3
"""Log in to Hubspace / Afero and write a local session cache.

Reads ``afero.yaml`` (see ``scripts/afero.yaml.example``). Password comes from
``AFERO_PASSWORD`` or an interactive prompt. OTP is prompted when required.

Example::

    cp scripts/afero.yaml.example afero.yaml
    uv sync --extra cli
    uv run --extra cli python scripts/afero_login.py
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
from pathlib import Path
import sys

import aiohttp

from aioafero import v1

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from afero_local import (  # noqa: E402
    DEFAULT_CONFIG,
    config_username,
    load_config,
    save_session,
    session_path,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Login and write .aioafero-session.json (or configured path).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"YAML config path (default: {DEFAULT_CONFIG}).",
    )
    return parser.parse_args()


async def _login(config: dict) -> None:
    username = config_username(config)
    password = os.environ.get("AFERO_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password for {username}: ")
    if not password:
        raise SystemExit("Password is required.")

    afero_client = str(config.get("afero_client") or "hubspace")
    out = session_path(config)

    session = aiohttp.ClientSession()
    try:
        auth = v1.AferoAuth.for_login(
            session, username, password, afero_client=afero_client
        )
        try:
            tokens = await auth.login()
        except v1.OTPRequired:
            code = input("Enter the OTP code from your email: ").strip()
            tokens = await auth.submit_otp(code)
        save_session(out, username, tokens)
        print(f"Wrote session for {username} to {out}")
    finally:
        await session.close()


def main() -> None:
    args = _parse_args()
    config = load_config(args.config)
    level = str(config.get("log_level") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_login(config))


if __name__ == "__main__":
    main()
