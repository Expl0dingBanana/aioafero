#!/usr/bin/env python3
"""Watch Hubspace device updates with Conclave push enabled.

Logs in (or reuses a refresh token), opens the bridge with ``enable_conclave=True``,
and prints human-readable diffs whenever a device model changes. Toggle something in
the Hubspace app and you should see updates within a second or two without waiting
for the REST poll interval.

Examples::

    uv run python scripts/conclave_watch.py \\
        --username you@example.com --password 'your-password'

    uv run python scripts/conclave_watch.py \\
        --username you@example.com --refresh-token 'stored-refresh-token'

Environment variables ``AFERO_USERNAME``, ``AFERO_PASSWORD``, and
``AFERO_REFRESH_TOKEN`` are used when CLI flags are omitted.

After a successful login the script writes ``.aioafero-session.json`` (gitignored)
so later runs reuse the refresh token and skip OTP. Use ``--clear-token-cache`` to
remove it and log in again with a password.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

import aiohttp

from aioafero import v1
from aioafero.types import EventType
from aioafero.v1.models import features
from aioafero.v1.models.resource import ResourceTypes

log = logging.getLogger("conclave_watch")

DEFAULT_TOKEN_CACHE = Path(".aioafero-session.json")


@dataclass
class SessionTokens:
    """OAuth tokens persisted between ``conclave_watch`` runs."""

    refresh_token: str
    token: str | None = None
    token_expiration: float | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch Hubspace device changes via Conclave push.",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("AFERO_USERNAME"),
        help="Hubspace account email (or AFERO_USERNAME).",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("AFERO_PASSWORD"),
        help="Account password for first-time login (or AFERO_PASSWORD).",
    )
    parser.add_argument(
        "--refresh-token",
        default=os.environ.get("AFERO_REFRESH_TOKEN"),
        help="Stored OAuth refresh token; skips password login (or AFERO_REFRESH_TOKEN).",
    )
    parser.add_argument(
        "--polling-interval",
        type=int,
        default=120,
        help="REST state poll interval in seconds (default: 120). Conclave is live.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging for aioafero (includes Conclave handshake).",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help=(
            "Log each pipeline stage: Conclave frame → cache patch → controller → "
            "subscriber. Use alongside mitmweb to compare with the Hubspace app."
        ),
    )
    parser.add_argument(
        "--token-cache",
        type=Path,
        default=DEFAULT_TOKEN_CACHE,
        help=f"Path for cached OAuth tokens (default: {DEFAULT_TOKEN_CACHE}).",
    )
    parser.add_argument(
        "--no-token-cache",
        action="store_true",
        help="Do not read or write the token cache file.",
    )
    parser.add_argument(
        "--clear-token-cache",
        action="store_true",
        help="Delete the token cache file and exit (use before a fresh password login).",
    )
    return parser.parse_args()


def _load_token_cache(path: Path, username: str) -> SessionTokens | None:
    """Load cached tokens when the file exists and matches ``username``."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        log.warning("Ignoring unreadable token cache %s: %s", path, err)
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("username") != username:
        log.info(
            "Token cache is for a different account (%s); ignoring.",
            payload.get("username"),
        )
        return None
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        return None
    token = payload.get("token")
    expiration = payload.get("token_expiration")
    return SessionTokens(
        refresh_token=str(refresh_token),
        token=str(token) if token else None,
        token_expiration=float(expiration) if expiration is not None else None,
    )


