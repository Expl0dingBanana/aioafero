"""Test Humidifiers"""

import logging

import pytest

from aioafero.device import AferoState
from aioafero.v1.models import features
from tests.v1 import utils

humidifier = utils.create_devices_from_data("humidifier.json")[0]
humidifier_id = "b8e4fe3c-1342-4476-af6b-91d897ff94af"

MIST_LEVEL = ("atomization-level", "humidifier")


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.humidifiers


@pytest.fixture
async def seeded_controller(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(humidifier)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    return mocked_controller


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(humidifier)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == humidifier_id
    assert dev.available is True
    assert dev.on == features.OnFeature(
        on=True, function_class="power", function_instance=None
    )
    assert dev.mode == features.ModeFeature(
        mode="manual",
        modes={"wellness", "sleep", "auto", "manual", "plant-care"},
        function_class="mode",
        function_instance="humidifier-mode",
    )
    assert dev.current_humidity == 58
    assert dev.target_humidity == features.NumbersFeature(
        value=60,
        min=30,
        max=80,
        step=5,
        name="Target Humidity",
        unit="%",
        function_class="humidity",
        function_instance="auto-target",
    )
    assert dev.numbers == {}
    assert dev.selects == {
        MIST_LEVEL: features.SelectFeature(
            selected="level-2",
            selects={"level-1", "level-2", "level-3"},
            name="Mist Level",
            function_class="atomization-level",
            function_instance="humidifier",
        ),
        ("humidity", "wellness-target"): features.SelectFeature(
            selected="wellness-sleep",
            selects={
                "skin-hydration",
                "wellness-sleep",
                "cold-flu",
                "congestion-cough",
            },
            name="Wellness Target",
            function_class="humidity",
            function_instance="wellness-target",
        ),
        ("humidity", "plant-care-target"): features.SelectFeature(
            selected="adaptables",
            selects={"adaptables", "cacti-succulents", "sub-tropical", "tropical"},
            name="Plant Care Target",
            function_class="humidity",
            function_instance="plant-care-target",
        ),
        ("dark-mode", None): features.SelectFeature(
            selected="off",
            selects={"on", "off"},
            name="Dark Mode",
            function_class="dark-mode",
            function_instance=None,
        ),
    }
    assert dev.sensors == {}
    assert dev.binary_sensors == {}
    assert dev.device_information.model == "VK-8529"


@pytest.mark.asyncio
async def test_update_elem(seeded_controller):
    dev_update = utils.create_devices_from_data("humidifier.json")[0]
    new_states = [
        AferoState(functionClass="available", value=False, lastUpdateTime=0),
        AferoState(functionClass="power", value="off", lastUpdateTime=0),
        AferoState(
            functionClass="mode",
            value="auto",
            lastUpdateTime=0,
            functionInstance="humidifier-mode",
        ),
        AferoState(
            functionClass="humidity",
            value=45,
            lastUpdateTime=0,
            functionInstance="current",
        ),
        AferoState(
            functionClass="humidity",
            value=50,
            lastUpdateTime=0,
            functionInstance="auto-target",
        ),
        AferoState(
            functionClass="humidity",
            value="cold-flu",
            lastUpdateTime=0,
            functionInstance="wellness-target",
        ),
        AferoState(
            functionClass="atomization-level",
            value="level-3",
            lastUpdateTime=0,
            functionInstance="humidifier",
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await seeded_controller.update_elem(dev_update)
    dev = seeded_controller.items[0]
    assert dev.available is False
    assert dev.on.on is False
    assert dev.mode.mode == "auto"
    assert dev.current_humidity == 45
    assert dev.target_humidity.value == 50
    assert dev.selects[("humidity", "wellness-target")].selected == "cold-flu"
    assert dev.selects[MIST_LEVEL].selected == "level-3"
    assert updates == {
        "available",
        "on",
        "mode",
        "humidity-current",
        "humidity-target",
        "select-('humidity', 'wellness-target')",
        "select-('atomization-level', 'humidifier')",
    }


@pytest.mark.asyncio
async def test_update_elem_no_updates(seeded_controller):
    dev_update = utils.create_devices_from_data("humidifier.json")[0]
    assert await seeded_controller.update_elem(dev_update) == set()


@pytest.mark.asyncio
async def test_set_state(seeded_controller, mocker):
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await seeded_controller.set_state(
        humidifier_id,
        on=False,
        mode="auto",
        target_humidity=50,
        selects={MIST_LEVEL: "level-3", ("nope", None): "nope"},
    )
    await seeded_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        humidifier_id,
        [
            {
                "functionClass": "power",
                "functionInstance": None,
                "value": "off",
                "lastUpdateTime": mocker.ANY,
            },
            {
                "functionClass": "mode",
                "functionInstance": "humidifier-mode",
                "value": "auto",
                "lastUpdateTime": mocker.ANY,
            },
            {
                "functionClass": "humidity",
                "functionInstance": "auto-target",
                "value": 50,
                "lastUpdateTime": mocker.ANY,
            },
            {
                "functionClass": "atomization-level",
                "functionInstance": "humidifier",
                "value": "level-3",
                "lastUpdateTime": mocker.ANY,
            },
        ],
    )
    dev = seeded_controller.items[0]
    assert dev.on.on is False
    assert dev.mode.mode == "auto"
    assert dev.target_humidity.value == 50
    assert dev.selects[MIST_LEVEL].selected == "level-3"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "expected"),
    [("turn_on", "on"), ("turn_off", "off")],
)
async def test_turn_on_off(seeded_controller, mocker, method, expected):
    # Start from the opposite state so a write is actually emitted
    seeded_controller.items[0].on.on = expected != "on"
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await getattr(seeded_controller, method)(humidifier_id)
    await seeded_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        humidifier_id,
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
    await seeded_controller.set_state(humidifier_id)
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_state_invalid_mode(seeded_controller, mocker, caplog):
    caplog.set_level(logging.DEBUG)
    update_afero_api = utils.mock_update_api(seeded_controller, mocker)
    await seeded_controller.set_state(
        humidifier_id,
        mode="i dont exist",
        selects={MIST_LEVEL: "level-3"},
    )
    await seeded_controller._bridge.async_block_until_done()
    assert "Unknown mode i dont exist" in caplog.text
    update_afero_api.assert_awaited_once_with(
        humidifier_id,
        [
            {
                "functionClass": "atomization-level",
                "functionInstance": "humidifier",
                "value": "level-3",
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert seeded_controller.items[0].mode.mode == "manual"


@pytest.fixture
def featureless_controller(seeded_controller):
    """Humidifier that did not report power, mode or target humidity."""
    dev = seeded_controller.items[0]
    dev.on = None
    dev.mode = None
    dev.target_humidity = None
    return seeded_controller


@pytest.mark.asyncio
async def test_update_elem_missing_features(featureless_controller):
    dev_update = utils.create_devices_from_data("humidifier.json")[0]
    new_states = [
        AferoState(functionClass="power", value="off", lastUpdateTime=0),
        AferoState(
            functionClass="mode",
            value="auto",
            lastUpdateTime=0,
            functionInstance="humidifier-mode",
        ),
        AferoState(
            functionClass="humidity",
            value=50,
            lastUpdateTime=0,
            functionInstance="auto-target",
        ),
        AferoState(
            functionClass="humidity",
            value=45,
            lastUpdateTime=0,
            functionInstance="current",
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await featureless_controller.update_elem(dev_update)
    dev = featureless_controller.items[0]
    assert updates == {"humidity-current"}
    assert dev.current_humidity == 45
    assert dev.on is None
    assert dev.mode is None
    assert dev.target_humidity is None


@pytest.mark.asyncio
async def test_set_state_missing_features(featureless_controller, mocker):
    update_afero_api = utils.mock_update_api(featureless_controller, mocker)
    await featureless_controller.set_state(
        humidifier_id,
        on=False,
        mode="auto",
        target_humidity=50,
        selects={MIST_LEVEL: "level-3"},
    )
    await featureless_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        humidifier_id,
        [
            {
                "functionClass": "atomization-level",
                "functionInstance": "humidifier",
                "value": "level-3",
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert featureless_controller.items[0].selects[MIST_LEVEL].selected == "level-3"
