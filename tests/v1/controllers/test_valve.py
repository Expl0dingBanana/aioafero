"""Test ValveController"""

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.valve import ValveController, features

from .. import utils

valve = utils.create_devices_from_data("water-timer.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.valves


@pytest.mark.asyncio
async def test_initialize_multi(mocked_controller):
    await mocked_controller.initialize_elem(valve)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[valve.id]
    assert dev.id == "60eb18c9-8510-4bcd-be3f-493dfb351268"
    assert dev.open == {
        None: features.OpenFeature(open=False, func_class="power", func_instance=None),
        "spigot-1": features.OpenFeature(
            open=False, func_class="toggle", func_instance="spigot-1"
        ),
        "spigot-2": features.OpenFeature(
            open=True, func_class="toggle", func_instance="spigot-2"
        ),
    }


@pytest.mark.asyncio
async def test_turn_on_multi(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    
    await mocked_controller.turn_on(valve.id, instance="spigot-1")
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[valve.id]
    assert dev.open[None].open is False
    assert dev.open["spigot-1"].open is True
    assert dev.open["spigot-2"].open is True


@pytest.mark.asyncio
async def test_turn_off(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    await mocked_controller.turn_off(valve.id, instance="spigot-2")
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[valve.id]
    assert dev.open[None].open is False
    assert dev.open["spigot-1"].open is False
    assert dev.open["spigot-2"].open is False


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    valve = utils.create_devices_from_data("water-timer.json")[0]
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    updates = await mocked_controller.update_elem(valve)
    assert updates == set()


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[valve.id]
    assert dev.available is True
    dev_update = utils.create_devices_from_data("water-timer.json")[0]
    new_states = [
        AferoState(
            functionClass="toggle", value="on", lastUpdateTime=0, functionInstance="spigot-1"
        ),
        AferoState(
            functionClass="toggle", value="off", lastUpdateTime=0, functionInstance="spigot-2"
        ),
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[valve.id]
    assert dev.open["spigot-1"].open is True
    assert dev.open["spigot-2"].open is False
    assert dev.available is False
    assert updates == {"open", "available"}


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    await mocked_controller.set_state(valve.id)


@pytest.mark.asyncio
async def test_valve_emitting(bridge):
    dev_update = utils.create_devices_from_data("water-timer.json")[0]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    await bridge.async_block_until_done()
    assert len(bridge.valves._items) == 1
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
    assert len(bridge.valves._items) == 1
    assert not bridge.valves[dev_update.id].available


@pytest.mark.asyncio
async def test_set_state_no_dev(mocked_controller, caplog):
    caplog.set_level(0)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller._bridge.add_device(valve.id, mocked_controller)
    await mocked_controller.set_state("not-a-device")
    mocked_controller._bridge.request.assert_not_called()
    assert "Unable to find device" in caplog.text


@pytest.mark.asyncio
async def test_set_state_invalid_instance(mocked_controller, caplog):
    caplog.set_level(0)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(valve)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller._bridge.add_device(valve.id, mocked_controller)
    await mocked_controller.set_state(
        valve.id, valve_open=True, instance="not-a-instance"
    )
    mocked_controller._bridge.request.assert_not_called()
    assert "No states to send. Skipping" in caplog.text