def _save_token_cache(path: Path, username: str, tokens: SessionTokens) -> None:
    """Persist tokens for the next run (mode ``0600``)."""
    payload = {
        "username": username,
        "refresh_token": tokens.refresh_token,
        "token": tokens.token,
        "token_expiration": tokens.token_expiration,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _clear_token_cache(path: Path) -> None:
    """Remove a cached session file if present."""
    if path.is_file():
        path.unlink()
        print(f"Removed token cache: {path}")
    else:
        print(f"No token cache at: {path}")


def _timestamp() -> str:
    return datetime.now(UTC).astimezone().strftime("%H:%M:%S")


def _device_label(item: Any) -> tuple[str, str]:
    info = getattr(item, "device_information", None)
    name = None
    if info is not None:
        name = info.name or info.default_name
    resource_type = getattr(item, "type", ResourceTypes.UNKNOWN)
    if isinstance(resource_type, ResourceTypes):
        type_label = resource_type.value
    else:
        type_label = str(resource_type)
    return name or item.id, type_label


def _on_label(instance: str | None) -> str:
    return "power" if instance in (None, "") else f"power ({instance})"


def _snapshot_item(item: Any) -> dict[str, str]:
    """Flatten the user-visible state of a controller model."""
    snap: dict[str, str] = {}
    snap["available"] = "online" if getattr(item, "available", True) else "offline"

    on = getattr(item, "on", None)
    if isinstance(on, features.OnFeature):
        snap[_on_label(on.func_instance)] = "on" if on.on else "off"
    elif isinstance(on, Mapping):
        for instance, feat in on.items():
            if isinstance(feat, features.OnFeature):
                snap[_on_label(instance)] = "on" if feat.on else "off"

    dimming = getattr(item, "dimming", None)
    if isinstance(dimming, features.DimmingFeature):
        snap["brightness"] = f"{dimming.brightness}%"

    color = getattr(item, "color", None)
    if isinstance(color, features.ColorFeature):
        snap["color"] = f"rgb({color.red}, {color.green}, {color.blue})"

    color_mode = getattr(item, "color_mode", None)
    if isinstance(color_mode, features.ColorModeFeature):
        snap["color mode"] = color_mode.mode

    color_temp = getattr(item, "color_temperature", None)
    if isinstance(color_temp, features.ColorTemperatureFeature):
        snap["color temperature"] = f"{color_temp.temperature} K"

    effect = getattr(item, "effect", None)
    if isinstance(effect, features.EffectFeature):
        snap["effect"] = effect.effect or "none"

    speed = getattr(item, "speed", None)
    if isinstance(speed, features.SpeedFeature):
        snap["speed"] = str(speed.speed)

    direction = getattr(item, "direction", None)
    if isinstance(direction, features.DirectionFeature):
        snap["direction"] = "forward" if direction.forward else "reverse"

    preset = getattr(item, "preset", None)
    if isinstance(preset, features.PresetFeature):
        snap["preset"] = "enabled" if preset.enabled else "disabled"

    position = getattr(item, "position", None)
    if isinstance(position, features.CurrentPositionFeature):
        snap["lock"] = position.position.value

    hvac_mode = getattr(item, "hvac_mode", None)
    if isinstance(hvac_mode, features.HVACModeFeature):
        snap["hvac mode"] = hvac_mode.mode

    target = getattr(item, "target_temperature", None)
    if target is not None:
        snap["target temperature"] = f"{target}°"

    current_temp = getattr(item, "current_temperature", None)
    if isinstance(current_temp, features.CurrentTemperatureFeature):
        snap["current temperature"] = f"{current_temp.temperature}°"

    fan_mode = getattr(item, "fan_mode", None)
    if isinstance(fan_mode, features.ModeFeature):
        snap["fan mode"] = fan_mode.mode

    fan_running = getattr(item, "fan_running", None)
    if fan_running is not None:
        snap["fan running"] = "yes" if fan_running else "no"

    hvac_action = getattr(item, "hvac_action", None)
    if hvac_action:
        snap["hvac action"] = str(hvac_action)

    for sensor_id, sensor in (getattr(item, "sensors", None) or {}).items():
        if sensor.value is not None:
            unit = f" {sensor.unit}" if sensor.unit else ""
            snap[f"sensor {sensor_id}"] = f"{sensor.value}{unit}"

    for sensor_id, sensor in (getattr(item, "binary_sensors", None) or {}).items():
        snap[f"binary sensor {sensor_id}"] = "alert" if sensor.value else "normal"

    for key, number in (getattr(item, "numbers", None) or {}).items():
        func_class, instance = key
        label = func_class if not instance else f"{func_class} ({instance})"
        snap[f"number {label}"] = str(number.value)

    for key, select in (getattr(item, "selects", None) or {}).items():
        func_class, instance = key
        label = func_class if not instance else f"{func_class} ({instance})"
        snap[f"select {label}"] = str(select.selected)

    return snap


def _format_changes(
    name: str,
    type_label: str,
    item_id: str,
    old: dict[str, str],
    new: dict[str, str],
) -> str | None:
    lines: list[str] = []
    keys = sorted(set(old) | set(new))
    for key in keys:
        before = old.get(key)
        after = new.get(key)
        if before == after:
            continue
        if before is None:
            lines.append(f"  • {key}: set to {after}")
        elif after is None:
            lines.append(f"  • {key}: cleared (was {before})")
        else:
            lines.append(f"  • {key}: {before} → {after}")
    if not lines:
        return None
    header = f"[{_timestamp()}] {name} ({type_label}, {item_id})"
    return "\n".join([header, *lines])


class ChangePrinter:
    """Track prior snapshots and print human-readable diffs."""

    def __init__(self) -> None:
        self._snapshots: dict[str, dict[str, str]] = {}

    def observe(self, item: Any) -> None:
        item_id = item.id
        new_snap = _snapshot_item(item)
        old_snap = self._snapshots.get(item_id)
        if old_snap is None:
            self._snapshots[item_id] = new_snap
            return
        name, type_label = _device_label(item)
        message = _format_changes(name, type_label, item_id, old_snap, new_snap)
        if message:
            print(message, flush=True)
        self._snapshots[item_id] = new_snap

    def seed(self, item: Any) -> None:
        self._snapshots[item.id] = _snapshot_item(item)


def _collect_devices(bridge: v1.AferoBridgeV1) -> list[Any]:
    devices: list[Any] = []
    for controller in bridge.controllers:
        devices.extend(controller.items)
    return devices


def _print_inventory(bridge: v1.AferoBridgeV1, printer: ChangePrinter) -> None:
    devices = _collect_devices(bridge)
    print(f"\nWatching {len(devices)} device(s). Toggle one in the Hubspace app.\n")
    for item in sorted(devices, key=lambda d: _device_label(d)[0].lower()):
        name, type_label = _device_label(item)
        printer.seed(item)
        snap = printer._snapshots[item.id]
        summary = ", ".join(f"{k}={v}" for k, v in sorted(snap.items())[:4])
        if len(snap) > 4:
            summary += ", …"
        print(f"  • {name} ({type_label}): {summary or 'no readable state'}")
    print()


def _token_data_to_session(token_data: v1.TokenData) -> SessionTokens:
    return SessionTokens(
        refresh_token=token_data.refresh_token,
        token=token_data.token,
        token_expiration=token_data.expiration,
    )


async def _login_with_password(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> SessionTokens:
    auth = v1.AferoAuth.for_login(session, username, password)
    try:
        token_data = await auth.login()
    except v1.OTPRequired:
        code = input("Enter the OTP code from your email: ").strip()
        token_data = await auth.submit_otp(code)
    return _token_data_to_session(token_data)


async def _resolve_session_tokens(
    session: aiohttp.ClientSession,
    username: str,
    password: str | None,
    refresh_token: str | None,
    *,
    token_cache: Path | None,
    use_token_cache: bool,
) -> SessionTokens:
    if refresh_token:
        return SessionTokens(refresh_token=refresh_token)
    if use_token_cache and token_cache is not None:
        cached = _load_token_cache(token_cache, username)
        if cached is not None:
            print(f"Using cached session from {token_cache}")
            return cached
    if not password:
        raise SystemExit(
            "Provide --password for login, --refresh-token, or a token cache file "
            f"({DEFAULT_TOKEN_CACHE})."
        )
    print("Logging in with password…")
    tokens = await _login_with_password(session, username, password)
    if use_token_cache and token_cache is not None:
        _save_token_cache(token_cache, username, tokens)
        print(f"Saved session to {token_cache}")
    return tokens


async def _run(args: argparse.Namespace) -> None:
    if not args.username:
        raise SystemExit("Provide --username (or set AFERO_USERNAME).")

    use_token_cache = not args.no_token_cache
    token_cache = args.token_cache if use_token_cache else None

    session = aiohttp.ClientSession()
    printer = ChangePrinter()
    bridge: v1.AferoBridgeV1 | None = None
    tokens: SessionTokens | None = None

    try:
        tokens = await _resolve_session_tokens(
            session,
            args.username,
            args.password,
            args.refresh_token,
            token_cache=token_cache,
            use_token_cache=use_token_cache,
        )
        bridge = v1.AferoBridgeV1(
            args.username,
            tokens.refresh_token,
            session=session,
            token=tokens.token,
            token_expiration=tokens.token_expiration,
            enable_conclave=True,
            polling_interval=args.polling_interval,
        )

        print("Initializing bridge (discovery poll + Conclave)…")
        await bridge.initialize()
        await bridge.async_block_until_done()

        conclave = bridge.conclave
        if conclave is None:
            print("WARNING: Conclave client was not started (enable_conclave=True?).")
        elif not await conclave.wait_until_logged_in(timeout=90.0):
            print(
                "ERROR: Conclave did not log in within 90s — live pushes will not arrive.\n"
                "       Check outbound TLS to conclave-stream*.afero.net:443, then re-run."
            )
        else:
            print("Conclave push channel is logged in and receiving events.")

        if args.trace:
            script_dir = Path(__file__).resolve().parent
            if str(script_dir) not in sys.path:
                sys.path.insert(0, str(script_dir))
            from conclave_trace import install_trace_hooks

            install_trace_hooks(bridge, device_label=_device_label)

        def on_event(event_type: EventType, item: Any) -> None:
            if args.trace and event_type == EventType.RESOURCE_UPDATED:
                name, type_label = _device_label(item)
                print(
                    f"TRACE subscriber callback: {name} ({type_label}) id={item.id}",
                    flush=True,
                )
            if event_type == EventType.RESOURCE_UPDATED:
                printer.observe(item)
            elif event_type == EventType.INVALID_AUTH:
                print(
                    f"[{_timestamp()}] AUTH ERROR: refresh token may be invalid. "
                    "Re-run with --password and --clear-token-cache."
                )
            elif event_type in (
                EventType.RESOURCE_ADDED,
                EventType.RESOURCE_DELETED,
            ):
                name, type_label = _device_label(item)
                verb = "added" if event_type == EventType.RESOURCE_ADDED else "removed"
                print(f"[{_timestamp()}] Device {verb}: {name} ({type_label})")
                if event_type == EventType.RESOURCE_ADDED:
                    printer.seed(item)

        # Must run after initialize(): bridge.subscribe only wires initialized controllers.
        bridge.subscribe(on_event)

        _print_inventory(bridge, printer)
        print("Listening for changes (Ctrl+C to quit)…\n")

        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        if (
            bridge is not None
            and tokens is not None
            and use_token_cache
            and token_cache is not None
        ):
            rotated = SessionTokens(
                refresh_token=bridge.refresh_token or tokens.refresh_token,
                token=tokens.token,
                token_expiration=tokens.token_expiration,
            )
            _save_token_cache(token_cache, args.username, rotated)
        if bridge is not None:
            await bridge.close()
        await session.close()


def main() -> None:
    args = _parse_args()
    if args.clear_token_cache:
        _clear_token_cache(args.token_cache)
        return
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("aioafero").setLevel(level)
    if args.debug or args.trace:
        logging.getLogger("aioafero.v1.conclave.events").setLevel(logging.DEBUG)
    if args.trace:
        logging.getLogger("aioafero.v1.conclave").setLevel(logging.INFO)
    asyncio.run(_run(args))


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        sys.exit(exc.code if exc.code is not None else 0)
