"""Controller holding and managing Afero IoT resources of type `blinds-zone`."""

from dataclasses import replace
from typing import Any, Literal

from aioafero import errors
from aioafero.device import AferoDevice
from aioafero.v1.models import features
from aioafero.v1.models.blinds import Blinds, BlindsGateway, BlindsPut
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import AferoBinarySensor, AferoSensor, BaseResourcesController
from .event import AferoEvent, EventType

GATEWAY_DEVICE_CLASS: str = "blinds-gateway"
# Values the API reports back after a one-shot command. They are never sent.
RESULT_VALUES = frozenset({"success", "failure"})


def get_commands(functions: list[dict[str, Any]] | None) -> dict[str, set[str]]:
    """Map each one-shot (category) function to the values it accepts.

    Based on the approach from aioafero PR #114 by @jstark-ttl.
    """
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


def _position_range(afero_device: AferoDevice, instance: str | None) -> dict:
    """Find the min / max / step the device advertises for its position."""
    for function in afero_device.functions:
        if (
            function.get("functionClass") == "blinds-open"
            and function.get("functionInstance") == instance
        ):
            for value in function.get("values", []):
                if position_range := value.get("range"):
                    return {
                        key: int(position_range[key])
                        for key in ("min", "max", "step")
                        if key in position_range
                    }
    return {}


def _is_available(afero_device: AferoDevice) -> bool:
    """Return the ``available`` state of a device, defaulting to unavailable."""
    return any(
        state.functionClass == "available" and state.value
        for state in afero_device.states
    )


