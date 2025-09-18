"""Test FanController"""

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
    return mocked_bridge.fans


@pytest.mark.asyncio
async def test_initialize_zandra(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
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
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    await mocked_controller.turn_on(zandra_fan.id)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.on.on is True


@pytest.mark.asyncio
async def test_turn_off(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = True
    await mocked_controller.turn_off(zandra_fan.id)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.on.on is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "speed",
    [
        # Speed of 0 should turn off
        (0),
        # Exact value
        (16),
    ],
)
async def test_set_speed(speed, mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    if speed:
        dev.on.on = False
    else:
        dev.on.on = True
    dev.speed.speed = "fan-speed-6-100"
    await mocked_controller.set_speed(zandra_fan.id, speed)
    await mocked_controller._bridge.async_block_until_done()
    if not speed:
        assert dev.on.on is False
    else:
        assert dev.on.on is True
        assert dev.speed.speed == speed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "on",
    [True, False],
)
@pytest.mark.parametrize(
    "forward",
    [
        (True),
        (False),
    ],
)
async def test_set_direction(on, forward, mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = on
    dev.direction.forward = not forward
    await mocked_controller.set_direction(zandra_fan.id, forward)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.direction.forward is forward


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "on",
    [
        (True,),
        (False,),
    ],
)
@pytest.mark.parametrize(
    "preset",
    [
        (True),
        (False),
    ],
)
async def test_set_preset(on, preset, mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = True
    dev.preset.enabled = not preset
    await mocked_controller.set_preset(zandra_fan.id, preset)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.preset.enabled is preset


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("fan-ZandraFan.json")[0]
    new_states = [
        AferoState(
            functionClass="toggle", value="disabled", lastUpdateTime=0, functionInstance="comfort-breeze"
        ),
        AferoState(
            functionClass="fan-speed", value="fan-speed-6-016", lastUpdateTime=0, functionInstance="fan-speed"
        ),
        AferoState(
            functionClass="fan-reverse", value="forward", lastUpdateTime=0, functionInstance="fan-reverse"
        ),
        AferoState(
            functionClass="power", value="off", lastUpdateTime=0, functionInstance="fan-power"
        ),
        AferoState(
            functionClass="toggle", value="disabled", lastUpdateTime=0, functionInstance="comfort-breeze"
        ),
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
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
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    updates = await mocked_controller.update_elem(zandra_fan)
    assert updates == set()


# @TODO - Create tests for BaseResourcesController
@pytest.mark.asyncio
async def test_update(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(zandra_fan)]
    )
    await mocked_controller._bridge.async_block_until_done()
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
    mocked_controller._bridge.mock_update_afero_api(zandra_fan.id, manual_update)
    await mocked_controller.update(zandra_fan.id, states=manual_update)
    await mocked_controller._bridge.async_block_until_done()
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
    await bridge.async_block_until_done()
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
    await bridge.async_block_until_done()
    assert len(bridge.fans._items) == 1
    assert not bridge.fans._items[dev_update.id].available
