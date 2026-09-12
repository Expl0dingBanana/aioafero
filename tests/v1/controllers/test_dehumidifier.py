"""Test Dehumidifiers"""

import logging

import pytest

from aioafero.device import AferoState
from aioafero.v1.models import features
from tests.v1 import utils

dehumidifier = utils.create_devices_from_data("dehumidifier.json")[0]
dehumidifier_id = "5240e1d0-958e-4861-a9cd-d273943a0d64"


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.dehumidifiers


@pytest.fixture
async def seeded_controller(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dehumidifier)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    return mocked_controller


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(dehumidifier)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == dehumidifier_id
    assert dev.available is True
    assert dev.on == features.OnFeature(
        on=True, function_class="power", function_instance=None
    )
    assert dev.mode == features.ModeFeature(
        mode="set",
        modes={"comfort", "dryer", "continuous", "set"},
        function_class="mode",
        function_instance="dehumidifier-mode",
    )
    assert dev.current_humidity == 48
    assert dev.target_humidity == features.NumbersFeature(
        value=40,
        min=35,
        max=85,
        step=5,
        name="Target Humidity",
        unit="%",
        function_class="humidity",
        function_instance="target",
    )
    assert dev.selects == {
        ("fan-speed", "dehumidifier-fan-speed"): features.SelectFeature(
            selected="fan-speed-2-100",
            selects={"fan-speed-2-100", "fan-speed-2-050"},
            name="Fan Speed",
            function_class="fan-speed",
            function_instance="dehumidifier-fan-speed",
        ),
        ("pump", None): features.SelectFeature(
            selected="on",
            selects={"on", "off"},
            name="Pump",
            function_class="pump",
            function_instance=None,
        ),
    }
    assert dev.sensors == {}
    assert dev.binary_sensors == {}
    assert dev.device_information.model == "VAD50PS1AWTS"


@pytest.mark.asyncio
async def test_update_elem(seeded_controller):
    dev_update = utils.create_devices_from_data("dehumidifier.json")[0]
    new_states = [
        AferoState(functionClass="available", value=False, lastUpdateTime=0),
        AferoState(functionClass="power", value="off", lastUpdateTime=0),
        AferoState(
            functionClass="mode",
            value="continuous",
            lastUpdateTime=0,
            functionInstance="dehumidifier-mode",
        ),
        AferoState(
            functionClass="humidity",
            value=55,
            lastUpdateTime=0,
            functionInstance="current",
        ),
        AferoState(
            functionClass="humidity",
            value=50,
            lastUpdateTime=0,
            functionInstance="target",
        ),
        AferoState(functionClass="pump", value="off", lastUpdateTime=0),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await seeded_controller.update_elem(dev_update)
    dev = seeded_controller.items[0]
    assert dev.available is False
    assert dev.on.on is False
    assert dev.mode.mode == "continuous"
    assert dev.current_humidity == 55
    assert dev.target_humidity.value == 50
    assert dev.selects[("pump", None)].selected == "off"
    assert updates == {
        "available",
        "on",
        "mode",
        "humidity-current",
        "humidity-target",
        "select-('pump', None)",
    }


@pytest.mark.asyncio
async def test_update_elem_no_updates(seeded_controller):
    dev_update = utils.create_devices_from_data("dehumidifier.json")[0]
    assert await seeded_controller.update_elem(dev_update) == set()


@pytest.mark.asyncio
async def test_set_state(seeded_controller, mocker):
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await seeded_controller.set_state(
        dehumidifier_id,
        on=False,
        mode="continuous",
        target_humidity=50,
        selects={("pump", None): "off", ("nope", None): "nope"},
    )
    await seeded_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        dehumidifier_id,
        [
            {
                "functionClass": "power",
                "functionInstance": None,
                "value": "off",
                "lastUpdateTime": mocker.ANY,
            },
            {
                "functionClass": "mode",
                "functionInstance": "dehumidifier-mode",
                "value": "continuous",
                "lastUpdateTime": mocker.ANY,
            },
            {
                "functionClass": "humidity",
                "functionInstance": "target",
                "value": 50,
                "lastUpdateTime": mocker.ANY,
            },
            {
                "functionClass": "pump",
                "functionInstance": None,
                "value": "off",
                "lastUpdateTime": mocker.ANY,
            },
        ],
    )
    dev = seeded_controller.items[0]
    assert dev.on.on is False
    assert dev.mode.mode == "continuous"
    assert dev.target_humidity.value == 50
    assert dev.selects[("pump", None)].selected == "off"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "expected"),
    [("turn_on", "on"), ("turn_off", "off")],
)
async def test_turn_on_off(seeded_controller, mocker, method, expected):
    # Start from the opposite state so a write is actually emitted
    seeded_controller.items[0].on.on = expected != "on"
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await getattr(seeded_controller, method)(dehumidifier_id)
    await seeded_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        dehumidifier_id,
        [
            {
                "functionClass": "power",
                "functionInstance": None,
                "value": expected,
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert seeded_controller.items[0].on.on is (expected == "on")


@pytest.mark.asyncio
async def test_set_state_invalid_dev(seeded_controller, mocker):
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await seeded_controller.set_state("nope", on=False)
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_state_no_updates(seeded_controller, mocker):
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await seeded_controller.set_state(dehumidifier_id)
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_state_invalid_mode(seeded_controller, mocker, caplog):
    caplog.set_level(logging.DEBUG)
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await seeded_controller.set_state(
        dehumidifier_id,
        mode="i dont exist",
        selects={("pump", None): "off"},
    )
    await seeded_controller._bridge.async_block_until_done()
    assert "Unknown mode i dont exist" in caplog.text
    update_afero_api.assert_awaited_once_with(
        dehumidifier_id,
        [
            {
                "functionClass": "pump",
                "functionInstance": None,
                "value": "off",
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert seeded_controller.items[0].mode.mode == "set"
