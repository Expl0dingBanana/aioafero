"""Test LightController"""

import pytest

from aioafero.device import AferoDevice, AferoState, merge_afero_states
from aioafero.v1.controllers import event, light
from aioafero.v1.controllers.base import get_afero_instance_for_state
from aioafero.v1.controllers.light import (
    features,
    process_color_temps,
    state_matches_instance,
)
from aioafero.v1.models.features import ColorFeature, EffectFeature
from aioafero.v1.models.light import Light
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes
from tests.v1 import utils

a21_light = utils.create_devices_from_data("light-a21.json")[0]
zandra_light = utils.create_devices_from_data("fan-ZandraFan.json")[1]
dimmer_light = utils.create_devices_from_data("dimmer-HPDA1110NWBP.json")[0]
speed_light = utils.create_devices_from_data("light-with-speed.json")[2]
flushmount_light = utils.create_devices_from_data("light-flushmount.json")[0]

speaker_power_light = utils.create_devices_from_data("light-with-speaker.json")[0]
speaker_power_light_speaker_id = f"{speaker_power_light.id}-light-speaker-power"

trim_light = utils.create_devices_from_data("light-with-trim.json")[0]
trim_light_primary_id = f"{trim_light.id}-light-main"
trim_light_trim_id = f"{trim_light.id}-light-trim"

rgbcw_strip_light = utils.create_devices_from_data("rgbcw-led-strip.json")[0]


def _trim_update_with_states(
    trim_dev: Light,
    *,
    main_power: str | None = None,
    main_brightness: int | None = None,
    main_color_rgb: dict | None = None,
    main_color_mode: str | None = None,
    main_color_temperature: int | None = None,
) -> AferoDevice:
    """Build an inbound AferoDevice update containing only main-zone states."""
    states: list[AferoState] = []
    if main_power is not None:
        states.append(
            AferoState(
                functionClass="power",
                value=main_power,
                lastUpdateTime=0,
                functionInstance="main",
            )
        )
    if main_brightness is not None:
        states.append(
            AferoState(
                functionClass="brightness",
                value=main_brightness,
                lastUpdateTime=0,
                functionInstance="main",
            )
        )
    if main_color_rgb is not None:
        states.append(
            AferoState(
                functionClass="color-rgb",
                value=main_color_rgb,
                lastUpdateTime=0,
                functionInstance="main",
            )
        )
    if main_color_mode is not None:
        states.append(
            AferoState(
                functionClass="color-mode",
                value=main_color_mode,
                lastUpdateTime=0,
                functionInstance="main",
            )
        )
    if main_color_temperature is not None:
        states.append(
            AferoState(
                functionClass="color-temperature",
                value=main_color_temperature,
                lastUpdateTime=0,
                functionInstance="main",
            )
        )
    return AferoDevice(
        id=trim_dev.id,
        device_id=trim_light.device_id,
        model=trim_light.model,
        device_class=ResourceTypes.LIGHT.value,
        default_name=trim_light.default_name,
        default_image=trim_light.default_image,
        friendly_name=trim_dev.device_information.name,
        split_identifier="light",
        states=states,
    )


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.lights


def test_generate_split_name():
    assert (
        light.generate_split_name(a21_light, "beans") == f"{a21_light.id}-light-beans"
    )


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        # Dual-channel RGB+WW fixtures stay one light
        (
            flushmount_light,
            [],
        ),
        (
            rgbcw_strip_light,
            [],
        ),
        # trim split
        (
            trim_light,
            [
                ("main", ResourceTypes.LIGHT),
                ("trim", ResourceTypes.LIGHT),
            ],
        ),
        # No splits
        (a21_light, []),
        (zandra_light, []),
        (dimmer_light, []),
    ],
)
def test_get_split_instances(device, expected):
    assert light.get_split_instances(device) == expected


