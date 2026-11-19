"""Test BlindsController"""

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import blinds, event
from aioafero.v1.models import features
from tests.v1 import utils

GATEWAY_DUMP = "blinds-gateway.json"
gateway, zone_1, zone_2 = utils.create_devices_from_data(GATEWAY_DUMP)

ALL_COMMANDS = {
    "stop-moving": {"stop"},
    "move-fine": {"up", "down"},
    "move-coarse": {"up", "down"},
    "clear-all-limits": {"clear"},
    "confirm-limit": {"confirm"},
    "start-limit-mode": {"top", "bottom"},
    "toggle-motor-reverse": {"toggle"},
    "pair-zone": {"pair"},
}


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.blinds


async def seed(controller):
    """Run discovery on the gateway dump."""
    await controller._bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump(GATEWAY_DUMP)
    )
    await controller._bridge.async_block_until_done()


def position_state(value, instance="blinds-open-1"):
    return AferoState(
        functionClass="blinds-open",
        functionInstance=instance,
        value=value,
        lastUpdateTime=0,
    )


def without_position(device):
    device.states = [s for s in device.states if s.functionClass != "blinds-open"]
    return device


@pytest.mark.asyncio
async def test_discovery(mocked_controller):
    await seed(mocked_controller)
    # Each zone is a shade; the gateway stays a parent device
    assert {item.id for item in mocked_controller} == {zone_1.id, zone_2.id}
    assert gateway.id in [item.id for item in mocked_controller._bridge.devices]
    dev = mocked_controller[zone_1.id]
    assert dev.available is True
    assert dev.position == features.PositionFeature(
        position=100,
        min=0,
        max=100,
        step=25,
        function_class="blinds-open",
        function_instance="blinds-open-1",
    )
    assert dev.commands == ALL_COMMANDS
    assert dev.device_information.parent_id == gateway.device_id
    assert dev.device_information.default_name == "Zone 1"
    assert mocked_controller[zone_2.id].position.position == 0
    assert mocked_controller[zone_2.id].position.function_instance == "blinds-open-2"


