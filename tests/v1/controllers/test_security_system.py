"""Test SecuritySystemController"""

import pytest

from aioafero.errors import SecuritySystemError
from aioafero.device import AferoDevice, AferoState, AferoCapability
from aioafero.v1.controllers import event
from aioafero.v1.controllers.security_system import SecuritySystemController, features, security_system_callback, get_valid_states, get_sensor_ids, get_valid_functions, get_sensor_name, get_model_type

from .. import utils

alarm_panel = utils.create_devices_from_data("security-system.json")[1]


def get_alarm_panel_with_siren() -> AferoDevice:
    alarm_panel_with_siren = utils.create_devices_from_data("security-system.json")[1]
    utils.modify_state(
        alarm_panel_with_siren,
        AferoState(
            functionClass="siren-action",
            functionInstance=None,
            value={"security-siren-action": {"resultCode": 0, "command": 4}},
        ),
    )
    return alarm_panel_with_siren


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    mocker.patch("aioafero.v1.controllers.security_system.UPDATE_TIME", 0)
    return mocked_bridge.security_systems


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == "7f4e4c01-e799-45c5-9b1a-385433a78edc"
    assert dev.alarm_state == features.ModeFeature(
        mode="disarmed",
        modes={
            "alarming-sos",
            "learning",
            "arm-started-stay",
            "alarming",
            "arm-stay",
            "disarmed",
            "arm-started-away",
            "triggered",
            "arm-away",
        },
    )
    assert dev.siren_action == features.SecuritySensorSirenFeature(
        result_code=None, command=None
    )
    assert dev.numbers == {
        ("arm-exit-delay", "away"): features.NumbersFeature(
            value=30, min=0, max=300, step=1, name="Arm Exit Delay Away", unit="seconds"
        ),
        ("arm-exit-delay", "stay"): features.NumbersFeature(
            value=0, min=0, max=300, step=1, name="Arm Exit Delay Home", unit="seconds"
        ),
        ("disarm-entry-delay", None): features.NumbersFeature(
            value=60, min=1, max=300, step=1, name="Disarm Entry Delay", unit="seconds"
        ),
        ("siren-alarm-timeout", None): features.NumbersFeature(
            value=180, min=0, max=600, step=30, name="Siren Timeout", unit="seconds"
        ),
        ("temporary-bypass-time", None): features.NumbersFeature(
            value=60, min=10, max=300, step=1, name="Bypass Time", unit="seconds"
        ),
    }
    assert dev.selects == {
        ("bypass-allowed", None): features.SelectFeature(
            selected="now-allowed",
            selects={"now-allowed", "allowed"},
            name="Enable Temporary Bypass",
        ),
        ("song-id", "alarm"): features.SelectFeature(
            selected="preset-01",
            selects={
                "preset-01",
                "preset-02",
                "preset-03",
                "preset-04",
                "preset-05",
                "preset-06",
                "preset-07",
                "preset-08",
                "preset-09",
                "preset-10",
                "preset-11",
                "preset-12",
                "preset-13",
            },
            name="Alarm Noise",
        ),
        ("song-id", "chime"): features.SelectFeature(
            selected="preset-02",
            selects={
                "preset-01",
                "preset-02",
                "preset-03",
                "preset-04",
                "preset-05",
                "preset-06",
                "preset-07",
                "preset-08",
                "preset-09",
                "preset-10",
                "preset-11",
                "preset-12",
                "preset-13",
            },
            name="Chime Noise",
        ),
        ("volume", "chime"): features.SelectFeature(
            selected="volume-01",
            selects={"volume-00", "volume-01", "volume-02", "volume-03", "volume-04"},
            name="Chime Volume",
        ),
        ("volume", "entry-delay"): features.SelectFeature(
            selected="volume-01",
            selects={"volume-00", "volume-01", "volume-02", "volume-03", "volume-04"},
            name="Entry Delay Volume",
        ),
        ("volume", "exit-delay-away"): features.SelectFeature(
            selected="volume-01",
            selects={"volume-00", "volume-01", "volume-02", "volume-03", "volume-04"},
            name="Exit Delay Volume Away",
        ),
        ("volume", "exit-delay-stay"): features.SelectFeature(
            selected="volume-01",
            selects={"volume-00", "volume-01", "volume-02", "volume-03", "volume-04"},
            name="Exit Delay Volume Home",
        ),
        ("volume", "siren"): features.SelectFeature(
            selected="volume-04",
            selects={"volume-00", "volume-01", "volume-02", "volume-03", "volume-04"},
            name="Alarm Volume",
        ),
    }


