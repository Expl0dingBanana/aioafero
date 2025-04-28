"""Test LockController"""

import asyncio

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.lock import LockController, features

from .. import utils

lock = utils.create_devices_from_data("door-lock-TBD.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = LockController(mocked_bridge)
    yield controller


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(lock)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "698e8a63-e8cb-4335-ba6b-83ca69d378f2"
    assert dev.position == features.CurrentPositionFeature(
        position=features.CurrentPositionEnum.LOCKED
    )


@pytest.mark.asyncio
async def test_lock(mocked_controller):
    await mocked_controller.initialize_elem(lock)
    assert len(mocked_controller.items) == 1
    await mocked_controller.lock(lock.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == lock.id
    expected_states = [
        {
            "functionClass": "lock-control",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "locking",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_unlock(mocked_controller):
    await mocked_controller.initialize_elem(lock)
    assert len(mocked_controller.items) == 1
    await mocked_controller.unlock(lock.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == lock.id
    expected_states = [
        {
            "functionClass": "lock-control",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": features.CurrentPositionEnum.UNLOCKING.value,
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    await mocked_controller.initialize_elem(lock)
    assert len(mocked_controller.items) == 1
    update = utils.create_devices_from_data("door-lock-TBD.json")[0]
    updates = await mocked_controller.update_elem(update)
    assert updates == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value, expected, expected_updates",
    [
        ("locking", features.CurrentPositionEnum.LOCKING, {"position"}),
        ("unlocking", features.CurrentPositionEnum.UNLOCKING, {"position"}),
        ("not-a-state", features.CurrentPositionEnum.UNKNOWN, {"position"}),
    ],
)
async def test_update_elem(value, expected, expected_updates, mocked_controller):
    await mocked_controller.initialize_elem(lock)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.available
    dev_update = utils.create_devices_from_data("door-lock-TBD.json")[0]
    new_states = [
        AferoState(
            **{
                "functionClass": "lock-control",
                "value": value,
                "lastUpdateTime": 0,
                "functionInstance": None,
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
    expected_updates.add("available")
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    assert dev.position.position == expected
    assert not dev.available
    assert updates == expected_updates


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller.initialize_elem(lock)
    await mocked_controller.set_state(lock.id)


@pytest.mark.asyncio
async def test_lock_emitting(bridge):
    dev_update = utils.create_devices_from_data("door-lock-TBD.json")[0]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.locks._items) == 1
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
    assert len(bridge.locks._items) == 1
    assert not bridge.locks._items[dev_update.id].available
