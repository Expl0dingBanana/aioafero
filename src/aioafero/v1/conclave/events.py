"""Apply Conclave ``private`` and ``public`` events to the cached bridge state."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError

from aioafero.device import AferoDevice, AferoState, merge_afero_states
from aioafero.errors import AferoError
from aioafero.types import EventType
from aioafero.util import normalize_afero_last_update_time_ms
from aioafero.v1.controllers.event import AferoEvent
from aioafero.v1.controllers.exhaust_fan import (
    SPLIT_IDENTIFIER as EXHAUST_FAN_SPLIT,
    get_valid_states as exhaust_fan_valid_states,
)
from aioafero.v1.controllers.light import (
    SPLIT_IDENTIFIER as LIGHT_SPLIT,
    get_valid_states as light_valid_states,
)
from aioafero.v1.controllers.portable_ac import (
    SPLIT_IDENTIFIER as PORTABLE_AC_SPLIT,
    get_valid_states as portable_ac_valid_states,
)
from aioafero.v1.controllers.security_system import (
    SENSOR_SPLIT_IDENTIFIER,
    get_valid_states as security_sensor_valid_states,
)

from .protocol import PUBLIC_INVALIDATE_EVENT, PrivateEventHandler, PublicEventHandler
from .semantics import build_attribute_index, coerce_rest_state_value, resolve_binding

if TYPE_CHECKING:  # pragma: no cover
    from aioafero.v1 import AferoBridgeV1

logger = logging.getLogger(__name__)


STATUS_FIELDS: tuple[str, ...] = ("available", "visible", "direct")

SplitStateRefresher = Callable[[AferoDevice, str], list[AferoState]]


def _refresh_security_sensor_states(
    parent: AferoDevice, instance: str
) -> list[AferoState]:
    return security_sensor_valid_states(parent.states, int(instance))


SPLIT_STATE_REFRESHERS: dict[str, SplitStateRefresher] = {
    LIGHT_SPLIT: light_valid_states,
    SENSOR_SPLIT_IDENTIFIER: _refresh_security_sensor_states,
    EXHAUST_FAN_SPLIT: exhaust_fan_valid_states,
    PORTABLE_AC_SPLIT: lambda parent, _instance: portable_ac_valid_states(parent),
}


def refresh_split_clone_states(parent: AferoDevice, clone: AferoDevice) -> None:
    """Copy filtered parent states onto a split clone before emitting events."""
    instance = split_instance_from_device(clone)
    if instance is None or not clone.split_identifier:
        return
    refresher = SPLIT_STATE_REFRESHERS.get(clone.split_identifier)
    if refresher is None:
        return
    clone.states = refresher(parent, instance)


def split_instance_from_device(device: AferoDevice) -> str | None:
    """Return the split-zone instance key encoded in a clone metadevice id."""
    if not device.split_identifier:
        return None
    marker = f"-{device.split_identifier}-"
    if marker not in device.id:
        return None
    return device.id.rsplit(marker, 1)[1]


def translate_attr_change(
    device: AferoDevice,
    attribute: Mapping[str, Any],
) -> AferoState | None:
    """Map one Conclave ``attribute`` block to an :class:`~aioafero.device.AferoState`."""
    attr_id = attribute.get("id")
    attr_value = attribute.get("value")
    attr_data = attribute.get("data")
    binding = resolve_binding(
        build_attribute_index(device),
        attr_id,
        attr_value,
        attr_data,
    )
    if binding is None:
        return None
    return AferoState(
        functionClass=binding.function_class,
        functionInstance=binding.function_instance,
        value=coerce_rest_state_value(binding, attr_value, attr_data),
        lastUpdateTime=normalize_afero_last_update_time_ms(
            attribute.get("updatedTimestamp")
        ),
    )


def translate_status_change(status: Mapping[str, Any]) -> list[AferoState]:
    """Map a Conclave ``status`` block to :class:`~aioafero.device.AferoState` rows."""
    timestamp = normalize_afero_last_update_time_ms(status.get("updatedTimestamp"))
    return [
        AferoState(
            functionClass=field,
            functionInstance=None,
            value=status[field],
            lastUpdateTime=timestamp,
        )
        for field in STATUS_FIELDS
        if field in status
    ]


def _private_data_block(payload: dict, block_key: str) -> tuple[str, dict] | None:
    """Return ``(device_id, block)`` when ``payload`` carries a usable private body."""
    device_id = payload.get("id")
    block = payload.get(block_key)
    if not device_id or not isinstance(block, dict):
        return None
    return str(device_id), block


def _unique_devices(devices: list[AferoDevice]) -> list[AferoDevice]:
    """Drop duplicate metadevices while preserving first-seen order."""
    seen: set[str] = set()
    unique: list[AferoDevice] = []
    for device in devices:
        if device.id in seen:
            continue
        seen.add(device.id)
        unique.append(device)
    return unique


async def _apply_to_conclave_devices(
    bridge: AferoBridgeV1,
    device_id: str,
    handler: Callable[[AferoDevice], Awaitable[bool]],
) -> bool:
    """Run ``handler(device)`` for each cached metadevice with this ``deviceId``."""
    applied = False
    for afero_device in bridge.find_afero_devices_by_conclave_id(device_id):
        if await handler(afero_device):
            applied = True
    if not applied:
        logger.debug("Ignoring Conclave push for unknown device %s", device_id)
    return applied


async def _patch_device_and_emit(
    bridge: AferoBridgeV1,
    device: AferoDevice,
    new_states: list[AferoState],
) -> None:
    """Merge ``new_states`` into ``device`` and fan out through split clones."""
    device.states = merge_afero_states(device.states, new_states)
    await _dispatch_conclave_device_update(bridge, device)


async def apply_attr_change(bridge: AferoBridgeV1, payload: dict) -> bool:
    """Apply a ``private`` / ``attr_change`` event to the cached device."""
    parsed = _private_data_block(payload, "attribute")
    if parsed is None:
        return False
    device_id, attribute = parsed

    async def _apply(device: AferoDevice) -> bool:
        new_state = translate_attr_change(device, attribute)
        if new_state is None:
            logger.debug(
                "Ignoring Conclave attr_change for unknown attribute id=%s on %s",
                attribute.get("id"),
                device.id,
            )
            return False
        logger.debug(
            "Conclave attr_change applied on %s: %s/%s=%r",
            device.id,
            new_state.functionClass,
            new_state.functionInstance,
            new_state.value,
        )
        await _patch_device_and_emit(bridge, device, [new_state])
        return True

    return await _apply_to_conclave_devices(bridge, device_id, _apply)


async def apply_status_change(bridge: AferoBridgeV1, payload: dict) -> bool:
    """Apply a ``private`` / ``status_change`` event to the cached device."""
    parsed = _private_data_block(payload, "status")
    if parsed is None:
        return False
    device_id, status = parsed
    new_states = translate_status_change(status)
    if not new_states:
        return False

    async def _apply(device: AferoDevice) -> bool:
        await _patch_device_and_emit(bridge, device, new_states)
        return True

    return await _apply_to_conclave_devices(bridge, device_id, _apply)


async def _dispatch_conclave_device_update(
    bridge: AferoBridgeV1, parent: AferoDevice
) -> None:
    """Route a patched metadevice through split clones and the event queue."""
    clones = await bridge.events.split_devices([parent])
    for clone in _unique_devices(clones):
        if clone.split_identifier:
            refresh_split_clone_states(parent, clone)
            bridge.add_afero_dev(clone, clone.id)
        await bridge.events.generate_events_from_update(clone)


def _unique_ids(ids: list[str]) -> list[str]:
    """Drop duplicate ids while preserving first-seen order."""
    seen: set[str] = set()
    unique: list[str] = []
    for device_id in ids:
        if device_id in seen:
            continue
        seen.add(device_id)
        unique.append(device_id)
    return unique


def _cached_ids_for_parents(bridge: AferoBridgeV1, parent_ids: set[str]) -> list[str]:
    """Return tracked/cache ids that belong to any parent in ``parent_ids``."""
    if not parent_ids:
        return []
    known_ids = set(bridge.tracked_devices) | bridge.known_afero_device_ids
    matched: list[str] = []
    for known_id in known_ids:
        if known_id in parent_ids:
            matched.append(known_id)
            continue
        if bridge.resolve_metadevice_id(known_id) in parent_ids:
            matched.append(known_id)
    for parent_id in parent_ids:
        if parent_id not in matched:
            matched.append(parent_id)
    return _unique_ids(matched)


def _metadevice_ids_from_values(values: object) -> list[str]:
    """Extract ``metadeviceId`` entries from an invalidate ``values`` list."""
    if not isinstance(values, list):
        return []
    ids: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        metadevice_id = value.get("metadeviceId")
        if metadevice_id:
            ids.append(str(metadevice_id))
    return ids


def _device_ids_from_values(values: object) -> list[str]:
    """Extract physical ``deviceId`` entries from an invalidate ``values`` list."""
    if not isinstance(values, list):
        return []
    ids: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        device_id = value.get("deviceId")
        if device_id:
            ids.append(str(device_id))
    return ids


async def _emit_resource_deleted(bridge: AferoBridgeV1, device_ids: list[str]) -> bool:
    """Queue ``RESOURCE_DELETED`` and drop cache entries for ``device_ids``."""
    emitted = False
    for device_id in _unique_ids(device_ids):
        logger.debug("Conclave invalidate remove → RESOURCE_DELETED %s", device_id)
        bridge.events.add_job(
            AferoEvent(type=EventType.RESOURCE_DELETED, device_id=device_id)
        )
        bridge.remove_device(device_id)
        emitted = True
    return emitted


async def apply_invalidate_remove(bridge: AferoBridgeV1, payload: dict) -> bool:
    """Apply a ``public`` / ``invalidate`` ``kind=remove`` inventory event."""
    target = payload.get("target")
    values = payload.get("values")
    if target == "metadevices":
        parent_ids = set(_metadevice_ids_from_values(values))
        return await _emit_resource_deleted(
            bridge, _cached_ids_for_parents(bridge, parent_ids)
        )
    if target == "devices":
        parent_ids: set[str] = set()
        for physical_id in _device_ids_from_values(values):
            for device in bridge.find_afero_devices_by_conclave_id(physical_id):
                parent_ids.add(bridge.resolve_metadevice_id(device.id))
                parent_ids.add(device.id)
        if not parent_ids:
            logger.debug(
                "Ignoring Conclave invalidate remove for unknown device target"
            )
            return False
        return await _emit_resource_deleted(
            bridge, _cached_ids_for_parents(bridge, parent_ids)
        )
    logger.debug("Ignoring Conclave invalidate remove target=%r", target)
    return False


async def apply_invalidate_add(bridge: AferoBridgeV1, payload: dict) -> bool:
    """Apply a ``public`` / ``invalidate`` ``kind=add`` inventory event.

    ``target=metadevices`` fetches the new metadevice over REST (Conclave only
    sends the id) and fans out ``RESOURCE_ADDED`` / ``RESOURCE_UPDATED`` like a
    discovery poll for that payload alone.

    ``target=devices`` is ignored when the physical device is already cached —
    the matching ``metadevices`` add carries the semantics we need. When the
    physical id is unknown, a full discovery poll reconciles inventory.
    """
    target = payload.get("target")
    values = payload.get("values")
    if target == "metadevices":
        applied = False
        for metadevice_id in _metadevice_ids_from_values(values):
            try:
                raw = await bridge.fetch_metadevice(metadevice_id)
            except (ClientResponseError, TimeoutError, OSError, AferoError) as err:
                logger.warning(
                    "Conclave invalidate add failed fetching metadevice %s: %s",
                    metadevice_id,
                    err,
                )
                continue
            if raw is None:
                logger.debug(
                    "Conclave invalidate add skipped empty metadevice %s",
                    metadevice_id,
                )
                continue
            devices = await bridge.events.generate_events_from_added_data([raw])
            if devices:
                applied = True
                logger.debug(
                    "Conclave invalidate add imported %d device(s) from %s",
                    len(devices),
                    metadevice_id,
                )
        return applied
    if target == "devices":
        unknown = [
            physical_id
            for physical_id in _device_ids_from_values(values)
            if not bridge.find_afero_devices_by_conclave_id(physical_id)
        ]
        if not unknown:
            logger.debug(
                "Conclave invalidate add devices already cached; waiting on "
                "metadevice semantics"
            )
            return False
        logger.info(
            "Conclave invalidate add for unknown device(s) %s; running discovery",
            unknown,
        )
        await bridge.events.perform_discovery_poll()
        return True
    logger.debug("Ignoring Conclave invalidate add target=%r", target)
    return False


async def apply_public_invalidate(bridge: AferoBridgeV1, payload: dict) -> bool:
    """Dispatch a ``public`` / ``invalidate`` inventory frame by ``kind``."""
    kind = payload.get("kind")
    handler = INVALIDATE_KIND_HANDLERS.get(kind) if isinstance(kind, str) else None
    if handler is None:
        logger.debug("Ignoring Conclave invalidate kind=%r", kind)
        return False
    return await handler(bridge, payload)


PRIVATE_EVENT_HANDLERS: dict[str, PrivateEventHandler] = {
    "attr_change": apply_attr_change,
    "status_change": apply_status_change,
}

INVALIDATE_KIND_HANDLERS: dict[str, PublicEventHandler] = {
    "add": apply_invalidate_add,
    "remove": apply_invalidate_remove,
}

PUBLIC_EVENT_HANDLERS: dict[str, PublicEventHandler] = {
    PUBLIC_INVALIDATE_EVENT: apply_public_invalidate,
}