@pytest.mark.asyncio
async def test_initialize_with_siren(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(get_alarm_panel_with_siren())]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.siren_action == features.SecuritySensorSirenFeature(
        result_code=0,
        command=4,
    )


@pytest.mark.asyncio
async def test_disarm(mocked_controller, mocker):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(get_alarm_panel_with_siren())]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[alarm_panel.id].alarm_state.mode = "arm-away"
    # Setup the response after disarm
    panel = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            functionClass="alarm-state", value="disarmed", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(panel, state)
    mocker.patch.object(mocked_controller._bridge, "fetch_device_states", return_value=panel.states)
    # Execute the test
    await mocked_controller.disarm(alarm_panel.id, 1234)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[alarm_panel.id]
    assert dev.alarm_state.mode == "disarmed"
    assert dev.siren_action.result_code is None
    assert dev.siren_action.command is None


@pytest.mark.asyncio
async def test_disarm_invalid_pin(mocked_controller, mocker):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(get_alarm_panel_with_siren())]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocked_controller[alarm_panel.id].alarm_state.mode = "arm-away"
    # Setup the response after disarm
    panel = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            functionClass="alarm-state", value="arm-away", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(panel, state)
    mocker.patch.object(mocked_controller._bridge, "fetch_device_states", return_value=panel.states)
    # Execute the test
    with pytest.raises(SecuritySystemError, match="Disarm PIN was not accepted"):
        await mocked_controller.disarm(alarm_panel.id, 1234)
        await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[alarm_panel.id]
    assert dev.alarm_state.mode == "arm-away"


def enable_sensors(dev):
    for state in dev.states:
        if state.functionClass not in ["sensor-state"] or state.value is None:
            continue
        state.value = {
            'security-sensor-state': {
                'deviceType': 1,
                'tampered': 0,
                'triggered': 0,
                'missing': 0,
                'versionBuild': 3,
                'versionMajor': 2,
                'versionMinor': 0,
                'batteryLevel': 100
            }
        }


def disable_sensors(dev):
    for state in dev.states:
        if state.functionClass not in ["sensor-state"] or state.value is None:
            continue
        state.value = {
            'security-sensor-state': {
                'deviceType': 1,
                'tampered': 1,
                'triggered': 1,
                'missing': 1,
                'versionBuild': 3,
                'versionMajor': 2,
                'versionMinor': 0,
                'batteryLevel': 100
            }
        }

def single_sensor_with_bypass(dev, sensor_id):
    enable_sensors(dev)
    for state in dev.states:
        if state.functionClass == "sensor-state" and state.functionInstance == f"sensor-{sensor_id}":
            state.value = {
                'security-sensor-state': {
                    'deviceType': 1,
                    'tampered': 0,
                    'triggered': 1, # Trigger the device, but it will be bypassed
                    'missing': 0,
                    'versionBuild': 3,
                    'versionMajor': 2,
                    'versionMinor': 0,
                    'batteryLevel': 100
                }
            }
        if state.functionClass == "sensor-config" and state.functionInstance == f"sensor-{sensor_id}":
            state.value = {
                "security-sensor-config-v2": {
                    "chirpMode": 1,
                    "triggerType": 3,
                    "bypassType": 4
                }
            }


def bypass_all_sensors(dev):
    for state in dev.states:
        if state.functionClass == "sensor-state":
            state.value = {
                'security-sensor-state': {
                    'deviceType': 1,
                    'tampered': 0,
                    'triggered': 0,
                    'missing': 0,
                    'versionBuild': 3,
                    'versionMajor': 2,
                    'versionMinor': 0,
                    'batteryLevel': 100
                }
            }
        if state.functionClass == "sensor-config":
            state.value = {
                "security-sensor-config-v2": {
                    "chirpMode": 1,
                    "triggerType": 3,
                    "bypassType": 4
                }
            }


