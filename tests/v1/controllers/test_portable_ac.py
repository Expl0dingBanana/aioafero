"""Test Portable ACs"""

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers.portable_ac import (
    PortableACController,
    features,
    generate_split_name,
    get_valid_states,
    portable_ac_callback,
)
from aioafero.v1.models import ResourceTypes

from .. import utils

portable_ac = utils.create_devices_from_data("portable-ac.json")[0]
portable_ac_id = "8d0414d6-a7f7-4bdb-99d5-d866318ff559"

portable_ac_swing = utils.create_devices_from_data("myko-portable-ac-with-swing.json")[1]
portable_ac_swing_id = "c31e1854-87de-47a7-ac62-f1cefe3ecba4"

portable_ac_f = utils.create_devices_from_data("portable-ac-f.json")[0]
portable_ac_f_id = "67fc0e41-9e20-47b4-b015-cad08df65f7c"


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.portable_acs


def test_generate_split_name():
    assert (
        generate_split_name(portable_ac, "power")
        == "8d0414d6-a7f7-4bdb-99d5-d866318ff559-portable-ac-power"
    )


def test_get_valid_states():
    assert get_valid_states(portable_ac) == [
        AferoState(
            functionClass="power",
            value="off",
            lastUpdateTime=0,
            functionInstance=None,
        ),
        AferoState(
            functionClass="available",
            value=True,
            lastUpdateTime=0,
            functionInstance=None,
        ),
    ]


def test_exhaust_fan_callback():
    devs, remove_original = portable_ac_callback(portable_ac)
    assert remove_original is False
    assert len(devs) == 1
    expected_ids = [
        "8d0414d6-a7f7-4bdb-99d5-d866318ff559-portable-ac-power",
    ]
    for ind, dev in enumerate(devs):
        assert dev.id == expected_ids[ind]
        assert len(dev.states) == 2
        assert dev.device_class == ResourceTypes.SWITCH.value


def test_exhaust_fan_callback_wrong_dev():
    devs, remove_original = portable_ac_callback(
        utils.create_devices_from_data("light-a21.json")[0]
    )
    assert remove_original is False
    assert len(devs) == 0


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(portable_ac)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == portable_ac_id
    assert dev.available is True
    assert dev.current_temperature == features.CurrentTemperatureFeature(
        temperature=35,
        function_class="temperature",
        function_instance="current-temp",
    )
    assert dev.hvac_mode == features.HVACModeFeature(
        mode="auto-cool",
        previous_mode="auto-cool",
        modes={"fan", "auto-cool", "dehumidify", "cool"},
        supported_modes={"fan", "auto-cool", "dehumidify", "cool"},
    )
    assert dev.target_temperature_cooling == features.TargetTemperatureFeature(
        value=22, step=0.5, min=16, max=30, instance="cooling-target"
    )
    assert dev.numbers == {}
    assert dev.selects == {
        ("fan-speed", "ac-fan-speed"): features.SelectFeature(
            selected="fan-speed-auto",
            selects={"fan-speed-auto", "fan-speed-2-100", "fan-speed-2-050"},
            name="Fan Speed",
        ),
        ("sleep", None): features.SelectFeature(
            selected="off",
            selects={"on", "off"},
            name="Sleep Mode",
        ),
    }
    assert dev.target_temperature_heating is None
    assert dev.target_temperature_auto_heating is None
    assert dev.target_temperature_auto_cooling is None


@pytest.mark.asyncio
async def test_initialize_f(mocked_controller):
    await mocked_controller.initialize_elem(portable_ac_f)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == portable_ac_f_id
    assert dev.available is True
    assert dev.current_temperature == features.CurrentTemperatureFeature(
        temperature=82,
        function_class="temperature",
        function_instance="current-temp",
    )
    assert dev.hvac_mode == features.HVACModeFeature(
        mode="auto-cool",
        previous_mode="auto-cool",
        modes={"fan", "auto-cool", "dehumidify", "cool"},
        supported_modes={"fan", "auto-cool", "dehumidify", "cool"},
    )
    assert dev.target_temperature_cooling == features.TargetTemperatureFeature(
        value=60, step=1, min=60, max=86, instance="cooling-target"
    )
    assert dev.numbers == {}
    assert dev.selects == {
        ("fan-speed", "ac-fan-speed"): features.SelectFeature(
            selected="fan-speed-auto",
            selects={"fan-speed-auto", "fan-speed-2-100", "fan-speed-2-050"},
            name="Fan Speed",
        ),
        ("sleep", None): features.SelectFeature(
            selected="off",
            selects={"on", "off"},
            name="Sleep Mode",
        ),
    }
    assert dev.target_temperature_heating is None
    assert dev.target_temperature_auto_heating is None
    assert dev.target_temperature_auto_cooling is None