@pytest.mark.parametrize(
    ("device", "instance", "expected"),
    [
        # Pull out speaker power
        (
            speaker_power_light,
            "speaker-power",
            [
                AferoState(
                    functionClass="toggle",
                    value="off",
                    lastUpdateTime=0,
                    functionInstance="speaker-power",
                ),
                AferoState(
                    functionClass="available",
                    value=True,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
            ],
        ),
        # Trim Light - main
        (
            trim_light,
            "main",
            [
                AferoState(
                    functionClass="color-mode",
                    value="white",
                    lastUpdateTime=0,
                    functionInstance="main",
                ),
                AferoState(
                    functionClass="color-rgb",
                    value={"color-rgb": {"r": 255, "b": 0, "g": 51}},
                    lastUpdateTime=0,
                    functionInstance="main",
                ),
                AferoState(
                    functionClass="color-temperature",
                    value=3000,
                    lastUpdateTime=0,
                    functionInstance="main",
                ),
                AferoState(
                    functionClass="brightness",
                    value=100,
                    lastUpdateTime=0,
                    functionInstance="main",
                ),
                AferoState(
                    functionClass="power",
                    value="on",
                    lastUpdateTime=0,
                    functionInstance="main",
                ),
                AferoState(
                    functionClass="available",
                    value=False,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
            ],
        ),
        # Trim Light - trim
        (
            trim_light,
            "trim",
            [
                AferoState(
                    functionClass="color-mode",
                    value="white",
                    lastUpdateTime=0,
                    functionInstance="trim",
                ),
                AferoState(
                    functionClass="color-rgb",
                    value={"color-rgb": {"r": 255, "b": 0, "g": 255}},
                    lastUpdateTime=0,
                    functionInstance="trim",
                ),
                AferoState(
                    functionClass="brightness",
                    value=100,
                    lastUpdateTime=0,
                    functionInstance="trim",
                ),
                AferoState(
                    functionClass="power",
                    value="off",
                    lastUpdateTime=0,
                    functionInstance="trim",
                ),
                AferoState(
                    functionClass="available",
                    value=False,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
            ],
        ),
    ],
)
def test_get_valid_states(device, instance, expected):
    assert light.get_valid_states(device, instance) == expected


def test_is_dual_channel_rgb_fixture():
    """RGBCW strips and flushmounts expose color/white channels on one fixture."""
    assert light.is_dual_channel_rgb_fixture(flushmount_light)
    assert light.is_dual_channel_rgb_fixture(rgbcw_strip_light)
    assert not light.is_dual_channel_rgb_fixture(trim_light)
    assert not light.is_dual_channel_rgb_fixture(a21_light)


def test_is_dual_channel_rgb_fixture_from_functions_without_states():
    """Dual-channel detection must not depend on runtime state values."""
    dev = AferoDevice(
        id="strip",
        device_id="strip-dev",
        model="AL-TP-RGBCW-60",
        device_class="light",
        default_name="Strip",
        default_image="icon",
        friendly_name="Strip",
        functions=rgbcw_strip_light.functions,
        states=[],
    )
    assert light.is_dual_channel_rgb_fixture(dev)
    assert light.get_split_instances(dev) == []


def test_preferred_brightness_instance_dual_channel():
    """Dual-channel lights use primary brightness when present."""
    assert light.preferred_brightness_instance(rgbcw_strip_light) == "primary"
    assert light.preferred_brightness_instance(flushmount_light) == "primary"


def test_preferred_brightness_instance_fallbacks():
    """Without primary, prefer null instance then the last brightness zone."""
    none_instance_dev = AferoDevice(
        id="strip-none",
        device_id="strip-dev",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="f",
        states=[
            AferoState(functionClass="brightness", value=50, functionInstance="color"),
            AferoState(functionClass="brightness", value=50, functionInstance=None),
        ],
    )
    assert light.preferred_brightness_instance(none_instance_dev) is None

    last_zone_dev = AferoDevice(
        id="strip-last",
        device_id="strip-dev",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="f",
        states=[
            AferoState(functionClass="brightness", value=50, functionInstance="color"),
            AferoState(functionClass="brightness", value=50, functionInstance="white"),
        ],
    )
    assert light.preferred_brightness_instance(last_zone_dev) == "white"


def test_should_use_brightness_state_non_brightness():
    """Non-brightness rows are always eligible for model updates."""
    assert (
        light.should_use_brightness_state(
            flushmount_light,
            AferoState(functionClass="power", value="on"),
        )
        is True
    )


def test_get_split_instances_skips_toggle_matching_light_zone():
    """Do not expose a switch when the zone is already a split light."""
    multi_zone = AferoDevice(
        id="multi",
        device_id="d",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="f",
        states=[
            AferoState(functionClass="brightness", value=50, functionInstance="main"),
            AferoState(functionClass="brightness", value=50, functionInstance="trim"),
            AferoState(functionClass="toggle", value="on", functionInstance="main"),
            AferoState(functionClass="toggle", value="on", functionInstance="speaker"),
        ],
    )
    splits = light.get_split_instances(multi_zone)
    assert splits == [
        ("main", ResourceTypes.LIGHT),
        ("speaker", ResourceTypes.SWITCH),
        ("trim", ResourceTypes.LIGHT),
    ]


def test_get_color_modes_for_device_fallback_without_instance_match():
    """Use the first color-mode function when the zone instance does not match."""
    split_dev = AferoDevice(
        id=trim_light_primary_id,
        device_id=trim_light.device_id,
        model=trim_light.model,
        device_class="light",
        default_name=trim_light.default_name,
        default_image=trim_light.default_image,
        friendly_name="main",
        split_identifier="light",
        states=[],
        functions=[
            {
                "functionClass": "color-mode",
                "functionInstance": "other",
                "values": [{"name": "white"}, {"name": "color"}],
            }
        ],
    )
    assert light.get_color_modes_for_device(split_dev) == ["white", "color"]


@pytest.mark.parametrize(
    ("color_mode", "color", "temperature", "effect", "expected"),
    [
        (None, None, None, None, "primary"),
        ("color", None, None, None, "color"),
        ("white", None, None, None, "white"),
        ("sequence", None, None, None, "color"),
        (None, (1, 2, 3), None, None, "color"),
        (None, None, 3000, None, "white"),
        (None, None, None, "sleep", "color"),
    ],
)
def test_resolve_brightness_instance_dual_channel(
    color_mode, color, temperature, effect, expected
):
    """Dual-channel PUTs target the active color or white channel when appropriate."""
    cur_item = Light(
        _id=flushmount_light.id,
        available=True,
        dual_channel=True,
        color_brightness=1,
        white_brightness=100,
        dimming=features.DimmingFeature(
            brightness=50, supported=[1, 100], func_instance="primary"
        ),
    )
    assert (
        light.resolve_brightness_instance(
            cur_item,
            color_mode=color_mode,
            color=color,
            temperature=temperature,
            effect=effect,
        )
        == expected
    )


def test_resolve_brightness_instance_from_cached_white_mode():
    """Brightness-only PUTs follow cached white mode when no explicit mode is passed."""
    cur_item = Light(
        _id=flushmount_light.id,
        available=True,
        dual_channel=True,
        color_mode=features.ColorModeFeature("white"),
        dimming=features.DimmingFeature(
            brightness=50, supported=[1, 100], func_instance="primary"
        ),
    )
    assert light.resolve_brightness_instance(cur_item) == "white"


def test_rgbcw_fixture_is_not_split():
    """RGBCW strips remain a single light with full color capabilities."""
    multi_devs, remove_dev = light.light_callback(rgbcw_strip_light)
    assert remove_dev is False
    assert multi_devs == []


def test_light_callback():
    multi_devs, remove_dev = light.light_callback(flushmount_light)
    assert remove_dev is False
    assert multi_devs == []


def test_light_speaker():
    multi_devs, remove_dev = light.light_callback(speaker_power_light)
    assert remove_dev is False
    assert len(multi_devs) == 1
    assert multi_devs[0].id == speaker_power_light_speaker_id
    assert multi_devs[0].device_class == ResourceTypes.SWITCH.value
    assert len(multi_devs[0].states) == 2


def test_light_callback_none():
    multi_devs, remove_dev = light.light_callback(a21_light)
    assert remove_dev is False
    assert len(multi_devs) == 0


def test_light_trim_callback():
    multi_devs, remove_dev = light.light_callback(trim_light)
    assert remove_dev is True
    assert len(multi_devs) == 3
    assert multi_devs[0].id == trim_light_primary_id
    assert multi_devs[0].friendly_name == f"{trim_light.friendly_name} - main"
    assert len(multi_devs[0].states) == 6
    assert multi_devs[0].device_class == ResourceTypes.LIGHT.value
    assert multi_devs[1].id == trim_light_trim_id
    assert len(multi_devs[1].states) == 5
    assert multi_devs[1].friendly_name == f"{trim_light.friendly_name} - trim"
    assert multi_devs[1].device_class == ResourceTypes.LIGHT.value
    assert multi_devs[2].id == trim_light.id
    assert len(multi_devs[2].states) == 7
    assert multi_devs[2].device_class == "parent-device"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            AferoState(
                functionClass="power",
                value="on",
                lastUpdateTime=0,
                functionInstance="trim",
            ),
            True,
        ),
        (
            AferoState(
                functionClass="power",
                value="off",
                lastUpdateTime=0,
                functionInstance="main",
            ),
            False,
        ),
        (
            AferoState(
                functionClass="power",
                value="on",
                lastUpdateTime=0,
                functionInstance="global",
            ),
            False,
        ),
        (
            AferoState(
                functionClass="available",
                value=True,
                lastUpdateTime=0,
                functionInstance=None,
            ),
            True,
        ),
    ],
)
def test_state_matches_instance_trim_zone(state, expected):
    """Inbound split updates must ignore other zones and global controls."""
    trim_device = AferoDevice(
        id=trim_light_trim_id,
        device_id=trim_light.device_id,
        model=trim_light.model,
        device_class="light",
        default_name=trim_light.default_name,
        default_image=trim_light.default_image,
        friendly_name="trim",
        split_identifier="light",
    )
    assert state_matches_instance(trim_device, state) is expected


