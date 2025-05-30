"""Controller holding and managing Afero IoT resources of type `switch`."""

from ... import errors
from ...device import AferoDevice
from ..models import features
from ..models.resource import DeviceInformation, ResourceTypes
from ..models.switch import Switch, SwitchPut
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController


class SwitchController(BaseResourcesController[Switch]):
    """Controller holding and managing Afero IoT resources of type `switch`.

    A switch can have one or more toggleable elements. They are controlled
    by their functionInstance.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [
        ResourceTypes.SWITCH,
        ResourceTypes.POWER_OUTLET,
        ResourceTypes.LANDSCAPE_TRANSFORMER,
        # Exhaust-Fans have On / Off toggles
        ResourceTypes.EXHAUST_FAN,
        # Portable ACs have On / Off toggle
        ResourceTypes.PORTABLE_AC,
    ]
    ITEM_CLS = Switch
    ITEM_MAPPING = {}
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {"watts": "W", "output-voltage-switch": "V"}
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {}

    async def turn_on(self, device_id: str, instance: str | None = None) -> None:
        """Turn on the switch."""
        await self.set_state(device_id, on=True, instance=instance)

    async def turn_off(self, device_id: str, instance: str | None = None) -> None:
        """Turn off the switch."""
        await self.set_state(device_id, on=False, instance=instance)

    async def initialize_elem(self, afero_device: AferoDevice) -> Switch:
        """Initialize the element"""
        available: bool = False
        on: dict[str, features.OnFeature] = {}
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        toggle_states = ["power", "toggle"]
        if afero_device.device_class == ResourceTypes.EXHAUST_FAN.value:
            toggle_states.remove("power")
        for state in afero_device.states:
            if state.functionClass in toggle_states:
                on[state.functionInstance] = features.OnFeature(
                    on=state.value == "on",
                    func_class=state.functionClass,
                    func_instance=state.functionInstance,
                )
            elif state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.device_id):
                if isinstance(sensor, AferoBinarySensor):
                    binary_sensors[sensor.id] = sensor
                else:
                    sensors[sensor.id] = sensor

        self._items[afero_device.id] = Switch(
            afero_device.functions,
            id=afero_device.id,
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
            ),
            on=on,
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        toggle_states = ["power", "toggle"]
        if afero_device.device_class == ResourceTypes.EXHAUST_FAN.value:
            toggle_states.remove("power")
        for state in afero_device.states:
            if state.functionClass in toggle_states:
                new_val = state.value == "on"
                if cur_item.on[state.functionInstance].on != new_val:
                    updated_keys.add("on")
                cur_item.on[state.functionInstance].on = state.value == "on"
            elif state.functionClass == "available":
                if cur_item.available != state.value:
                    updated_keys.add("available")
                cur_item.available = state.value
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)

        return updated_keys

    async def set_state(
        self,
        device_id: str,
        on: bool | None = None,
        instance: str | None = None,
    ) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = SwitchPut()
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if on is not None:
            try:
                update_obj.on = features.OnFeature(
                    on=on,
                    func_class=cur_item.on[instance].func_class,
                    func_instance=instance,
                )
            except KeyError:
                self._logger.info("Unable to find instance %s", instance)
        await self.update(device_id, obj_in=update_obj)
