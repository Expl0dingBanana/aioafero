"""Debug trace hooks for ``scripts/conclave_watch.py``."""

from __future__ import annotations

from types import MethodType
from typing import Any

from aioafero.types import EventType
from aioafero.v1 import AferoBridgeV1


def install_trace_hooks(bridge: AferoBridgeV1, *, device_label: callable) -> None:
    """Wrap controller emit paths so we can see where updates stop."""
    for controller in bridge.controllers:
        controller_name = type(controller).__name__
        original_emit = controller.emit_to_subscribers

        async def traced_emit(
            evt_type: EventType,
            item_id: str,
            item: Any,
            *,
            _orig=original_emit,
            _name=controller_name,
        ) -> None:
            name, type_label = device_label(item)
            print(
                f"TRACE controller→subscriber: {_name} {evt_type.name} "
                f"{name} ({type_label}) id={item_id}",
                flush=True,
            )
            await _orig(evt_type, item_id, item)

        controller.emit_to_subscribers = traced_emit  # type: ignore[method-assign]

        original_handle = controller._handle_event

        async def traced_handle(
            evt_type: EventType,
            evt_data: Any,
            *,
            _orig=original_handle,
            _name=controller_name,
        ) -> None:
            item_id = None if evt_data is None else evt_data.get("device_id")
            await _orig(evt_type, evt_data)
            if evt_type in (
                EventType.RESOURCE_UPDATED,
                EventType.RESOURCE_UPDATE_RESPONSE,
            ):
                print(
                    f"TRACE event handled: {_name} {evt_type.name} device_id={item_id}",
                    flush=True,
                )

        controller._handle_event = traced_handle  # type: ignore[method-assign]

        original_handle_type = controller._handle_event_type

        async def traced_handle_type(
            self,
            evt_type: EventType,
            item_id: str,
            evt_data: Any,
            *,
            _orig=original_handle_type,
            _name=controller_name,
        ) -> Any:
            result = await _orig(evt_type, item_id, evt_data)
            if evt_type in (
                EventType.RESOURCE_UPDATED,
                EventType.RESOURCE_UPDATE_RESPONSE,
            ) and result is None:
                print(
                    f"TRACE dropped: {_name} {evt_type.name} id={item_id} "
                    "(device not found or no model diff)",
                    flush=True,
                )
            return result

        controller._handle_event_type = MethodType(traced_handle_type, controller)
