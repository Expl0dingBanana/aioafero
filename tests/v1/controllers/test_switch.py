"""Test SwitchController"""

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.switch import features
from aioafero.v1.models import AferoSensor

from .. import utils

switch = utils.create_devices_from_data("switch-HPDA311CWB.json")[0]
transformer = utils.create_devices_from_data("transformer.json")[0]
glass_door = utils.create_devices_from_data("glass-door.json")[0]
exhaust_fan = utils.create_devices_from_data("exhaust-fan.json")[0]
portable_ac = utils.create_devices_from_data("portable-ac.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    yield mocked_bridge.switches


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(switch)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "feb5d9db-0562-478b-aaa0-00c889f0a758"
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None),
    }
    assert dev.sensors == {}
    assert dev.binary_sensors == {}


@pytest.mark.asyncio
async def test_initialize_multi(mocked_controller):
    await mocked_controller.initialize_elem(transformer)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "f9aa07e9-a4ce-46b4-b6bc-ad3bc070bc90"
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None),
        "zone-1": features.OnFeature(
            on=False, func_class="toggle", func_instance="zone-1"
        ),
        "zone-2": features.OnFeature(
            on=True, func_class="toggle", func_instance="zone-2"
        ),
        "zone-3": features.OnFeature(
            on=False, func_class="toggle", func_instance="zone-3"
        ),
    }
    assert dev.sensors == {
        "output-voltage-switch": AferoSensor(
            id="output-voltage-switch",
            owner="1a6ac487-63bd-42a3-927d-66866eb641ac",
            value=12,
            unit="V",
            instance=None,
        ),
        "watts": AferoSensor(
            id="watts",
            owner="1a6ac487-63bd-42a3-927d-66866eb641ac",
            value=0,
            unit="W",
            instance=None,
        ),
    }
    assert dev.binary_sensors == {}


@pytest.mark.asyncio
async def test_initialize_glass_door(mocked_controller):
    await mocked_controller.initialize_elem(glass_door)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "89d12e53-2c38-46b3-af2a-ced1ccc04c39"
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None),
    }


@pytest.mark.asyncio
async def test_initialize_exhaust_fan(bridge):
    await bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("exhaust-fan.json")
    )
    await bridge.async_block_until_done()
    controller = bridge.switches
    assert len(controller.items) == 5
    for expected_id in [
        "44620d02-8b62-49ce-afe8-1ea8f15e0ec5-exhaust-fan-humidity-detection-enabled",
        "44620d02-8b62-49ce-afe8-1ea8f15e0ec5-exhaust-fan-humidity-sensor-led",
        "44620d02-8b62-49ce-afe8-1ea8f15e0ec5-exhaust-fan-motion-detection-enabled-exhaust-fan",
        "44620d02-8b62-49ce-afe8-1ea8f15e0ec5-exhaust-fan-motion-sensor-led",
        "44620d02-8b62-49ce-afe8-1ea8f15e0ec5-exhaust-fan-speaker-power",
    ]:
        assert controller.get_device(expected_id) is not None


@pytest.mark.asyncio
async def test_initialize_portable_ac(bridge):
    await bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("portable-ac.json")
    )
    await bridge.async_block_until_done()
    controller = bridge.switches
    assert len(controller.items) == 1
    for expected_id in [
        "8d0414d6-a7f7-4bdb-99d5-d866318ff559-portable-ac-power",
    ]:
        assert controller.get_device(expected_id) is not None


@pytest.mark.asyncio
async def test_turn_on(mocked_controller):
    await mocked_controller.initialize_elem(switch)
    dev = mocked_controller.items[0]
    await mocked_controller.turn_on(switch.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == switch.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        None: features.OnFeature(on=True, func_class="power", func_instance=None)
    }
    assert dev.sensors == {}
    assert dev.binary_sensors == {}


@pytest.mark.asyncio
async def test_turn_on_multi(mocked_controller):
    await mocked_controller.initialize_elem(transformer)
    dev = mocked_controller.items[0]
    await mocked_controller.turn_on(transformer.id, instance="zone-1")
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == transformer.id
    expected_states = [
        {
            "functionClass": "toggle",
            "functionInstance": "zone-1",
            "lastUpdateTime": 12345,
            "value": "on",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None),
        "zone-1": features.OnFeature(
            on=True, func_class="toggle", func_instance="zone-1"
        ),
        "zone-2": features.OnFeature(
            on=True, func_class="toggle", func_instance="zone-2"
        ),
        "zone-3": features.OnFeature(
            on=False, func_class="toggle", func_instance="zone-3"
        ),
    }


@pytest.mark.asyncio
async def test_turn_on_glass_door(mocked_controller):
    await mocked_controller.initialize_elem(glass_door)
    dev = mocked_controller.items[0]
    await mocked_controller.turn_on(glass_door.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == glass_door.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        None: features.OnFeature(on=True, func_class="power", func_instance=None)
    }


