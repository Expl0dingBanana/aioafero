from unittest.mock import AsyncMock

import pytest

from aioafero.device import AferoDevice, AferoState
from aioafero.v1.conclave import events


@pytest.mark.asyncio
async def test_apply_attr_change_patches_state_and_dispatches(conclave_bridge):
    bridge, device, generate = conclave_bridge
    payload = {
        "id": device.device_id,
        "attribute": {
            "id": 1,
            "data": "01",
            "value": "1",
            "updatedTimestamp": 1780876821586,
        },
    }
    assert await events.apply_attr_change(bridge, payload) is True
    generate.assert_awaited_once_with(device)
    state = next(s for s in device.states if s.functionClass == "power")
    assert state.value == "on"
    assert state.lastUpdateTime == 1780876821586


@pytest.mark.asyncio
async def test_apply_attr_change_brightness_writes_numeric_value(conclave_bridge):
    bridge, device, generate = conclave_bridge
    payload = {
        "id": device.device_id,
        "attribute": {"id": 2, "data": "28", "value": "40"},
    }
    assert await events.apply_attr_change(bridge, payload) is True
    state = next(s for s in device.states if s.functionClass == "brightness")
    assert state.value == 40
    generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_attr_change_unknown_attribute_id_skipped(conclave_bridge, caplog):
    bridge, device, generate = conclave_bridge
    payload = {
        "id": device.device_id,
        "attribute": {"id": 65001, "data": "ff", "value": "ignored"},
    }
    with caplog.at_level("DEBUG"):
        assert await events.apply_attr_change(bridge, payload) is False
    generate.assert_not_called()
    assert "unknown attribute" in caplog.text


@pytest.mark.asyncio
async def test_apply_attr_change_unknown_device_swallowed(conclave_bridge, caplog):
    bridge, _, generate = conclave_bridge
    payload = {
        "id": "not-a-real-device",
        "attribute": {"id": 1, "value": "1"},
    }
    with caplog.at_level("DEBUG"):
        assert await events.apply_attr_change(bridge, payload) is False
    generate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "x"},
        {"id": "x", "attribute": None},
        {"attribute": {"id": 1, "value": "1"}},
    ],
)
async def test_apply_attr_change_malformed_payload_is_false(conclave_bridge, payload):
    bridge, _, generate = conclave_bridge
    assert await events.apply_attr_change(bridge, payload) is False
    generate.assert_not_called()


@pytest.mark.asyncio
async def test_apply_status_change_patches_available_visible_direct(conclave_bridge):
    bridge, device, generate = conclave_bridge
    payload = {
        "id": device.device_id,
        "status": {
            "available": False,
            "visible": False,
            "direct": False,
            "connected": False,
            "linked": True,
            "rssi": 0,
            "updatedTimestamp": 1780876821586,
        },
    }
    assert await events.apply_status_change(bridge, payload) is True
    generate.assert_awaited_once_with(device)
    fcs = {s.functionClass: s.value for s in device.states}
    assert fcs == {"available": False, "visible": False, "direct": False}
    # status_change must not touch `linked` / `connected` / `rssi`.
    assert "connected" not in fcs
    assert "linked" not in fcs


@pytest.mark.asyncio
async def test_apply_status_change_partial_fields(conclave_bridge):
    bridge, device, generate = conclave_bridge
    payload = {"id": device.device_id, "status": {"available": True}}
    assert await events.apply_status_change(bridge, payload) is True
    assert any(
        s.functionClass == "available" and s.value is True for s in device.states
    )
    generate.assert_awaited_once_with(device)


@pytest.mark.asyncio
async def test_apply_status_change_no_actionable_fields(conclave_bridge):
    bridge, _, generate = conclave_bridge
    payload = {"id": "8ad8cc7b5c18ce2a", "status": {"linked": True}}
    assert await events.apply_status_change(bridge, payload) is False
    generate.assert_not_called()


@pytest.mark.asyncio
async def test_apply_status_change_unknown_device(conclave_bridge):
    bridge, _, generate = conclave_bridge
    assert (
        await events.apply_status_change(
            bridge, {"id": "unknown", "status": {"available": True}}
        )
        is False
    )
    generate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "x"},
        {"id": "x", "status": None},
        {"status": {"available": True}},
    ],
)
async def test_apply_status_change_malformed_payload(conclave_bridge, payload):
    bridge, _, generate = conclave_bridge
    assert await events.apply_status_change(bridge, payload) is False
    generate.assert_not_called()


@pytest.mark.asyncio
async def test_apply_attr_change_finds_device_cached_by_metadevice_id(conclave_bridge):
    """Production caches by metadevice UUID; Conclave pushes physical deviceId."""
    bridge, device, generate = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    payload = {
        "id": device.device_id,
        "attribute": {"id": 1, "data": "01", "value": "1"},
    }
    assert await events.apply_attr_change(bridge, payload) is True
    generate.assert_awaited_once_with(device)
    state = next(s for s in device.states if s.functionClass == "power")
    assert state.value == "on"


