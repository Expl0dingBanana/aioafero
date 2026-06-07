"""Mint a short-lived Conclave access token via REST.

The Hubspace app calls ``POST .../accounts/{accountId}/conclaveAccess`` before
opening the Conclave TLS socket. The OAuth bearer is **only used to mint this
short-lived token** — the socket itself authenticates with ``tokens[0].token``
from this response, not the JWT (using the JWT was the historic cause of
"hello works, login rejected").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from securelogging import add_secret

from aioafero.errors import AferoError
from aioafero.v1 import v1_const

if TYPE_CHECKING:  # pragma: no cover
    from aioafero.v1 import AferoBridgeV1


CONCLAVE_ACCESS_ENDPOINT = "/v1/accounts/{}/conclaveAccess"


@dataclass(frozen=True)
class ConclaveAccess:
    """Parsed response from ``POST .../conclaveAccess``.

    :param host: TLS host for the Conclave socket
        (e.g. ``conclave-stream1.afero.net``).
    :param port: TLS port for the Conclave socket.
    :param ssl: ``True`` when the server advertises TLS (always ``True``
        in observed captures).
    :param compression: ``True`` when the server announces zlib compression
        on the wire (the initial ``hello`` is sent as a single zlib blob).
    :param token: Short-lived single-use Conclave socket access token. **Not**
        the OAuth bearer — pass this as ``login.accessToken``.
    :param channel_id: Conclave channel ID (the account UUID).
    :param expires_timestamp: Optional epoch milliseconds at which ``token``
        expires; observed tokens may also be single-use, so callers should
        always mint a fresh token on reconnect rather than trust this clock.
    """

    host: str
    port: int
    ssl: bool
    compression: bool
    token: str
    channel_id: str
    expires_timestamp: int | None = None


async def request_conclave_access(
    bridge: AferoBridgeV1,
    *,
    user: bool = True,
    soft_hub: bool = False,
) -> ConclaveAccess:
    """Mint a fresh Conclave access token.

    Always call this on first connect and on every reconnect — observed
    tokens are short-lived and may be single-use.

    :param bridge: Initialized :class:`~aioafero.v1.AferoBridgeV1`; the bearer
        token and account ID are read from the bridge.
    :param user: Set ``True`` for end-user clients (the only mode observed in
        captures). Always ``True`` for HA / app-style consumers.
    :param soft_hub: Set ``True`` only for soft-hub clients. Token shape and
        channel routing for ``softHub=true`` are not yet captured — leave
        ``False`` unless you have verified the response shape.

    :returns: Parsed :class:`ConclaveAccess`.

    :raises AferoError: If the response is missing the conclave host or
        an account-scoped token.
    """
    endpoint = CONCLAVE_ACCESS_ENDPOINT.format(bridge.account_id)
    url = bridge.generate_api_url(endpoint)
    headers = {
        "host": v1_const.AFERO_CLIENTS[bridge.afero_client]["API_HOST"],
        "content-type": "application/json; charset=utf-8",
    }
    payload = {"user": user, "softHub": soft_hub}
    res = await bridge.request("POST", url, headers=headers, json=payload)
    res.raise_for_status()
    data = await res.json()
    return _parse_conclave_access(data)


def _parse_conclave_access(data: dict) -> ConclaveAccess:
    """Validate and parse the ``conclaveAccess`` JSON payload."""
    if not isinstance(data, dict):
        raise AferoError("conclaveAccess response is not a JSON object")
    conclave = data.get("conclave")
    if not isinstance(conclave, dict):
        raise AferoError("conclaveAccess response is missing 'conclave' block")
    host = _require_non_empty_str(
        conclave.get("host"),
        "conclaveAccess response is missing host/port",
    )
    port = _require_positive_port(
        conclave.get("port"),
        "conclaveAccess response is missing host/port",
    )
    token_entry = _select_account_token(data.get("tokens"))
    if token_entry is None:
        raise AferoError("conclaveAccess response is missing an account token")
    token = _require_non_empty_str(
        token_entry.get("token"),
        "conclaveAccess account token is missing token/channelId",
    )
    channel_id = _require_non_empty_str(
        token_entry.get("channelId"),
        "conclaveAccess account token is missing token/channelId",
    )
    add_secret(token)
    return ConclaveAccess(
        host=host,
        port=port,
        ssl=bool(conclave.get("ssl", True)),
        compression=bool(conclave.get("compression", True)),
        token=token,
        channel_id=channel_id,
        expires_timestamp=_coerce_int(token_entry.get("expiresTimestamp")),
    )


def _require_non_empty_str(value: object, message: str) -> str:
    """Return ``value`` when it is a non-empty string; otherwise raise."""
    if not isinstance(value, str) or not value.strip():
        raise AferoError(message)
    return value


def _require_positive_port(value: object, message: str) -> int:
    """Return a positive TCP port from ``value``; otherwise raise."""
    try:
        port = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise AferoError(message) from None
    if port <= 0:
        raise AferoError(message)
    return port


def _select_account_token(raw_tokens: object) -> dict | None:
    """Pick the account-scoped token from ``tokens[]``.

    Captures always return ``type: "account"`` first; fall back to the first
    entry if a future deployment reshuffles ordering.
    """
    tokens = raw_tokens if isinstance(raw_tokens, list) else []
    for entry in tokens:
        if isinstance(entry, dict) and entry.get("type") == "account":
            return entry
    first = tokens[0] if tokens else None
    return first if isinstance(first, dict) else None


def _coerce_int(value: object) -> int | None:
    """Best-effort int coercion for optional timestamp fields."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