class BlindsController(BaseResourcesController[Blinds]):
    """Blinds zones on ``bridge.blinds``.

    Position is a percentage where 100 is fully open and 0 is closed.

    Each zone is its own Afero device that shares a parent id with the Smart
    Blinds Gateway. A zone is only ``available`` when it reports itself
    available **and** its gateway does, so a gateway that is offline takes all
    of its zones down with it.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.BLINDS_ZONE]
    ITEM_CLS = Blinds

    def __init__(self, *args, **kwargs):
        """Initialize instance."""
        super().__init__(*args, **kwargs)
        # Availability each zone reports for itself, ignoring the gateway
        self._own_available: dict[str, bool] = {}

    async def initialize(self) -> None:
        """Initialize the controller and follow the gateway's availability."""
        if self._initialized:
            return
        await super().initialize()
        self._bridge.events.subscribe(
            self._handle_gateway_event,
            resource_filter=(GATEWAY_DEVICE_CLASS,),
        )

    def _gateway_available(self, parent_id: str | None) -> bool:
        """Determine if the gateway for a zone is available.

        A zone with no known gateway is not penalized, as there is nothing to
        indicate that it is down.
        """
        for device_id in self._bridge.known_afero_device_ids:
            gateway = self._bridge.get_afero_device(device_id)
            if (
                gateway.device_class == GATEWAY_DEVICE_CLASS
                and gateway.device_id == parent_id
            ):
                return _is_available(gateway)
        return True

    async def _handle_gateway_event(
        self, evt_type: EventType, evt_data: AferoEvent | None
    ) -> None:
        """Propagate a gateway availability change to its zones."""
        if evt_data is None or evt_type == EventType.RESOURCE_DELETED:
            return
        gateway: AferoDevice | None = evt_data.get("device")
        if gateway is None:
            return
        gateway_available = _is_available(gateway)
        for item in list(self._items.values()):
            if item.device_information.parent_id != gateway.device_id:
                continue
            available = self._own_available.get(item.id, False) and gateway_available
            if item.available == available:
                continue
            item.available = available
            await self.emit_to_subscribers(EventType.RESOURCE_UPDATED, item.id, item)

    async def open(self, device_id: str) -> None:
        """Fully open the blinds.

        Args:
            device_id: Device ID from this controller.

        """
        await self.set_state(device_id, position=100)

    async def close(self, device_id: str) -> None:
        """Fully close the blinds.

        Args:
            device_id: Device ID from this controller.

        """
        await self.set_state(device_id, position=0)

    async def set_position(self, device_id: str, position: int) -> None:
        """Move the blinds to a position.

        Args:
            device_id: Device ID from this controller.
            position: Target position, 0 (closed) to 100 (open). It is moved to
                the nearest step the device supports (25 for Hubspace blinds).

        """
        await self.set_state(device_id, position=position)

    async def stop(self, device_id: str) -> None:
        """Stop the blinds if they are moving.

        Args:
            device_id: Device ID from this controller.

        """
        await self._send_command(device_id, "stop-moving", "stop")

    async def move(
        self,
        device_id: str,
        direction: Literal["up", "down"],
        *,
        fine: bool = False,
    ) -> None:
        """Jog the blinds up or down.

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
        """Put the blinds into limit-setting mode for the top or bottom limit."""
        await self._send_command(device_id, "start-limit-mode", limit)

    async def confirm_limit(self, device_id: str) -> None:
        """Save the blinds' current spot as the limit being set."""
        await self._send_command(device_id, "confirm-limit", "confirm")

    async def clear_limits(self, device_id: str) -> None:
        """Clear both limits."""
        await self._send_command(device_id, "clear-all-limits", "clear")

    async def toggle_motor_direction(self, device_id: str) -> None:
        """Swap which way the motor turns for up and down."""
        await self._send_command(device_id, "toggle-motor-reverse", "toggle")

    async def _send_command(
        self, device_id: str, function_class: str, value: str
    ) -> None:
        """Send a one-shot command the blinds list in their functions."""
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

    async def initialize_elem(self, afero_device: AferoDevice) -> Blinds:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        self._logger.info("Initializing %s", afero_device.id)
        available: bool = False
        position: features.PositionFeature | None = None
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        for state in afero_device.states:
            if state.functionClass == "blinds-open":
                position = features.PositionFeature(
                    position=state.value,
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                    **_position_range(afero_device, state.functionInstance),
                )
            elif state.functionClass == "available":
                available = state.value

        self._own_available[afero_device.id] = bool(available)
        available = bool(available) and self._gateway_available(afero_device.device_id)
        self._items[afero_device.id] = Blinds(
            _id=afero_device.id,
            available=available,
            sensors=sensors,
            binary_sensors=binary_sensors,
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
            position=position,
            commands=get_commands(afero_device.functions),
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        """Update the Blinds with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        for state in afero_device.states:
            if state.functionClass == "blinds-open" and cur_item.position:
                if cur_item.position.position != state.value:
                    updated_keys.add("position")
                cur_item.position.position = state.value
            elif state.functionClass == "available":
                self._own_available[afero_device.id] = bool(state.value)

        available = self._own_available.get(
            afero_device.id, cur_item.available
        ) and self._gateway_available(afero_device.device_id)
        if cur_item.available != available:
            updated_keys.add("available")
            cur_item.available = available

        return updated_keys

    async def set_state(
        self,
        device_id: str,
        *,
        position: int | None = None,
    ) -> None:
        """Update blinds state in the cloud.

        Args:
            device_id: Device ID from this controller.
            position: Target position, 0 (closed) to 100 (open). It is moved to
                the nearest step the device supports and clamped to its range.

        """
        update_obj = BlindsPut()
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if position is not None and cur_item.position is not None:
            update_obj.position = replace(
                cur_item.position, position=cur_item.position.snap(position)
            )
        # Resend matching targets: a jog or the remote can leave the cached
        # position behind the real one, and the user still expects a move.
        # Approach from aioafero PR #114 by @jstark-ttl.
        await self.update(device_id, obj_in=update_obj, send_duplicate_states=True)


class BlindsGatewayController(BaseResourcesController[BlindsGateway]):
    """Smart Blinds Gateways on ``bridge.blinds_gateways`` (read-only).

    Only status is tracked, for troubleshooting. Wi-Fi signal strength is already
    reported by ``bridge.devices``, so only the gateway-specific Wi-Fi states are
    tracked here.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.BLINDS_GATEWAY]
    ITEM_CLS = BlindsGateway
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str | None] = {
        "wifi-steady-state": None,
        "wifi-setup-state": None,
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> BlindsGateway:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        self._logger.info("Initializing %s", afero_device.id)
        available: bool = False
        sensors: dict[str, AferoSensor] = {}
        for state in afero_device.states:
            if state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.id):
                sensors[sensor.id] = sensor

        self._items[afero_device.id] = BlindsGateway(
            _id=afero_device.id,
            available=available,
            sensors=sensors,
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
        """Update the BlindsGateway with the latest API data.

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
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)

        return updated_keys
