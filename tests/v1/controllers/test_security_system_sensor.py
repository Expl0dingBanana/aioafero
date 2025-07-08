"""Test Security System Sensor"""

import asyncio
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
)

from .. import utils

security_system = utils.create_devices_from_data("security-system.json")[1]

security_system_sensors = security_system_callback(
    utils.create_devices_from_data("security-system.json")
)
security_system_sensor_2 = security_system_sensors[1]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = SecuritySystemSensorController(mocked_bridge)
    yield controller


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(security_system_sensor_2)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.available is True
    assert dev.id == "7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"
    assert dev.update_id == "7f4e4c01-e799-45c5-9b1a-385433a78edc"
    assert dev.sensor_id == 2
    assert dev.sensors == {
        "battery-level": AferoSensor(
            id="sensor-state",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            _value=100,
            unit="%",
            instance=None,
        ),
    }
    assert dev.binary_sensors == {
        "tampered": AferoBinarySensor(
            id="tampered",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            _value=0,
            _error=1,
            unit=None,
            instance="tampered",
        ),
        "triggered": AferoBinarySensor(
            id="triggered",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            _value=1,
            _error=1,
            unit=None,
            instance="triggered",
        ),
    }
    assert dev.selects == {
        ("sensor-2", "bypassType"): features.SelectFeature(
            selected="Off",
            selects={
                "Off",
                "On",
            },
            name="Can Be Bypassed",
        ),
        ("sensor-2", "chirpMode"): features.SelectFeature(
            selected="Off",
            selects={
                "Off",
                "On",
            },
            name="Chirp Mode",
        ),
        ("sensor-2", "triggerType"): features.SelectFeature(
            selected="Home/Away",
            selects={
                "Away",
                "Home",
                "Home/Away",
                "Off",
            },
            name="Triggers",
        ),
    }


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(security_system_sensor_2)
    assert len(mocked_controller.items) == 1
    dev_update = copy.deepcopy(security_system_sensor_2)
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
    updates = await mocked_controller.update_elem(dev_update)
    assert updates == {
        "battery-level",
        "bypassType",
        "chirpMode",
        "tampered",
        "triggerType",
        "triggered",
        "available",
    }
    dev = mocked_controller.items[0]
    assert dev.available is False
    assert dev.sensors == {
        "battery-level": AferoSensor(
            id="sensor-state",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            _value=95,
            unit="%",
            instance=None,
        ),
    }
    assert dev.binary_sensors == {
        "tampered": AferoBinarySensor(
            id="tampered",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            _value=1,
            _error=1,
            unit=None,
            instance="tampered",
        ),
        "triggered": AferoBinarySensor(
            id="triggered",
            owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
            _value=0,
            _error=1,
            unit=None,
            instance="triggered",
        ),
    }
    assert dev.selects == {
        ("sensor-2", "bypassType"): features.SelectFeature(
            selected="On",
            selects={
                "Off",
                "On",
            },
            name="Can Be Bypassed",
        ),
        ("sensor-2", "chirpMode"): features.SelectFeature(
            selected="On",
            selects={
                "Off",
                "On",
            },
            name="Chirp Mode",
        ),
        ("sensor-2", "triggerType"): features.SelectFeature(
            selected="Away",
            selects={
                "Away",
                "Home",
                "Home/Away",
                "Off",
            },
            name="Triggers",
        ),
    }


@pytest.mark.asyncio
async def test_update_security_sensor_no_updates(mocked_controller):
    await mocked_controller.initialize_elem(security_system_sensor_2)
    assert len(mocked_controller.items) == 1
    updates = await mocked_controller.update_elem(security_system_sensor_2)
    assert updates == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "device",
        "updates",
        "expected_updates",
    ),
    [
        # Selects are updated
        (
            security_system_sensor_2,
            {
                "selects": {
                    ("sensor-2", "chirpMode"): "On",
                    ("sensor-2", "triggerType"): "Away",
                    ("sensor-2", "bypassType"): "On",
                    ("sensor-2", "doesnt_exist"): "On",
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
async def test_set_state(device, updates, expected_updates, mocked_controller):
    await mocked_controller.initialize_elem(device)
    await mocked_controller.set_state(device.id, **updates)
    utils.ensure_states_sent(
        mocked_controller,
        expected_updates,
        device_id="7f4e4c01-e799-45c5-9b1a-385433a78edc",
    )


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
async def test_emitting(bridge):
    # Simulate the discovery process
    await bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("security-system.json")
    )
    # @TODO - Determine why bridge.async_block_until_done is not successfully stopping for these
    # await bridge.async_block_until_done()
    await asyncio.sleep(1)
    assert len(bridge.security_systems_sensors._items) == 3
    dev_update = copy.deepcopy(security_system_sensor_2)
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
    update_event = {
        "type": "update",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    bridge.events.emit(event.EventType.RESOURCE_UPDATED, update_event)
    await bridge.async_block_until_done()
    assert len(bridge.security_systems_sensors._items) == 3
    assert not bridge.security_systems_sensors._items[dev_update.id].available
