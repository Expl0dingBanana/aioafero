"""Controller holding and managing Afero IoT resources of type `portable-air-conditioner`."""

from ... import device
from ...device import AferoDevice, AferoState
from ...errors import DeviceNotFound
from ...util import calculate_hubspace_celsius, process_function
from ..models import features
from ..models.portable_ac import PortableAC, PortableACPut
from ..models.resource import DeviceInformation, ResourceTypes
from .base import BaseResourcesController


class PortableACController(BaseResourcesController[PortableAC]):
    """Controller holding and managing Afero IoT resources of type `portable-air-conditioner`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.PORTABLE_AC]
    ITEM_CLS = PortableAC
    ITEM_MAPPING = {
        "hvac_mode": "mode",
    }
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {}
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {}
    # Elements that map to numbers. func class / func instance to unit
    ITEM_NUMBERS: dict[tuple[str, str | None], str] = {
        ("timer", None): "minutes",
    }
    # Elements that map to Select. func class / func instance to name
    ITEM_SELECTS = {
        ("fan-speed", "ac-fan-speed"): "Fan Speed",
        ("sleep", None): "Sleep Mode",
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> PortableAC:
        """Initialize the element"""
        available: bool = False
        # Afero reports in Celsius by default
        display_celsius: bool = True
        current_temperature: features.CurrentTemperatureFeature | None = None
        hvac_mode: features.HVACModeFeature | None = None
        target_temperature_cooling: features.TargetTemperatureFeature | None = None
        numbers: dict[tuple[str, str], features.NumbersFeature] = {}
        selects: dict[tuple[str, str], features.SelectFeature] = {}
        for state in afero_device.states:
            func_def = device.get_function_from_device(
                afero_device.functions, state.functionClass, state.functionInstance
            )
            if (
                state.functionClass == "temperature"
                and state.functionInstance == "current-temp"
            ):
                current_temperature = features.CurrentTemperatureFeature(
                    temperature=round(state.value, 1),
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif (
                state.functionClass == "temperature"
                and state.functionInstance == "cooling-target"
            ):
                target_temperature_cooling = generate_target_temp(
                    func_def["values"][0], state
                )

            elif state.functionClass == "mode":
                all_modes = set(process_function(afero_device.functions, "mode"))
                hvac_mode = features.HVACModeFeature(
                    mode=state.value,
                    previous_mode=state.value,
                    modes=all_modes,
                    supported_modes=all_modes,
                )
            elif state.functionClass == "available":
                available = state.value
            elif number := await self.initialize_number(func_def, state):
                numbers[number[0]] = number[1]
            elif select := await self.initialize_select(afero_device.functions, state):
                selects[select[0]] = select[1]
            elif state.functionClass == "temperature-units":
                display_celsius = state.value == "celsius"

        self._items[afero_device.id] = PortableAC(
            afero_device.functions,
            id=afero_device.id,
            available=available,
            current_temperature=current_temperature,
            hvac_mode=hvac_mode,
            target_temperature_cooling=target_temperature_cooling,
            numbers=numbers,
            selects=selects,
            binary_sensors={},
            sensors={},
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
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        updated_keys = set()
        cur_item = self.get_device(afero_device.id)
        for state in afero_device.states:
            if state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add("available")
            elif (
                state.functionClass == "temperature"
                and state.functionInstance == "current-temp"
            ):
                if cur_item.current_temperature.temperature != round(state.value, 1):
                    cur_item.current_temperature.temperature = round(state.value, 1)
                    updated_keys.add(f"temperature-{state.functionInstance}")
            elif (
                state.functionClass == "temperature"
                and state.functionInstance == "cooling-target"
            ):
                if cur_item.target_temperature_cooling.value != state.value:
                    cur_item.target_temperature_cooling.value = state.value
                    updated_keys.add(f"temperature-{state.functionInstance}")
            elif state.functionClass == "mode":
                if cur_item.hvac_mode.mode != state.value:
                    cur_item.hvac_mode.previous_mode = cur_item.hvac_mode.mode
                    cur_item.hvac_mode.mode = state.value
                    updated_keys.add(state.functionClass)
            elif update_key := await self.update_number(state, cur_item):
                updated_keys.add(update_key)
            elif update_key := await self.update_select(state, cur_item):
                updated_keys.add(update_key)
            elif state.functionClass == "temperature-units":
                new_val: bool = state.value == "celsius"
                if cur_item.display_celsius != new_val:
                    cur_item.display_celsius = new_val
                    updated_keys.add(state.functionClass)
        return updated_keys

    async def set_state(self, device_id: str, **kwargs) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = PortableACPut()
        hvac_mode: str | None = kwargs.get("hvac_mode")
        target_temperature: float | None = kwargs.get("target_temperature")
        numbers: dict[tuple[str, str | None], float] | None = kwargs.get("numbers")
        selects: dict[tuple[str, str | None], str] | None = kwargs.get("selects")
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if hvac_mode:
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
        if target_temperature is not None:
            if not cur_item.display_celsius and not kwargs.get("is_celsius", False):
                target_temperature = calculate_hubspace_celsius(target_temperature)
            update_obj.target_temperature_cooling = features.TargetTemperatureFeature(
                value=target_temperature,
                min=cur_item.target_temperature_cooling.min,
                max=cur_item.target_temperature_cooling.max,
                step=cur_item.target_temperature_cooling.step,
                instance=cur_item.target_temperature_cooling.instance,
            )
        if numbers:
            for key, val in numbers.items():
                if key not in cur_item.numbers:
                    continue
                update_obj.numbers[key] = features.NumbersFeature(
                    value=val,
                    min=cur_item.numbers[key].min,
                    max=cur_item.numbers[key].max,
                    step=cur_item.numbers[key].step,
                    name=cur_item.numbers[key].name,
                    unit=cur_item.numbers[key].unit,
                )
                # Currently only ("timer", None) exists
                update_obj.current_temperature = features.CurrentTemperatureFeature(
                    temperature=cur_item.current_temperature.temperature + 1,
                    function_class=cur_item.current_temperature.function_class,
                    function_instance=cur_item.current_temperature.function_instance,
                )
        if selects:
            for key, val in selects.items():
                if key not in cur_item.selects:
                    continue
                update_obj.selects[key] = features.SelectFeature(
                    selected=val,
                    selects=cur_item.selects[key].selects,
                    name=cur_item.selects[key].name,
                )
        await self.update(device_id, obj_in=update_obj)


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