@pytest.mark.asyncio
async def test_turn_off(mocked_controller):
    await mocked_controller.initialize_elem(switch)
    dev = mocked_controller.items[0]
    await mocked_controller.turn_off(switch.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == switch.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "off",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None)
    }


@pytest.mark.asyncio
async def test_turn_off_multi(mocked_controller):
    await mocked_controller.initialize_elem(transformer)
    dev = mocked_controller.items[0]
    await mocked_controller.turn_off(transformer.id, instance="zone-2")
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == transformer.id
    expected_states = [
        {
            "functionClass": "toggle",
            "functionInstance": "zone-2",
            "lastUpdateTime": 12345,
            "value": "off",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None),
        "zone-1": features.OnFeature(
            on=False, func_class="toggle", func_instance="zone-1"
        ),
        "zone-2": features.OnFeature(
            on=False, func_class="toggle", func_instance="zone-2"
        ),
        "zone-3": features.OnFeature(
            on=False, func_class="toggle", func_instance="zone-3"
        ),
    }


@pytest.mark.asyncio
async def test_turn_off_glass_door(mocked_controller):
    await mocked_controller.initialize_elem(glass_door)
    dev = mocked_controller.items[0]
    await mocked_controller.turn_off(glass_door.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == glass_door.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "off",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None)
    }


@pytest.mark.asyncio
async def test_turn_on_split_device(mocked_bridge):
    await mocked_bridge.generate_devices_from_data(
        utils.create_devices_from_data("light-with-speaker.json")
    )
    speaker_id = "3bec6eaa-3d87-4f3c-a065-a2b32f87c39f-light-speaker-power"
    mocked_controller = mocked_bridge.switches
    dev = mocked_controller[speaker_id]
    await mocked_controller.turn_on(speaker_id, instance="speaker-power")
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == "3bec6eaa-3d87-4f3c-a065-a2b32f87c39f"
    expected_states = [
        {
            "functionClass": "toggle",
            "functionInstance": "speaker-power",
            "lastUpdateTime": 12345,
            "value": "on",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.on == {
        "speaker-power": features.OnFeature(on=True, func_class="toggle", func_instance="speaker-power")
    }


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(transformer)
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("transformer.json")[0]
    new_states = [
        AferoState(
            functionClass="toggle", value="on", lastUpdateTime=0, functionInstance="zone-1"
        ),
        AferoState(
            functionClass="toggle", value="off", lastUpdateTime=0, functionInstance="zone-2"
        ),
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="watts",
            functionInstance=None,
            value=22,
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.on["zone-1"].on is True
    assert dev.on["zone-2"].on is False
    assert dev.sensors["watts"].value == 22
    assert updates == {"on", "available", "sensor-watts"}
    assert dev.available is False


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    switch = utils.create_devices_from_data("switch-HPDA311CWB.json")[0]
    await mocked_controller.initialize_elem(switch)
    assert len(mocked_controller.items) == 1
    updates = await mocked_controller.update_elem(switch)
    assert updates == set()


@pytest.mark.asyncio
async def test_switch_emit_update(bridge):
    add_event = {
        "type": "add",
        "device_id": transformer.id,
        "device": transformer,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    await bridge.async_block_until_done()
    assert len(bridge.switches._items) == 1
    bridge.switches._items[transformer.id].sensors["watts"].value = 0
    # Simulate an update
    transformer_update = utils.create_devices_from_data("transformer.json")[0]
    utils.modify_state(
        transformer_update,
        AferoState(
            functionClass="toggle",
            functionInstance="zone-2",
            value="off",
        ),
    )
    utils.modify_state(
        transformer_update,
        AferoState(
            functionClass="watts",
            functionInstance=None,
            value=1,
        ),
    )
    update_event = {
        "type": "update",
        "device_id": transformer.id,
        "device": transformer_update,
    }
    bridge.events.emit(event.EventType.RESOURCE_UPDATED, update_event)
    await bridge.async_block_until_done()
    assert len(bridge.switches._items) == 1
    assert not bridge.switches._items[transformer.id].on["zone-2"].on
    assert bridge.switches._items[transformer.id].sensors["watts"].value == 1


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller.initialize_elem(switch)
    await mocked_controller.set_state(switch.id)


@pytest.mark.asyncio
async def test_set_state_no_dev(mocked_controller, caplog):
    caplog.set_level(0)
    await mocked_controller.initialize_elem(transformer)
    mocked_controller._bridge.add_device(transformer.id, mocked_controller)
    await mocked_controller.set_state("not-a-device")
    mocked_controller._bridge.request.assert_not_called()
    assert "Unable to find device" in caplog.text


@pytest.mark.asyncio
async def test_set_state_invalid_instance(mocked_controller, caplog):
    caplog.set_level(0)
    await mocked_controller.initialize_elem(transformer)
    mocked_controller._bridge.add_device(transformer.id, mocked_controller)
    await mocked_controller.set_state(
        transformer.id, on=True, instance="not-a-instance"
    )
    mocked_controller._bridge.request.assert_not_called()
    assert "No states to send. Skipping" in caplog.text
