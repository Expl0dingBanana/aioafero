from unittest.mock import AsyncMock

import pytest

from aioafero.device import AferoDevice, SplitDeviceId
from aioafero.errors import AferoError
from aioafero.types import EventType
from aioafero.v1.conclave import events
from tests.v1 import utils
from tests.v1.conclave.helpers import get_conclave_dump, get_conclave_frames
from tests.v1.utils import create_devices_from_data, create_hs_raw_from_device


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
    generate.assert_awaited_once_with(device)


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


@pytest.mark.asyncio
async def test_apply_attr_change_skips_split_clones_sharing_device_id(conclave_bridge):
    """Parent + split clones share Conclave deviceId; only the parent is patched."""
    bridge, parent, generate = conclave_bridge
    clone = AferoDevice(
        id=f"{parent.id}-light-trim",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="Trim",
        functions=parent.functions,
        states=[],
        split=SplitDeviceId(parent.id, "light", "trim"),
    )
    bridge.add_afero_dev(clone, clone.id)
    payload = {
        "id": parent.device_id,
        "attribute": {"id": 1, "data": "01", "value": "1"},
    }
    assert await events.apply_attr_change(bridge, payload) is True
    generate.assert_awaited_once_with(parent)
    # Clone must not receive the raw parent-level power patch.
    assert clone.states == []


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
    assert set(events.INVALIDATE_KIND_HANDLERS) == {"add", "remove"}
    assert set(events.PUBLIC_EVENT_HANDLERS) == {"invalidate"}


@pytest.mark.asyncio
async def test_captured_attr_change_updates_live_light_brightness(mocked_bridge):
    """Captured brightness payloads update a light seeded from device_dumps."""
    a21 = utils.create_devices_from_data("light-a21.json")[0]
    await mocked_bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-a21.json")
    )
    await mocked_bridge.async_block_until_done()

    light = mocked_bridge.lights[a21.id]
    cached = mocked_bridge.get_afero_device(a21.id)
    assert light.brightness == 50

    payloads = get_conclave_dump("brightness_attr_change.json")
    assert len(payloads) == 2

    assert await events.apply_attr_change(mocked_bridge, payloads[0])
    await mocked_bridge.async_block_until_done()
    assert light.brightness == 28

    assert await events.apply_attr_change(mocked_bridge, payloads[1])
    await mocked_bridge.async_block_until_done()
    assert light.brightness == 100

    brightness = next(s for s in cached.states if s.functionClass == "brightness")
    assert brightness.lastUpdateTime == 1786298006828


@pytest.mark.asyncio
async def test_apply_invalidate_remove_metadevice(conclave_bridge):
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    bridge.add_device(device.id, bridge.lights)
    jobs: list = []
    bridge.events.add_job = jobs.append

    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "metadevices",
                "values": [{"metadeviceId": device.id}],
            },
        )
        is True
    )
    assert device.id not in bridge._known_afero_devices
    assert device.id not in bridge.tracked_devices
    assert any(
        job["type"] == EventType.RESOURCE_DELETED and job["device_id"] == device.id
        for job in jobs
    )


@pytest.mark.asyncio
async def test_apply_invalidate_remove_physical_device(conclave_bridge):
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    bridge.add_device(device.id, bridge.lights)
    jobs: list = []
    bridge.events.add_job = jobs.append

    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "devices",
                "values": [{"deviceId": device.device_id}],
            },
        )
        is True
    )
    assert device.id not in bridge._known_afero_devices
    assert any(job["type"] == EventType.RESOURCE_DELETED for job in jobs)


@pytest.mark.asyncio
async def test_apply_invalidate_remove_unknown_device_is_false(conclave_bridge):
    bridge, _, _ = conclave_bridge
    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "devices",
                "values": [{"deviceId": "deadbeefdeadbeef"}],
            },
        )
        is False
    )


@pytest.mark.asyncio
async def test_apply_invalidate_remove_unknown_target(conclave_bridge, caplog):
    bridge, _, _ = conclave_bridge
    with caplog.at_level("DEBUG"):
        assert (
            await events.apply_invalidate_remove(
                bridge, {"kind": "remove", "target": "rooms", "values": []}
            )
            is False
        )
    assert "Ignoring Conclave invalidate remove" in caplog.text


@pytest.mark.asyncio
async def test_apply_public_invalidate_update_ignored(conclave_bridge, caplog):
    bridge, _, _ = conclave_bridge
    with caplog.at_level("DEBUG"):
        assert (
            await events.apply_public_invalidate(
                bridge,
                {
                    "kind": "update",
                    "type": "metadevice",
                    "id": "x",
                    "fields": [{"name": "friendlyName", "value": "N"}],
                },
            )
            is False
        )
    assert "Ignoring Conclave invalidate kind" in caplog.text