@pytest.mark.asyncio
async def test_arm_home(mocked_controller, mocker):
    dev = utils.create_devices_from_data("security-system.json")[1]
    enable_sensors(dev)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dev)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    # Setup the response after disarm
    panel = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            functionClass="alarm-state", value="arm-started-stay", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(panel, state)
    mocker.patch.object(mocked_controller._bridge, "fetch_device_states", return_value=panel.states)
    # Execute the test
    await mocked_controller.arm_home(alarm_panel.id)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[alarm_panel.id]
    assert dev.alarm_state.mode == "arm-started-stay"


@pytest.mark.asyncio
async def test_arm_away(mocked_controller, mocker):
    dev = utils.create_devices_from_data("security-system.json")[1]
    enable_sensors(dev)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dev)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    # Setup the response after disarm
    panel = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            functionClass="alarm-state", value="arm-started-away", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(panel, state)
    mocker.patch.object(mocked_controller._bridge, "fetch_device_states", return_value=panel.states)
    # Execute the test
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.arm_away(alarm_panel.id)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[alarm_panel.id]
    assert dev.alarm_state.mode == "arm-started-away"


@pytest.mark.asyncio
async def test_arm_bad_sensors(mocked_controller, mocker):
    dev = utils.create_devices_from_data("security-system.json")[1]
    disable_sensors(dev)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dev)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    mocker.patch.object(mocked_controller._bridge, "fetch_device_states", return_value=dev.states)
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    exp_err = "Sensors are open or unavailable: "
    with pytest.raises(SecuritySystemError, match=exp_err):
        await mocked_controller.arm_away(alarm_panel.id)
        await mocked_controller._bridge.async_block_until_done()


@pytest.mark.asyncio
async def test_alarm_trigger(mocked_controller, mocker):
    dev = utils.create_devices_from_data("security-system.json")[1]
    enable_sensors(dev)
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dev)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    # Setup the response after disarm
    panel = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            functionClass="alarm-state", value="alarming-sos", lastUpdateTime=0, functionInstance=None
        ),
    ]
    for state in new_states:
        utils.modify_state(panel, state)
    mocker.patch.object(mocked_controller._bridge, "fetch_device_states", return_value=panel.states)
    # Execute the test
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    await mocked_controller.alarm_trigger(alarm_panel.id)
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[alarm_panel.id]
    assert dev.alarm_state.mode == "alarming-sos"


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(alarm_panel)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    update = utils.create_devices_from_data("security-system.json")[1]
    updates = await mocked_controller.update_elem(update)
    assert updates == set()


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(alarm_panel)]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[alarm_panel.id]
    assert dev.available
    update = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            functionClass="alarm-state", value="triggered", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="available", value=False, lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="battery-powered", value="battery-powered", lastUpdateTime=0, functionInstance=None
        ),
        AferoState(
            functionClass="arm-exit-delay", value=300, lastUpdateTime=0, functionInstance="away"
        ),
        AferoState(
            functionClass="song-id", value="preset-12", lastUpdateTime=0, functionInstance="alarm"
        ),
        AferoState(
            functionClass="siren-action",
            functionInstance=None,
            value={"security-siren-action": {"resultCode": 0, "command": 4}},
        ),
    ]
    for state in new_states:
        utils.modify_state(update, state)
    updates = await mocked_controller.update_elem(update)
    assert not dev.available
    assert updates == {
        "alarm-state",
        "number-('arm-exit-delay', 'away')",
        "available",
        "select-('song-id', 'alarm')",
        "binary-battery-powered|None",
        "siren-action",
    }
    assert dev.alarm_state.mode == "triggered"
    assert dev.numbers[("arm-exit-delay", "away")].value == 300
    assert dev.selects[("song-id", "alarm")].selected == "preset-12"
    assert dev.binary_sensors["battery-powered|None"].current_value == "battery-powered"
    assert dev.binary_sensors["battery-powered|None"].value is True
    assert dev.siren_action.result_code == 0
    assert dev.siren_action.command == 4


