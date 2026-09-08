"""Controller holding and managing Afero IoT resources of type `dehumidifier`."""

from dataclasses import replace

from aioafero.device import AferoDevice, AferoState, get_function_from_device
from aioafero.errors import DeviceNotFound
from aioafero.util import process_function
from aioafero.v1.models import features
from aioafero.v1.models.dehumidifier import Dehumidifier, DehumidifierPut
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import BaseResourcesController


def generate_target_humidity(
    functions: list[dict], state: AferoState
) -> features.NumbersFeature:
    """Build the target humidity number from the function definition."""
    func_def = get_function_from_device(
        functions, state.functionClass, state.functionInstance
    )
    humidity_range = func_def["values"][0]["range"]
    return features.NumbersFeature(
        value=state.value,
        min=humidity_range["min"],
        max=humidity_range["max"],
        step=humidity_range["step"],
        name="Target Humidity",
        unit="%",
        function_class=state.functionClass,
        function_instance=state.functionInstance,
    )


class DehumidifierController(BaseResourcesController[Dehumidifier]):
    """Dehumidifiers on ``bridge.dehumidifiers``.

    Error states (water tray full, filter, sensor failures) are reported by
    ``bridge.devices`` like every other parent device.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.DEHUMIDIFIER]
    ITEM_CLS = Dehumidifier
    # Elements that map to Select. func class / func instance to name
    ITEM_SELECTS = {
        ("fan-speed", "dehumidifier-fan-speed"): "Fan Speed",
        ("pump", None): "Pump",
    }

    async def turn_on(self, device_id: str) -> None:
        """Turn on the dehumidifier.

        Args:
            device_id: Device ID from this controller.

        """
        await self.set_state(device_id, on=True)

    async def turn_off(self, device_id: str) -> None:
        """Turn off the dehumidifier.

        Args:
            device_id: Device ID from this controller.

        """
        await self.set_state(device_id, on=False)

    async def initialize_elem(self, afero_device: AferoDevice) -> Dehumidifier:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        available: bool = False
        on: features.OnFeature | None = None
        mode: features.ModeFeature | None = None
        current_humidity: int | None = None
        target_humidity: features.NumbersFeature | None = None
        selects: dict[tuple[str, str | None], features.SelectFeature] = {}
        for state in afero_device.states:
            if state.functionClass == "power":
                on = features.OnFeature(
                    on=state.value == "on",
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif state.functionClass == "mode":
                mode = features.ModeFeature(
                    mode=state.value,
                    modes=set(
                        process_function(
                            afero_device.functions,
                            state.functionClass,
                            state.functionInstance,
                        )
                    ),
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif state.functionClass == "humidity":
                if state.functionInstance == "current":
                    current_humidity = state.value
                elif state.functionInstance == "target":
                    target_humidity = generate_target_humidity(
                        afero_device.functions, state
                    )
            elif state.functionClass == "available":
                available = state.value
            elif select := await self.initialize_select(afero_device.functions, state):
                selects[select[0]] = select[1]

        self._items[afero_device.id] = Dehumidifier(
            _id=afero_device.id,
            available=available,
            on=on,
            mode=mode,
            current_humidity=current_humidity,
            target_humidity=target_humidity,
            selects=selects,
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
        """Update the Dehumidifier with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        for state in afero_device.states:
            if state.functionClass == "power":
                new_val = state.value == "on"
                if cur_item.on.on != new_val:
                    cur_item.on.on = new_val
                    updated_keys.add("on")
            elif state.functionClass == "mode":
                if cur_item.mode.mode != state.value:
                    cur_item.mode.mode = state.value
                    updated_keys.add("mode")
            elif state.functionClass == "humidity":
                if state.functionInstance == "current":
                    if cur_item.current_humidity != state.value:
                        cur_item.current_humidity = state.value
                        updated_keys.add("humidity-current")
                elif (
                    state.functionInstance == "target"
                    and cur_item.target_humidity.value != state.value
                ):
                    cur_item.target_humidity.value = state.value
                    updated_keys.add("humidity-target")
            elif state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add("available")
            elif update_key := await self.update_select(state, cur_item):
                updated_keys.add(update_key)
        return updated_keys

    async def set_state(
        self,
        device_id: str,
        *,
        on: bool | None = None,
        mode: str | None = None,
        target_humidity: int | None = None,
        selects: dict[tuple[str, str | None], str] | None = None,
    ) -> None:
        """Update dehumidifier state in the cloud.

        Args:
            device_id: Device ID from this controller.
            on: Power state.
            mode: Mode name from ``mode.modes`` (``set``, ``continuous``, ...).
            target_humidity: Target relative humidity in percent.
            selects: Select features keyed by ``(functionClass, functionInstance)``.

        """
        update_obj = DehumidifierPut()
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if on is not None:
            update_obj.on = replace(cur_item.on, on=on)
        if mode is not None:
            if mode in cur_item.mode.modes:
                update_obj.mode = replace(cur_item.mode, mode=mode)
            else:
                self._logger.debug(
                    "Unknown mode %s. Available modes: %s",
                    mode,
                    ", ".join(sorted(cur_item.mode.modes)),
                )
        if target_humidity is not None:
            update_obj.target_humidity = replace(
                cur_item.target_humidity, value=target_humidity
            )
        for key, val in (selects or {}).items():
            if key not in cur_item.selects:
                continue
            update_obj.selects[key] = replace(cur_item.selects[key], selected=val)
        await self.update(device_id, obj_in=update_obj)