@pytest.mark.asyncio
async def test_update_elem_flushmount_applies_null_instance_rgb(
    mocked_controller,
):
    """Inbound null-instance color-rgb must update the unsplit flushmount light."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[flushmount_light.id]
    dev_update = AferoDevice(
        id=flushmount_light.id,
        device_id=flushmount_light.device_id,
        model=flushmount_light.model,
        device_class="light",
        default_name=flushmount_light.default_name,
        default_image=flushmount_light.default_image,
        friendly_name=dev.device_information.name,
        states=[
            AferoState(
                functionClass="color-rgb",
                value={"color-rgb": {"r": 10, "g": 20, "b": 30}},
                lastUpdateTime=0,
                functionInstance=None,
            )
        ],
    )
    updates = await mocked_controller.update_elem(dev_update)
    assert dev.color.red == 10
    assert dev.color.green == 20
    assert dev.color.blue == 30
    assert "color" in updates


@pytest.mark.asyncio
async def test_update_elem_dual_channel_brightness_fields(mocked_controller):
    """Dual-channel updates track per-channel brightness and dimming instance."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[flushmount_light.id]
    dev.dimming.func_instance = "color"
    dev_update = AferoDevice(
        id=flushmount_light.id,
        device_id=flushmount_light.device_id,
        model=flushmount_light.model,
        device_class="light",
        default_name=flushmount_light.default_name,
        default_image=flushmount_light.default_image,
        friendly_name=dev.device_information.name,
        states=[
            AferoState(
                functionClass="brightness",
                value=25,
                lastUpdateTime=0,
                functionInstance="color",
            ),
            AferoState(
                functionClass="brightness",
                value=75,
                lastUpdateTime=0,
                functionInstance="white",
            ),
            AferoState(
                functionClass="brightness",
                value=40,
                lastUpdateTime=0,
                functionInstance="primary",
            ),
        ],
    )
    updates = await mocked_controller.update_elem(dev_update)
    assert dev.color_brightness == 25
    assert dev.white_brightness == 75
    assert dev.dimming.brightness == 40
    assert dev.dimming.func_instance == "primary"
    assert updates == {"color_brightness", "white_brightness", "dimming"}


@pytest.mark.asyncio
async def test_parent_cache_keeps_full_states_after_trim_split(mocked_bridge):
    """Parent metadevice cache must stay the full device, not the parent-device shell."""
    await mocked_bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_bridge.async_block_until_done()
    parent = mocked_bridge.get_afero_device(trim_light.id)
    assert parent.device_class == "light"
    assert any(
        s.functionClass == "power" and s.functionInstance == "main"
        for s in parent.states
    )
    assert any(
        s.functionClass == "power" and s.functionInstance == "trim"
        for s in parent.states
    )


@pytest.mark.asyncio
async def test_split_children_exclude_parent_id_and_dedupe(mocked_bridge):
    """Parent children list must not include the parent id and must not grow on re-split."""
    await mocked_bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_bridge.async_block_until_done()
    parent = mocked_bridge.get_afero_device(trim_light.id)
    assert trim_light.id not in parent.children
    assert trim_light_trim_id in parent.children
    assert trim_light_primary_id in parent.children
    children_after_first = list(parent.children)
    await mocked_bridge.events.split_devices([parent])
    assert parent.children == children_after_first


@pytest.mark.asyncio
async def test_split_devices_cache_split_clones(mocked_bridge):
    """Split children must be cached as filtered clones, not the parent device."""
    await mocked_bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_bridge.async_block_until_done()
    trim_cached = mocked_bridge.get_afero_device(trim_light_trim_id)
    assert trim_cached.split_identifier == "light"
    assert trim_cached.id == trim_light_trim_id
    assert all(
        s.functionInstance in (None, "trim") or s.functionClass == "available"
        for s in trim_cached.states
        if s.functionClass
        in ("power", "brightness", "color-rgb", "color-mode", "color-temperature")
    )


