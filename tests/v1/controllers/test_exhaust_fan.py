"""Test ExhaustFanController"""

import asyncio

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.exhaust_fan import ExhaustFanController, features
from aioafero.v1.models.sensor import AferoBinarySensor

from .. import utils

exhaust_fan = utils.create_devices_from_data("exhaust-fan.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = ExhaustFanController(mocked_bridge)
    yield controller


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(exhaust_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "44620d02-8b62-49ce-afe8-1ea8f15e0ec5"
    assert dev.binary_sensors == {
        "humidity-threshold-met|humidity-threshold-met": AferoBinarySensor(
            id="humidity-threshold-met|humidity-threshold-met",
            owner="7475607b-c3ea-4afe-a465-1c11c5c09985",
            _value="below-threshold",
            _error="above-threshold",
            unit=None,
            instance="humidity-threshold-met",
        ),
        "motion-detection|motion-detection": AferoBinarySensor(
            id="motion-detection|motion-detection",
            owner="7475607b-c3ea-4afe-a465-1c11c5c09985",
            _value="motion-detected",
            _error="motion-detected",
            unit=None,
            instance="motion-detection",
        ),
    }
    assert dev.sensors == {}
    assert dev.numbers == {
        ("auto-off-timer", "auto-off"): features.NumbersFeature(
            value=1200,
            min=60,
            max=1800,
            step=60,
            name="Auto Off Timer",
            unit="seconds",
        )
    }
    assert dev.selects == {
        ("motion-action", "exhaust-fan"): features.SelectFeature(
            selected="light", selects={"both", "fan", "light"}, name="Motion Action"
        ),
        ("sensitivity", "humidity-sensitivity"): features.SelectFeature(
            selected="3-medium",
            selects={"1-low", "2-low-medium", "3-medium", "4-medium-high", "5-high"},
            name="Humidity Sensitivity",
        ),
    }


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(exhaust_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.available is True
    dev_update = utils.create_devices_from_data("exhaust-fan.json")[0]
    new_states = [
        AferoState(
            **{
                "functionClass": "available",
                "value": False,
                "lastUpdateTime": 0,
                "functionInstance": None,
            }
        ),
        AferoState(
            **{
                "functionClass": "humidity-threshold-met",
                "value": "above-threshold",
                "lastUpdateTime": 0,
                "functionInstance": "humidity-threshold-met",
            }
        ),
        AferoState(
            **{
                "functionClass": "auto-off-timer",
                "value": 120,
                "lastUpdateTime": 0,
                "functionInstance": "auto-off",
            }
        ),
        AferoState(
            **{
                "functionClass": "motion-action",
                "value": "both",
                "lastUpdateTime": 0,
                "functionInstance": "exhaust-fan",
            }
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.available is False
    assert (
        dev.binary_sensors["humidity-threshold-met|humidity-threshold-met"]._value
        == "above-threshold"
    )
    assert dev.numbers[("auto-off-timer", "auto-off")].value == 120
    assert dev.selects[("motion-action", "exhaust-fan")].selected == "both"
    assert updates == {
        "binary-humidity-threshold-met|humidity-threshold-met",
        "available",
        "number-('auto-off-timer', 'auto-off')",
        "select-('motion-action', 'exhaust-fan')",
    }


@pytest.mark.asyncio
async def test_update_state_no_change(mocked_controller):
    await mocked_controller.initialize_elem(exhaust_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.available is True
    dev_update = utils.create_devices_from_data("exhaust-fan.json")[0]
    new_states = [
        AferoState(
            **{
                "functionClass": "available",
                "value": True,
                "lastUpdateTime": 0,
                "functionInstance": None,
            }
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.available is True
    assert updates == set()


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller.initialize_elem(exhaust_fan)
    await mocked_controller.set_state(exhaust_fan.id)


@pytest.mark.asyncio
async def test_set_state(mocked_controller):
    await mocked_controller.initialize_elem(exhaust_fan)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.available is True
    await mocked_controller.set_state(
        exhaust_fan.id,
        numbers={
            ("auto-off-timer", "auto-off"): 120,
            ("invalid", "state"): None,
        },
        selects={
            ("motion-action", "exhaust-fan"): "both",
            ("invalid", "state"): None,
        },
    )
    dev = mocked_controller.items[0]
    assert dev.numbers[("auto-off-timer", "auto-off")].value == 120
    assert dev.selects[("motion-action", "exhaust-fan")].selected == "both"


@pytest.mark.asyncio
async def test_exhaust_fan_emitting(bridge):
    dev_update = utils.create_devices_from_data("exhaust-fan.json")[0]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.exhaust_fans._items) == 1
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
    assert len(bridge.exhaust_fans._items) == 1
    assert not bridge.exhaust_fans._items[dev_update.id].available


@pytest.mark.asyncio
async def test_set_state_no_dev(mocked_controller, caplog):
    caplog.set_level(0)
    await mocked_controller.initialize_elem(exhaust_fan)
    mocked_controller._bridge.add_device(exhaust_fan.id, mocked_controller)
    await mocked_controller.set_state("not-a-device")
    mocked_controller._bridge.request.assert_not_called()
    assert "Unable to find device" in caplog.text
