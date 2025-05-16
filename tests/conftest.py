import datetime

import pytest
import pytest_asyncio
from aioresponses import aioresponses

from aioafero.v1 import AferoBridgeV1
from aioafero.v1.auth import token_data
from aioafero.v1.controllers.event import EventType


@pytest.fixture
def mocked_bridge(mocker):
    bridge: AferoBridgeV1 = AferoBridgeV1("username2", "password2")
    mocker.patch.object(
        bridge,
        "get_account_id",
        side_effect=mocker.AsyncMock(return_value="mocked-account-id"),
    )
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "fetch_data", return_value=[])
    mocker.patch.object(bridge, "request", side_effect=mocker.AsyncMock())
    mocker.patch.object(bridge, "initialize", side_effect=mocker.AsyncMock())
    # Force initialization so test elements are not overwritten
    for controller in bridge._controllers:
        controller._initialized = True

    # Enable ad-hoc event updates
    def emit_event(event_type, data):
        bridge.events.emit(EventType(event_type), data)

    bridge.emit_event = emit_event
    bridge.__aenter__ = mocker.AsyncMock(return_value=bridge)
    bridge.__aexit__ = mocker.AsyncMock()
    yield bridge


@pytest.fixture
def mocked_bridge_req(mocker):
    bridge: AferoBridgeV1 = AferoBridgeV1("username2", "password2")
    mocker.patch.object(
        bridge,
        "get_account_id",
        side_effect=mocker.AsyncMock(return_value="mocked-account-id"),
    )
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "initialize", side_effect=mocker.AsyncMock())
    mocker.patch.object(bridge, "fetch_data", side_effect=bridge.fetch_data)
    mocker.patch.object(bridge, "request", side_effect=bridge.request)
    bridge._auth._token_data = token_data(
        "mock-token",
        None,
        "mock-refresh-token",
        expiration=datetime.datetime.now().timestamp() + 200,
    )
    # Force initialization so test elements are not overwritten
    for controller in bridge._controllers:
        controller._initialized = True

    # Enable ad-hoc event updates
    def emit_event(event_type, data):
        bridge.events.emit(EventType(event_type), data)

    bridge.emit_event = emit_event
    bridge.__aenter__ = mocker.AsyncMock(return_value=bridge)
    bridge.__aexit__ = mocker.AsyncMock()
    yield bridge


@pytest_asyncio.fixture
async def bridge(mocker):
    bridge = AferoBridgeV1("user", "passwd")
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "fetch_data", return_value=[])
    mocker.patch.object(bridge, "request", side_effect=mocker.AsyncMock())
    await bridge.initialize()
    yield bridge
    await bridge.close()


@pytest.fixture
def mock_aioresponse():
    with aioresponses() as m:
        yield m