@pytest.mark.asyncio
async def test_trim_split_initializes_without_color_temperature(mocked_controller):
    """Trim zone has white/RGB in API but no trim color-temperature (Hubspace Kelvin UI gap)."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    main_dev = mocked_controller[trim_light_primary_id]
    assert trim_dev.color_temperature is None
    assert main_dev.color_temperature is not None
    assert trim_dev.color_mode is not None
    assert "white" in (trim_dev.color_modes or [])


def test_get_color_modes_for_device_trim_vs_main():
    """Each split zone uses its own color-mode function definition."""
    trim_light = utils.create_devices_from_data("light-with-trim.json")[0]
    # Build split-shaped devices like light_callback does
    trim_afero = AferoDevice(
        id=trim_light_trim_id,
        device_id=trim_light.device_id,
        model=trim_light.model,
        device_class="light",
        default_name=trim_light.default_name,
        default_image=trim_light.default_image,
        friendly_name="trim",
        split_identifier="light",
        states=light.get_valid_states(trim_light, "trim"),
        functions=trim_light.functions,
    )
    main_afero = AferoDevice(
        id=trim_light_primary_id,
        device_id=trim_light.device_id,
        model=trim_light.model,
        device_class="light",
        default_name=trim_light.default_name,
        default_image=trim_light.default_image,
        friendly_name="main",
        split_identifier="light",
        states=light.get_valid_states(trim_light, "main"),
        functions=trim_light.functions,
    )
    trim_modes = light.get_color_modes_for_device(trim_afero)
    main_modes = light.get_color_modes_for_device(main_afero)
    assert trim_modes == ["sequence", "white", "color"]
    assert main_modes == ["circadian-rhythm", "sequence", "white", "color"]
    assert "circadian-rhythm" not in trim_modes


@pytest.mark.asyncio
async def test_get_afero_instance_for_trim_split_uses_elem_instance(mocked_controller):
    """Outbound must use elem.instance; get_instance() alone would pick main."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_resource = mocked_controller[trim_light_trim_id]
    assert trim_resource.instance == "trim"
    assert trim_resource.get_instance("color-rgb") == "main"
    assert (
        get_afero_instance_for_state(
            trim_resource, ColorFeature(red=0, green=0, blue=0), "color-rgb"
        )
        == "trim"
    )


def test_merge_afero_states_preserves_other_instances():
    """Partial API payloads must not drop other functionInstance rows."""
    existing = [
        AferoState(functionClass="power", value="on", functionInstance="main"),
        AferoState(functionClass="power", value="off", functionInstance="trim"),
    ]
    incoming = [
        AferoState(functionClass="power", value="off", functionInstance="main"),
    ]
    merged = merge_afero_states(existing, incoming)
    by_key = {(s.functionClass, s.functionInstance): s.value for s in merged}
    assert by_key[("power", "main")] == "off"
    assert by_key[("power", "trim")] == "off"


@pytest.mark.asyncio
async def test_generate_update_dev_merges_partial_trim_states(mocked_controller):
    """PUT response subsets must merge into the parent cache."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    parent = mocked_controller._bridge.get_afero_device(trim_light.id)
    assert any(
        s.functionClass == "power" and s.functionInstance == "trim"
        for s in parent.states
    )
    mocked_controller.generate_update_dev(
        trim_light.id,
        [
            AferoState(
                functionClass="power",
                value="off",
                lastUpdateTime=0,
                functionInstance="main",
            )
        ],
    )
    assert any(
        s.functionClass == "power" and s.functionInstance == "trim"
        for s in parent.states
    )


@pytest.mark.asyncio
async def test_initialize_a21(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "dd883754-e9f2-4c48-b755-09bf6ce776be"
    assert dev.on == features.OnFeature(on=True)
    assert dev.color == features.ColorFeature(red=232, green=255, blue=30)
    assert dev.color_mode == features.ColorModeFeature(mode="white")
    assert dev.color_temperature == features.ColorTemperatureFeature(
        temperature=4000,
        supported=[
            2200,
            2300,
            2400,
            2500,
            2600,
            2700,
            2800,
            2900,
            3000,
            3100,
            3200,
            3300,
            3400,
            3500,
            3600,
            3700,
            3800,
            3900,
            4000,
            4100,
            4200,
            4300,
            4400,
            4500,
            4600,
            4700,
            4800,
            4900,
            5000,
            5100,
            5200,
            5300,
            5400,
            5500,
            5600,
            5700,
            5800,
            5900,
            6000,
            6100,
            6200,
            6300,
            6400,
            6500,
        ],
        prefix="",
    )
    assert dev.dimming == features.DimmingFeature(
        brightness=50,
        supported=[
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
            26,
            27,
            28,
            29,
            30,
            31,
            32,
            33,
            34,
            35,
            36,
            37,
            38,
            39,
            40,
            41,
            42,
            43,
            44,
            45,
            46,
            47,
            48,
            49,
            50,
            51,
            52,
            53,
            54,
            55,
            56,
            57,
            58,
            59,
            60,
            61,
            62,
            63,
            64,
            65,
            66,
            67,
            68,
            69,
            70,
            71,
            72,
            73,
            74,
            75,
            76,
            77,
            78,
            79,
            80,
            81,
            82,
            83,
            84,
            85,
            86,
            87,
            88,
            89,
            90,
            91,
            92,
            93,
            94,
            95,
            96,
            97,
            98,
            99,
            100,
        ],
    )
    assert dev.effect == features.EffectFeature(
        effect="getting-ready",
        effects={
            "preset": {"jump-3", "fade-3", "fade-7", "jump-7", "flash"},
            "custom": {
                "dinner-party",
                "wake-up",
                "focus",
                "sleep",
                "valentines-day",
                "rainbow",
                "getting-ready",
                "christmas",
                "july-4th",
                "chill",
                "nightlight",
                "moonlight",
                "clarity",
            },
        },
    )


@pytest.mark.asyncio
async def test_initialize_zandra(mocked_controller):
    await mocked_controller.initialize_elem(zandra_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "3a0c5015-c19d-417f-8e08-e71cd5bc221b"
    assert dev.on == features.OnFeature(
        on=True, func_class="power", func_instance="light-power"
    )
    assert dev.color is None
    assert dev.color_mode is None
    assert dev.color_temperature == features.ColorTemperatureFeature(
        temperature=3000, supported=[2700, 3000, 3500, 4000, 5000, 6500], prefix="K"
    )


@pytest.mark.asyncio
async def test_initialize_dimmer(mocked_controller):
    await mocked_controller.initialize_elem(dimmer_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "ebda9f3b-05bc-4764-a9f7-e2d52f707130"
    assert dev.on == features.OnFeature(
        on=False, func_class="power", func_instance="gang-1"
    )


@pytest.mark.asyncio
async def test_initialize_with_speed(mocked_controller):
    await mocked_controller.initialize_elem(speed_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "a2d36de5-8b91-411a-907a-ecb665422d00"
    assert dev.numbers == {
        ("speed", "color-sequence"): features.NumbersFeature(
            value=-10, min=-10, max=10, step=1, unit="speed", name="speed"
        )
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "afero_dev",
    [
        (a21_light),
        (zandra_light),
        (dimmer_light),
    ],
)
async def test_turn_on(afero_dev, mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(afero_dev)]
    )
    await bridge.async_block_until_done()
    await mocked_controller.initialize_elem(afero_dev)
    dev = mocked_controller.items[0]
    dev.on.on = False
    await mocked_controller.turn_on(afero_dev.id)
    await bridge.async_block_until_done()
    assert dev.is_on


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "afero_dev",
    [
        (a21_light),
        (zandra_light),
        (dimmer_light),
    ],
)
async def test_turn_off(afero_dev, mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(afero_dev)]
    )
    await bridge.async_block_until_done()
    dev = mocked_controller.items[0]
    dev.on.on = True
    await mocked_controller.turn_off(afero_dev.id)
    await bridge.async_block_until_done()
    assert not dev.is_on


@pytest.mark.asyncio
async def test_set_color_temperature(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.color_temperature.temperature = 2700
    dev.color_mode.mode = "color"
    await mocked_controller.set_color_temperature(a21_light.id, 3475)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.is_on
    assert dev.color_mode.mode == "white"
    assert dev.color_temperature.temperature == 3500


@pytest.mark.asyncio
async def test_set_state_temperature_defaults_color_mode_white(
    mocked_controller, mocker
):
    """CCT updates without an explicit color_mode must still send color-mode white."""
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[a21_light.id]
    dev.color_mode.mode = "color"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": a21_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_state(a21_light.id, on=True, temperature=3475)
    await mocked_controller._bridge.async_block_until_done()
    sent_states = update_afero_api.call_args[0][1]
    by_class = {state["functionClass"]: state for state in sent_states}
    assert by_class["color-mode"]["value"] == "white"
    assert "color-temperature" in by_class


@pytest.mark.asyncio
async def test_set_brightness(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.dimming.brightness = 50
    await mocked_controller.set_brightness(a21_light.id, 60)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.is_on
    assert dev.dimming.brightness == 60


@pytest.mark.asyncio
async def test_set_brightness_dual_channel(mocked_controller, mocker):
    """Dual-channel fixtures in mixed mode PUT overall primary brightness."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller._bridge.lights._items) == 1
    dev = mocked_controller[flushmount_light.id]
    dev.on.on = False
    dev.color_mode.mode = "mixed"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": flushmount_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_brightness(flushmount_light.id, 20)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["brightness"] == "primary"
    assert dev.is_on


