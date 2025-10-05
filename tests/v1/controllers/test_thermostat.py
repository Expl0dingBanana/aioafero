"""Test ThermostatController"""

import logging

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers.device import AferoBinarySensor
from aioafero.v1.controllers.thermostat import (
    ThermostatController,
    features,
    get_supported_modes,
)

from .. import utils

thermostat = utils.create_devices_from_data("thermostat.json")[0]
thermostat_id = "cc770a99-25da-4888-8a09-2a569da5be08"


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.thermostats


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(thermostat)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[thermostat.id]
    assert dev.id == thermostat_id
    assert dev.current_temperature.temperature == 18.3
    assert dev.fan_mode == features.ModeFeature(
        mode="auto", modes={"on", "auto", "intermittent"}
    )
    assert dev.fan_running is False
    assert dev.hvac_action == "off"
    assert dev.hvac_mode == features.HVACModeFeature(
        mode="heat",
        previous_mode="heat",
        modes={"off", "heat", "auto", "fan", "cool"},
        supported_modes={"off", "heat", "fan"},
    )
    assert dev.safety_max_temp == features.TargetTemperatureFeature(
        value=36, min=29.5, max=37, step=0.5, instance="safety-mode-max-temp"
    )
    assert dev.safety_min_temp == features.TargetTemperatureFeature(
        value=4, min=4, max=13, step=0.5, instance="safety-mode-min-temp"
    )
    assert dev.target_temperature_auto_cooling == features.TargetTemperatureFeature(
        value=26.5, step=0.5, min=10, max=37, instance="auto-cooling-target"
    )
    assert dev.target_temperature_auto_heating == features.TargetTemperatureFeature(
        value=18.5, step=0.5, min=4, max=32, instance="auto-heating-target"
    )
    assert dev.target_temperature_cooling == features.TargetTemperatureFeature(
        value=26.5, step=0.5, min=10, max=37, instance="cooling-target"
    )
    assert dev.target_temperature_heating == features.TargetTemperatureFeature(
        value=18, step=0.5, min=4, max=32, instance="heating-target"
    )
    assert dev.sensors == {}
    assert dev.binary_sensors == {
        "filter-replacement|None": AferoBinarySensor(
            id="filter-replacement|None",
            owner="cc770a99-25da-4888-8a09-2a569da5be08",
            current_value="not-needed",
            _error="replacement-needed",
            instance=None,
        ),
        "max-temp-exceeded|None": AferoBinarySensor(
            id="max-temp-exceeded|None",
            owner="cc770a99-25da-4888-8a09-2a569da5be08",
            current_value="normal",
            _error="alerting",
            instance=None,
        ),
        "min-temp-exceeded|None": AferoBinarySensor(
            id="min-temp-exceeded|None",
            owner="cc770a99-25da-4888-8a09-2a569da5be08",
            current_value="normal",
            _error="alerting",
            instance=None,
        ),
    }


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller[thermostat_id].hvac_mode.mode = "heat"
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("thermostat.json")[0]
    new_states = [
        AferoState(
            functionClass="current-fan-state", value="on", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="fan-mode", value="on", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="temperature", value=22, lastUpdateTime=0, functionInstance="auto-heating-target"
        ),
        AferoState(
            functionClass="temperature", value=22.5, lastUpdateTime=0, functionInstance="auto-cooling-target"
        ),
        AferoState(
            functionClass="temperature", value=17, lastUpdateTime=0, functionInstance="heating-target"
        ),
        AferoState(
            functionClass="temperature", value=18, lastUpdateTime=0, functionInstance="cooling-target"
        ),
        AferoState(
            functionClass="temperature", value=19, lastUpdateTime=0, functionInstance="current-temp"
        ),
        AferoState(
            functionClass="temperature", value=35, lastUpdateTime=0, functionInstance="safety-mode-max-temp"
        ),
        AferoState(
            functionClass="temperature", value=32, lastUpdateTime=0, functionInstance="safety-mode-min-temp"
        ),
        AferoState(
            functionClass="mode", value="cool", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="current-system-state", value="cooling", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller[thermostat_id]
    assert dev.current_temperature.temperature == 19
    assert dev.fan_running is True
    assert dev.fan_mode.mode == "on"
    assert dev.hvac_action == "cooling"
    assert dev.hvac_mode.mode == "cool"
    assert dev.hvac_mode.previous_mode == "heat"
    assert dev.safety_max_temp.value == 35
    assert dev.safety_min_temp.value == 32
    assert dev.target_temperature_auto_heating.value == 22
    assert dev.target_temperature_auto_cooling.value == 22.5
    assert dev.target_temperature_heating.value == 17
    assert dev.target_temperature_cooling.value == 18
    assert dev.available is False
    assert updates == {
        "temperature-safety-mode-max-temp",
        "temperature-heating-target",
        "temperature-auto-cooling-target",
        "temperature-cooling-target",
        "current-fan-state",
        "temperature-current-temp",
        "current-system-state",
        "available",
        "temperature-auto-heating-target",
        "mode",
        "temperature-safety-mode-min-temp",
        "fan-mode",
    }


@pytest.mark.asyncio
async def test_update_elem_no_prev_mode_change(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller[thermostat_id].hvac_mode.mode = "off"
    mocked_controller[thermostat_id].hvac_mode.previous_mode = "heat"
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("thermostat.json")[0]
    new_states = [
        AferoState(
            functionClass="mode", value="cool", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="temperature-units", value="fahrenheit", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller[thermostat_id]
    assert dev.hvac_mode.mode == "cool"
    assert dev.hvac_mode.previous_mode == "heat"
    assert updates == {"mode"}


@pytest.mark.asyncio
async def test_update_elem_no_updates(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller[thermostat_id].hvac_mode.mode = "heat"
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("thermostat.json")[0]
    new_states = [
        AferoState(
            functionClass="current-fan-state", value="off", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="fan-mode", value="auto", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="temperature", value=18.5, lastUpdateTime=0, functionInstance="auto-heating-target"
        ),
        AferoState(
            functionClass="temperature", value=26.5, lastUpdateTime=0, functionInstance="auto-cooling-target"
        ),
        AferoState(
            functionClass="temperature", value=18, lastUpdateTime=0, functionInstance="heating-target"
        ),
        AferoState(
            functionClass="temperature", value=26.5, lastUpdateTime=0, functionInstance="cooling-target"
        ),
        AferoState(
            functionClass="temperature", value=18.3, lastUpdateTime=0, functionInstance="current-temp"
        ),
        AferoState(
            functionClass="temperature", value=36, lastUpdateTime=0, functionInstance="safety-mode-max-temp"
        ),
        AferoState(
            functionClass="temperature", value=4, lastUpdateTime=0, functionInstance="safety-mode-min-temp"
        ),
        AferoState(
            functionClass="mode", value="heat", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="current-system-state", value="off", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="available", value=True, lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    assert updates == set()


@pytest.mark.asyncio
async def test_set_state(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller[thermostat_id].hvac_mode.mode = "heat"
    mocked_controller[thermostat_id].hvac_mode.supported_modes.add("cool")
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(
        thermostat_id,
        hvac_mode="cool",
        safety_max_temp=35,
        safety_min_temp=8,
        target_temperature_auto_heating=22,
        target_temperature_auto_cooling=22.5,
        target_temperature_heating=17,
        target_temperature_cooling=18,
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    assert dev.fan_mode.mode == "auto"
    assert dev.fan_running is False
    assert dev.hvac_mode.mode == "cool"
    assert dev.safety_max_temp.value == 35
    assert dev.safety_min_temp.value == 8
    assert dev.target_temperature_auto_heating.value == 22
    assert dev.target_temperature_auto_cooling.value == 22.5
    assert dev.target_temperature_heating.value == 17
    assert dev.target_temperature_cooling.value == 18


@pytest.mark.asyncio
async def test_set_state_in_f_force_c(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[thermostat_id].hvac_mode.mode = "heat"
    mocked_controller[thermostat_id].hvac_mode.supported_modes.add("cool")
    await mocked_controller.set_state(
        thermostat_id,
        hvac_mode="cool",
        safety_max_temp=35,
        safety_min_temp=8,
        target_temperature_auto_heating=22,
        target_temperature_auto_cooling=22.5,
        target_temperature_heating=17,
        target_temperature_cooling=18,
        is_celsius=True,
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    assert dev.fan_mode.mode == "auto"
    assert dev.fan_running is False
    assert dev.hvac_mode.mode == "cool"
    assert dev.safety_max_temp.value == 35
    assert dev.safety_min_temp.value == 8
    assert dev.target_temperature_auto_heating.value == 22
    assert dev.target_temperature_auto_cooling.value == 22.5
    assert dev.target_temperature_heating.value == 17
    assert dev.target_temperature_cooling.value == 18


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_mode, prev_mode, params, expected_result, expected_messages",
    [
        # Testing target_temp / cooling
        (
            "cool",
            "cool",
            {"target_temperature": 25},
            {"instance": "cooling-target", "value": 25},
            [],
        ),
        # Testing target_temp / cooling
        (
            "heat",
            "heat",
            {"target_temperature": 24},
            {"instance": "heating-target", "value": 24},
            [],
        ),
        # Testing changing mode
        (
            "heat",
            "heat",
            {"target_temperature": 24, "hvac_mode": "cool"},
            {"instance": "cooling-target", "value": 24, "mode": "cool"},
            [],
        ),
        # Testing target_temp / debug message
        (
            "off",
            "off",
            {"target_temperature": 25},
            [],
            ["Unable to set the target temperature due to the active mode: off"],
        ),
        # Invalid fan mode
        (
            "auto",
            "cool",
            {"fan_mode": "beans"},
            [],
            ["Unknown fan mode beans. Available modes: auto, intermittent, on"],
        ),
        # Invalid hvac mode
        (
            "auto",
            "cool",
            {"hvac_mode": "beans"},
            [],
            ["Unknown hvac mode beans. Available modes: cool, fan, heat, off"],
        ),
    ],
)
async def test_set_state_hvac_generics(
    current_mode,
    prev_mode,
    params,
    expected_result,
    expected_messages,
    mocked_controller,
    caplog,
):
    caplog.set_level(logging.DEBUG)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller[thermostat_id].hvac_mode.mode = current_mode
    mocked_controller[thermostat_id].hvac_mode.supported_modes.add("cool")
    mocked_controller[thermostat_id].hvac_mode.previous_mode = prev_mode
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(thermostat_id, **params)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    if expected_result:
        if "mode" in expected_result:
            assert dev.hvac_mode.mode == expected_result["mode"]
        if expected_result["instance"] == "heating-target":
            assert dev.target_temperature_heating.value == expected_result["value"]
        elif expected_result["instance"] == "cooling-target":
            assert dev.target_temperature_cooling.value == expected_result["value"]
    for message in expected_messages:
        assert message in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fan_mode, hvac_mode, params, expected_states, expected_messages",
    [
        (
            "off",
            "off",
            {"fan_mode": "auto"},
            {"fan-mode": "auto", "mode": "fan"},
            [],
        ),
        (
            "on",
            "fan",
            {"fan_mode": "auto"},
            {"fan-mode": "auto", "mode": "fan"},
            [],
        ),
        (
            "off",
            "off",
            {"fan_mode": "bad"},
            [],
            ["Unknown fan mode bad. Available modes: auto, intermittent, on"],
        ),
    ],
)
async def test_set_state_fan_generics(
    fan_mode,
    hvac_mode,
    params,
    expected_states,
    expected_messages,
    mocked_controller,
    caplog,
):
    caplog.set_level(logging.DEBUG)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    mocked_controller[thermostat_id].hvac_mode.mode = hvac_mode
    mocked_controller[thermostat_id].fan_mode.mode = fan_mode
    assert len(mocked_controller.items) == 1
    await mocked_controller.set_state(thermostat_id, **params)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    if expected_states:
        assert dev.fan_mode.mode == expected_states["fan-mode"]
        assert dev.hvac_mode.mode == expected_states["mode"]
    for message in expected_messages:
        assert message in caplog.text


@pytest.mark.asyncio
async def test_set_fan_mode(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[thermostat_id].fan_mode.mode = "off"
    await mocked_controller.set_fan_mode(thermostat_id, "on")
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    assert dev.fan_mode.mode == "on"
    assert dev.hvac_mode.mode == "fan"


@pytest.mark.asyncio
async def test_set_hvac_mode(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[thermostat_id].hvac_mode.mode = "heat"
    mocked_controller[thermostat_id].hvac_mode.supported_modes.add("cool")
    await mocked_controller.set_hvac_mode(thermostat_id, "cool")
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    assert dev.hvac_mode.mode == "cool"


@pytest.mark.asyncio
async def test_set_target_temperature(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[thermostat_id].hvac_mode.mode = "heat"
    mocked_controller[thermostat_id].target_temperature_heating.value = 20
    await mocked_controller.set_target_temperature(thermostat_id, 21)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    assert dev.target_temperature_heating.value == 21


@pytest.mark.asyncio
async def test_set_temperature_range(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(thermostat)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[thermostat_id].hvac_mode.mode = "auto"
    mocked_controller[thermostat_id].target_temperature_auto_heating.value = 20
    mocked_controller[thermostat_id].target_temperature_auto_cooling.value = 21
    await mocked_controller.set_temperature_range(thermostat_id, 21, 22)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[thermostat_id]
    assert dev.target_temperature_auto_heating.value == 21
    assert dev.target_temperature_auto_cooling.value == 22


standard = {"heat", "cool", "off", "fan", "auto"}


@pytest.mark.parametrize(
    "system_type, modes, expected",
    [
        ("cool-beans", {"heat", "cool", "beans"}, {"beans"}),
        ("1-compressor-heat-pump-1-aux-on-cool-boiler-aux", standard, standard),
        ("1-stage-cooling-conventional", standard, {"cool", "off", "fan"}),
        ("1-stage-heating-conventional-boiler", standard, {"heat", "off", "fan"}),
    ],
)
def test_get_supported_modes(system_type, modes, expected):
    assert get_supported_modes(system_type, modes) == expected


async def set_state_invalid_device(mocked_controller):
    assert await mocked_controller.set_state("invalid", hvac_mode="cool") is None