@pytest.mark.asyncio
async def test_update_elem_from_siren(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(get_alarm_panel_with_siren())]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    update = get_alarm_panel_with_siren()
    utils.modify_state(
        update,
        AferoState(
            functionClass="siren-action",
            functionInstance=None,
            value=None,
        ),
    )
    updates = await mocked_controller.update_elem(update)
    assert updates == {"siren-action"}
    dev = mocked_controller[alarm_panel.id]
    assert dev.siren_action == features.SecuritySensorSirenFeature(
        result_code=None, command=None
    )


@pytest.mark.asyncio
async def test_update_elem_from_siren_empty(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(get_alarm_panel_with_siren())]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert len(mocked_controller.items) == 1
    update = get_alarm_panel_with_siren()
    updates = await mocked_controller.update_elem(update)
    assert updates == set()


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(alarm_panel)]
    )
    await mocked_controller._bridge.async_block_until_done()
    await mocked_controller.set_state(alarm_panel.id)


@pytest.mark.asyncio
async def test_set_state(mocked_controller):
    await mocked_controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(alarm_panel)]
    )
    await mocked_controller._bridge.async_block_until_done()
    await mocked_controller.set_state(
        alarm_panel.id,
        numbers={("arm-exit-delay", "away"): 300, ("bad", None): False},
        selects={("song-id", "alarm"): "preset-12", ("bad", None): False},
    )
    await mocked_controller._bridge.async_block_until_done()
    dev = mocked_controller[alarm_panel.id]
    assert dev.numbers[("arm-exit-delay", "away")].value == 300
    assert dev.selects[("song-id", "alarm")].selected == "preset-12"


@pytest.mark.asyncio
async def test_set_state_bad_device(mocked_controller):
    await mocked_controller.set_state(
        alarm_panel.id,
        numbers={("arm-exit-delay", "away"): 300, ("bad", None): False},
        selects={("song-id", "alarm"): "preset-12", ("bad", None): False},
    )
    mocked_controller._bridge.request.assert_not_called()


@pytest.mark.asyncio
async def test_emitting(bridge):
    dev_update = utils.create_devices_from_data("security-system.json")[1]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    await bridge.async_block_until_done()
    assert len(bridge.security_systems._items) == 1
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
    assert len(bridge.security_systems._items) == 1
    assert not bridge.security_systems[dev_update.id].available


def test_get_sensor_ids():
    assert get_sensor_ids(alarm_panel) == {1, 2, 4}


def test_get_valid_elements_state():
    assert get_valid_states(alarm_panel.states, 4) == [
        AferoState(functionClass='chirpMode', value="On", lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='triggerType', value="Home/Away", lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='bypassType', value="Off", lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='top-level-key', value="security-sensor-config-v2", lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='battery-level', value=100, lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='tampered', value="Off", lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='triggered', value="Off", lastUpdateTime=None, functionInstance=None),
        AferoState(functionClass='available', value=True, lastUpdateTime=None, functionInstance=None),
    ]


def test_get_valid_functions():
    assert get_valid_functions(alarm_panel.functions, 4) == [
        {'functionClass': 'chirpMode', 'functionInstance': 'sensor-4', 'type': 'category', 'values': [{'name': 'Off'}, {'name': 'On'}]},
        {'functionClass': 'triggerType', 'functionInstance': 'sensor-4', 'type': 'category', 'values': [{'name': 'Off'}, {'name': 'Home'}, {'name': 'Away'}, {'name': 'Home/Away'}]},
        {'functionClass': 'bypassType', 'functionInstance': 'sensor-4', 'type': 'category', 'values': [{'name': 'Off'}, {'name': 'Manual'}, {'name': 'On'}]},
    ]


def test_security_system_callback():
    results = security_system_callback(alarm_panel)
    assert results.remove_original is False
    assert len(results.split_devices) == 3
    assert results.split_devices[0].model == "Security System - Motion Sensor"
    assert results.split_devices[1].model == "Security System - Door/Window Sensor"
    assert results.split_devices[2].model == "Security System - Unknown"