@pytest.mark.asyncio
async def test_apply_invalidate_add_metadevice(mocked_bridge):
    light = create_devices_from_data("light-a21.json")[0]
    raw = create_hs_raw_from_device(light)
    mocked_bridge.fetch_metadevice = AsyncMock(return_value=raw)

    assert (
        await events.apply_invalidate_add(
            mocked_bridge,
            {
                "kind": "add",
                "target": "metadevices",
                "values": [{"metadeviceId": light.id}],
            },
        )
        is True
    )
    await mocked_bridge.async_block_until_done()
    assert light.id in mocked_bridge.lights
    assert light.id in mocked_bridge.devices


@pytest.mark.asyncio
async def test_apply_invalidate_add_devices_already_cached_is_false(conclave_bridge):
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    assert (
        await events.apply_invalidate_add(
            bridge,
            {
                "kind": "add",
                "target": "devices",
                "values": [{"deviceId": device.device_id}],
            },
        )
        is False
    )


@pytest.mark.asyncio
async def test_apply_invalidate_add_devices_unknown_triggers_discovery(
    conclave_bridge, mocker
):
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.events.tombstone_device("stale-meta")

    async def poll_imports():
        bridge.add_afero_dev(device, device.device_id)

    poll = mocker.patch.object(
        bridge.events, "perform_discovery_poll", side_effect=poll_imports
    )
    assert (
        await events.apply_invalidate_add(
            bridge,
            {
                "kind": "add",
                "target": "devices",
                "values": [{"deviceId": device.device_id}],
            },
        )
        is True
    )
    poll.assert_awaited_once()
    assert bridge.events._discovery_tombstones == {}


@pytest.mark.asyncio
async def test_apply_invalidate_add_devices_unknown_discovery_miss_is_false(
    conclave_bridge, mocker, caplog
):
    bridge, _, _ = conclave_bridge
    mocker.patch.object(bridge.events, "perform_discovery_poll", new_callable=AsyncMock)
    with caplog.at_level("WARNING"):
        assert (
            await events.apply_invalidate_add(
                bridge,
                {
                    "kind": "add",
                    "target": "devices",
                    "values": [{"deviceId": "ffffffffffffffff"}],
                },
            )
            is False
        )
    assert "did not import" in caplog.text


@pytest.mark.asyncio
async def test_apply_invalidate_add_fetch_failure(conclave_bridge, mocker, caplog):
    bridge, device, _ = conclave_bridge
    bridge.events.tombstone_device(device.id)
    mocker.patch.object(
        bridge,
        "fetch_metadevice",
        new_callable=AsyncMock,
        side_effect=AferoError("nope"),
    )
    with caplog.at_level("WARNING"):
        assert (
            await events.apply_invalidate_add(
                bridge,
                {
                    "kind": "add",
                    "target": "metadevices",
                    "values": [{"metadeviceId": device.id}],
                },
            )
            is False
        )
    assert "failed fetching metadevice" in caplog.text
    assert device.id not in bridge.events._discovery_tombstones


@pytest.mark.asyncio
async def test_apply_invalidate_add_empty_metadevice(conclave_bridge, mocker, caplog):
    bridge, device, _ = conclave_bridge
    bridge.events.tombstone_device(device.id)
    mocker.patch.object(
        bridge, "fetch_metadevice", new_callable=AsyncMock, return_value=None
    )
    with caplog.at_level("DEBUG"):
        assert (
            await events.apply_invalidate_add(
                bridge,
                {
                    "kind": "add",
                    "target": "metadevices",
                    "values": [{"metadeviceId": device.id}],
                },
            )
            is False
        )
    assert "skipped empty metadevice" in caplog.text
    assert device.id not in bridge.events._discovery_tombstones


@pytest.mark.asyncio
async def test_apply_invalidate_add_unknown_target(conclave_bridge, caplog):
    bridge, _, _ = conclave_bridge
    with caplog.at_level("DEBUG"):
        assert (
            await events.apply_invalidate_add(
                bridge, {"kind": "add", "target": "rooms", "values": []}
            )
            is False
        )
    assert "Ignoring Conclave invalidate add" in caplog.text


@pytest.mark.asyncio
async def test_apply_invalidate_remove_malformed_values(conclave_bridge):
    bridge, _, _ = conclave_bridge
    assert (
        await events.apply_invalidate_remove(
            bridge, {"kind": "remove", "target": "metadevices", "values": "nope"}
        )
        is False
    )
    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "metadevices",
                "values": ["skip", {"metadeviceId": None}, {}],
            },
        )
        is False
    )


