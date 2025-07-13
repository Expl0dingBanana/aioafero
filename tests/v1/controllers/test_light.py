"""Test LightController"""

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event, light
from aioafero.v1.controllers.light import LightController, features, process_color_temps
from aioafero.v1.models.features import EffectFeature
from aioafero.v1.models.light import Light
from aioafero.v1.models.resource import ResourceTypes, DeviceInformation

from .. import utils

a21_light = utils.create_devices_from_data("light-a21.json")[0]
zandra_light = utils.create_devices_from_data("fan-ZandraFan.json")[1]
dimmer_light = utils.create_devices_from_data("dimmer-HPDA1110NWBP.json")[0]
flushmount_light = utils.create_devices_from_data("light-flushmount.json")[0]
flushmount_light_color_id = f"{flushmount_light.id}-light-color"
flushmount_light_white_id = f"{flushmount_light.id}-light-white"

speaker_power_light = utils.create_devices_from_data("light-with-speaker.json")[0]
speaker_power_light_id = f"{speaker_power_light.id}-light-speaker-power"


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = LightController(mocked_bridge)
    return controller


def test_generate_split_name():
    assert (
        light.generate_split_name(a21_light, "beans") == f"{a21_light.id}-light-beans"
    )


@pytest.mark.parametrize(
    "device, expected",
    [
        # Flushmount splits
        (
            flushmount_light,
            [
                ("color", ResourceTypes.LIGHT),
                ("white", ResourceTypes.LIGHT),
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
    "device, instance, expected",
    [
        # Has no split instances
        (a21_light, "nada", []),
        # Flushmount white
        (
            flushmount_light,
            "white",
            [
                AferoState(
                    functionClass="toggle",
                    value="off",
                    lastUpdateTime=0,
                    functionInstance="white",
                ),
                AferoState(
                    functionClass="brightness",
                    value=100,
                    lastUpdateTime=0,
                    functionInstance="white",
                ),
                AferoState(
                    functionClass="available",
                    value=True,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
            ],
        ),
        # Flushmount color
        (
            flushmount_light,
            "color",
            [
                AferoState(
                    functionClass="brightness",
                    value=1,
                    lastUpdateTime=0,
                    functionInstance="color",
                ),
                AferoState(
                    functionClass="restore-values",
                    value="partial-restore",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="color-sequence",
                    value="sleep",
                    lastUpdateTime=0,
                    functionInstance="custom",
                ),
                AferoState(
                    functionClass="toggle",
                    value="on",
                    lastUpdateTime=0,
                    functionInstance="color",
                ),
                AferoState(
                    functionClass="color-mode",
                    value="color",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="color-rgb",
                    value={
                        "color-rgb": {
                            "b": 204,
                            "g": 242,
                            "r": 255,
                        },
                    },
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="speed",
                    value=0,
                    lastUpdateTime=0,
                    functionInstance="color-sequence",
                ),
                AferoState(
                    functionClass="color-sequence",
                    value="custom",
                    lastUpdateTime=0,
                    functionInstance="preset",
                ),
                AferoState(
                    functionClass="color-temperature",
                    value=3000,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="wifi-ssid",
                    value="c87d78a4-3f6e-4468-a034-4bef7b7cd4b3",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="wifi-rssi",
                    value=-37,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="wifi-steady-state",
                    value="connected",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="wifi-setup-state",
                    value="connected",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="wifi-mac-address",
                    value="0ddc8684-2404-4e10-8495-fd5c82dda3e6",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="geo-coordinates",
                    value={
                        "geo-coordinates": {
                            "latitude": "0",
                            "longitude": "0",
                        },
                    },
                    lastUpdateTime=0,
                    functionInstance="system-device-location",
                ),
                AferoState(
                    functionClass="scheduler-flags",
                    value=1,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="available",
                    value=True,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="visible",
                    value=True,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="direct",
                    value=True,
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
                AferoState(
                    functionClass="ble-mac-address",
                    value="444a8248-56ef-4735-a5a6-9dc486a16f85",
                    lastUpdateTime=0,
                    functionInstance=None,
                ),
            ],
        ),
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

            ]
        ),
    ],
)
def test_get_valid_states(device, instance, expected):
    assert light.get_valid_states(device, instance) == expected


def test_light_callback():
    multi_devs, remove_dev = light.light_callback(flushmount_light)
    assert remove_dev is True
    assert len(multi_devs) == 3
    assert len(multi_devs[0].states) == 20
    assert multi_devs[0].id == flushmount_light_color_id
    assert multi_devs[0].device_class == ResourceTypes.LIGHT.value
    assert len(multi_devs[1].states) == 3
    assert multi_devs[1].id == flushmount_light_white_id
    assert multi_devs[1].friendly_name == f"{flushmount_light.friendly_name} - white"
    assert multi_devs[1].device_class == ResourceTypes.LIGHT.value
    assert multi_devs[2].id == flushmount_light.id
    assert len(multi_devs[2].states) == 7
    assert multi_devs[2].device_class == "parent-device"


def test_light_speaker():
    multi_devs, remove_dev = light.light_callback(speaker_power_light)
    assert remove_dev is False
    assert len(multi_devs) == 1
    assert len(multi_devs[0].states) == 2
    assert multi_devs[0].id == speaker_power_light_id
    assert multi_devs[0].device_class == ResourceTypes.SWITCH.value


def test_light_callback_none():
    multi_devs, remove_dev = light.light_callback(a21_light)
    assert remove_dev is False
    assert len(multi_devs) == 0


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
@pytest.mark.parametrize(
    "afero_dev, expected_instance",
    [
        (a21_light, None),
        (zandra_light, "light-power"),
        (dimmer_light, "gang-1"),
    ],
)
async def test_turn_on(afero_dev, expected_instance, mocked_controller):
    await mocked_controller.initialize_elem(afero_dev)
    dev = mocked_controller.items[0]
    dev.on.on = False
    await mocked_controller.turn_on(afero_dev.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == afero_dev.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": expected_instance,
            "lastUpdateTime": 12345,
            "value": "on",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert dev.is_on


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "afero_dev, expected_instance",
    [
        (a21_light, None),
        (zandra_light, "light-power"),
        (dimmer_light, "gang-1"),
    ],
)
async def test_turn_off(afero_dev, expected_instance, mocked_controller):
    await mocked_controller.initialize_elem(afero_dev)
    dev = mocked_controller.items[0]
    dev.on.on = True
    await mocked_controller.turn_off(afero_dev.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == afero_dev.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": expected_instance,
            "lastUpdateTime": 12345,
            "value": "off",
        }
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
    assert not dev.is_on


@pytest.mark.asyncio
async def test_set_color_temperature(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.color_temperature.temperature = 2700
    dev.color_mode.mode = "color"
    await mocked_controller.set_color_temperature(a21_light.id, 3475)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == a21_light.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        },
        {
            "functionClass": "color-temperature",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "3500",
        },
        {
            "functionClass": "color-mode",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "white",
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_set_brightness(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.dimming.brightness = 50
    await mocked_controller.set_brightness(a21_light.id, 60)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == a21_light.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        },
        {
            "functionClass": "brightness",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": 60,
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_set_brightness_split(bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = bridge.lights
    await bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-flushmount.json")
    )
    await bridge.async_block_until_done()
    assert len(bridge.lights._items) == 2
    dev = controller[flushmount_light_white_id]
    assert dev.on.on is False
    await controller.set_brightness(flushmount_light_white_id, 20)
    await bridge.async_block_until_done()
    expected_states = [
        {
            "functionClass": "toggle",
            "functionInstance": "white",
            "lastUpdateTime": 12345,
            "value": "on",
        },
        {
            "functionClass": "brightness",
            "functionInstance": "white",
            "lastUpdateTime": 12345,
            "value": 20,
        },
    ]
    utils.ensure_states_sent(controller, expected_states, device_id=flushmount_light.id)


@pytest.mark.asyncio
async def test_set_rgb(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.color_mode.mode = "white"
    dev.color.red = 100
    dev.color.green = 100
    dev.color.blue = 100
    await mocked_controller.set_rgb(a21_light.id, 0, 20, 40)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == a21_light.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        },
        {
            "functionClass": "color-mode",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "color",
        },
        {
            "functionClass": "color-rgb",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": {
                "color-rgb": {
                    "r": 0,
                    "g": 20,
                    "b": 40,
                }
            },
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "effect, expected_instance",
    [
        ("rainbow", "custom"),
        ("fade-7", "preset"),
    ],
)
async def test_set_effect(effect, expected_instance, mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.on.on = False
    dev.effect.effect = None
    await mocked_controller.set_effect(a21_light.id, effect)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == a21_light.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        },
        {
            "functionClass": "color-mode",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "sequence",
        },
    ]
    if expected_instance == "preset":
        expected_states.append(
            {
                "functionClass": "color-sequence",
                "functionInstance": expected_instance,
                "lastUpdateTime": 12345,
                "value": effect,
            }
        )
    else:
        expected_states.append(
            {
                "functionClass": "color-sequence",
                "functionInstance": "preset",
                "lastUpdateTime": 12345,
                "value": expected_instance,
            }
        )
        expected_states.append(
            {
                "functionClass": "color-sequence",
                "functionInstance": expected_instance,
                "lastUpdateTime": 12345,
                "value": effect,
            }
        )
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    dev.available = False
    dev.on.on = False
    dev_update = utils.create_devices_from_data("light-a21.json")[0]
    new_states = [
        AferoState(
            functionClass="color-temperature", value="3000K", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="brightness", value=40, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="color-rgb", value={
                    "color-rgb": {
                        "r": 2,
                        "g": 3,
                        "b": 4,
                    }
                }, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="power", value="on", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="color-mode", value="color", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="available", value=True, lastUpdateTime=0, functionInstance=None
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
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    assert not await mocked_controller.update_elem(a21_light)


states_custom = [
    AferoState(
        functionClass="color-sequence", functionInstance="preset", lastUpdateTime=0, value="custom"
    ),
    AferoState(
        functionClass="color-sequence", functionInstance="custom", lastUpdateTime=0, value="rainbow"
    ),
]

states_preset = [
    AferoState(
        functionClass="color-sequence", functionInstance="preset", lastUpdateTime=0, value="fade-7"
    ),
    AferoState(
        functionClass="color-sequence", functionInstance="custom", lastUpdateTime=0, value="rainbow",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_states, expected",
    [
        (states_custom, "rainbow"),
        (states_preset, "fade-7"),
    ],
)
async def test_update_elem_effect(new_states, expected, mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
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
        functionClass="color-sequence", value="custom", lastUpdateTime=0, functionInstance="preset"
    ),
    "custom": AferoState(
        functionClass="color-sequence", value="rainbow", lastUpdateTime=0, functionInstance="custom"
    ),
}

seq_preset = {
    "preset": AferoState(
        functionClass="color-sequence", value="fade-3", lastUpdateTime=0, functionInstance="preset"
    ),
    "custom": AferoState(
        functionClass="color-sequence", value="rainbow", lastUpdateTime=0, functionInstance="custom"
    ),
}

light1_effects = {
    "preset": {"fade-3"},
    "custom": {"rainbow"},
}
light1 = Light(
    [],
    id="test-light-1",
    available=True,
    effect=EffectFeature(effect="getting-ready", effects=light1_effects),
    device_information=DeviceInformation(model="TBD"),
)
light1_no_update = Light(
    [],
    id="test-light-1",
    available=True,
    effect=EffectFeature(effect="rainbow", effects=light1_effects),
device_information=DeviceInformation(model="TBD"),
)
light1_no_update_preset = Light(
    [],
    id="test-light-1",
    available=True,
    effect=EffectFeature(effect="fade-3", effects=light1_effects),
device_information=DeviceInformation(model="TBD"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "elem, color_seq_states, expected_effect, updated",
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
    assert len(bridge.lights._items) == 2
    assert bridge.lights[flushmount_light_color_id].on.on
    assert bridge.lights[flushmount_light_color_id].brightness == 1
    assert not bridge.lights[flushmount_light_white_id].on.on
    assert bridge.lights[flushmount_light_white_id].brightness == 100
    assert bridge.devices[flushmount_light.id].available is True
    dev_update = utils.create_devices_from_data("light-flushmount.json")[0]
    # Simulate an update
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="toggle",
            functionInstance="white",
            value="on",
        ),
    )
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="brightness",
            functionInstance="white",
            value=50,
        ),
    )
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="toggle",
            functionInstance="color",
            value="off",
        ),
    )
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="brightness",
            functionInstance="color",
            value=55,
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
    assert bridge.lights[flushmount_light_color_id].brightness == 55
    assert not bridge.lights[flushmount_light_color_id].on.on
    assert bridge.lights[flushmount_light_white_id].brightness == 50
    assert bridge.lights[flushmount_light_white_id].on.on
    assert bridge.devices[flushmount_light.id].available is False


@pytest.mark.asyncio
async def test_set_state_white_light(mocked_controller):
    await mocked_controller.initialize_elem(speaker_power_light)
    await mocked_controller.set_state(speaker_power_light.id, on=True, force_white_mode=75)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == speaker_power_light.id
    expected_states = [
        {
            "functionClass": "power",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "on",
        },
        {
            "functionClass": "color-mode",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "white",
        },
        {
            "functionClass": "brightness",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": 75
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)
