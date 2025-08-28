import asyncio
import logging

import pytest

from aioafero import EventType, InvalidAuth
from aioafero.errors import DeviceNotFound, AferoError, ExceededMaximumRetries
from aioafero.v1 import AferoBridgeV1, TokenData, add_secret, v1_const
from aioafero.v1.controllers.device import DeviceController
from aioafero.v1.controllers.event import EventStream
from aioafero.v1.controllers.fan import FanController
from aioafero.v1.controllers.light import LightController
from aioafero.v1.controllers.lock import LockController
from aioafero.v1.controllers.switch import SwitchController
from aioafero.v1.controllers.valve import ValveController
from aiohttp.client_exceptions import ClientResponseError

from . import utils

zandra_light = utils.create_devices_from_data("fan-ZandraFan.json")[1]


@pytest.mark.skip(reason="Not yet implemented")
def test_context_manager(mocked_bridge):
    pass


def test_devices(mocked_bridge):
    assert isinstance(mocked_bridge.devices, DeviceController)


def test_events(mocked_bridge):
    assert isinstance(mocked_bridge.events, EventStream)


def test_fans(mocked_bridge):
    assert isinstance(mocked_bridge.fans, FanController)


def test_lights(mocked_bridge):
    assert isinstance(mocked_bridge.lights, LightController)


def test_locks(mocked_bridge):
    assert isinstance(mocked_bridge.locks, LockController)


def test_switches(mocked_bridge):
    assert isinstance(mocked_bridge.switches, SwitchController)


def test_valves(mocked_bridge):
    assert isinstance(mocked_bridge.valves, ValveController)


def test_controllers(mocked_bridge):
    mocked_bridge.devices._initialized = False
    mocked_bridge.exhaust_fans._initialized = False
    mocked_bridge.fans._initialized = False
    mocked_bridge.lights._initialized = False
    mocked_bridge.locks._initialized = True
    mocked_bridge.portable_acs._initialized = False
    mocked_bridge.security_systems._initialized = False
    mocked_bridge.security_systems_sensors._initialized = False
    mocked_bridge.switches._initialized = False
    mocked_bridge.thermostats._initialized = False
    mocked_bridge.valves._initialized = True
    assert mocked_bridge.controllers == [mocked_bridge.locks, mocked_bridge.valves]
    mocked_bridge.switches._initialized = True
    assert mocked_bridge.controllers == [
        mocked_bridge.locks,
        mocked_bridge.switches,
        mocked_bridge.valves,
    ]


def test_tracked_devices(mocked_bridge):
    assert mocked_bridge.tracked_devices == set()
    mocked_bridge.add_device(zandra_light.id, mocked_bridge.lights)
    assert mocked_bridge.tracked_devices == {zandra_light.id}


def test_add_device(mocked_bridge):
    assert mocked_bridge.tracked_devices == set()
    mocked_bridge.add_device(zandra_light.id, mocked_bridge.lights)
    assert mocked_bridge.tracked_devices == {zandra_light.id}
    assert mocked_bridge._known_devs == {zandra_light.id: mocked_bridge.lights}


def test_remove_device(mocked_bridge):
    assert mocked_bridge.tracked_devices == set()
    mocked_bridge.add_device(zandra_light.id, mocked_bridge.lights)
    assert mocked_bridge.tracked_devices == {zandra_light.id}
    assert mocked_bridge._known_devs == {zandra_light.id: mocked_bridge.lights}
    mocked_bridge.remove_device(zandra_light.id)
    assert mocked_bridge.tracked_devices == set()
    assert mocked_bridge._known_devs == {}


def test_set_polling_interval(mocked_bridge):
    assert mocked_bridge.events._polling_interval == 30
    mocked_bridge.set_polling_interval(10)
    assert mocked_bridge.events._polling_interval == 10


@pytest.mark.skip(reason="Not yet implemented")
@pytest.mark.asyncio
async def test_close():
    pass


@pytest.mark.skip(reason="Not yet implemented")
def test_subscribe():
    pass


