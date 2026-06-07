"""Apply Conclave ``private`` events to the cached bridge state."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import TYPE_CHECKING, Any

from aioafero.device import AferoDevice, AferoState, merge_afero_states
from aioafero.util import normalize_afero_last_update_time_ms
from aioafero.v1.controllers.light import get_valid_states

from .protocol import PrivateEventHandler
from .semantics import build_attribute_index, coerce_rest_state_value, resolve_binding

if TYPE_CHECKING:  # pragma: no cover
    from aioafero.v1 import AferoBridgeV1

logger = logging.getLogger(__name__)


STATUS_FIELDS: tuple[str, ...] = ("available", "visible", "direct")


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
        instance = split_instance_from_device(clone)
        if instance is not None:
            clone.states = get_valid_states(parent, instance)
            bridge.add_afero_dev(clone, clone.id)
        await bridge.events.generate_events_from_update(clone)


PRIVATE_EVENT_HANDLERS: dict[str, PrivateEventHandler] = {
    "attr_change": apply_attr_change,
    "status_change": apply_status_change,
}
