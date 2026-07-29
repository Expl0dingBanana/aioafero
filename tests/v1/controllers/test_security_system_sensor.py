"""Test Security System Sensor"""

import copy

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers.security_system import security_system_callback
from aioafero.v1.controllers.security_system_sensor import AferoBinarySensor, features
from tests.v1 import utils

security_system = utils.create_devices_from_data("security-system.json")[1]
security_system_sensors = security_system_callback(
    utils.create_devices_from_data("security-system.json")[1]
).split_devices
security_system_sensor_2 = security_system_sensors[1]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.security_systems_sensors


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data([security_system])
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 3
    dev = mocked_controller["7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"]
    assert dev.available is True
    assert dev.id == "7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"
    assert dev.update_id == "7f4e4c01-e799-45c5-9b1a-385433a78edc"
    assert dev.instance == 2
    assert dev.sensors == {}
    assert dev.binary_sensors == {
        "tampered|None": AferoBinarySensor(
            id="tampered|None",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            current_value="Off",
            _error="On",
            unit=None,
            instance=None,
        ),
        "triggered|None": AferoBinarySensor(
            id="triggered|None",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            current_value="On",
            _error="On",
            unit=None,
            instance=None,
        ),
    }
    assert dev.selects == {
        ("bypassType", None): features.SelectFeature(
            function_class="bypassType",
            function_instance=None,
            selected="Off",
            selects={
                "Off",
                "Manual",
                "On",
            },
            name="Bypass",
        ),
        ("chirpMode", None): features.SelectFeature(
            function_class="chirpMode",
            function_instance=None,
            selected="Off",
            selects={
                "Off",
                "On",
            },
            name="Chime",
        ),
        ("triggerType", None): features.SelectFeature(
            function_class="triggerType",
            function_instance=None,
            selected="Home/Away",
            selects={
                "Away",
                "Home",
                "Home/Away",
                "Off",
            },
            name="Alarming State",
        ),
    }


@pytest.mark.asyncio
async def test_update_elem(mocked_controller, caplog):
    caplog.set_level("DEBUG")
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("security-system.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    dev_update = copy.deepcopy(security_system_sensor_2)
    new_states = [
        AferoState(
            functionClass="chirpMode",
            value="On",
            lastUpdateTime=None,
            functionInstance=None,
        ),
        AferoState(
            functionClass="triggerType",
            value="Away",
            lastUpdateTime=None,
            functionInstance=None,
        ),
        AferoState(
            functionClass="bypassType",
            value="Manual",
            lastUpdateTime=None,
            functionInstance=None,
        ),
        AferoState(
            functionClass="top-level-key",
            value="security-sensor-config-v2",
            lastUpdateTime=None,
            functionInstance=None,
        ),
        AferoState(
            functionClass="tampered",
            value="On",
            lastUpdateTime=None,
            functionInstance=None,
        ),
        AferoState(
            functionClass="triggered",
            value="Off",
            lastUpdateTime=None,
            functionInstance=None,
        ),
        AferoState(
            functionClass="available",
            value=False,
            lastUpdateTime=None,
            functionInstance=None,
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    await mocked_controller._bridge.async_block_until_done()
    assert updates == {
        "select-('bypassType', None)",
        "select-('chirpMode', None)",
        "binary-tampered|None",
        "select-('triggerType', None)",
        "binary-triggered|None",
        "available",
    }
    dev = mocked_controller[security_system_sensor_2.id]
    assert dev.available is False
    assert dev.sensors == {}
    assert dev.binary_sensors == {
        "tampered|None": AferoBinarySensor(
            id="tampered|None",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            current_value="On",
            _error="On",
            unit=None,
            instance=None,
        ),
        "triggered|None": AferoBinarySensor(
            id="triggered|None",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            current_value="Off",
            _error="On",
            unit=None,
            instance=None,
        ),
    }
    assert dev.selects == {
        ("bypassType", None): features.SelectFeature(
            function_class="bypassType",
            function_instance=None,
            selected="Manual",
            selects={
                "Off",
                "Manual",
                "On",
            },
            name="Bypass",
        ),
        ("chirpMode", None): features.SelectFeature(
            function_class="chirpMode",
            function_instance=None,
            selected="On",
            selects={
                "Off",
                "On",
            },
            name="Chime",
        ),
        ("triggerType", None): features.SelectFeature(
            function_class="triggerType",
            function_instance=None,
            selected="Away",
            selects={
                "Away",
                "Home",
                "Home/Away",
                "Off",
            },
            name="Alarming State",
        ),
    }


@pytest.mark.asyncio
async def test_update_security_sensor_no_updates(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("security-system.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    updates = await mocked_controller.update_elem(security_system_sensor_2)
    assert updates == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "device",
        "updates",
    ),
    [
        # Selects are updated
        (
            security_system_sensor_2,
            {
                "selects": {
                    ("chirpMode", None): "On",
                    ("triggerType", None): "Away",
                    ("bypassType", None): "On",
                    ("doesnt_exist", None): "On",
                }
            },
        ),
    ],
)
async def test_set_state(device, updates, mocked_controller, mocker):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("security-system.json")
    )
    await bridge.async_block_until_done()
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(device.id, **updates)
    await bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        security_system.id,
        [
            {
                "functionClass": "sensor-config",
                "functionInstance": "sensor-2",
                "value": {
                    "security-sensor-config-v2": {
                        "chirpMode": 1,
                        "triggerType": 2,
                        "bypassType": 4,
                    }
                },
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    dev = mocked_controller["7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"]
    assert dev.selects[("chirpMode", None)].selected == "On"
    assert dev.selects[("triggerType", None)].selected == "Away"
    assert dev.selects[("bypassType", None)].selected == "On"


@pytest.mark.asyncio
async def test_set_state_bad_device(mocked_controller, mocker):
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(
        "bad device",
        selects={
            "selects": {
                ("sensor-2", "chirpMode"): "On",
                ("sensor-2", "triggerType"): "Away",
                ("sensor-2", "bypassType"): "On",
            }
        },
    )
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_states_nothing(mocked_controller, mocker):
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("security-system.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(
        security_system_sensor_2.id,
    )
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_emitting(mocked_bridge):
    # Simulate the discovery process
    await mocked_bridge.generate_devices_from_data([security_system])
    await mocked_bridge.async_block_until_done()
    assert len(mocked_bridge.security_systems_sensors._items) == 3
    dev_update = copy.deepcopy(security_system)
    # Simulate an update
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="sensor-state",
            functionInstance="sensor-2",
            value={
                "security-sensor-state": {
                    "deviceType": 2,
                    "tampered": 0,
                    "triggered": 1,
                    "missing": 1,
                    "versionBuild": 3,
                    "versionMajor": 2,
                    "versionMinor": 0,
                    "batteryLevel": 100,
                }
            },
        ),
    )
    await mocked_bridge.generate_devices_from_data([dev_update])
    await mocked_bridge.async_block_until_done()
    assert len(mocked_bridge.security_systems_sensors._items) == 3
    assert not mocked_bridge.security_systems_sensors._items[
        "7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"
    ].available
