"""Controller holding and managing Afero IoT resources of type `blinds-zone`."""

from dataclasses import replace
from typing import Any, Literal

from aioafero import errors
from aioafero.device import AferoDevice, AferoState
from aioafero.v1.models import features
from aioafero.v1.models.blinds import Blind, BlindPut
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import BaseResourcesController

POSITION_FUNCTION = "blinds-open"
# Values the API reports back after a one-shot command. They are never sent.
RESULT_VALUES = frozenset({"success", "failure"})


class BlindsController(BaseResourcesController[Blind]):
    """Roller shades on ``bridge.blinds``.

    Each shade is a ``blinds-zone`` metadevice behind a blinds gateway; the
    gateway itself is a parent device on ``bridge.devices``. Position runs from
    ``0`` (closed) to ``100`` (open). Shades move in fixed steps (25 on Home
    Decorators Collection shades), so requested positions snap to the nearest
    step.

    Setting a limit: call :meth:`start_limit_setting`, move the shade with
    :meth:`move`, then save it with :meth:`confirm_limit`.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.BLINDS_ZONE]
    ITEM_CLS = Blind

    async def initialize_elem(self, afero_device: AferoDevice) -> Blind:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        available: bool = False
        position: features.PositionFeature | None = None
        for state in afero_device.states:
            if state.functionClass == "available":
                available = state.value
            elif state.functionClass == POSITION_FUNCTION:
                position = get_position_feature(afero_device.functions, state)

        self._items[afero_device.id] = Blind(
            _id=afero_device.id,
            available=available,
            position=position,
            commands=get_commands(afero_device.functions),
            device_information=DeviceInformation(
                device_class=afero_device.device_class,
                default_image=afero_device.default_image,
                default_name=afero_device.default_name,
                manufacturer=afero_device.manufacturerName,
                model=afero_device.model,
                name=afero_device.friendly_name,
                parent_id=afero_device.device_id,
                children=afero_device.children,
                functions=afero_device.functions,
            ),
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        """Update the Blind with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        for state in afero_device.states:
            if state.functionClass == "available":
                if cur_item.available != state.value:
                    updated_keys.add("available")
                cur_item.available = state.value
            elif state.functionClass == POSITION_FUNCTION:
                new_position = get_position_feature(
                    cur_item.device_information.functions, state
                )
                if new_position is None:
                    continue
                if (
                    cur_item.position is None
                    or cur_item.position.position != new_position.position
                ):
                    updated_keys.add("position")
                cur_item.position = new_position
        return updated_keys

    async def set_state(self, device_id: str, *, position: int | None = None) -> None:
        """Move a shade.

        Args:
            device_id: Device ID from this controller.
            position: Target from ``0`` (closed) to ``100`` (open). Snapped to
                the shade's step and clamped to its range.

        """
        update_obj = BlindPut()
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if position is not None:
            if cur_item.position is None:
                self._logger.info("%s does not report a position", device_id)
            else:
                update_obj.position = replace(
                    cur_item.position,
                    position=snap_position(cur_item.position, position),
                )
        # Resend matching targets: a jog or remote can leave the cached position
        # behind the real one, and the user still expects the shade to move.
        await self.update(device_id, obj_in=update_obj, send_duplicate_states=True)

    async def open(self, device_id: str) -> None:
        """Open a shade fully."""
        await self.set_state(device_id, position=100)

    async def close(self, device_id: str) -> None:
        """Close a shade fully."""
        await self.set_state(device_id, position=0)

    async def stop(self, device_id: str) -> None:
        """Stop a moving shade."""
        await self._send_command(device_id, "stop-moving", "stop")

    async def move(
        self,
        device_id: str,
        direction: Literal["up", "down"],
        *,
        fine: bool = False,
    ) -> None:
        """Jog a shade up or down.

        Args:
            device_id: Device ID from this controller.
            direction: ``up`` or ``down``.
            fine: ``True`` for a small step, ``False`` for a large one.

        """
        function_class = "move-fine" if fine else "move-coarse"
        await self._send_command(device_id, function_class, direction)

    async def start_limit_setting(
        self, device_id: str, limit: Literal["top", "bottom"]
    ) -> None:
        """Put a shade into limit-setting mode for its top or bottom limit."""
        await self._send_command(device_id, "start-limit-mode", limit)

    async def confirm_limit(self, device_id: str) -> None:
        """Save the shade's current spot as the limit being set."""
        await self._send_command(device_id, "confirm-limit", "confirm")

    async def clear_limits(self, device_id: str) -> None:
        """Clear both limits on a shade."""
        await self._send_command(device_id, "clear-all-limits", "clear")

    async def toggle_motor_direction(self, device_id: str) -> None:
        """Swap which way the motor turns for up and down."""
        await self._send_command(device_id, "toggle-motor-reverse", "toggle")

    async def _send_command(
        self, device_id: str, function_class: str, value: str
    ) -> None:
        """Send a one-shot command the shade lists in its functions."""
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if value not in cur_item.commands.get(function_class, set()):
            self._logger.warning(
                "%s does not support %s=%s", device_id, function_class, value
            )
            return
        await self.update(
            device_id,
            states=[
                {
                    "functionClass": function_class,
                    "functionInstance": None,
                    "value": value,
                }
            ],
        )


def get_position_feature(
    functions: list[dict[str, Any]] | None, state: AferoState
) -> features.PositionFeature | None:
    """Build the position feature from a ``blinds-open`` state.

    Range and step come from the matching function definition. Returns ``None``
    when the value is not a number.
    """
    try:
        position = int(float(state.value))
    except (TypeError, ValueError):
        return None
    value_range: dict[str, Any] = {}
    for func in functions or []:
        if (
            func.get("functionClass") == state.functionClass
            and func.get("functionInstance") == state.functionInstance
        ):
            value_range = (func.get("values") or [{}])[0].get("range") or {}
            break
    return features.PositionFeature(
        position=position,
        min=int(value_range.get("min") or 0),
        max=int(value_range.get("max") or 100),
        step=int(value_range.get("step") or 1),
        function_class=state.functionClass,
        function_instance=state.functionInstance,
    )


def get_commands(functions: list[dict[str, Any]] | None) -> dict[str, set[str]]:
    """Map each one-shot (category) function to the values it accepts."""
    commands: dict[str, set[str]] = {}
    for func in functions or []:
        if func.get("type") != "category" or not func.get("functionClass"):
            continue
        values = {
            val["name"]
            for val in func.get("values") or []
            if val.get("name") and val["name"] not in RESULT_VALUES
        }
        if values:
            commands[func["functionClass"]] = values
    return commands


def snap_position(feature: features.PositionFeature, position: int) -> int:
    """Clamp ``position`` to the shade's range and round it to the nearest step."""
    clamped = min(max(position, feature.min), feature.max)
    snapped = feature.min + round((clamped - feature.min) / feature.step) * feature.step
    return min(snapped, feature.max)
