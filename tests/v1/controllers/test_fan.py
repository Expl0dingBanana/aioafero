"""Test FanController"""

import asyncio
import logging

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.fan import FanController, features

from .. import utils

zandra_fan = utils.create_devices_from_data("fan-ZandraFan.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = FanController(mocked_bridge)
    yield controller


@pytest.mark.asyncio
async def test_initialize_zandra(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "066c0e38-c49b-4f60-b805-486dc07cab74"
    assert dev.on == features.OnFeature(on=True)
    assert dev.speed == features.SpeedFeature(
        speed=50,
        speeds=[
            "fan-speed-6-016",
            "fan-speed-6-033",
            "fan-speed-6-050",
            "fan-speed-6-066",
            "fan-speed-6-083",
            "fan-speed-6-100",
        ],
    )
    assert dev.direction == features.DirectionFeature(forward=False)
    assert dev.device_information.model == "Zandra"


@pytest.mark.asyncio
async def test_turn_on(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    await mocked_controller.turn_on(zandra_fan.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == zandra_fan.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": "fan-power",
            "lastUpdateTime": 12345,
            "value": "on",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_turn_off(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = True
    await mocked_controller.turn_off(zandra_fan.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == zandra_fan.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": "fan-power",
            "lastUpdateTime": 12345,
            "value": "off",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "speed, expected_speed",
    [
        # Speed of 0 should turn off
        (0, None),
        # Find the next highest value
        (1, "fan-speed-6-016"),
        # Exact value
        (16, "fan-speed-6-016"),
    ],
)
async def test_set_speed(speed, expected_speed, mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    if expected_speed:
        dev.on.on = False
    else:
        dev.on.on = True
    dev.speed.speed = "fan-speed-6-100"
    await mocked_controller.set_speed(zandra_fan.id, speed)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == zandra_fan.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": "fan-power",
            "lastUpdateTime": 12345,
            "value": "on",
        },
    ]
    if expected_speed is None:
        expected_states[0]["value"] = "off"
    else:
        expected_states.append(
            {
                "functionClass": "fan-speed",
                "functionInstance": "fan-speed",
                "lastUpdateTime": 12345,
                "value": expected_speed,
            }
        )
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "on",
    [True, False],
)
@pytest.mark.parametrize(
    "forward, value",
    [
        (True, "forward"),
        (False, "reverse"),
    ],
)
async def test_set_direction(on, forward, value, mocked_controller, caplog):
    caplog.set_level(logging.DEBUG)
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = on
    dev.direction.forward = not forward
    await mocked_controller.set_direction(zandra_fan.id, forward)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == zandra_fan.id
    expected_states = [
        {
            "functionClass": "fan-reverse",
            "functionInstance": "fan-reverse",
            "lastUpdateTime": 12345,
            "value": value,
        },
    ]
    if not on:
        assert "Fan is not running so direction will not be set" in caplog.text
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "on",
    [
        (True,),
        (False,),
    ],
)
@pytest.mark.parametrize(
    "preset, value",
    [
        (True, "enabled"),
        (False, "disabled"),
    ],
)
async def test_set_preset(on, preset, value, mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = True
    dev.preset.enabled = not preset
    await mocked_controller.set_preset(zandra_fan.id, preset)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == zandra_fan.id
    expected_states = [
        {
            "functionClass": "toggle",
            "functionInstance": "comfort-breeze",
            "lastUpdateTime": 12345,
            "value": value,
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("fan-ZandraFan.json")[0]
    new_states = [
        AferoState(
            **{
                "functionClass": "toggle",
                "value": "disabled",
                "lastUpdateTime": 0,
                "functionInstance": "comfort-breeze",
            }
        ),
        AferoState(
            **{
                "functionClass": "fan-speed",
                "value": "fan-speed-6-016",
                "lastUpdateTime": 0,
                "functionInstance": "fan-speed",
            }
        ),
        AferoState(
            **{
                "functionClass": "fan-reverse",
                "value": "forward",
                "lastUpdateTime": 0,
                "functionInstance": "fan-reverse",
            }
        ),
        AferoState(
            **{
                "functionClass": "power",
                "value": "off",
                "lastUpdateTime": 0,
                "functionInstance": "fan-power",
            }
        ),
        AferoState(
            **{
                "functionClass": "toggle",
                "value": "disabled",
                "lastUpdateTime": 0,
                "functionInstance": "comfort-breeze",
            }
        ),
        AferoState(
            **{
                "functionClass": "available",
                "value": False,
                "lastUpdateTime": 0,
                "functionInstance": None,
            }
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.preset.enabled is False
    assert dev.speed.speed == 16
    assert dev.direction.forward is True
    assert dev.on.on is False
    assert dev.available is False
    assert updates == {"speed", "direction", "on", "preset", "available"}


@pytest.mark.asyncio
async def test_update_elem_no_updates(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    updates = await mocked_controller.update_elem(zandra_fan)
    assert updates == set()


# @TODO - Create tests for BaseResourcesController
@pytest.mark.asyncio
async def test_update(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.on.on is True
    manual_update = [
        {
            "functionClass": "power",
            "value": "off",
            "functionInstance": "fan-power",
        }
    ]
    await mocked_controller.update(zandra_fan.id, states=manual_update)
    assert dev.on.on is False


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller.initialize_elem(zandra_fan)
    await mocked_controller.set_state(zandra_fan.id)


@pytest.mark.asyncio
async def test_fan_emitting(bridge):
    dev_update = utils.create_devices_from_data("fan-ZandraFan.json")[0]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.fans._items) == 1
    # Simulate an update
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="available",
            functionInstance=None,
            value=False,
        ),
    )
    update_event = {
        "type": "update",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    bridge.events.emit(event.EventType.RESOURCE_UPDATED, update_event)
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.fans._items) == 1
    assert not bridge.fans._items[dev_update.id].available
