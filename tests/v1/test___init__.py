import pytest

from aioafero import EventType, InvalidAuth
from aioafero.errors import DeviceNotFound
from aioafero.v1.controllers.device import DeviceController
from aioafero.v1.controllers.event import EventStream
from aioafero.v1.controllers.fan import FanController
from aioafero.v1.controllers.light import LightController
from aioafero.v1.controllers.lock import LockController
from aioafero.v1.controllers.switch import SwitchController
from aioafero.v1.controllers.valve import ValveController

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
    mocked_bridge.fans._initialized = False
    mocked_bridge.lights._initialized = False
    mocked_bridge.locks._initialized = True
    mocked_bridge.switches._initialized = False
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
async def test_get_account_id():
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
        with pytest.raises(ValueError):
            await mocked_bridge_req.fetch_data()


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
        async with mocked_bridge.create_request("get", "https://not-called.io"):
            pass

    emit.assert_called_once_with(EventType.INVALID_AUTH)