@pytest.mark.asyncio
async def test_set_brightness_in_color_mode_routes_to_color(mocked_controller, mocker):
    """Brightness-only updates follow the cached API color mode on dual-channel lights."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[flushmount_light.id]
    dev.color_mode.mode = "color"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": flushmount_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_brightness(flushmount_light.id, 35)
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["brightness"] == "color"


@pytest.mark.asyncio
async def test_initialize_dual_channel_tracks_channel_brightness(mocked_controller):
    """Dual-channel lights cache per-channel brightness on the light model."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[flushmount_light.id]
    assert dev.dual_channel
    assert dev.color_brightness == 1
    assert dev.white_brightness == 100
    assert dev.dimming.func_instance == "primary"
    assert ("brightness", "color") not in dev.numbers
    assert ("brightness", "white") not in dev.numbers


@pytest.mark.asyncio
async def test_set_state_rgb_with_brightness_routes_to_color(mocked_controller, mocker):
    """RGB commands dim the color channel, not primary or white."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": flushmount_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_state(
        flushmount_light.id,
        on=True,
        color=(10, 20, 30),
        color_mode="color",
        brightness=40,
    )
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["brightness"] == "color"
    assert instances["color-rgb"] is None


@pytest.mark.asyncio
async def test_set_state_white_with_brightness_routes_to_white(
    mocked_controller, mocker
):
    """White/CCT commands dim the white channel."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": flushmount_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_state(
        flushmount_light.id,
        on=True,
        temperature=3000,
        brightness=25,
    )
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["brightness"] == "white"


@pytest.mark.asyncio
async def test_set_rgb(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.color_mode.mode = "white"
    dev.color.red = 100
    dev.color.green = 100
    dev.color.blue = 100
    await mocked_controller.set_rgb(a21_light.id, 0, 20, 40)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.is_on
    assert dev.color_mode.mode == "color"
    assert dev.color.red == 0
    assert dev.color.green == 20
    assert dev.color.blue == 40


@pytest.mark.asyncio
async def test_set_rgb_trim(mocked_controller, mocker):
    """Trim split lights must target the trim functionInstance, not main."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.on.on = False
    trim_dev.color_mode.mode = "white"
    trim_dev.color.red = 100
    trim_dev.color.green = 100
    trim_dev.color.blue = 100
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_rgb(trim_light_trim_id, 10, 20, 30)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    assert update_afero_api.call_args[0][0] == trim_light.id
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["power"] == "trim"
    assert instances["color-rgb"] == "trim"
    assert instances["color-mode"] == "trim"


@pytest.mark.asyncio
async def test_initialize_rgbcw_single_light_supports_rgb(mocked_controller):
    """RGBCW strips stay one light with shared color functions."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("rgbcw-led-strip.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller._bridge.lights._items) == 1
    dev = mocked_controller[rgbcw_strip_light.id]
    assert dev.supports_color
    assert dev.supports_color_temperature
    assert dev.color_mode is not None
    assert dev.dimming.func_instance == "primary"


