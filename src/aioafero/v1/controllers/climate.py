"""Base controller for climate devices."""

from typing import TypeVar

from aioafero import device
from aioafero.device import AferoCapability, AferoDevice, AferoResource, AferoState
from aioafero.util import process_function
from aioafero.v1.models import features

from .base import BaseResourcesController

AferoResourceT = TypeVar("AferoResourceT", bound=AferoResource)


TARGET_INSTANCE_MAPPING = {
    "cooling-target": "target_temperature_cooling",
    "heating-target": "target_temperature_heating",
    "auto-cooling-target": "target_temperature_auto_cooling",
    "auto-heating-target": "target_temperature_auto_heating",
    "safety-mode-max-temp": "safety_max_temp",
    "safety-mode-min-temp": "safety_min_temp",
}


def generate_target_temp(
    func_def: dict, state: AferoState
) -> features.TargetTemperatureFeature:
    """Determine the target temp based on the function definition."""
    return features.TargetTemperatureFeature(
        value=round(state.value, 1),
        step=func_def["range"]["step"],
        min=func_def["range"]["min"],
        max=func_def["range"]["max"],
        instance=state.functionInstance,
    )


def generate_target_temp_capability(
    capability: AferoCapability, state: AferoState
) -> features.TargetTemperatureFeature:
    """Determine the target temp based on the function definition."""
    return features.TargetTemperatureFeature(
        value=round(state.value, 1),
        step=capability.options["range"]["step"],
        min=capability.options["range"]["min"],
        max=capability.options["range"]["max"],
        instance=state.functionInstance,
    )


class ClimateController(BaseResourcesController[AferoResourceT]):
    """Base controller for climate devices."""

    async def initialize_climate_elem(self, afero_device: AferoDevice) -> dict:
        """Initialize the climate elements of a device."""
        climate_data = {
            "available": False,
            "current_temperature": None,
            "hvac_mode": None,
            "target_temperature_cooling": None,
            "target_temperature_heating": None,
            "target_temperature_auto_cooling": None,
            "target_temperature_auto_heating": None,
            "safety_max_temp": None,
            "safety_min_temp": None,
            "numbers": {},
            "selects": {},
            "sensors": {},
            "binary_sensors": {},
        }
        for state in afero_device.states:
            if state.functionClass == "temperature":
                if state.functionInstance == "current-temp":
                    climate_data["current_temperature"] = (
                        features.CurrentTemperatureFeature(
                            temperature=round(state.value, 1),
                            function_class=state.functionClass,
                            function_instance=state.functionInstance,
                        )
                    )
                else:
                    capability_def = device.get_capability_from_device(
                        afero_device.capabilities,
                        state.functionClass,
                        state.functionInstance,
                    )
                    if capability_def:
                        target_data = generate_target_temp_capability(
                            capability_def, state
                        )
                    else:
                        # @TODO - This exists as we do not have data dumps with capabilities
                        # for all devices. We should remove this fallback once we do
                        func_def = device.get_function_from_device(
                            afero_device.functions,
                            state.functionClass,
                            state.functionInstance,
                        )
                        target_data = generate_target_temp(func_def["values"][0], state)
                    if state.functionInstance in TARGET_INSTANCE_MAPPING:
                        climate_data[
                            TARGET_INSTANCE_MAPPING[state.functionInstance]
                        ] = target_data
                    else:
                        self._logger.warning("Found unknown temp instance, %s", state)
            elif state.functionClass == "mode":
                all_modes = set(process_function(afero_device.functions, "mode"))
                climate_data["hvac_mode"] = features.HVACModeFeature(
                    mode=state.value,
                    previous_mode=state.value,
                    modes=all_modes,
                    supported_modes=all_modes,
                )
            elif state.functionClass == "available":
                climate_data["available"] = state.value
            elif select := await self.initialize_select(afero_device.functions, state):
                climate_data["selects"][select[0]] = select[1]

        return climate_data

    async def update_climate_elem(self, afero_device: AferoDevice) -> set:
        """Update the climate elements of a device."""
        updated_keys = set()
        cur_item = self.get_device(afero_device.id)
        for state in afero_device.states:
            if state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add("available")
            elif state.functionClass == "temperature":
                if state.functionInstance == "current-temp":
                    temp_value = cur_item.current_temperature.temperature
                    rounded_val = round(state.value, 1)
                    if temp_value != rounded_val:
                        cur_item.current_temperature.temperature = rounded_val
                        updated_keys.add(f"temperature-{state.functionInstance}")
                elif state.functionInstance in TARGET_INSTANCE_MAPPING:
                    temp_item = getattr(
                        cur_item,
                        TARGET_INSTANCE_MAPPING.get(state.functionInstance),
                        None,
                    )
                    if temp_item and temp_item.value != state.value:
                        temp_item.value = state.value
                        updated_keys.add(f"temperature-{state.functionInstance}")
            elif state.functionClass == "mode":
                if cur_item.hvac_mode and cur_item.hvac_mode.mode != state.value:
                    # We only want to update the previous mode when we are in heat or cool
                    if cur_item.hvac_mode.mode in ["cool", "heat"]:
                        cur_item.hvac_mode.previous_mode = cur_item.hvac_mode.mode
                    cur_item.hvac_mode.mode = state.value
                    updated_keys.add(state.functionClass)
            elif (update_key := await self.update_number(state, cur_item)) or (
                update_key := await self.update_select(state, cur_item)
            ):
                updated_keys.add(update_key)
        return updated_keys

    async def set_climate_state(self, device_id: str, update_obj, **kwargs) -> None:
        """Set climate state."""
        cur_item = self.get_device(device_id)

        temperature_kwargs = {
            "target_temperature_auto_heating": "target_temperature_auto_heating",
            "target_temperature_auto_cooling": "target_temperature_auto_cooling",
            "target_temperature_heating": "target_temperature_heating",
            "target_temperature_cooling": "target_temperature_cooling",
            "safety_min_temp": "safety_min_temp",
            "safety_max_temp": "safety_max_temp",
        }

        for kwarg_name, attr_name in temperature_kwargs.items():
            temp_val = kwargs.get(kwarg_name)
            if temp_val is not None:
                cur_temp_feature = getattr(cur_item, attr_name, None)

                setattr(
                    update_obj,
                    attr_name,
                    features.TargetTemperatureFeature(
                        value=temp_val,
                        min=cur_temp_feature.min,
                        max=cur_temp_feature.max,
                        step=cur_temp_feature.step,
                        instance=cur_temp_feature.instance,
                    ),
                )

        await self.update(device_id, obj_in=update_obj)