@pytest.mark.asyncio
async def test_initialize_swing(mocked_controller):
    await mocked_controller.initialize_elem(portable_ac_swing)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == portable_ac_swing_id
    assert dev.available is True
    assert dev.current_temperature == features.CurrentTemperatureFeature(
        temperature=21,
        function_class="temperature",
        function_instance="current-temp",
    )
    assert dev.hvac_mode == features.HVACModeFeature(
        mode="cool",
        previous_mode="cool",
        modes={"fan", "dehumidify", "heat", "cool"},
        supported_modes={"fan", "dehumidify", "heat", "cool"},
    )
    assert dev.target_temperature_cooling == features.TargetTemperatureFeature(
        value=21, step=1, min=16, max=31, instance="cooling-target"
    )
    assert dev.target_temperature_heating == features.TargetTemperatureFeature(
        value=31, step=1, min=16, max=31, instance="heating-target"
    )
    assert dev.numbers == {}
    assert dev.selects == {
        ("fan-speed", "ac-fan-speed"): features.SelectFeature(
            selected="fan-speed-3-033",
            selects={"fan-speed-3-100", "fan-speed-3-033", "fan-speed-3-066"},
            name="Fan Speed",
        ),
        ("sleep", None): features.SelectFeature(
            selected="off",
            selects={"on", "off"},
            name="Sleep Mode",
        ),
        ("air-swing", None): features.SelectFeature(
            selected="on",
            selects={"on", "off"},
            name="Swing",
        ),
    }


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(portable_ac)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("portable-ac.json")[0]
    new_states = [
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="temperature", value=19, lastUpdateTime=0, functionInstance="current-temp"
        ),
        AferoState(
            functionClass="temperature", value=18, lastUpdateTime=0, functionInstance="cooling-target"
        ),
        AferoState(
            functionClass="mode", value="cool", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="fan-speed",
            functionInstance="ac-fan-speed",
            lastUpdateTime=0,
            value="fan-speed-2-100",
        ),
        AferoState(
            functionClass="temperature-units",
            functionInstance=None,
            lastUpdateTime=0,
            value="celsius",
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.available is False
    assert dev.current_temperature == features.CurrentTemperatureFeature(
        temperature=19,
        function_class="temperature",
        function_instance="current-temp",
    )
    assert dev.target_temperature_cooling.value == 18
    assert dev.hvac_mode.mode == "cool"
    assert dev.hvac_mode.previous_mode == "auto-cool"
    assert dev.selects[("fan-speed", "ac-fan-speed")].selected == "fan-speed-2-100"
    assert updates == {
        "available",
        "temperature-cooling-target",
        "temperature-current-temp",
        "mode",
        "select-('fan-speed', 'ac-fan-speed')",
    }


@pytest.mark.asyncio
async def test_update_elem_no_updates(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(portable_ac)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("portable-ac.json")[0]
    updates = await mocked_controller.update_elem(dev_update)
    assert updates == set()


@pytest.mark.asyncio
async def test_set_state(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(portable_ac)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        portable_ac_id,
        hvac_mode="cool",
        target_temperature=22.5,
        selects={("fan-speed", "ac-fan-speed"): "fan-speed-2-100", ("nope", "exist", None): "nope"},
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller.items[0]
    assert dev.target_temperature_cooling.value == 22.5
    assert dev.hvac_mode.mode == "cool"
    assert dev.hvac_mode.previous_mode == "auto-cool"
    assert dev.selects[("fan-speed", "ac-fan-speed")].selected == "fan-speed-2-100"

@pytest.mark.asyncio
async def test_set_state_invalid_dev(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(portable_ac)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        "nope",
        hvac_mode="cool",
        target_temperature=22.5,
        selects={("fan-speed", "ac-fan-speed"): "fan-speed-2-100"},
    )
    mocked_controller._bridge.request.assert_not_called()


@pytest.mark.asyncio
async def test_set_state_no_updates(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(portable_ac)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        portable_ac_id,
    )
    mocked_controller._bridge.request.assert_not_called()


@pytest.mark.asyncio
async def test_set_state_invalid_updates(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(portable_ac)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        portable_ac_id,
        hvac_mode="i dont exist",
        selects={(None, None): 7, ("fan-speed", "ac-fan-speed"): "fan-speed-2-100"},
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller.items[0]
    assert dev.selects[("fan-speed", "ac-fan-speed")].selected == "fan-speed-2-100"
