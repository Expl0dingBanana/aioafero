"""Test Security System Sensor"""

import copy

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.security_system import security_system_callback
from aioafero.v1.controllers.security_system_sensor import (
    AferoBinarySensor,
    AferoSensor,
    SecuritySystemSensorController,
    features,
    get_valid_states
)

from .. import utils

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
            selected="Off",
            selects={
                "Off",
                "On",
            },
            name="Bypass",
        ),
        ("chirpMode", None): features.SelectFeature(
            selected="Off",
            selects={
                "Off",
                "On",
            },
            name="Chime",
        ),
        ("triggerType", None): features.SelectFeature(
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
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data([security_system])
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 3
    dev = mocked_controller["7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"]
    assert dev.available is True
    dev_update = copy.deepcopy(security_system)
    new_states = [
        AferoState(
            functionClass="sensor-state",
            value={
                "security-sensor-state": {
                    "deviceType": 2,
                    "tampered": 1,
                    "triggered": 0,
                    "missing": 1,
                    "versionBuild": 3,
                    "versionMajor": 2,
                    "versionMinor": 0,
                    "batteryLevel": 95,
                }
            },
            lastUpdateTime=0,
            functionInstance="sensor-2",
        ),
        AferoState(
            functionClass="sensor-config",
            value={
                "security-sensor-config-v2": {
                    "chirpMode": 1,
                    "triggerType": 2,
                    "bypassType": 1,
                }
            },
            lastUpdateTime=0,
            functionInstance="sensor-2",
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    await mocked_controller._bridge.generate_devices_from_data([dev_update])
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller["7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"]
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
            instance=None
        ),
    }
    assert dev.selects == {
        ("bypassType", None): features.SelectFeature(
            selected="On",
            selects={
                "Off",
                "On",
            },
            name="Bypass",
        ),
        ("chirpMode", None): features.SelectFeature(
            selected="On",
            selects={
                "Off",
                "On",
            },
            name="Chime",
        ),
        ("triggerType", None): features.SelectFeature(
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
    # Simulate the discovery process
    await mocked_controller._bridge.generate_devices_from_data([security_system])
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller._bridge.security_systems_sensors._items) == 3
    new_states = get_valid_states(security_system.states, 2)
    dev = mocked_controller["7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"]
    assert await mocked_controller._update_elem(dev, new_states) == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "device_id",
        "update_id",
        "updates",
        "expected_updates",
    ),
    [
        # Selects are updated
        (
            "7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            "7f4e4c01-e799-45c5-9b1a-385433a78edc",
            {
                "selects": {
                    ("chirpMode", None): "On",
                    ("triggerType", None): "Away",
                    ("bypassType", None): "On",
                    ("doesnt_exist", None): "On",
                }
            },
            [
                {
                    "functionClass": "sensor-config",
                    "value": {
                        "security-sensor-config-v2": {
                            "chirpMode": 1,
                            "triggerType": 2,
                            "bypassType": 1,
                        }
                    },
                    "functionInstance": "sensor-2",
                    "lastUpdateTime": 12345,
                }
            ],
        ),
    ],
)
async def test_set_state(device_id, update_id, updates, expected_updates, mocked_controller, caplog):
    caplog.set_level("DEBUG")
    await mocked_controller._bridge.generate_devices_from_data([security_system])
    await mocked_controller._bridge.async_block_until_done()
    await mocked_controller.set_state(device_id, **updates)
    await mocked_controller._bridge.async_block_until_done()
    utils.ensure_states_sent(
        mocked_controller,
        expected_updates,
        device_id=update_id,
    )
    assert mocked_controller[device_id].selects[("chirpMode", None)].selected == "On"
    assert mocked_controller[device_id].selects[("triggerType", None)].selected == "Away"
    assert mocked_controller[device_id].selects[("bypassType", None)].selected == "On"


@pytest.mark.asyncio
async def test_set_state_bad_device(mocked_controller):
    await mocked_controller.set_state(
        "bad device",
        {
            "selects": {
                ("sensor-2", "chirpMode"): "On",
                ("sensor-2", "triggerType"): "Away",
                ("sensor-2", "bypassType"): "On",
            }
        },
    )
    mocked_controller._bridge.request.assert_not_called()


@pytest.mark.asyncio
async def test_set_states_nothing(mocked_controller):
    await mocked_controller.initialize_elem(security_system_sensor_2)
    await mocked_controller.set_state(
        security_system_sensor_2.id,
    )
    mocked_controller._bridge.request.assert_not_called()


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
    assert not mocked_bridge.security_systems_sensors._items["7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"].available
