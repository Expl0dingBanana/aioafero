"""Controller that holds top-level devices"""

import re
from typing import Any

from ...device import AferoDevice, AferoState, get_afero_device
from ..models import sensor
from ..models.device import Device
from ..models.resource import DeviceInformation, ResourceTypes
from .base import BaseResourcesController

unit_extractor = re.compile(r"(\d*)(\D*)")

SENSOR_TO_UNIT: dict[str, str] = {
    "power": "W",
    "watts": "W",
    "wifi-rssi": "dB",
}


class DeviceController(BaseResourcesController[Device]):
    """Controller that identifies top-level components."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = []
    ITEM_CLS = Device

    async def initialize_elem(self, device: AferoDevice) -> Device:
        """Initialize the element"""
        available: bool = False
        sensors: dict[str, sensor.AferoSensor] = {}
        binary_sensors: dict[str, sensor.AferoSensor | sensor.AferoSensorError] = {}
        wifi_mac: str | None = None
        ble_mac: str | None = None

        for state in device.states:
            if state.functionClass == "available":
                available = state.value
            elif state.functionClass in sensor.MAPPED_SENSORS:
                value, unit = split_sensor_data(state)
                sensors[state.functionClass] = sensor.AferoSensor(
                    id=state.functionClass,
                    owner=device.device_id,
                    _value=value,
                    unit=unit,
                )
            elif state.functionClass in sensor.BINARY_SENSORS:
                value, unit = split_sensor_data(state)
                key = f"{state.functionClass}|{state.functionInstance}"
                sensor_class = (
                    sensor.AferoSensorError
                    if state.functionClass == "error"
                    else sensor.AferoSensor
                )
                binary_sensors[key] = sensor_class(
                    id=key,
                    owner=device.device_id,
                    _value=value,
                    unit=unit,
                    instance=state.functionInstance,
                )
            elif state.functionClass == "wifi-mac-address":
                wifi_mac = state.value
            elif state.functionClass == "ble-mac-address":
                ble_mac = state.value

        self._items[device.id] = Device(
            id=device.id,
            available=available,
            sensors=sensors,
            binary_sensors=binary_sensors,
            device_information=DeviceInformation(
                device_class=device.device_class,
                default_image=device.default_image,
                default_name=device.default_name,
                manufacturer=device.manufacturerName,
                model=device.model,
                name=device.friendly_name,
                parent_id=device.device_id,
                wifi_mac=wifi_mac,
                ble_mac=ble_mac,
            ),
        )
        return self._items[device.id]

    def get_filtered_devices(self, initial_data: list[dict]) -> list[AferoDevice]:
        """Find parent devices"""
        parents: dict = {}
        potential_parents: dict = {}
        for element in initial_data:
            if element["typeId"] != self.ITEM_TYPE_ID.value:
                self._logger.debug(
                    "TypeID [%s] does not match %s",
                    element["typeId"],
                    self.ITEM_TYPE_ID.value,
                )
                continue
            device: AferoDevice = get_afero_device(element)
            if device.children:
                parents[device.device_id] = device
            elif device.device_id not in parents and (
                device.device_id not in parents
                and device.device_id not in potential_parents
            ):
                potential_parents[device.device_id] = device
            else:
                self._logger.debug("skipping %s as its tracked", device.device_id)
        for potential_parent in potential_parents.values():
            if potential_parent.device_id not in parents:
                parents[potential_parent.device_id] = potential_parent
        return list(parents.values())

    async def update_elem(self, device: AferoDevice) -> set:
        cur_item = self.get_device(device.id)
        updated_keys = set()
        for state in device.states:
            if state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add(state.functionClass)
            elif state.functionClass in sensor.MAPPED_SENSORS:
                value, _ = split_sensor_data(state)
                if cur_item.sensors[state.functionClass]._value != value:
                    cur_item.sensors[state.functionClass]._value = value
                    updated_keys.add(f"sensor-{state.functionClass}")
            elif state.functionClass in sensor.BINARY_SENSORS:
                value, _ = split_sensor_data(state)
                key = f"{state.functionClass}|{state.functionInstance}"
                if cur_item.binary_sensors[key]._value != value:
                    cur_item.binary_sensors[key]._value = value
                    updated_keys.add(f"binary-{key}")
        return updated_keys


def split_sensor_data(state: AferoState) -> tuple[Any, str | None]:
    if isinstance(state.value, str):
        match = unit_extractor.match(state.value)
        if match and match.group(1) and match.group(2):
            return int(match.group(1)), match.group(2)
    return state.value, SENSOR_TO_UNIT.get(state.functionClass, None)