capability_device = AferoDevice(
    id="12345",
    device_id="123456",
    model="its fake!",
    device_class="its fake!",
    default_name="its fake!",
    default_image="its fake!",
    friendly_name="its fake!",
    capabilities=[
        AferoCapability(
            functionClass="sensor-state-for-continue",
            functionInstance="sensor-1",
            type="object",
            schedulable=False,
            _opts={
                "name": "Aaaaa"
            }
        ),
        AferoCapability(
            functionClass="sensor-state",
            functionInstance="sensor-1",
            type="object",
            schedulable=False,
            _opts={
                "name": "Aaaaa"
            }
        )
    ]
)

@pytest.mark.parametrize(
    (("device", "sensor_id", "expected")),
    [
        # No capabilities
        (
            alarm_panel,
            4,
            "Sensor 4"
        ),
        # Capabilities
        (
            capability_device,
            1,
            "Aaaaa",
        )
    ]
)
def test_get_sensor_name(device, sensor_id, expected):
    assert get_sensor_name(device.capabilities, sensor_id) == expected


@pytest.mark.parametrize(
    (("device", "expected")),
    [
        # No valid data
        ([], "Unknown"),
        # Valid data and valid type
        (
            [
                AferoState(
                    functionClass="sensor-state",
                    functionInstance="sensor-4",
                    value={
                        "security-sensor-state": {
                            "deviceType": 1,
                            "tampered": 0,
                            "triggered": 0,
                            "missing": 0,
                            "versionBuild": 3,
                            "versionMajor": 2,
                            "versionMinor": 0,
                            "batteryLevel": 100
                        }
                    },
                )
            ],
            "Motion Sensor",
        ),
        # Valid data and invalid type
        (
            [
                AferoState(
                    functionClass="sensor-state",
                    functionInstance="sensor-4",
                    value={
                        "security-sensor-state": {
                            "deviceType": 3,
                            "tampered": 0,
                            "triggered": 0,
                            "missing": 0,
                            "versionBuild": 3,
                            "versionMajor": 2,
                            "versionMinor": 0,
                            "batteryLevel": 100
                        }
                    },
                )
            ],
            "Unknown",
        ),
    ]
)
def test_get_model_type(device, expected):
    assert get_model_type(device, 4) == expected


@pytest.mark.asyncio
async def test_validate_arm_state(mocked_controller, caplog):
    caplog.set_level("DEBUG")
    bridge = mocked_controller._bridge
    panel = get_alarm_panel_with_siren()
    single_sensor_with_bypass(panel, 4)
    await bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(panel)
        ]
    )
    await mocked_controller._bridge.async_block_until_done()
    await mocked_controller.validate_arm_state(panel.id, 4)
    await bridge.async_block_until_done()


@pytest.mark.asyncio
async def test_validate_arm_all_bypassed(mocked_controller, caplog):
    caplog.set_level("DEBUG")
    bridge = mocked_controller._bridge
    panel = get_alarm_panel_with_siren()
    bypass_all_sensors(panel)
    await bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(panel)
        ]
    )
    await mocked_controller._bridge.async_block_until_done()
    with pytest.raises(SecuritySystemError, match="No sensors are configured for the requested mode."):
        await mocked_controller.validate_arm_state(panel.id, 4)
        await bridge.async_block_until_done()


@pytest.mark.asyncio
async def test_validate_arm_state_invalid_controller(mocked_controller, mocker):
    bridge = mocked_controller._bridge
    panel = get_alarm_panel_with_siren()
    zandra_light = utils.create_devices_from_data("fan-ZandraFan.json")[1]
    panel.children.append(zandra_light.id)
    await bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(zandra_light),
            utils.create_hs_raw_from_device(panel)
        ]
    )
    await mocked_controller._bridge.async_block_until_done()
    exp_err = "Sensors are open or unavailable: "
    with pytest.raises(SecuritySystemError, match=exp_err):
        await mocked_controller.validate_arm_state(panel.id, 4)
        await bridge.async_block_until_done()
