"""Test SecuritySystemController"""

import pytest

from aioafero.device import AferoDevice, AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.security_system import SecuritySystemController, features

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
    controller = SecuritySystemController(mocked_bridge)
    yield controller


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
    await mocked_controller.initialize_elem(get_alarm_panel_with_siren())
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.siren_action == features.SecuritySensorSirenFeature(
        result_code=0,
        command=4,
    )


@pytest.mark.asyncio
async def test_disarm(mocked_controller):
    await mocked_controller.initialize_elem(get_alarm_panel_with_siren())
    assert len(mocked_controller.items) == 1
    mocked_controller[alarm_panel.id].alarm_state.mode = "arm-away"
    await mocked_controller.disarm(alarm_panel.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == alarm_panel.id
    expected_states = [
        {
            "functionClass": "alarm-state",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "disarmed",
        },
        {
            "functionClass": "siren-action",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": None,
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_arm_home(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    assert len(mocked_controller.items) == 1
    await mocked_controller.arm_home(alarm_panel.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == alarm_panel.id
    expected_states = [
        {
            "functionClass": "alarm-state",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "arm-started-stay",
        },
        {
            "functionClass": "siren-action",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": {"security-siren-action": {"resultCode": 0, "command": 4}},
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_arm_away(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    assert len(mocked_controller.items) == 1
    await mocked_controller.arm_away(alarm_panel.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == alarm_panel.id
    expected_states = [
        {
            "functionClass": "alarm-state",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "arm-started-away",
        },
        {
            "functionClass": "siren-action",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": {"security-siren-action": {"resultCode": 0, "command": 4}},
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_alarm_trigger(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    assert len(mocked_controller.items) == 1
    await mocked_controller.alarm_trigger(alarm_panel.id)
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == alarm_panel.id
    expected_states = [
        {
            "functionClass": "alarm-state",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "alarming-sos",
        },
        {
            "functionClass": "siren-action",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": {"security-siren-action": {"resultCode": 0, "command": 5}},
        },
    ]
    utils.ensure_states_sent(mocked_controller, expected_states)


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    assert len(mocked_controller.items) == 1
    update = utils.create_devices_from_data("security-system.json")[1]
    updates = await mocked_controller.update_elem(update)
    assert updates == set()


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[alarm_panel.id]
    assert dev.available
    update = utils.create_devices_from_data("security-system.json")[1]
    new_states = [
        AferoState(
            **{
                "functionClass": "alarm-state",
                "value": "triggered",
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
        AferoState(
            **{
                "functionClass": "battery-powered",
                "value": "battery-powered",
                "lastUpdateTime": 0,
                "functionInstance": None,
            }
        ),
        AferoState(
            **{
                "functionClass": "arm-exit-delay",
                "value": 300,
                "lastUpdateTime": 0,
                "functionInstance": "away",
            }
        ),
        AferoState(
            **{
                "functionClass": "song-id",
                "value": "preset-12",
                "lastUpdateTime": 0,
                "functionInstance": "alarm",
            }
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
    assert dev.binary_sensors["battery-powered|None"]._value == "battery-powered"
    assert dev.binary_sensors["battery-powered|None"].value is True
    assert dev.siren_action.result_code == 0
    assert dev.siren_action.command == 4


@pytest.mark.asyncio
async def test_update_elem_from_siren(mocked_controller):
    await mocked_controller.initialize_elem(get_alarm_panel_with_siren())
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
    await mocked_controller.initialize_elem(get_alarm_panel_with_siren())
    assert len(mocked_controller.items) == 1
    update = get_alarm_panel_with_siren()
    updates = await mocked_controller.update_elem(update)
    assert updates == set()


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    await mocked_controller.set_state(alarm_panel.id)


@pytest.mark.asyncio
async def test_set_state(mocked_controller):
    await mocked_controller.initialize_elem(alarm_panel)
    await mocked_controller.set_state(
        alarm_panel.id,
        mode="alarming-sos",
        numbers={("arm-exit-delay", "away"): 300, ("bad", None): False},
        selects={("song-id", "alarm"): "preset-12", ("bad", None): False},
    )
    dev = mocked_controller[alarm_panel.id]
    assert dev.numbers[("arm-exit-delay", "away")].value == 300
    assert dev.selects[("song-id", "alarm")].selected == "preset-12"
    req = utils.get_json_call(mocked_controller)
    assert req["metadeviceId"] == alarm_panel.id
    expected_calls = [
        {
            "functionClass": "alarm-state",
            "functionInstance": None,
            "lastUpdateTime": 12345,
            "value": "alarming-sos",
        },
        {
            "functionClass": "arm-exit-delay",
            "functionInstance": "away",
            "lastUpdateTime": 12345,
            "value": 300,
        },
        {
            "functionClass": "song-id",
            "functionInstance": "alarm",
            "lastUpdateTime": 12345,
            "value": "preset-12",
        },
    ]
    for call in expected_calls:
        assert call in req["values"]


@pytest.mark.asyncio
async def test_set_state_bad_device(mocked_controller):
    await mocked_controller.set_state(
        alarm_panel.id,
        mode="alarming-sos",
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
    assert not bridge.security_systems._items[dev_update.id].available
