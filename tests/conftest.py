import datetime
import inspect
from unittest.mock import Mock

import aiohttp
from aioresponses import aioresponses
import pytest
import pytest_asyncio
import securelogging

from aioafero import AferoDevice
from aioafero.v1 import AferoBridgeV1
from aioafero.v1.auth import TokenData
from aioafero.v1.controllers.base import dataclass_to_afero
from tests.v1.utils import create_hs_raw_from_device


def _patch_aioresponses_for_aiohttp_314() -> None:
    """Default stream_writer for mocked ClientResponse on aiohttp 3.14+.

    aioresponses 0.7.8 constructs ClientResponse without the stream_writer
    argument that aiohttp 3.14 made required. Remove once aioresponses ships
    the fix (see pnuckowski/aioresponses#288).
    """
    if (
        "stream_writer"
        not in inspect.signature(aiohttp.ClientResponse.__init__).parameters
    ):
        return
    if getattr(aiohttp.ClientResponse.__init__, "_aioafero_aiohttp314_patch", False):
        return
    original_init = aiohttp.ClientResponse.__init__

    def client_response_init(self, method, url, **kwargs):
        if "stream_writer" not in kwargs:
            kwargs["stream_writer"] = Mock(output_size=0)
        return original_init(self, method, url, **kwargs)

    client_response_init._aioafero_aiohttp314_patch = True  # type: ignore[attr-defined]
    aiohttp.ClientResponse.__init__ = client_response_init  # type: ignore[method-assign]


_patch_aioresponses_for_aiohttp_314()


@pytest.fixture(autouse=True)
def reset_logging_secrets():
    securelogging._called_from_test = True
    securelogging.reset_secrets()


@pytest_asyncio.fixture(scope="function")
async def aio_sess() -> aiohttp.ClientSession:
    session = aiohttp.ClientSession()
    yield session
    if not session.closed:
        await session.close()


@pytest_asyncio.fixture
async def mocked_bridge(mocker, aio_sess) -> AferoBridgeV1:
    """Create a mocked afero bridge to be used in tests."""
    mocker.patch("time.time", return_value=12345)
    mocker.patch("aioafero.v1.controllers.event.EventStream.gather_discovery_data")

    bridge: AferoBridgeV1 = AferoBridgeV1(
        "username2", "mock-refresh-token", session=aio_sess
    )
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "fetch_discovery_data", return_value=[])
    mocker.patch.object(bridge.events, "initialize_discovery")
    mocker.patch.object(bridge, "request", side_effect=mocker.AsyncMock())
    mocker.patch.object(
        bridge, "fetch_discovery_data", side_effect=mocker.AsyncMock(return_value=[])
    )
    mocker.patch.object(bridge.events, "_first_poll_completed", True)
    bridge._close_session = False

    bridge.set_token_data(
        TokenData(
            "mock-token",
            "mock-access",
            "mock-refresh-token",
            expiration=datetime.datetime.now().timestamp() + 200,
        )
    )

    # Fake a poll for discovery
    async def generate_devices_from_data(devices: list[AferoDevice]):
        raw_data = [create_hs_raw_from_device(device) for device in devices]
        mocker.patch(
            "aioafero.v1.controllers.event.EventStream.gather_discovery_data",
            return_value=raw_data,
        )
        await bridge.events.generate_events_from_data(raw_data)
        await bridge.async_block_until_done()

    # Fake the response from the API when updating states
    def mock_update_afero_api(device_id, result):
        json_resp = mocker.AsyncMock()
        json_resp.return_value = {"metadeviceId": device_id, "values": result}
        resp = mocker.AsyncMock()
        resp.json = json_resp
        resp.status = 200
        mocker.patch(
            "aioafero.v1.controllers.base.BaseResourcesController.update_afero_api",
            return_value=resp,
        )

    # Enable "results" to be returned on update
    actual_dataclass_to_afero = dataclass_to_afero

    def mocked_dataclass_to_afero(*args, **kwargs):
        result = actual_dataclass_to_afero(*args, **kwargs)
        mock_update_afero_api(args[0].id, result)
        return result

    mocker.patch(
        "aioafero.v1.controllers.base.dataclass_to_afero",
        side_effect=mocked_dataclass_to_afero,
    )

    bridge.mock_update_afero_api = mock_update_afero_api
    bridge.generate_devices_from_data = generate_devices_from_data

    await bridge.initialize()
    yield bridge
    await bridge.close()


@pytest.fixture
def mocked_bridge_req(mocker, aio_sess):
    bridge: AferoBridgeV1 = AferoBridgeV1(
        "username2", "mock-refresh-token", session=aio_sess
    )
    mocker.patch.object(
        bridge,
        "get_account_id",
        side_effect=mocker.AsyncMock(return_value="mocked-account-id"),
    )
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "initialize", side_effect=mocker.AsyncMock())
    mocker.patch.object(
        bridge, "fetch_discovery_data", side_effect=bridge.fetch_discovery_data
    )
    mocker.patch.object(bridge, "request", side_effect=bridge.request)
    bridge._close_session = False
    mocker.patch.object(bridge.events, "_first_poll_completed", True)
    bridge.set_token_data(
        TokenData(
            "mock-token",
            None,
            "mock-refresh-token",
            expiration=datetime.datetime.now().timestamp() + 200,
        )
    )
    # Force initialization so test elements are not overwritten
    for controller in bridge._controllers.values():
        controller._initialized = True

    return bridge


@pytest_asyncio.fixture
async def bridge(mocker, aio_sess):
    bridge = AferoBridgeV1("user", "mock-refresh-token", aio_sess)
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "fetch_discovery_data", return_value=[])
    mocker.patch.object(bridge, "request", side_effect=mocker.AsyncMock())
    mocker.patch.object(bridge.events, "_first_poll_completed", True)
    await bridge.initialize()
    await bridge.async_block_until_done()
    yield bridge
    await bridge.close()


@pytest_asyncio.fixture
async def bridge_with_acct(mocker, aio_sess):
    bridge = AferoBridgeV1("user", "mock-refresh-token", aio_sess)
    bridge.set_token_data(
        TokenData(
            "mock-token",
            None,
            "mock-refresh-token",
            expiration=datetime.datetime.now().timestamp() + 200,
        )
    )
    yield bridge
    await bridge.close()


@pytest_asyncio.fixture
async def bridge_with_acct_req(mocker, aio_sess):
    bridge = AferoBridgeV1("user", "mock-refresh-token", aio_sess)
    mocker.patch.object(bridge, "_account_id", "mocked-account-id")
    mocker.patch.object(bridge, "request", side_effect=bridge.request)
    mocker.patch.object(bridge.events, "_first_poll_completed", True)
    bridge.set_token_data(
        TokenData(
            "mock-token",
            None,
            "mock-refresh-token",
            expiration=datetime.datetime.now().timestamp() + 200,
        )
    )
    await bridge.initialize()
    await bridge.async_block_until_done()
    yield bridge
    await bridge.close()


@pytest.fixture
def mock_aioresponse():
    with aioresponses() as m:
        yield m
