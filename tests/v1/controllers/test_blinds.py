"""Test BlindsController"""

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.blinds import features
from tests.v1 import utils

blinds = utils.create_devices_from_data("blinds-zone.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.blinds


async def _load(controller):
    await controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(blinds)]
    )
    await controller._bridge.async_block_until_done()


@pytest.mark.asyncio
async def test_initialize(mocked_controller):
    await mocked_controller.initialize_elem(blinds)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller[blinds.id]
    assert dev.id == "0f6c2326-d4db-483f-855a-13800b0a8291"
    assert dev.available is True
    assert dev.position == features.PositionFeature(
        position=100,
        function_class="blinds-open",
        function_instance="blinds-open-1",
        min=0,
        max=100,
        step=25,
    )


@pytest.mark.asyncio
async def test_initialize_no_position(mocked_controller):
    dev_no_pos = utils.create_devices_from_data("blinds-zone.json")[0]
    dev_no_pos.states = [
        s for s in dev_no_pos.states if s.functionClass != "blinds-open"
    ]
    await mocked_controller.initialize_elem(dev_no_pos)
    assert mocked_controller[dev_no_pos.id].position is None
    # Updates must not fail when there is no position to update
    assert await mocked_controller.update_elem(blinds) == set()


@pytest.mark.parametrize(
    ("method", "args", "expected"),
    [
        ("close", (), 0),
        ("set_position", (40,), 50),
        ("set_position", (37,), 25),
        ("set_position", (63,), 75),
        ("set_position", (-5,), 0),
    ],
)
@pytest.mark.asyncio
async def test_move(mocked_controller, mocker, method, args, expected):
    await _load(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await getattr(mocked_controller, method)(blinds.id, *args)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        blinds.id,
        [
            {
                "functionClass": "blinds-open",
                "functionInstance": "blinds-open-1",
                "value": expected,
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    assert mocked_controller[blinds.id].position.position == expected


@pytest.mark.asyncio
async def test_open_unchanged(mocked_controller, mocker, caplog):
    """Already fully open in the dump, so nothing is sent."""
    await _load(mocked_controller)
    update_afero_api = mocker.patch.object(mocked_controller, "update_afero_api")
    with caplog.at_level("DEBUG"):
        await mocked_controller.open(blinds.id)
    update_afero_api.assert_not_awaited()
    assert "No states to send. Skipping" in caplog.text


@pytest.mark.asyncio
async def test_update_elem(mocked_controller):
    await _load(mocked_controller)
    dev_update = utils.create_devices_from_data("blinds-zone.json")[0]
    for state in [
        AferoState(
            functionClass="blinds-open",
            value=25,
            lastUpdateTime=0,
            functionInstance="blinds-open-1",
        ),
        AferoState(
            functionClass="available",
            value=False,
            lastUpdateTime=0,
            functionInstance=None,
        ),
    ]:
        utils.modify_state(dev_update, state)
    updates = await mocked_controller.update_elem(dev_update)
    dev = mocked_controller[blinds.id]
    assert dev.position.position == 25
    assert dev.available is False
    assert updates == {"position", "available"}


@pytest.mark.asyncio
async def test_empty_update(mocked_controller):
    await _load(mocked_controller)
    assert await mocked_controller.update_elem(blinds) == set()


@pytest.mark.asyncio
async def test_set_state_empty(mocked_controller, mocker):
    await _load(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state(blinds.id)
    update_afero_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_state_no_dev(mocked_controller, caplog, mocker):
    caplog.set_level(0)
    await _load(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.set_state("not-a-device", position=10)
    update_afero_api.assert_not_awaited()
    assert "Unable to find device" in caplog.text


@pytest.mark.asyncio
async def test_blinds_emitting(bridge):
    dev_update = utils.create_devices_from_data("blinds-zone.json")[0]
    bridge.events.emit(
        event.EventType.RESOURCE_ADDED,
        {"type": "add", "device_id": dev_update.id, "device": dev_update},
    )
    await bridge.async_block_until_done()
    assert len(bridge.blinds._items) == 1
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="blinds-open", functionInstance="blinds-open-1", value=0
        ),
    )
    bridge.events.emit(
        event.EventType.RESOURCE_UPDATED,
        {"type": "update", "device_id": dev_update.id, "device": dev_update},
    )
    await bridge.async_block_until_done()
    assert bridge.blinds[dev_update.id].position.position == 0


@pytest.mark.asyncio
async def test_set_position_clamps_high(mocked_controller, mocker):
    """250 clamps to 100, which is where the dump already is."""
    await _load(mocked_controller)
    update_afero_api = mocker.patch.object(mocked_controller, "update_afero_api")
    await mocked_controller.set_position(blinds.id, 250)
    update_afero_api.assert_not_awaited()


gateway = utils.create_devices_from_data("blinds-gateway.json")[0]


async def _load_with_gateway(controller):
    await controller._bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(gateway),
            utils.create_hs_raw_from_device(blinds),
        ]
    )
    await controller._bridge.async_block_until_done()


async def _poll(controller, gateway_dev, zone_dev=blinds):
    """Simulate a full discovery poll, which always lists the zone too."""
    await controller._bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(gateway_dev),
            utils.create_hs_raw_from_device(zone_dev),
        ]
    )
    await controller._bridge.async_block_until_done()