@pytest.mark.asyncio
async def test_apply_invalidate_remove_includes_split_clone(conclave_bridge):
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    clone = AferoDevice(
        id=f"{device.id}-light-main",
        device_id=device.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="clone",
        functions=[],
        states=[],
        split=SplitDeviceId(device.id, "light", "main"),
    )
    bridge.add_afero_dev(clone)
    bridge.add_device(device.id, bridge.lights)
    bridge.add_device(clone.id, bridge.lights)
    jobs: list = []
    bridge.events.add_job = jobs.append

    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "metadevices",
                "values": [{"metadeviceId": device.id}],
            },
        )
        is True
    )
    deleted_ids = {job["device_id"] for job in jobs}
    assert device.id in deleted_ids
    assert clone.id in deleted_ids
    assert device.id not in bridge._known_afero_devices
    assert clone.id not in bridge._known_afero_devices


def test_unique_ids_dedupes():
    assert events._unique_ids(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_cached_ids_for_parents_empty():
    class _Bridge:
        tracked_devices = set()
        known_afero_device_ids = set()

        def resolve_metadevice_id(self, device_id):
            return device_id

    assert events._cached_ids_for_parents(_Bridge(), set()) == []


def test_cached_ids_for_parents_ignores_untracked_parent():
    """Already-cleared parents must not reappear as delete targets."""

    class _Bridge:
        tracked_devices = set()
        known_afero_device_ids = set()

        def resolve_metadevice_id(self, device_id):
            return device_id

    assert events._cached_ids_for_parents(_Bridge(), {"orphan-parent"}) == []


@pytest.mark.asyncio
async def test_emit_resource_deleted_skips_already_gone(conclave_bridge):
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    jobs: list = []
    bridge.events.add_job = jobs.append
    assert await events._emit_resource_deleted(bridge, [device.id]) is False
    assert jobs == []
    """Conclave often sends devices + metadevices remove; only one DELETED batch."""
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    bridge.add_device(device.id, bridge.lights)
    jobs: list = []
    bridge.events.add_job = jobs.append

    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "devices",
                "values": [{"deviceId": device.device_id}],
            },
        )
        is True
    )
    first_deletes = [job for job in jobs if job["type"] == EventType.RESOURCE_DELETED]
    assert first_deletes

    assert (
        await events.apply_invalidate_remove(
            bridge,
            {
                "kind": "remove",
                "target": "metadevices",
                "values": [{"metadeviceId": device.id}],
            },
        )
        is False
    )
    assert [
        job for job in jobs if job["type"] == EventType.RESOURCE_DELETED
    ] == first_deletes


def test_value_helpers_skip_non_dicts():
    assert events._metadevice_ids_from_values(None) == []
    assert events._device_ids_from_values(None) == []
    assert events._device_ids_from_values(["x", {"deviceId": "abc"}]) == ["abc"]


@pytest.mark.asyncio
async def test_captured_invalidate_remove_deletes_live_light(mocked_bridge):
    """Captured inventory remove frames delete a dump-seeded light."""
    a21 = utils.create_devices_from_data("light-a21.json")[0]
    await mocked_bridge.events.generate_events_from_data(
        utils.create_hs_raw_from_dump("light-a21.json")
    )
    await mocked_bridge.async_block_until_done()
    assert a21.id in mocked_bridge.lights

    for frame in get_conclave_frames("inventory_remove.json"):
        public = frame.get("public")
        if isinstance(public, dict):
            await events.apply_public_invalidate(mocked_bridge, public["data"])
            continue
        private = frame.get("private")
        if isinstance(private, dict) and private.get("event") == "status_change":
            await events.apply_status_change(mocked_bridge, private["data"])
    await mocked_bridge.async_block_until_done()

    assert a21.id not in mocked_bridge.lights
    assert a21.id not in mocked_bridge.devices
    assert a21.id not in mocked_bridge.tracked_devices


@pytest.mark.asyncio
async def test_captured_invalidate_add_imports_live_light(mocked_bridge):
    """Captured inventory add frames import a light via fetch_metadevice."""
    dump = get_conclave_dump("inventory_add.json")
    metadevice_id = dump["metadevice_id"]
    mocked_bridge.fetch_metadevice = AsyncMock(return_value=dump["metadevice_response"])

    for frame in get_conclave_frames("inventory_add.json"):
        public = frame.get("public")
        if isinstance(public, dict):
            await events.apply_public_invalidate(mocked_bridge, public["data"])
    await mocked_bridge.async_block_until_done()

    mocked_bridge.fetch_metadevice.assert_awaited()
    assert metadevice_id in mocked_bridge.lights
    assert metadevice_id in mocked_bridge.devices
    assert mocked_bridge.get_afero_device(metadevice_id).device_id == dump["device_id"]
