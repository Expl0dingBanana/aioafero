"""Controller holding and managing Afero IoT resources of type `valve`."""

from typing import Any

from aioafero import errors
from aioafero.device import AferoDevice, get_function_from_device
from aioafero.v1.models import features
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes
from aioafero.v1.models.valve import Valve, ValvePut

from .base import AferoBinarySensor, AferoSensor, BaseResourcesController

# Per-spigot numeric functions. These are instanced (``spigot-1``, ``spigot-2``,
# ...) so they cannot be enumerated statically in ITEM_NUMBERS; they are parsed
# by functionClass and stored in the ``numbers`` dict keyed by (class, instance).
NUMBER_CLASSES = {"timer", "max-on-time"}
# Display units for the per-spigot numbers. Both are 0/1-360 on the known
# fixtures and represent durations in minutes. ``max-on-time`` is documented as
# 1-360 minutes; ``timer``'s unit is inferred from its shared range and should
# be confirmed against live hardware (see k3s-q9l7 sub-task 5 traffic capture).
NUMBER_UNITS = {"timer": "minutes", "max-on-time": "minutes"}


def _rain_delay_pauses(value: Any) -> list:
    """Pull the pause-window list out of a `schedule-pause`/`rain-delay` value.

    Wire shape:
        {"schedule-pause-time-array": {"schedulePauseTimeArray": [...]}}
    Tolerant of a missing/short payload -- returns an empty list rather than
    raising so a partial device dump still parses.
    """
    if not isinstance(value, dict):
        return []
    nested = value.get("schedule-pause-time-array") or {}
    return list(nested.get("schedulePauseTimeArray") or [])


class ValveController(BaseResourcesController[Valve]):
    """Controller holding and managing Afero IoT resources of type `valve`.

    A valve can have one or more toggleable elements (spigots). Each spigot is
    controlled by its functionInstance and carries a ``timer`` and
    ``max-on-time`` number. The device also exposes a ``battery-level`` sensor
    and a ``schedule-pause`` (rain-delay) feature.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.WATER_TIMER]
    ITEM_CLS = Valve
    ITEM_MAPPING = {}
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {"battery-level": "%"}

    async def turn_on(self, device_id: str, instance: str | None = None) -> None:
        """Open the valve."""
        await self.set_state(device_id, valve_open=True, instance=instance)

    async def turn_off(self, device_id: str, instance: str | None = None) -> None:
        """Close the valve."""
        await self.set_state(device_id, valve_open=False, instance=instance)

    def _number_feature(
        self, afero_device: AferoDevice, state
    ) -> features.NumbersFeature:
        """Build a NumbersFeature for a per-spigot numeric state.

        Mirrors ``BaseResourcesController.initialize_number`` but matches by
        functionClass rather than an exact (class, instance) key, so any number
        of spigots is supported.
        """
        func_def = get_function_from_device(
            afero_device.functions, state.functionClass, state.functionInstance
        )
        working_def = func_def["values"][0]
        fallback_name = state.functionClass
        if state.functionInstance is not None:
            fallback_name += f"-{state.functionInstance}"
        return features.NumbersFeature(
            value=state.value,
            min=working_def["range"]["min"],
            max=working_def["range"]["max"],
            step=working_def["range"]["step"],
            name=working_def.get("name", fallback_name),
            unit=NUMBER_UNITS.get(state.functionClass),
        )

    async def initialize_elem(self, afero_device: AferoDevice) -> Valve:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        self._logger.info("Initializing %s", afero_device.id)
        available: bool = False
        valve_open: dict[str | None, features.OpenFeature] = {}
        numbers: dict[tuple[str, str | None], features.NumbersFeature] = {}
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        rain_delay_active: bool = False
        rain_delay_pauses: list = []
        rain_delay_seen: bool = False
        for state in afero_device.states:
            if state.functionClass in ["power", "toggle"]:
                valve_open[state.functionInstance] = features.OpenFeature(
                    open=state.value == "on",
                    func_class=state.functionClass,
                    func_instance=state.functionInstance,
                )
            elif state.functionClass in NUMBER_CLASSES:
                numbers[(state.functionClass, state.functionInstance)] = (
                    self._number_feature(afero_device, state)
                )
            elif state.functionClass == "schedule-pause":
                rain_delay_seen = True
                if state.functionInstance == "active":
                    rain_delay_active = state.value == "on"
                elif state.functionInstance == "rain-delay":
                    rain_delay_pauses = _rain_delay_pauses(state.value)
            elif state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.id):
                sensors[sensor.id] = sensor

        self._items[afero_device.id] = Valve(
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
            open=valve_open,
            numbers=numbers,
            rain_delay=(
                features.RainDelayFeature(
                    active=rain_delay_active, pauses=rain_delay_pauses
                )
                if rain_delay_seen
                else None
            ),
        )
        return self._items[afero_device.id]

    def _update_rain_delay(self, cur_item: Valve, state) -> bool:
        """Apply a `schedule-pause` state to the item. Returns True if changed."""
        if cur_item.rain_delay is None:
            cur_item.rain_delay = features.RainDelayFeature(active=False)
        if state.functionInstance == "active":
            new_active = state.value == "on"
            if cur_item.rain_delay.active != new_active:
                cur_item.rain_delay.active = new_active
                return True
        elif state.functionInstance == "rain-delay":
            new_pauses = _rain_delay_pauses(state.value)
            if cur_item.rain_delay.pauses != new_pauses:
                cur_item.rain_delay.pauses = new_pauses
                return True
        return False

    async def update_elem(self, afero_device: AferoDevice) -> set:
        """Update the Valve with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        for state in afero_device.states:
            if state.functionClass in ["power", "toggle"]:
                new_state = state.value == "on"
                if cur_item.open[state.functionInstance].open != new_state:
                    updated_keys.add("open")
                cur_item.open[state.functionInstance].open = new_state
            elif state.functionClass in NUMBER_CLASSES:
                key = (state.functionClass, state.functionInstance)
                if key in cur_item.numbers and cur_item.numbers[key].value != state.value:
                    cur_item.numbers[key].value = state.value
                    updated_keys.add(f"number-{key}")
            elif state.functionClass == "schedule-pause":
                if self._update_rain_delay(cur_item, state):
                    updated_keys.add("rain-delay")
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
        valve_open: bool | None = None,
        instance: str | None = None,
        numbers: dict[tuple[str, str | None], float] | None = None,
        rain_delay: bool | None = None,
    ) -> None:
        """Set supported feature(s) on the valve resource."""
        update_obj = ValvePut()
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if valve_open is not None:
            try:
                update_obj.open = features.OpenFeature(
                    open=valve_open,
                    func_class=cur_item.open[instance].func_class,
                    func_instance=instance,
                )
            except KeyError:
                self._logger.info("Unable to find instance %s", instance)
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
        if rain_delay is not None:
            update_obj.rain_delay = features.RainDelayFeature(active=rain_delay)
        await self.update(device_id, obj_in=update_obj)
