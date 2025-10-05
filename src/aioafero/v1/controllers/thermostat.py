"""Controller holding and managing Afero IoT resources of type `thermostat`."""

import copy

from aioafero.device import AferoDevice
from aioafero.util import process_function
from aioafero.v1.models import features
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes
from aioafero.v1.models.thermostat import Thermostat, ThermostatPut

from .climate import ClimateController


class ThermostatController(ClimateController[Thermostat]):
    """Controller holding and managing Afero IoT resources of type `thermostat`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.THERMOSTAT]
    ITEM_CLS = Thermostat
    ITEM_MAPPING = {
        "fan_mode": "fan-mode",
        "hvac_mode": "mode",
    }
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "filter-replacement": "replacement-needed",
        "max-temp-exceeded": "alerting",
        "min-temp-exceeded": "alerting",
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> Thermostat:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        climate_data = await self.initialize_climate_elem(afero_device)

        fan_running: bool | None = None
        fan_mode: features.ModeFeature | None = None
        hvac_action: str | None = None
        system_type: str | None = None

        for state in afero_device.states:
            if state.functionClass == "fan-mode":
                fan_mode = features.ModeFeature(
                    mode=state.value,
                    modes=set(process_function(afero_device.functions, "fan-mode")),
                )
            elif state.functionClass == "current-fan-state":
                fan_running = state.value == "on"
            elif state.functionClass == "current-system-state":
                hvac_action = state.value
            elif state.functionClass == "system-type":
                system_type = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.id):
                climate_data["binary_sensors"][sensor.id] = sensor

        # Determine supported modes
        climate_data["hvac_mode"].supported_modes = get_supported_modes(
            system_type, climate_data["hvac_mode"].modes
        )

        self._items[afero_device.id] = Thermostat(
            _id=afero_device.id,
            available=climate_data["available"],
            sensors=climate_data["sensors"],
            binary_sensors=climate_data["binary_sensors"],
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
            current_temperature=climate_data["current_temperature"],
            fan_running=fan_running,
            fan_mode=fan_mode,
            hvac_action=hvac_action,
            hvac_mode=climate_data["hvac_mode"],
            safety_max_temp=climate_data["safety_max_temp"],
            safety_min_temp=climate_data["safety_min_temp"],
            target_temperature_auto_cooling=climate_data[
                "target_temperature_auto_cooling"
            ],
            target_temperature_auto_heating=climate_data[
                "target_temperature_auto_heating"
            ],
            target_temperature_cooling=climate_data["target_temperature_cooling"],
            target_temperature_heating=climate_data["target_temperature_heating"],
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        """Update the Thermostat with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        updated_keys = await self.update_climate_elem(afero_device)
        cur_item = self.get_device(afero_device.id)

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
            elif state.functionClass == "current-system-state":
                if cur_item.hvac_action != state.value:
                    cur_item.hvac_action = state.value
                    updated_keys.add(state.functionClass)
        return updated_keys

    async def set_fan_mode(self, device_id: str, fan_mode: str) -> None:
        """Enable or disable fan mode."""
        return await self.set_state(device_id, fan_mode=fan_mode)

    async def set_hvac_mode(self, device_id: str, hvac_mode: str) -> None:
        """Set the current mode of the HVAC system."""
        return await self.set_state(device_id, hvac_mode=hvac_mode)

    async def set_target_temperature(
        self, device_id: str, target_temperature: float
    ) -> None:
        """Set the target temperature."""
        return await self.set_state(device_id, target_temperature=target_temperature)

    async def set_temperature_range(
        self, device_id: str, temp_low: float, temp_high: float
    ) -> None:
        """Set the temperature range for the thermostat."""
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
        **kwargs,
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
                    ", ".join(sorted(cur_item.hvac_mode.supported_modes)),
                )
        # Setting the temp without a specific means we need to adjust the active
        # mode.
        target_temperature = kwargs.pop("target_temperature", None)
        if target_temperature:
            if hvac_mode and hvac_mode in cur_item.hvac_mode.supported_modes:
                mode_to_set = hvac_mode
            else:
                mode_to_set = cur_item.get_mode_to_check()
            if mode_to_set == "cool":
                target_temperature_cooling = target_temperature
                kwargs["target_temperature_cooling"] = target_temperature
            elif mode_to_set == "heat":
                target_temperature_heating = target_temperature
                kwargs["target_temperature_heating"] = target_temperature
            else:
                self._logger.debug(
                    "Unable to set the target temperature due to the active mode: %s",
                    cur_item.hvac_mode.mode,
                )
        kwargs["safety_min_temp"] = safety_min_temp
        kwargs["safety_max_temp"] = safety_max_temp
        kwargs["target_temperature_auto_heating"] = target_temperature_auto_heating
        kwargs["target_temperature_auto_cooling"] = target_temperature_auto_cooling
        kwargs["target_temperature_heating"] = target_temperature_heating
        kwargs["target_temperature_cooling"] = target_temperature_cooling
        await self.set_climate_state(device_id, update_obj, **kwargs)


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