@pytest.mark.skip(reason="Not yet implemented")
@pytest.mark.asyncio
async def test_initialize():
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expected_val,error",
    [
        # good data
        ([], False),
        # bad data
        ("i dont know", True),
    ],
)
async def test_fetch_data(expected_val, error, mocked_bridge_req, mocker):
    expected = mocker.Mock()
    mocker.patch.object(
        expected, "json", side_effect=mocker.AsyncMock(return_value=expected_val)
    )
    mocker.patch.object(mocked_bridge_req, "request", return_value=expected)
    if not error:
        assert await mocked_bridge_req.fetch_data() == expected_val
    else:
        with pytest.raises(TypeError):
            await mocked_bridge_req.fetch_data()


def fake_version_data(*args, **kwargs):
    yield {"version": "1.0.0"}
    yield {"version": "2.0.0"}


@pytest.mark.asyncio
async def test_fetch_data_with_version(mocked_bridge_req, mocker):
    get_device_versions = mocker.patch.object(mocked_bridge_req, "get_device_version", side_effect=fake_version_data())
    mocked_response = [
        {
            "typeId": "metadevice.room"
        },
        {
            "typeId": "metadevice.device",
            "deviceId": "test_device_id",
        },
        {
            "typeId": "metadevice.device",
            "deviceId": "test_device_id2",
        },
        {
            "typeId": "metadevice.device",
            "deviceId": "test_device_id",
        },
    ]
    expected = mocker.Mock()
    mocker.patch.object(
        expected, "json", side_effect=mocker.AsyncMock(return_value=mocked_response)
    )
    mocker.patch.object(mocked_bridge_req, "request", return_value=expected)
    resp = await mocked_bridge_req.fetch_data(version_poll=True)
    assert get_device_versions.call_count == 2
    assert get_device_versions.call_args_list[0][0][0] == "test_device_id"
    assert get_device_versions.call_args_list[1][0][0] == "test_device_id2"
    assert resp == [
        {'typeId': 'metadevice.room'},
        {'typeId': 'metadevice.device', 'deviceId': 'test_device_id', 'version_data': {'version': '1.0.0'}},
        {'typeId': 'metadevice.device', 'deviceId': 'test_device_id2', 'version_data': {'version': '2.0.0'}},
        {'typeId': 'metadevice.device', 'deviceId': 'test_device_id', 'version_data': {'version': '1.0.0'}}
    ]


@pytest.mark.asyncio
async def test_get_device_versions(mocked_bridge, mocker):
    req = mocker.patch.object(mocked_bridge, "request")
    await mocked_bridge.get_device_version("test_device_id")
    req.assert_called_once_with("GET", "https://api2.afero.net/v1/accounts/mocked-account-id/devices/test_device_id/versions")


@pytest.mark.asyncio
async def test_send_service_request_dev_not_found(mocked_bridge):
    with pytest.raises(DeviceNotFound):
        await mocked_bridge.send_service_request("no", [{}])


@pytest.mark.asyncio
async def test_send_service_request(mocked_bridge):
    controller = mocked_bridge.lights
    await controller.initialize_elem(zandra_light)
    mocked_bridge.add_device(zandra_light.id, controller)
    assert controller[zandra_light.id].on.on is True
    await mocked_bridge.send_service_request(
        zandra_light.id,
        [{"functionClass": "power", "functionInstance": "light-power", "value": "off"}],
    )
    assert controller[zandra_light.id].on.on is False


@pytest.mark.asyncio
async def test_create_request_err(mocked_bridge, mocker):
    mocker.patch.object(mocked_bridge._auth, "token", side_effect=InvalidAuth)
    emit = mocker.patch.object(mocked_bridge.events, "emit")
    with pytest.raises(InvalidAuth):
        async with mocked_bridge.create_request("get", "https://not-called.io", True):
            pass

    emit.assert_called_once_with(EventType.INVALID_AUTH)