def _gateway_update(available: bool):
    update = utils.create_devices_from_data("blinds-gateway.json")[0]
    utils.modify_state(
        update,
        AferoState(functionClass="available", functionInstance=None, value=available),
    )
    return update


@pytest.mark.asyncio
async def test_gateway_down_at_discovery(mocked_controller):
    down = _gateway_update(False)
    await mocked_controller._bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(down),
            utils.create_hs_raw_from_device(blinds),
        ]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert mocked_controller[blinds.id].available is False


@pytest.mark.asyncio
async def test_gateway_availability_propagates(mocked_controller, mocker):
    await _load_with_gateway(mocked_controller)
    assert mocked_controller[blinds.id].available is True
    callback = mocker.Mock()
    mocked_controller.subscribe(callback)
    # Gateway goes down
    await _poll(mocked_controller, _gateway_update(False))
    assert mocked_controller[blinds.id].available is False
    callback.assert_called_once_with(
        event.EventType.RESOURCE_UPDATED, mocked_controller[blinds.id]
    )
    # Zone still reports itself available, but gateway stays down
    zone = utils.create_devices_from_data("blinds-zone.json")[0]
    assert await mocked_controller.update_elem(zone) == set()
    assert mocked_controller[blinds.id].available is False
    # Another gateway event with no change does not re-emit
    callback.reset_mock()
    await _poll(mocked_controller, _gateway_update(False))
    callback.assert_not_called()
    # Gateway recovers
    await _poll(mocked_controller, _gateway_update(True))
    assert mocked_controller[blinds.id].available is True
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_zone_down_while_gateway_up(mocked_controller):
    await _load_with_gateway(mocked_controller)
    zone = utils.create_devices_from_data("blinds-zone.json")[0]
    utils.modify_state(
        zone,
        AferoState(functionClass="available", functionInstance=None, value=False),
    )
    assert await mocked_controller.update_elem(zone) == {"available"}
    # Gateway event must not revive a zone that is itself down
    await _poll(mocked_controller, _gateway_update(True), zone)
    assert mocked_controller[blinds.id].available is False


@pytest.mark.asyncio
async def test_gateway_of_other_parent_ignored(mocked_controller):
    await _load_with_gateway(mocked_controller)
    other = _gateway_update(False)
    other.device_id = "some-other-parent"
    await mocked_controller._bridge.events.generate_events_from_data(
        [
            utils.create_hs_raw_from_device(other),
            utils.create_hs_raw_from_device(blinds),
        ]
    )
    await mocked_controller._bridge.async_block_until_done()
    assert mocked_controller[blinds.id].available is True


@pytest.mark.asyncio
async def test_gateway_event_empty_or_deleted(mocked_controller):
    await _load_with_gateway(mocked_controller)
    await mocked_controller._handle_gateway_event(
        event.EventType.RESOURCE_UPDATED, None
    )
    await mocked_controller._handle_gateway_event(
        event.EventType.RESOURCE_DELETED,
        {"type": "delete", "device_id": gateway.id, "device": gateway},
    )
    assert mocked_controller[blinds.id].available is True


@pytest.mark.asyncio
async def test_gateway_event_without_device(mocked_controller):
    await _load_with_gateway(mocked_controller)
    await mocked_controller._handle_gateway_event(
        event.EventType.RESOURCE_UPDATED, {"type": event.EventType.RESOURCE_UPDATED}
    )
    assert mocked_controller[blinds.id].available is True


@pytest.mark.asyncio
async def test_initialize_only_once(mocked_controller):
    await mocked_controller.initialize()
    subscribers = len(mocked_controller._bridge.events._subscribers)
    await mocked_controller.initialize()
    assert len(mocked_controller._bridge.events._subscribers) == subscribers