@pytest.mark.asyncio
async def test_set_rgb_rgbcw_single_light(mocked_controller, mocker):
    """RGBCW strip color updates use shared null-instance color functions."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("rgbcw-led-strip.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[rgbcw_strip_light.id]
    dev.on.on = False
    dev.color_mode.mode = "white"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": rgbcw_strip_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_rgb(rgbcw_strip_light.id, 12, 34, 56)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    assert update_afero_api.call_args[0][0] == rgbcw_strip_light.id
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["power"] == "primary"
    assert instances["color-rgb"] is None
    assert instances["color-mode"] is None


@pytest.mark.asyncio
async def test_set_brightness_trim(mocked_controller, mocker):
    """Trim split brightness updates must target the trim functionInstance."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.on.on = False
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_brightness(trim_light_trim_id, 42)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["power"] == "trim"
    assert instances["brightness"] == "trim"


@pytest.mark.asyncio
async def test_update_elem_trim_ignores_main_power(mocked_controller):
    """Inbound updates must not apply main-zone power to the trim entity."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.on.on = True
    await mocked_controller.update_elem(
        _trim_update_with_states(trim_dev, main_power="off")
    )
    assert trim_dev.on.on is True


@pytest.mark.asyncio
async def test_update_elem_trim_ignores_main_brightness(mocked_controller):
    """Inbound main brightness must not change trim dimming."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_brightness = trim_dev.dimming.brightness
    await mocked_controller.update_elem(
        _trim_update_with_states(
            trim_dev,
            main_brightness=10,
        )
    )
    assert trim_dev.dimming.brightness == trim_brightness


@pytest.mark.asyncio
async def test_update_elem_trim_ignores_main_color(mocked_controller):
    """Inbound main RGB must not change trim color."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    await mocked_controller.update_elem(
        _trim_update_with_states(
            trim_dev,
            main_color_rgb={"color-rgb": {"r": 1, "g": 2, "b": 3}},
        )
    )
    assert trim_dev.color.red != 1
    assert trim_dev.color.green != 2
    assert trim_dev.color.blue != 3


@pytest.mark.asyncio
async def test_update_elem_ignores_color_temperature_without_feature(mocked_controller):
    """Inbound main CCT rows must not crash trim resources with no CCT capability."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    updates = await mocked_controller.update_elem(
        _trim_update_with_states(
            trim_dev,
            main_color_temperature=3000,
        )
    )
    assert trim_dev.color_temperature is None
    assert "color_temperature" not in updates


@pytest.mark.asyncio
async def test_set_white_trim_sends_color_mode_not_cct(mocked_controller, mocker):
    """White-only zones use color-mode white, never main's color-temperature."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    assert trim_dev.supports_color_white
    trim_dev.color_mode.mode = "color"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_white(trim_light_trim_id, on=None, brightness=40)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    assert update_afero_api.call_args[0][0] == trim_light.id
    sent_states = update_afero_api.call_args[0][1]
    by_class = {state["functionClass"]: state for state in sent_states}
    assert by_class["color-mode"]["functionInstance"] == "trim"
    assert by_class["color-mode"]["value"] == "white"
    assert by_class["brightness"]["functionInstance"] == "trim"
    assert by_class["brightness"]["value"] == 40
    assert "color-temperature" not in by_class


@pytest.mark.asyncio
async def test_set_color_temperature_trim_routes_to_white(mocked_controller, mocker):
    """set_color_temperature on a no-CCT zone must not emit color-temperature."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    assert trim_dev.supports_color_white
    assert trim_dev.color_temperature is None
    trim_dev.color_mode.mode = "color"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_color_temperature(trim_light_trim_id, 2700)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    sent_states = update_afero_api.call_args[0][1]
    by_class = {state["functionClass"]: state for state in sent_states}
    assert by_class["color-mode"]["functionInstance"] == "trim"
    assert by_class["color-mode"]["value"] == "white"
    assert "color-temperature" not in by_class


@pytest.mark.asyncio
async def test_set_color_temperature_missing_device(mocked_controller, mocker):
    """Unknown device id must not call the API."""
    update_afero_api = mocker.patch.object(mocked_controller, "update_afero_api")
    await mocked_controller.set_color_temperature("missing-light-id", 3000)
    update_afero_api.assert_not_called()


@pytest.mark.asyncio
async def test_set_color_temperature_no_cct_no_white(mocked_controller, mocker):
    """Lights without CCT or white mode must not send updates."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.color_modes = ["color", "sequence"]
    update_afero_api = mocker.patch.object(mocked_controller, "update_afero_api")
    await mocked_controller.set_color_temperature(trim_light_trim_id, 2700)
    update_afero_api.assert_not_called()


@pytest.mark.asyncio
async def test_set_color_temperature_trim_logs_ignored_kelvin(
    mocked_controller, mocker, caplog
):
    """No-CCT zones log that the requested Kelvin value is ignored."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    mocker.patch.object(mocked_controller, "update_afero_api", return_value=resp)
    caplog.set_level("INFO")
    await mocked_controller.set_color_temperature(trim_light_trim_id, 2700)
    assert "ignoring 2700 K" in caplog.text


@pytest.mark.asyncio
async def test_set_white_trim_already_white_resends_color_mode(
    mocked_controller, mocker
):
    """Explicit white on a no-CCT trim zone must PUT color-mode even if cache is white."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.color_mode.mode = "white"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_white(trim_light_trim_id, on=None, brightness=40)
    await mocked_controller._bridge.async_block_until_done()
    sent_states = update_afero_api.call_args[0][1]
    by_class = {state["functionClass"]: state for state in sent_states}
    assert by_class["color-mode"]["functionInstance"] == "trim"
    assert by_class["color-mode"]["value"] == "white"
    assert by_class["brightness"]["value"] == 40


@pytest.mark.asyncio
async def test_set_state_temperature_respects_explicit_color_mode(
    mocked_controller, mocker
):
    """Explicit color_mode must not be overridden when routing temperature on no-CCT zones."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.color_mode.mode = "white"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_state(
        trim_light_trim_id, on=True, temperature=2700, color_mode="color"
    )
    await mocked_controller._bridge.async_block_until_done()
    by_class = {
        state["functionClass"]: state for state in update_afero_api.call_args[0][1]
    }
    assert by_class["color-mode"]["value"] == "color"
    assert "color-temperature" not in by_class


