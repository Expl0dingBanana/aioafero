import pytest

from aioafero.v1.conclave.access import ConclaveAccess
from aioafero.v1.conclave.protocol import (
    build_login_frame,
    parse_private_frame,
    server_heartbeat_seconds,
)


def test_build_login_frame_uses_access_token():
    access = ConclaveAccess(
        host="conclave-stream1.afero.net",
        port=443,
        ssl=True,
        compression=True,
        token="socket-token",
        channel_id="account-uuid",
    )
    frame = build_login_frame(access)
    login = frame["login"]
    assert login["channelId"] == "account-uuid"
    assert login["accessToken"] == "socket-token"
    assert login["type"] == "aioafero"
    assert login["protocol"] == 2
    assert login["trace"] is False


def test_parse_private_frame_attr_change():
    frame = {
        "private": {
            "event": "attr_change",
            "data": {"id": "abc", "attribute": {"id": 1, "value": "1"}},
        }
    }
    parsed = parse_private_frame(frame)
    assert parsed is not None
    assert parsed.event == "attr_change"
    assert parsed.data["id"] == "abc"


def test_server_heartbeat_seconds_reads_welcome_then_handshake():
    assert (
        server_heartbeat_seconds(
            {"hello": {"heartbeat": 30}},
            {"welcome": {"heartbeat": 45}},
        )
        == 45.0
    )
    assert server_heartbeat_seconds({"tunnel": {"heartbeat": 90}}, {}) == 90.0
    assert server_heartbeat_seconds({}, {}) == 60.0


@pytest.mark.parametrize(
    "heartbeat",
    ["not-a-number", -1, 0],
)
def test_server_heartbeat_seconds_skips_invalid_values(heartbeat):
    assert server_heartbeat_seconds({"hello": {"heartbeat": heartbeat}}, {}) == 60.0


def test_parse_private_frame_rejects_malformed():
    assert parse_private_frame({}) is None
    assert parse_private_frame({"private": None}) is None
    assert parse_private_frame({"private": {"event": "x", "data": "nope"}}) is None
