"""Test SecuritySystemController"""

import pytest

from aioafero.v1.controllers.security_system_keypad import SecuritySystemKeypadController, features, AferoBinarySensor
from aioafero import AferoState

from .. import utils


security_system = utils.create_devices_from_data("security-system.json")
keypad_id = "1f31be19-b9b9-4ca8-8a22-20d0015ec2dd"


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.security_systems_keypads


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data(security_system)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[keypad_id]
    assert dev.available is True
    assert dev.selects == {
        ("volume", "buzzer-volume"): features.SelectFeature(
            selected="volume-02",
            selects={"volume-00", "volume-01", "volume-02", "volume-03", "volume-04"},
            name="Buzzer Volume",
        ),
    }
    assert dev.binary_sensors == {
        'tamper-detection|None': AferoBinarySensor(
            id='tamper-detection|None',
            owner='ce68c348-cd68-4ce3-937d-bf18619ae970',
            current_value='not-tampered',
            _error='tampered',
            unit=None,
            instance=None)
    }


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data(security_system)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    update = utils.create_devices_from_data("security-system.json")[0]
    updates = await mocked_controller.update_elem(update)
    assert updates == set()


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data(security_system)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[keypad_id]
    assert dev.available
    update = utils.create_devices_from_data("security-system.json")[0]
    new_states = [
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="volume", value="volume-03", lastUpdateTime=0, functionInstance="buzzer-volume"
        ),
        AferoState(
            functionClass="tamper-detection", value="tampered", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(update, state)
    updates = await mocked_controller.update_elem(update)
    await mocked_controller._bridge.async_block_until_done()
    assert not dev.available
    assert updates == {
        "available",
        "select-('volume', 'buzzer-volume')",
        "binary-tamper-detection|None",
    }
    assert dev.selects[("volume", "buzzer-volume")].selected == "volume-03"
    assert dev.binary_sensors["tamper-detection|None"].current_value == "tampered"


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data(security_system)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(keypad_id)


@pytest.mark.asyncio
async def test_set_state(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data(security_system)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        keypad_id,
        selects={("volume", "buzzer-volume"): "volume-03", ("bad", None): False},
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[keypad_id]
    assert dev.selects[("volume", "buzzer-volume")].selected == "volume-03"

@pytest.mark.asyncio
async def test_set_state_bad_device(mocked_controller):
    await mocked_controller._bridge.generate_devices_from_data(security_system)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        "doesnt-exist",
        selects={("volume", "buzzer-volume"): "volume-03", ("bad", None): False},
    )
    mocked_controller._bridge.request.assert_not_called()


@pytest.mark.asyncio
async def test_emitting(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.generate_devices_from_data(security_system)
    await bridge.async_block_until_done()
    dev = bridge.security_systems_keypads[keypad_id]
    assert dev.available
    update = utils.create_devices_from_data("security-system.json")[0]
    new_states = [
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="volume", value="volume-03", lastUpdateTime=0, functionInstance="buzzer-volume"
        ),
        AferoState(
            functionClass="tamper-detection", value="tampered", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(update, state)
    await bridge.generate_devices_from_data([update])
    await bridge.async_block_until_done()
    dev = bridge.security_systems_keypads[keypad_id]
    assert not dev.available
    assert dev.selects[("volume", "buzzer-volume")].selected == "volume-03"
    assert dev.binary_sensors["tamper-detection|None"].current_value == "tampered"
