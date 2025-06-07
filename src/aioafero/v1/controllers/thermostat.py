"""Controller holding and managing Afero IoT resources of type `thermostat`."""

import copy

from ... import device
from ...device import AferoDevice, AferoState
from ...util import calculate_hubspace_celsius, process_function
from ..models import features
from ..models.resource import DeviceInformation, ResourceTypes
from ..models.thermostat import Thermostat, ThermostatPut
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController


class ThermostatController(BaseResourcesController[Thermostat]):
    """Controller holding and managing Afero IoT resources of type `thermostat`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.THERMOSTAT]
    ITEM_CLS = Thermostat
    ITEM_MAPPING = {
        "fan_mode": "fan-mode",
        "hvac_mode": "mode",
    }
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {}
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "filter-replacement": "replacement-needed",
        "max-temp-exceeded": "alerting",
        "min-temp-exceeded": "alerting",
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> Thermostat:
        """Initialize the element"""
        available: bool = False
        # Afero reports in Celsius by default
        display_celsius: bool = True
        current_temperature: features.CurrentTemperatureFeature | None = None
        fan_running: bool | None = None
        fan_mode: features.ModeFeature | None = None
        hvac_action: str | None = None
        hvac_mode: features.HVACModeFeature | None = None
        safety_max_temp: features.TargetTemperatureFeature | None = None
        safety_min_temp: features.TargetTemperatureFeature | None = None
        target_temperature_auto_heating: features.TargetTemperatureFeature | None = None
        target_temperature_auto_cooling: features.TargetTemperatureFeature | None = None
        target_temperature_heating: features.TargetTemperatureFeature | None = None
        target_temperature_cooling: features.TargetTemperatureFeature | None = None
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        all_modes: set[str] | None = None
        current_mode: str | None = None
        system_type: str | None = None
        for state in afero_device.states:
            func_def = device.get_function_from_device(
                afero_device.functions, state.functionClass, state.functionInstance
            )
            if state.functionClass == "fan-mode":
                fan_mode = features.ModeFeature(
                    mode=state.value,
                    modes=set(process_function(afero_device.functions, "fan-mode")),
                )
            if state.functionClass == "current-fan-state":
                fan_running = state.value == "on"
            elif state.functionClass == "temperature":
                if state.functionInstance == "current-temp":
                    current_temperature = features.CurrentTemperatureFeature(
                        temperature=round(state.value, 1),
                        function_class=state.functionClass,
                        function_instance=state.functionInstance,
                    )
                elif state.functionInstance == "safety-mode-max-temp":
                    safety_max_temp = generate_target_temp(func_def["values"][0], state)
                elif state.functionInstance == "safety-mode-min-temp":
                    safety_min_temp = generate_target_temp(func_def["values"][0], state)
                elif state.functionInstance == "auto-heating-target":
                    target_temperature_auto_heating = generate_target_temp(
                        func_def["values"][0], state
                    )
                elif state.functionInstance == "auto-cooling-target":
                    target_temperature_auto_cooling = generate_target_temp(
                        func_def["values"][0], state
                    )
                elif state.functionInstance == "heating-target":
                    target_temperature_heating = generate_target_temp(
                        func_def["values"][0], state
                    )
                elif state.functionInstance == "cooling-target":
                    target_temperature_cooling = generate_target_temp(
                        func_def["values"][0], state
                    )
            elif state.functionClass == "mode":
                all_modes = set(process_function(afero_device.functions, "mode"))
                current_mode = state.value
            elif state.functionClass == "current-system-state":
                hvac_action = state.value
            elif state.functionClass == "system-type":
                system_type = state.value
            elif state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.id):
                if isinstance(sensor, AferoBinarySensor):
                    binary_sensors[sensor.id] = sensor
                else:
                    sensors[sensor.id] = sensor
            elif state.functionClass == "temperature-units":
                display_celsius = state.value == "celsius"

        # Determine supported modes
        if current_mode and all_modes and system_type:
            hvac_mode = features.HVACModeFeature(
                mode=current_mode,
                previous_mode=current_mode,
                modes=all_modes,
                supported_modes=get_supported_modes(system_type, all_modes),
            )

        self._items[afero_device.id] = Thermostat(
            afero_device.functions,
            id=afero_device.id,
            available=available,
            sensors=sensors,
            binary_sensors=binary_sensors,
            display_celsius=display_celsius,
            device_information=DeviceInformation(
                device_class=afero_device.device_class,
                default_image=afero_device.default_image,
                default_name=afero_device.default_name,
                manufacturer=afero_device.manufacturerName,
                model=afero_device.model,
                name=afero_device.friendly_name,
                parent_id=afero_device.device_id,
            ),
            current_temperature=current_temperature,
            fan_running=fan_running,
            fan_mode=fan_mode,
            hvac_action=hvac_action,
            hvac_mode=hvac_mode,
            safety_max_temp=safety_max_temp,
            safety_min_temp=safety_min_temp,
            target_temperature_auto_cooling=target_temperature_auto_cooling,
            target_temperature_auto_heating=target_temperature_auto_heating,
            target_temperature_cooling=target_temperature_cooling,
            target_temperature_heating=target_temperature_heating,
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        updated_keys = set()
        cur_item = self.get_device(afero_device.id)
        temperature_mapping = {
            "auto-heating-target": "target_temperature_auto_heating",
            "auto-cooling-target": "target_temperature_auto_cooling",
            "cooling-target": "target_temperature_cooling",
            "heating-target": "target_temperature_heating",
            "safety-mode-max-temp": "safety_max_temp",
            "safety-mode-min-temp": "safety_min_temp",
        }
        for state in afero_device.states:
            if state.functionClass == "current-fan-state":
                temp_val = state.value == "on"
                if cur_item.fan_running != temp_val:
                    cur_item.fan_running = temp_val
                    updated_keys.add("current-fan-state")
            elif state.functionClass == "fan-mode":
                if cur_item.fan_mode.mode != state.value:
                    cur_item.fan_mode.mode = state.value
                    updated_keys.add("fan-mode")
            elif state.functionClass == "mode":
                if cur_item.hvac_mode.mode != state.value:
                    # We only want to update the previous mode when we are in heat or cool
                    if cur_item.hvac_mode.mode in ["cool", "heat"]:
                        cur_item.hvac_mode.previous_mode = cur_item.hvac_mode.mode
                    cur_item.hvac_mode.mode = state.value
                    updated_keys.add(state.functionClass)
            elif state.functionClass == "temperature":
                if state.functionInstance == "current-temp":
                    temp_value = cur_item.current_temperature.temperature
                    rounded_val = round(state.value, 1)
                    if temp_value != rounded_val:
                        cur_item.current_temperature.temperature = rounded_val
                        updated_keys.add(f"temperature-{state.functionInstance}")
                elif state.functionInstance in temperature_mapping.keys():
                    temp_item = getattr(
                        cur_item, temperature_mapping.get(state.functionInstance), None
                    )
                    if temp_item.value != state.value:
                        temp_item.value = state.value
                        updated_keys.add(f"temperature-{state.functionInstance}")
            elif state.functionClass == "current-system-state":
                if cur_item.hvac_action != state.value:
                    cur_item.hvac_action = state.value
                    updated_keys.add(state.functionClass)
            elif state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add("available")
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)
            elif state.functionClass == "temperature-units":
                new_val: bool = state.value == "celsius"
                if cur_item.display_celsius != new_val:
                    cur_item.display_celsius = new_val
                    updated_keys.add(state.functionClass)
        return updated_keys

    async def set_fan_mode(self, device_id: str, fan_mode: str) -> None:
        return await self.set_state(device_id, fan_mode=fan_mode)

    async def set_hvac_mode(self, device_id: str, hvac_mode: str) -> None:
        return await self.set_state(device_id, hvac_mode=hvac_mode)

    async def set_target_temperature(
        self, device_id: str, target_temperature: float
    ) -> None:
        return await self.set_state(device_id, target_temperature=target_temperature)

    async def set_temperature_range(
        self, device_id: str, temp_low: float, temp_high: float
    ) -> None:
        return await self.set_state(
            device_id,
            target_temperature_auto_heating=temp_low,
            target_temperature_auto_cooling=temp_high,
        )

    async def set_state(
        self,
        device_id: str,
        fan_mode: str | None = None,
        hvac_mode: str | None = None,
        safety_max_temp: float | None = None,
        safety_min_temp: float | None = None,
        target_temperature_auto_heating: float | None = None,
        target_temperature_auto_cooling: float | None = None,
        target_temperature_heating: float | None = None,
        target_temperature_cooling: float | None = None,
        target_temperature: float | None = None,
        is_celsius: bool = None,
    ) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = ThermostatPut()
        cur_item = self.get_device(device_id)
        if fan_mode is not None:
            if fan_mode in cur_item.fan_mode.modes:
                update_obj.fan_mode = features.ModeFeature(
                    mode=fan_mode,
                    modes=cur_item.fan_mode.modes,
                )
                update_obj.hvac_mode = features.HVACModeFeature(
                    mode="fan",
                    modes=cur_item.hvac_mode.modes,
                    previous_mode=cur_item.hvac_mode.mode,
                    supported_modes=cur_item.hvac_mode.supported_modes,
                )
            else:
                self._logger.debug(
                    "Unknown fan mode %s. Available modes: %s",
                    fan_mode,
                    ", ".join(sorted(cur_item.fan_mode.modes)),
                )
        if hvac_mode is not None and not update_obj.hvac_mode:
            if hvac_mode in cur_item.hvac_mode.supported_modes:
                update_obj.hvac_mode = features.HVACModeFeature(
                    mode=hvac_mode,
                    modes=cur_item.hvac_mode.modes,
                    previous_mode=cur_item.hvac_mode.mode,
                    supported_modes=cur_item.hvac_mode.supported_modes,
                )
            else:
                self._logger.debug(
                    "Unknown hvac mode %s. Available modes: %s",
                    hvac_mode,
                    ", ".join(sorted(cur_item.hvac_mode.modes)),
                )
        # Setting the temp without a specific means we need to adjust the active
        # mode.
        if target_temperature:
            if hvac_mode and hvac_mode in cur_item.hvac_mode.supported_modes:
                mode_to_set = hvac_mode
            else:
                mode_to_set = cur_item.get_mode_to_check()
            if mode_to_set == "cool":
                target_temperature_cooling = target_temperature
            elif mode_to_set == "heat":
                target_temperature_heating = target_temperature
            else:
                self._logger.debug(
                    "Unable to set the target temperature due to the active mode: %s",
                    cur_item.hvac_mode.mode,
                )
        if safety_min_temp is not None:
            safety_min_temp = await self.get_hubspace_temp(
                cur_item, safety_min_temp, is_celsius
            )
            update_obj.safety_min_temp = features.TargetTemperatureFeature(
                value=safety_min_temp,
                min=cur_item.safety_min_temp.min,
                max=cur_item.safety_min_temp.max,
                step=cur_item.safety_min_temp.step,
                instance=cur_item.safety_min_temp.instance,
            )
        if safety_max_temp is not None:
            safety_max_temp = await self.get_hubspace_temp(
                cur_item, safety_max_temp, is_celsius
            )
            update_obj.safety_max_temp = features.TargetTemperatureFeature(
                value=safety_max_temp,
                min=cur_item.safety_max_temp.min,
                max=cur_item.safety_max_temp.max,
                step=cur_item.safety_max_temp.step,
                instance=cur_item.safety_max_temp.instance,
            )
        if target_temperature_auto_heating is not None:
            target_temperature_auto_heating = await self.get_hubspace_temp(
                cur_item, target_temperature_auto_heating, is_celsius
            )
            update_obj.target_temperature_auto_heating = (
                features.TargetTemperatureFeature(
                    value=target_temperature_auto_heating,
                    min=cur_item.target_temperature_auto_heating.min,
                    max=cur_item.target_temperature_auto_heating.max,
                    step=cur_item.target_temperature_auto_heating.step,
                    instance=cur_item.target_temperature_auto_heating.instance,
                )
            )
        if target_temperature_auto_cooling is not None:
            target_temperature_auto_cooling = await self.get_hubspace_temp(
                cur_item, target_temperature_auto_cooling, is_celsius
            )
            update_obj.target_temperature_auto_cooling = (
                features.TargetTemperatureFeature(
                    value=target_temperature_auto_cooling,
                    min=cur_item.target_temperature_auto_cooling.min,
                    max=cur_item.target_temperature_auto_cooling.max,
                    step=cur_item.target_temperature_auto_cooling.step,
                    instance=cur_item.target_temperature_auto_cooling.instance,
                )
            )
        if target_temperature_heating is not None:
            target_temperature_heating = await self.get_hubspace_temp(
                cur_item, target_temperature_heating, is_celsius
            )
            update_obj.target_temperature_heating = features.TargetTemperatureFeature(
                value=target_temperature_heating,
                min=cur_item.target_temperature_heating.min,
                max=cur_item.target_temperature_heating.max,
                step=cur_item.target_temperature_heating.step,
                instance=cur_item.target_temperature_heating.instance,
            )
        if target_temperature_cooling is not None:
            target_temperature_cooling = await self.get_hubspace_temp(
                cur_item, target_temperature_cooling, is_celsius
            )
            update_obj.target_temperature_cooling = features.TargetTemperatureFeature(
                value=target_temperature_cooling,
                min=cur_item.target_temperature_cooling.min,
                max=cur_item.target_temperature_cooling.max,
                step=cur_item.target_temperature_cooling.step,
                instance=cur_item.target_temperature_cooling.instance,
            )
        await self.update(device_id, obj_in=update_obj)

    async def get_hubspace_temp(
        self, resource: Thermostat, temperature: float, is_celsius: bool
    ) -> float:
        if resource.display_celsius or is_celsius:
            return temperature
        else:
            return calculate_hubspace_celsius(temperature)


def generate_target_temp(
    func_def: dict, state: AferoState
) -> features.TargetTemperatureFeature:
    return features.TargetTemperatureFeature(
        value=round(state.value, 2),
        step=func_def["range"]["step"],
        min=func_def["range"]["min"],
        max=func_def["range"]["max"],
        instance=state.functionInstance,
    )


def get_supported_modes(system_type: str, all_modes: set[str]) -> set:
    """Determine the supported modes based on the system_type."""
    supported_modes = copy.copy(all_modes)
    if "heat-pump" in system_type:
        supports_heating = True
        supports_cooling = True
    else:
        supports_heating = "heating" in system_type
        supports_cooling = "cooling" in system_type
    if not supports_heating and "heat" in supported_modes:
        supported_modes.remove("heat")
    if not supports_cooling and "cool" in supported_modes:
        supported_modes.remove("cool")
    if (not supports_cooling or not supports_heating) and "auto" in supported_modes:
        supported_modes.remove("auto")
    return supported_modes
