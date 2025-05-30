"""Test SwitchController"""

import asyncio

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.switch import SwitchController, features
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
    controller = SwitchController(mocked_bridge)
    yield controller


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
            _value=12,
            unit="V",
            instance=None,
        ),
        "watts": AferoSensor(
            id="watts",
            owner="1a6ac487-63bd-42a3-927d-66866eb641ac",
            _value=0,
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
async def test_initialize_exhaust_fan(mocked_controller):
    await mocked_controller.initialize_elem(exhaust_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "44620d02-8b62-49ce-afe8-1ea8f15e0ec5"
    assert dev.on == {
        "humidity-detection-enabled": features.OnFeature(
            on=False, func_class="toggle", func_instance="humidity-detection-enabled"
        ),
        "humidity-sensor-led": features.OnFeature(
            on=False, func_class="toggle", func_instance="humidity-sensor-led"
        ),
        "motion-sensor-led": features.OnFeature(
            on=True, func_class="toggle", func_instance="motion-sensor-led"
        ),
        "speaker-power": features.OnFeature(
            on=True, func_class="toggle", func_instance="speaker-power"
        ),
        "motion-detection-enabled-exhaust-fan": features.OnFeature(
            on=True,
            func_class="toggle",
            func_instance="motion-detection-enabled-exhaust-fan",
        ),
    }


@pytest.mark.asyncio
async def test_initialize_portable_ac(mocked_controller):
    await mocked_controller.initialize_elem(portable_ac)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "8d0414d6-a7f7-4bdb-99d5-d866318ff559"
    assert dev.on == {
        None: features.OnFeature(on=False, func_class="power", func_instance=None),
    }


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
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(transformer)
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("transformer.json")[0]
    new_states = [
        AferoState(
            **{
                "functionClass": "toggle",
                "value": "on",
                "lastUpdateTime": 0,
                "functionInstance": "zone-1",
            }
        ),
        AferoState(
            **{
                "functionClass": "toggle",
                "value": "off",
                "lastUpdateTime": 0,
                "functionInstance": "zone-2",
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
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.switches._items) == 1
    bridge.switches._items[transformer.id].sensors["watts"]._value = 0
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
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
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