@pytest.mark.asyncio
async def test_update_elem_ignores_trim_zone_color_temperature_without_feature(
    mocked_controller,
):
    """Inbound trim CCT rows must be ignored when the zone has no CCT feature."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    assert trim_dev.color_temperature is None
    dev_update = AferoDevice(
        id=trim_light_trim_id,
        device_id=trim_light.device_id,
        model=trim_light.model,
        device_class="light",
        default_name=trim_light.default_name,
        default_image=trim_light.default_image,
        friendly_name=trim_dev.device_information.name,
        split_identifier="light",
        states=[
            AferoState(
                functionClass="color-temperature",
                value=3000,
                lastUpdateTime=0,
                functionInstance="trim",
            )
        ],
    )
    updates = await mocked_controller.update_elem(dev_update)
    assert trim_dev.color_temperature is None
    assert "color_temperature" not in updates


@pytest.mark.asyncio
async def test_set_state_temperature_routes_to_white_without_cct(
    mocked_controller, mocker
):
    """set_state with temperature on no-CCT zones uses color-mode, not CCT."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_dev.color_mode.mode = "color"
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_state(
        trim_light_trim_id, on=True, temperature=2700, color_mode=None
    )
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_called_once()
    sent_states = update_afero_api.call_args[0][1]
    by_class = {state["functionClass"]: state for state in sent_states}
    assert by_class["color-mode"]["value"] == "white"
    assert "color-temperature" not in by_class


@pytest.mark.asyncio
async def test_update_elem_trim_ignores_main_color_mode(mocked_controller):
    """Inbound main color-mode must not change trim mode (e.g. main white vs trim RGB)."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    trim_dev = mocked_controller[trim_light_trim_id]
    trim_mode = trim_dev.color_mode.mode
    await mocked_controller.update_elem(
        _trim_update_with_states(trim_dev, main_color_mode="white")
    )
    assert trim_dev.color_mode.mode == trim_mode


@pytest.mark.asyncio
async def test_update_elem_main_ignores_trim_power(mocked_controller):
    """Inbound trim power must not change main on-state (symmetric with trim tests)."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    main_dev = mocked_controller[trim_light_primary_id]
    main_dev.on.on = True
    await mocked_controller.update_elem(
        AferoDevice(
            id=trim_light_primary_id,
            device_id=trim_light.device_id,
            model=trim_light.model,
            device_class=ResourceTypes.LIGHT.value,
            default_name=trim_light.default_name,
            default_image=trim_light.default_image,
            friendly_name=f"{trim_light.friendly_name} - main",
            split_identifier="light",
            states=[
                AferoState(
                    functionClass="power",
                    value="off",
                    lastUpdateTime=0,
                    functionInstance="trim",
                ),
            ],
        )
    )
    assert main_dev.on.on is True


