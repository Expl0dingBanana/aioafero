from unittest.mock import AsyncMock

import pytest

from aioafero.errors import AferoError
from aioafero.v1.conclave import access


def _ok_payload(**overrides) -> dict:
    payload = {
        "conclave": {
            "host": "conclave-stream1.afero.net",
            "ssl": True,
            "compression": True,
            "port": 443,
        },
        "tokens": [
            {
                "token": "short-lived-uuid",
                "channelId": "account-uuid",
                "type": "account",
                "expiresTimestamp": 1780876821586,
                "client": {"type": "user"},
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_parse_conclave_access_happy_path():
    parsed = access._parse_conclave_access(_ok_payload())
    assert parsed.host == "conclave-stream1.afero.net"
    assert parsed.port == 443
    assert parsed.ssl is True
    assert parsed.compression is True
    assert parsed.token == "short-lived-uuid"
    assert parsed.channel_id == "account-uuid"
    assert parsed.expires_timestamp == 1780876821586


def test_parse_conclave_access_picks_account_token_first():
    payload = _ok_payload(
        tokens=[
            {"token": "user", "channelId": "c", "type": "user"},
            {"token": "acct", "channelId": "c", "type": "account"},
        ]
    )
    assert access._parse_conclave_access(payload).token == "acct"


def test_parse_conclave_access_falls_back_to_first_when_no_account_type():
    payload = _ok_payload(
        tokens=[
            {"token": "anon", "channelId": "c", "type": "unknown"},
        ]
    )
    assert access._parse_conclave_access(payload).token == "anon"


def test_parse_conclave_access_handles_invalid_expires_timestamp():
    payload = _ok_payload(
        tokens=[
            {
                "token": "t",
                "channelId": "c",
                "type": "account",
                "expiresTimestamp": "not-a-number",
            }
        ]
    )
    assert access._parse_conclave_access(payload).expires_timestamp is None


def test_parse_conclave_access_missing_expires_timestamp_is_none():
    payload = _ok_payload(tokens=[{"token": "t", "channelId": "c", "type": "account"}])
    assert access._parse_conclave_access(payload).expires_timestamp is None


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: [], "not a JSON object"),
        (lambda p: {**p, "conclave": None}, "missing 'conclave'"),
        (
            lambda p: {**p, "conclave": {"host": "", "port": 443}},
            "missing host/port",
        ),
        (
            lambda p: {**p, "conclave": {"host": "h", "port": 0}},
            "missing host/port",
        ),
        (
            lambda p: {**p, "conclave": {"host": "h", "port": "nope"}},
            "missing host/port",
        ),
        (lambda p: {**p, "tokens": []}, "missing an account token"),
        (
            lambda p: {
                **p,
                "tokens": [{"token": "", "channelId": "c", "type": "account"}],
            },
            "missing token/channelId",
        ),
    ],
)
def test_parse_conclave_access_validation_errors(mutator, match):
    with pytest.raises(AferoError, match=match):
        access._parse_conclave_access(mutator(_ok_payload()))


def test_parse_conclave_access_tokens_falsy_entry():
    payload = _ok_payload(
        tokens=[None, {"token": "t", "channelId": "c", "type": "account"}]
    )
    parsed = access._parse_conclave_access(payload)
    assert parsed.token == "t"


def test_parse_conclave_access_tokens_falsy_first_no_account():
    payload = _ok_payload(tokens=[None])
    with pytest.raises(AferoError, match="missing an account token"):
        access._parse_conclave_access(payload)


def test_parse_conclave_access_rejects_non_list_tokens():
    payload = _ok_payload()
    payload["tokens"] = "not-a-list"
    with pytest.raises(AferoError, match="missing an account token"):
        access._parse_conclave_access(payload)


@pytest.mark.asyncio
async def test_request_conclave_access_posts_and_parses(mocked_bridge, mocker):
    payload = _ok_payload()
    response = mocker.Mock()
    response.raise_for_status = mocker.Mock()
    response.json = AsyncMock(return_value=payload)
    request = mocker.patch.object(
        mocked_bridge, "request", AsyncMock(return_value=response)
    )
    parsed = await access.request_conclave_access(
        mocked_bridge, user=True, soft_hub=False
    )
    assert parsed.token == "short-lived-uuid"
    args, kwargs = request.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/v1/accounts/mocked-account-id/conclaveAccess")
    assert kwargs["json"] == {"user": True, "softHub": False}


@pytest.mark.asyncio
async def test_request_conclave_access_soft_hub_payload(mocked_bridge, mocker):
    response = mocker.Mock()
    response.raise_for_status = mocker.Mock()
    response.json = AsyncMock(return_value=_ok_payload())
    request = mocker.patch.object(
        mocked_bridge, "request", AsyncMock(return_value=response)
    )
    await access.request_conclave_access(mocked_bridge, soft_hub=True)
    assert request.call_args.kwargs["json"]["softHub"] is True