@pytest.mark.asyncio
async def test_initialize_elem_without_position(mocked_controller):
    dev = await mocked_controller.initialize_elem(
        without_position(utils.create_devices_from_data(GATEWAY_DUMP)[1])
    )
    assert dev.position is None
    assert dev.commands == ALL_COMMANDS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested", "sent"),
    [
        (100, 100),
        (0, 0),
        (60, 50),
        (63, 75),
        (130, 100),
        (-5, 0),
    ],
)
async def test_set_state(mocked_controller, mocker, requested, sent):
    await seed(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(zone_2.id, position=requested)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        zone_2.id,
        [
            {
                "functionClass": "blinds-open",
                "functionInstance": "blinds-open-2",
                "value": sent,
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert mocked_controller[zone_2.id].position.position == sent


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "sent"), [("open", 100), ("close", 0)])
async def test_open_close(mocked_controller, mocker, method, sent):
    await seed(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    # zone 1 is already open: open() must still send so the shade moves
    await getattr(mocked_controller, method)(zone_1.id)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        zone_1.id,
        [
            {
                "functionClass": "blinds-open",
                "functionInstance": "blinds-open-1",
                "value": sent,
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert mocked_controller[zone_1.id].position.position == sent


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller, mocker):
    await seed(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(zone_1.id)
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_state_no_position(mocked_controller, mocker, caplog):
    caplog.set_level(0)
    await seed(mocked_controller)
    mocked_controller[zone_1.id].position = None
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(zone_1.id, position=50)
    update_afero_api.assert_not_awaited()
    assert "does not report a position" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "kwargs", "function_class", "value"),
    [
        ("stop", {}, "stop-moving", "stop"),
        ("move", {"direction": "up"}, "move-coarse", "up"),
        ("move", {"direction": "down"}, "move-coarse", "down"),
        ("move", {"direction": "up", "fine": True}, "move-fine", "up"),
        ("move", {"direction": "down", "fine": True}, "move-fine", "down"),
        ("start_limit_setting", {"limit": "top"}, "start-limit-mode", "top"),
        ("start_limit_setting", {"limit": "bottom"}, "start-limit-mode", "bottom"),
        ("confirm_limit", {}, "confirm-limit", "confirm"),
        ("clear_limits", {}, "clear-all-limits", "clear"),
        ("toggle_motor_direction", {}, "toggle-motor-reverse", "toggle"),
    ],
)
async def test_commands(
    mocked_controller, mocker, method, kwargs, function_class, value
):
    await seed(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await getattr(mocked_controller, method)(zone_2.id, **kwargs)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        zone_2.id,
        [
            {
                "functionClass": function_class,
                "functionInstance": None,
                "value": value,
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    # One-shot commands never touch the cached position
    assert mocked_controller[zone_2.id].position.position == 0


@pytest.mark.asyncio
async def test_command_not_supported(mocked_controller, mocker, caplog):
    caplog.set_level(0)
    await seed(mocked_controller)
    mocked_controller[zone_1.id].commands.pop("stop-moving")
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.stop(zone_1.id)
    update_afero_api.assert_not_awaited()
    assert "does not support stop-moving=stop" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["set_state", "stop"])
async def test_no_dev(mocked_controller, mocker, caplog, method):
    caplog.set_level(0)
    await seed(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await getattr(mocked_controller, method)("not-a-device")
    update_afero_api.assert_not_awaited()
    assert "Unable to find device" in caplog.text


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await seed(mocked_controller)
    dev_update = utils.create_devices_from_data(GATEWAY_DUMP)[1]
    utils.modify_state(dev_update, position_state(50))
    utils.modify_state(
        dev_update,
        AferoState(functionClass="available", functionInstance=None, value=False),
    )
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller[zone_1.id]
    assert updates == {"position", "available"}
    assert dev.position.position == 50
    assert dev.position.step == 25
    assert dev.available is False


@pytest.mark.asyncio
async def test_update_elem_no_change(mocked_controller):
    await seed(mocked_controller)
    updates = await mocked_controller.update_elem(
        utils.create_devices_from_data(GATEWAY_DUMP)[1]
    )
    assert updates == set()


@pytest.mark.asyncio
async def test_update_elem_bad_position(mocked_controller):
    await seed(mocked_controller)
    dev_update = utils.create_devices_from_data(GATEWAY_DUMP)[1]
    utils.modify_state(dev_update, position_state("not-a-number"))
    updates = await mocked_controller.update_elem(dev_update)
    assert updates == set()
    assert mocked_controller[zone_1.id].position.position == 100


@pytest.mark.asyncio
async def test_update_elem_first_position(mocked_controller):
    dev = await mocked_controller.initialize_elem(
        without_position(utils.create_devices_from_data(GATEWAY_DUMP)[1])
    )
    assert dev.position is None
    dev_update = utils.create_devices_from_data(GATEWAY_DUMP)[1]
    # Conclave pushes numeric values as strings
    utils.modify_state(dev_update, position_state("75"))
    updates = await mocked_controller.update_elem(dev_update)
    assert updates == {"position"}
    assert mocked_controller[zone_1.id].position.position == 75


@pytest.mark.asyncio
async def test_blinds_emitting(bridge):
    dev_update = utils.create_devices_from_data(GATEWAY_DUMP)[2]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    await bridge.async_block_until_done()
    assert len(bridge.blinds._items) == 1
    # Simulate an update
    utils.modify_state(dev_update, position_state(25, instance="blinds-open-2"))
    update_event = {
        "type": "update",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    bridge.events.emit(event.EventType.RESOURCE_UPDATED, update_event)
    await bridge.async_block_until_done()
    assert len(bridge.blinds._items) == 1
    assert bridge.blinds[dev_update.id].position.position == 25


@pytest.mark.parametrize(
    ("functions", "value", "expected"),
    [
        # Range comes from the matching function definition
        (zone_1.functions, 50, (50, 0, 100, 25)),
        # No definition: fall back to 0-100 in steps of 1
        (None, 50, (50, 0, 100, 1)),
        ([], "75", (75, 0, 100, 1)),
        # A zero step would never move
        (
            [
                {
                    "functionClass": "blinds-open",
                    "functionInstance": "blinds-open-1",
                    "values": [{"range": {"min": 0, "max": 10, "step": 0}}],
                },
            ],
            5,
            (5, 0, 10, 1),
        ),
        (zone_1.functions, None, None),
        (zone_1.functions, "open", None),
    ],
)
def test_get_position_feature(functions, value, expected):
    feature = blinds.get_position_feature(functions, position_state(value))
    if expected is None:
        assert feature is None
    else:
        assert (feature.position, feature.min, feature.max, feature.step) == expected
        assert feature.function_class == "blinds-open"
        assert feature.function_instance == "blinds-open-1"


@pytest.mark.parametrize(
    ("functions", "expected"),
    [
        (zone_1.functions, ALL_COMMANDS),
        (None, {}),
        (
            [
                # Only result values: nothing to send
                {
                    "functionClass": "stop-moving",
                    "type": "category",
                    "values": [{"name": "success"}, {"name": "failure"}],
                },
                # Not a one-shot command
                {"functionClass": "blinds-open", "type": "numeric", "values": []},
            ],
            {},
        ),
    ],
)
def test_get_commands(functions, expected):
    assert blinds.get_commands(functions) == expected


@pytest.mark.parametrize(
    ("bounds", "requested", "expected"),
    [
        ((0, 100, 25), 12, 0),
        ((0, 100, 25), 13, 25),
        ((0, 100, 25), 99, 100),
        ((0, 100, 1), 42, 42),
        ((0, 100, 30), 100, 90),
        ((10, 50, 20), 0, 10),
    ],
)
def test_snap_position(bounds, requested, expected):
    low, high, step = bounds
    feature = features.PositionFeature(
        position=0,
        min=low,
        max=high,
        step=step,
        function_class="blinds-open",
        function_instance=None,
    )
    assert blinds.snap_position(feature, requested) == expected