@pytest.mark.asyncio
async def test_set_rgb_main_split(mocked_controller, mocker):
    """Main split lights must target the main functionInstance, not trim."""
    await mocked_controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-with-trim.json")
    )
    await mocked_controller._bridge.async_block_until_done()
    main_dev = mocked_controller[trim_light_primary_id]
    main_dev.on.on = False
    resp = mocker.AsyncMock()
    resp.status = 200
    json_resp = mocker.AsyncMock()
    json_resp.return_value = {"metadeviceId": trim_light.id, "values": []}
    resp.json = json_resp
    update_afero_api = mocker.patch.object(
        mocked_controller, "update_afero_api", return_value=resp
    )
    await mocked_controller.set_rgb(trim_light_primary_id, 4, 5, 6)
    await mocked_controller._bridge.async_block_until_done()
    sent_states = update_afero_api.call_args[0][1]
    instances = {
        state["functionClass"]: state["functionInstance"] for state in sent_states
    }
    assert instances["color-rgb"] == "main"
    assert instances["power"] == "main"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "effect",
    [
        ("rainbow"),
        ("fade-7"),
    ],
)
async def test_set_effect(effect, mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.effect.effect = None
    await mocked_controller.set_effect(a21_light.id, effect)
    await mocked_controller._bridge.async_block_until_done()
    assert dev.is_on
    assert dev.color_mode.mode == "sequence"
    assert dev.effect.effect == effect


@pytest.mark.asyncio
async def test_update_elem_speed(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(speed_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.numbers[("speed", "color-sequence")].value = 0
    updates = await mocked_controller.update_elem(speed_light)
    dev = mocked_controller.items[0]
    assert updates == {"number-('speed', 'color-sequence')"}
    assert dev.numbers[("speed", "color-sequence")].value == -10


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.available = False
    dev.on.on = False
    dev_update = utils.create_devices_from_data("light-a21.json")[0]
    new_states = [
        AferoState(
            functionClass="color-temperature",
            value="3000K",
            lastUpdateTime=0,
            functionInstance=None,
        ),
        AferoState(
            functionClass="brightness",
            value=40,
            lastUpdateTime=0,
            functionInstance=None,
        ),
        AferoState(
            functionClass="color-rgb",
            value={
                "color-rgb": {
                    "r": 2,
                    "g": 3,
                    "b": 4,
                }
            },
            lastUpdateTime=0,
            functionInstance=None,
        ),
        AferoState(
            functionClass="power", value="on", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="color-mode",
            value="color",
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
    for state in new_states:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.on.on is True
    assert dev.color_temperature.temperature == 3000
    assert dev.dimming.brightness == 40
    assert dev.color.red == 2
    assert dev.color.green == 3
    assert dev.color.blue == 4
    assert dev.color_mode.mode == "color"
    assert updates == {
        "on",
        "color_temperature",
        "dimming",
        "color",
        "color_mode",
        "available",
    }


@pytest.mark.asyncio
async def test_update_elem_no_updates(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    assert not await mocked_controller.update_elem(a21_light)


states_custom = [
    AferoState(
        functionClass="color-sequence",
        functionInstance="preset",
        lastUpdateTime=0,
        value="custom",
    ),
    AferoState(
        functionClass="color-sequence",
        functionInstance="custom",
        lastUpdateTime=0,
        value="rainbow",
    ),
]

states_preset = [
    AferoState(
        functionClass="color-sequence",
        functionInstance="preset",
        lastUpdateTime=0,
        value="fade-7",
    ),
    AferoState(
        functionClass="color-sequence",
        functionInstance="custom",
        lastUpdateTime=0,
        value="rainbow",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("new_states", "expected"),
    [
        (states_custom, "rainbow"),
        (states_preset, "fade-7"),
    ],
)
async def test_update_elem_effect(new_states, expected, mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(a21_light)]
    )
    await bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev_update = utils.create_devices_from_data("light-a21.json")[0]
    for state in new_states:
        utils.modify_state(dev_update, state)
    await mocked_controller.update_elem(dev_update)
    dev = mocked_controller.items[0]
    assert dev.effect.effect == expected


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    await mocked_controller.set_state(a21_light.id)


@pytest.mark.asyncio
async def test_light_emitting(bridge):
    dev_update = utils.create_devices_from_data("light-a21.json")[0]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    await bridge.async_block_until_done()
    assert len(bridge.lights._items) == 1
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
    assert len(bridge.lights._items) == 1
    assert not bridge.lights._items[dev_update.id].available


@pytest.mark.asyncio
async def test_set_state_no_dev(mocked_controller, caplog):
    caplog.set_level(0)
    await mocked_controller.initialize_elem(a21_light)
    mocked_controller._bridge.add_device(a21_light.id, mocked_controller)
    await mocked_controller.set_state("not-a-device")
    mocked_controller._bridge.request.assert_not_called()
    assert "Unable to find device" in caplog.text


seq_custom = {
    "preset": AferoState(
        functionClass="color-sequence",
        value="custom",
        lastUpdateTime=0,
        functionInstance="preset",
    ),
    "custom": AferoState(
        functionClass="color-sequence",
        value="rainbow",
        lastUpdateTime=0,
        functionInstance="custom",
    ),
}

seq_preset = {
    "preset": AferoState(
        functionClass="color-sequence",
        value="fade-3",
        lastUpdateTime=0,
        functionInstance="preset",
    ),
    "custom": AferoState(
        functionClass="color-sequence",
        value="rainbow",
        lastUpdateTime=0,
        functionInstance="custom",
    ),
}

light1_effects = {
    "preset": {"fade-3"},
    "custom": {"rainbow"},
}
light1 = Light(
    _id="test-light-1",
    available=True,
    effect=EffectFeature(effect="getting-ready", effects=light1_effects),
    device_information=DeviceInformation(model="TBD"),
)
light1_no_update = Light(
    _id="test-light-1",
    available=True,
    effect=EffectFeature(effect="rainbow", effects=light1_effects),
    device_information=DeviceInformation(model="TBD"),
)
light1_no_update_preset = Light(
    _id="test-light-1",
    available=True,
    effect=EffectFeature(effect="fade-3", effects=light1_effects),
    device_information=DeviceInformation(model="TBD"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("elem", "color_seq_states", "expected_effect", "updated"),
    [
        (light1, {}, "getting-ready", False),
        (light1, seq_custom, "rainbow", True),
        (light1_no_update, seq_custom, "rainbow", False),
        (light1, seq_preset, "fade-3", True),
        (light1_no_update_preset, seq_preset, "fade-3", False),
    ],
)
async def test_update_elem_color(
    mocked_controller, elem, color_seq_states, expected_effect, updated
):
    updates = await mocked_controller.update_elem_color(elem, color_seq_states)
    assert len(updates) == int(updated)
    assert elem.effect.effect == expected_effect


def test_process_color_temps():
    temps = [{"name": "2700K"}, {"name": "3000"}]
    assert process_color_temps(temps) == [2700, 3000]


@pytest.mark.asyncio
async def test_emitting(bridge):
    # Simulate the discovery process
    await bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await bridge.async_block_until_done()
    assert len(bridge.lights._items) == 1
    dev = bridge.lights[flushmount_light.id]
    assert dev.on.on
    assert dev.dimming.brightness == 1
    assert dev.supports_color
    assert bridge.devices[flushmount_light.id].available is True
    dev_update = utils.create_devices_from_data("light-flushmount.json")[0]
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="brightness",
            functionInstance="primary",
            value=50,
        ),
    )
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="available",
            functionInstance=None,
            value=False,
        ),
    )
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dev_update)]
    )
    await bridge.async_block_until_done()
    assert bridge.lights[flushmount_light.id].dimming.brightness == 50
    assert bridge.devices[flushmount_light.id].available is False


@pytest.mark.asyncio
async def test_set_state_white_light(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(speaker_power_light)]
    )
    await bridge.async_block_until_done()
    await mocked_controller.set_state(
        speaker_power_light.id, on=True, force_white_mode=75
    )
    await mocked_controller._bridge.async_block_until_done()
    assert mocked_controller[speaker_power_light.id].on.on is True
    assert mocked_controller[speaker_power_light.id].color_mode.mode == "white"
    assert mocked_controller[speaker_power_light.id].dimming.brightness == 75


@pytest.mark.asyncio
async def test_set_state_speed(mocked_controller):
    bridge = mocked_controller._bridge
    await bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(speed_light)]
    )
    await bridge.async_block_until_done()
    await mocked_controller.set_state(
        speed_light.id,
        numbers={("speed", "color-sequence"): 5, ("doesnt-exist", "color-sequence"): 5},
    )
    await mocked_controller._bridge.async_block_until_done()
    assert (
        mocked_controller[speed_light.id].numbers[("speed", "color-sequence")].value
        == 5
    )