@pytest.mark.parametrize(
    "hide_secrets",
    [True, False],
)
def test_AferoBridgeV1_hide_secrets(hide_secrets, caplog):
    caplog.set_level(logging.DEBUG)
    bridge = AferoBridgeV1("username", "password", hide_secrets=hide_secrets)
    secret = "this-is-super-secret-beans"
    add_secret(secret)
    with bridge.secret_logger():
        bridge.logger.debug(secret)
    if hide_secrets:
        assert "th***ns" in caplog.text
    else:
        assert secret in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("account_id", "response", "expected", "err"),
    [
        # Uninitialized, happy patch
        (
            None,
            {
                "status": 200,
                "payload": {
                    "accountAccess": [
                        {
                            "account": {
                                "accountId": "test_account_id"
                            }
                        }
                    ]
                }
            },
            "test_account_id",
            None,
        ),
        # Uninitialized, bad status
        (
            None,
            {
                "status": 400,
                "payload": {
                    "accountAccess": [
                        {
                            "account": {
                                "accountId": "test_account_id"
                            }
                        }
                    ]
                }
            },
            None,
            ClientResponseError,
        ),
        # Uninitialized, bad response
        (
            None,
            {
                "status": 200,
                "payload": {
                }
            },
            None,
            AferoError,
        ),
        # Initialized, dont do anything
        (
            "mocked-account-id",
            None,
            "mocked-account-id",
            None,
        )
    ]
)
async def test_get_account_id(account_id, response, expected, err, mock_aioresponse, bridge_with_acct, mocker):
    bridge = bridge_with_acct
    mocker.patch.object(bridge, "_account_id", account_id)
    if account_id is None:
        url = bridge.generate_api_url(v1_const.AFERO_GENERICS["ACCOUNT_ID_ENDPOINT"])
        mock_aioresponse.get(url, payload=response["payload"], status=response["status"])
        if not err:
            assert await bridge.get_account_id() == expected
        else:
            with pytest.raises(err):
                await bridge.get_account_id()
    else:
        logger = mocker.patch.object(bridge_with_acct, "logger")
        await bridge.get_account_id()
        logger.assert_not_called()


class DummyResponse:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def read(self):
        return "cool-beans"


def test_set_token_data(mocked_bridge):
    data = TokenData(
        "token",
        "access_token",
        "refresh_token",
        12345,
    )
    mocked_bridge.set_token_data(data)
    assert mocked_bridge.refresh_token == "refresh_token"


@pytest.mark.asyncio
async def test_cleanup_process(mocked_bridge_req):
    mocked_bridge_req.add_job(asyncio.create_task(asyncio.sleep(1)))
    assert len(mocked_bridge_req._adhoc_tasks) == 1
    await mocked_bridge_req.initialize_cleanup()
    await mocked_bridge_req.async_block_until_done()
    assert len(mocked_bridge_req._adhoc_tasks) == 0
    await mocked_bridge_req.close()


@pytest.mark.asyncio
async def test_double_initialize(bridge):
    assert len(bridge._scheduled_tasks) == 1
    await bridge.initialize()
    assert len(bridge._scheduled_tasks) == 1


class AsyncContextManagerMock:
    def __init__(self):
        self.total = 0

    async def __aenter__(self):
        status_code = 429 if self.total < 2 else 200
        self.total += 1
        return DummyResponse(status=status_code)

    async def __aexit__(self, exc_type, exc, tb):
        pass



@pytest.mark.asyncio
@pytest.mark.parametrize(
    "max_retries, times_to_sleep, response_gen, exp_error", [
        # Out of retries
        (
            0, 0, None, ExceededMaximumRetries
        ),
        # Double retry
        (
            None, 2, True, None
        )
    ]
)
async def test_request(max_retries, times_to_sleep, response_gen, exp_error, mocker):
    bridge = AferoBridgeV1("username", "password")
    mock_sleep = mocker.patch("asyncio.sleep", new=mocker.AsyncMock())
    if response_gen:
        async_mock_response = AsyncContextManagerMock()
        mocker.patch.object(bridge, "create_request", return_value=async_mock_response)
    if max_retries is not None:
        mocker.patch.object(v1_const, "MAX_RETRIES", max_retries)
    if exp_error:
        with pytest.raises(exp_error):
            await bridge.request("fff", "fff")
    else:
        await bridge.request("fff", "fff")
    if times_to_sleep:
        assert mock_sleep.call_count == times_to_sleep
