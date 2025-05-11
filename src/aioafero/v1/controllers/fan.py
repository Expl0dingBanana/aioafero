"""Controller holding and managing Afero IoT resources of type `fan`."""

from ... import device
from ...device import AferoDevice
from ...util import ordered_list_item_to_percentage
from ..models import features
from ..models.fan import Fan, FanPut
from ..models.resource import DeviceInformation, ResourceTypes
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController

KNOWN_PRESETS = {"comfort-breeze"}


class FanController(BaseResourcesController[Fan]):
    """Controller holding and managing Afero IoT resources of type `fan`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.FAN]
    ITEM_CLS = Fan
    ITEM_MAPPING = {
        "on": "power",
        "speed": "fan-speed",
        "direction": "fan-reverse",
    }
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {}
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {}

    async def turn_on(self, device_id: str) -> None:
        """Turn on the fan."""
        await self.set_state(device_id, on=True)

    async def turn_off(self, device_id: str) -> None:
        """Turn off the fan."""
        await self.set_state(device_id, on=False)

    async def set_speed(self, device_id: str, speed: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self.set_state(device_id, on=True, speed=speed)

    async def set_direction(self, device_id: str, forward: bool) -> None:
        """Set the direction of the fan to forward."""
        cur_item = self.get_device(device_id)
        if not cur_item.is_on:
            # Thanks Hubspace for this one! Additionally, turning it on and setting
            # direction at the same time does not work as expected
            self._logger.info("Fan is not running so direction will not be set")
        await self.set_state(device_id, forward=forward)

    async def set_preset(self, device_id: str, preset: bool) -> None:
        """Set the preset of the fan."""
        await self.set_state(device_id, on=True, preset=preset)

    async def initialize_elem(self, afero_device: AferoDevice) -> Fan:
        """Initialize the element"""
        available: bool = False
        on: features.OnFeature | None = None
        speed: features.SpeedFeature | None = None
        direction: features.DirectionFeature | None = None
        preset: features.PresetFeature | None = None
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        for state in afero_device.states:
            if state.functionClass == "power":
                on = features.OnFeature(on=state.value == "on")
            elif state.functionClass == "fan-speed":
                speeds = device.get_function_from_device(
                    afero_device.functions, state.functionClass, state.functionInstance
                )
                tmp_speed = set()
                for value in speeds["values"]:
                    if not value["name"].endswith("-000"):
                        tmp_speed.add(value["name"])
                speeds = list(sorted(tmp_speed))
                percentage = ordered_list_item_to_percentage(speeds, state.value)
                speed = features.SpeedFeature(speed=percentage, speeds=speeds)
            elif state.functionClass == "fan-reverse":
                direction = features.DirectionFeature(forward=state.value == "forward")
            elif (
                state.functionClass == "toggle"
                and state.functionInstance in KNOWN_PRESETS
            ):
                # I have only seen fans with a single preset
                preset = features.PresetFeature(
                    enabled=state.value == "enabled",
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

        self._items[afero_device.id] = Fan(
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
            speed=speed,
            direction=direction,
            preset=preset,
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        updated_keys = set()
        cur_item = self.get_device(afero_device.id)
        for state in afero_device.states:
            if state.functionClass == "power":
                new_val = state.value == "on"
                if cur_item.on.on != new_val:
                    cur_item.on.on = new_val
                    updated_keys.add("on")
            elif state.functionClass == "fan-speed":
                new_val = ordered_list_item_to_percentage(
                    cur_item.speed.speeds, state.value
                )
                if cur_item.speed.speed != new_val:
                    cur_item.speed.speed = new_val
                    updated_keys.add("speed")
            elif state.functionClass == "fan-reverse":
                new_val = state.value == "forward"
                if cur_item.direction.forward != new_val:
                    cur_item.direction.forward = new_val
                    updated_keys.add("direction")
            elif (
                state.functionClass == "toggle"
                and state.functionInstance in KNOWN_PRESETS
            ):
                new_val = state.value == "enabled"
                if cur_item.preset.enabled != new_val:
                    cur_item.preset.enabled = new_val
                    updated_keys.add("preset")
            elif state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add("available")
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)

        return updated_keys

    async def set_state(
        self,
        device_id: str,
        on: bool | None = None,
        speed: int | None = None,
        forward: bool | None = None,
        preset: bool | None = None,
    ) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = FanPut()
        cur_item = self.get_device(device_id)
        if on is not None:
            update_obj.on = features.OnFeature(on=on)
        if speed is not None and cur_item.speed is not None:
            if speed == 0:
                update_obj.on = features.OnFeature(on=False)
            else:
                update_obj.speed = features.SpeedFeature(
                    speed=speed, speeds=cur_item.speed.speeds
                )
        if preset is not None and cur_item.preset is not None:
            update_obj.preset = features.PresetFeature(
                enabled=preset,
                func_class=cur_item.preset.func_class,
                func_instance=cur_item.preset.func_instance,
            )
        if forward is not None and cur_item.direction is not None:
            update_obj.direction = features.DirectionFeature(forward=forward)
        await self.update(device_id, obj_in=update_obj)