def test_translate_attr_change_brightness(conclave_bridge):
    _, device, _ = conclave_bridge
    state = events.translate_attr_change(device, {"id": 2, "value": "40"})
    assert state is not None
    assert state.functionClass == "brightness"
    assert state.value == 40


def test_translate_attr_change_unknown_attribute_returns_none(conclave_bridge):
    _, device, _ = conclave_bridge
    assert events.translate_attr_change(device, {"id": 999}) is None


def test_translate_status_change_maps_availability_fields():
    states = events.translate_status_change(
        {"available": False, "visible": True, "linked": True}
    )
    assert len(states) == 2
    assert {s.functionClass: s.value for s in states} == {
        "available": False,
        "visible": True,
    }


def test_private_event_handlers_cover_supported_events():
    assert set(events.PRIVATE_EVENT_HANDLERS) == {"attr_change", "status_change"}


def test_refresh_split_clone_states_noop_without_split_marker(conclave_bridge):
    _, parent, _ = conclave_bridge
    clone = AferoDevice(
        id="orphan-id",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        split_identifier="light",
        states=[AferoState(functionClass="power", functionInstance=None, value="on")],
    )
    events.refresh_split_clone_states(parent, clone)
    assert clone.states[0].value == "on"


def test_refresh_split_clone_states_noop_for_unknown_split_type(conclave_bridge):
    _, parent, _ = conclave_bridge
    clone = AferoDevice(
        id=f"{parent.id}-custom-zone",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        split_identifier="custom",
        states=[],
    )
    events.refresh_split_clone_states(parent, clone)
    assert clone.states == []


def test_split_instance_from_device():
    device = AferoDevice(
        id="uuid-light-trim",
        device_id="physical",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        split_identifier="light",
    )
    assert events.split_instance_from_device(device) == "trim"
    device.split_identifier = None
    assert events.split_instance_from_device(device) is None
    device.split_identifier = "missing"
    device.id = "uuid-without-marker"
    assert events.split_instance_from_device(device) is None


@pytest.mark.asyncio
async def test_dispatch_refreshes_light_split_clone_from_parent(
    conclave_bridge, mocker
):
    """Split-light clones must be refreshed from the parent before events fire."""
    bridge, parent, generate = conclave_bridge
    parent.id = "8866648e-ef12-47b1-a7af-16c86214933e"
    parent.states = [
        AferoState(functionClass="power", functionInstance="trim", value="on"),
        AferoState(functionClass="power", functionInstance="other", value="off"),
    ]
    clone = AferoDevice(
        id=f"{parent.id}-light-trim",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="Split light",
        functions=parent.functions,
        states=[],
        split_identifier="light",
    )
    bridge.events.split_devices = AsyncMock(return_value=[parent, clone, clone])
    add_dev = mocker.patch.object(bridge, "add_afero_dev")
    await events._dispatch_conclave_device_update(bridge, parent)
    assert generate.await_count == 2
    assert len(clone.states) == 1
    assert clone.states[0].functionInstance == "trim"
    add_dev.assert_called_once_with(clone, clone.id)


@pytest.mark.asyncio
async def test_dispatch_refreshes_security_sensor_split_clone_from_parent(
    conclave_bridge, mocker
):
    """Security sensor splits use security_system state filtering, not light rules."""
    bridge, parent, generate = conclave_bridge
    parent.id = "7f4e4c01-e799-45c5-9b1a-385433a78edc"
    parent.states = [
        AferoState(
            functionClass="sensor-state",
            functionInstance="sensor-12",
            value={
                "cfg-12": {
                    "batteryLevel": 90,
                    "tampered": 0,
                    "triggered": 1,
                    "missing": 0,
                    "deviceType": 2,
                }
            },
        ),
        AferoState(
            functionClass="sensor-state",
            functionInstance="sensor-18",
            value={
                "cfg-18": {
                    "batteryLevel": 80,
                    "tampered": 0,
                    "triggered": 0,
                    "missing": 0,
                    "deviceType": 1,
                }
            },
        ),
    ]
    clone = AferoDevice(
        id=f"{parent.id}-sensor-12",
        device_id=f"{parent.id}-sensor-12",
        model="m",
        device_class="security-system-sensor",
        default_name="n",
        default_image="i",
        friendly_name="Sensor 12",
        functions=[],
        states=[],
        split_identifier="sensor",
    )
    bridge.events.split_devices = AsyncMock(return_value=[parent, clone])
    await events._dispatch_conclave_device_update(bridge, parent)
    assert generate.await_count == 2
    triggered = next(
        (state for state in clone.states if state.functionClass == "triggered"),
        None,
    )
    assert triggered is not None
    assert triggered.value == "On"