@pytest.mark.parametrize(
    "functions",
    [
        [],
        [{"functionClass": "blinds-open", "functionInstance": "other", "values": []}],
        [
            {
                "functionClass": "blinds-open",
                "functionInstance": "blinds-open-1",
                "values": [{"range": {}}],
            }
        ],
    ],
)
@pytest.mark.asyncio
async def test_initialize_no_range_defaults(mocked_controller, functions):
    """Without an advertised range any whole position is accepted."""
    dev = utils.create_devices_from_data("blinds-zone.json")[0]
    dev.functions = functions
    await mocked_controller.initialize_elem(dev)
    position = mocked_controller[dev.id].position
    assert (position.min, position.max, position.step) == (0, 100, 1)
    assert position.snap(37) == 37


@pytest.mark.asyncio
async def test_stop(mocked_controller, mocker):
    await _load(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.stop(blinds.id)
    await mocked_controller._bridge.async_block_until_done()
    update_afero_api.assert_awaited_once_with(
        blinds.id,
        [
            {
                "functionClass": "stop-moving",
                "functionInstance": None,
                "value": "stop",
                "lastUpdateTime": mocker.ANY,
            }
        ],
    )
    # Stopping does not change the tracked position
    assert mocked_controller[blinds.id].position.position == 100


@pytest.mark.asyncio
async def test_stop_no_dev(mocked_controller, caplog, mocker):
    caplog.set_level(0)
    await _load(mocked_controller)
    update_afero_api = utils.mock_update_api(mocked_controller, mocker)
    await mocked_controller.stop("not-a-device")
    update_afero_api.assert_not_awaited()
    assert "Unable to find device" in caplog.text


@pytest.fixture
def mocked_gateways(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    return mocked_bridge.blinds_gateways


async def _load_gateway(controller, dev=gateway):
    await controller._bridge.events.generate_events_from_data(
        [utils.create_hs_raw_from_device(dev)]
    )
    await controller._bridge.async_block_until_done()


@pytest.mark.asyncio
async def test_gateway_initialize(mocked_gateways):
    await mocked_gateways.initialize_elem(gateway)
    dev = mocked_gateways[gateway.id]
    assert dev.id == "2f513922-1b10-401a-8b6e-9a010de5766d"
    assert dev.available is True
    assert dev.sensors["wifi-steady-state"].value == "connected"
    assert dev.sensors["wifi-setup-state"].value == "connected"
    # Signal strength is already reported by the device controller
    assert "wifi-rssi" not in dev.sensors
    # Read-only: nothing to control on the model or the controller
    assert not hasattr(dev, "status_leds")
    assert not hasattr(mocked_gateways, "set_state")


@pytest.mark.asyncio
async def test_gateway_update_elem(mocked_gateways):
    await _load_gateway(mocked_gateways)
    update = utils.create_devices_from_data("blinds-gateway.json")[0]
    for state in [
        AferoState(
            functionClass="wifi-steady-state", functionInstance=None, value="offline"
        ),
        AferoState(functionClass="available", functionInstance=None, value=False),
    ]:
        utils.modify_state(update, state)
    updates = await mocked_gateways.update_elem(update)
    dev = mocked_gateways[gateway.id]
    assert dev.sensors["wifi-steady-state"].value == "offline"
    assert dev.available is False
    assert updates == {"available", "sensor-wifi-steady-state"}


@pytest.mark.asyncio
async def test_gateway_empty_update(mocked_gateways):
    await _load_gateway(mocked_gateways)
    assert await mocked_gateways.update_elem(gateway) == set()


@pytest.mark.asyncio
async def test_gateway_emitting(bridge):
    dev_update = utils.create_devices_from_data("blinds-gateway.json")[0]
    bridge.events.emit(
        event.EventType.RESOURCE_ADDED,
        {"type": "add", "device_id": dev_update.id, "device": dev_update},
    )
    await bridge.async_block_until_done()
    assert len(bridge.blinds_gateways._items) == 1
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="wifi-setup-state", functionInstance=None, value="pending"
        ),
    )
    bridge.events.emit(
        event.EventType.RESOURCE_UPDATED,
        {"type": "update", "device_id": dev_update.id, "device": dev_update},
    )
    await bridge.async_block_until_done()
    assert (
        bridge.blinds_gateways[dev_update.id].sensors["wifi-setup-state"].value
        == "pending"
    )
