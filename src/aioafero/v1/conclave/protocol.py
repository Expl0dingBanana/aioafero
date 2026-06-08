"""Conclave login and private-envelope helpers (no I/O)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .access import ConclaveAccess

if TYPE_CHECKING:  # pragma: no cover
    from aioafero.v1 import AferoBridgeV1

# Server may greet with either key after the opening ``{}``.
HANDSHAKE_FRAME_KEYS: frozenset[str] = frozenset({"hello", "tunnel"})
WELCOME_FRAME_KEY = "welcome"

CONCLAVE_CLIENT_TYPE = "aioafero"
CONCLAVE_CLIENT_VERSION = "1.0.0"
CONCLAVE_PROTOCOL = 2

PrivateEventHandler = Callable[["AferoBridgeV1", dict[str, Any]], Awaitable[bool]]


@dataclass(frozen=True)
class PrivateEvent:
    """Parsed ``private`` envelope from a Conclave push frame."""

    event: str
    data: dict[str, Any]


def build_login_frame(
    access: ConclaveAccess,
    *,
    client_type: str = CONCLAVE_CLIENT_TYPE,
    version: str = CONCLAVE_CLIENT_VERSION,
    protocol: int = CONCLAVE_PROTOCOL,
    trace: bool = False,
) -> dict[str, Any]:
    """Build the client ``login`` JSON frame for a :class:`~.access.ConclaveAccess`."""
    return {
        "login": {
            "channelId": access.channel_id,
            "accessToken": access.token,
            "type": client_type,
            "version": version,
            "protocol": protocol,
            "trace": trace,
        }
    }


def server_heartbeat_seconds(
    handshake: dict[str, Any], welcome: dict[str, Any]
) -> float:
    """Return the server-advertised heartbeat interval in seconds."""
    for envelope in (
        welcome.get(WELCOME_FRAME_KEY),
        handshake.get("hello"),
        handshake.get("tunnel"),
    ):
        if not isinstance(envelope, dict):
            continue
        heartbeat = envelope.get("heartbeat")
        if heartbeat is None:
            continue
        try:
            seconds = float(heartbeat)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return seconds
    return 60.0


def parse_private_frame(frame: dict[str, Any]) -> PrivateEvent | None:
    """Extract a ``private`` event from a decoded Conclave frame.

    :returns: :class:`PrivateEvent` when ``frame`` carries a well-formed
        ``private`` block; otherwise ``None``.
    """
    private = frame.get("private")
    if not isinstance(private, dict):
        return None
    event = private.get("event")
    data = private.get("data")
    if not isinstance(event, str) or not isinstance(data, dict):
        return None
    return PrivateEvent(event=event, data=data)
