"""Controller that holds top-level devices"""

from ...device import AferoDevice, get_afero_device
from ..models.device import Device
from ..models.resource import DeviceInformation, ResourceTypes
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController


class DeviceController(BaseResourcesController[Device]):
    """Controller that identifies top-level components."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = []
    ITEM_CLS = Device
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {
        "battery-level": "%",
        "wifi-rssi": "dB",
    }
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "error": "alerting",
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> Device:
        """Initialize the element"""
        available: bool = False
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        wifi_mac: str | None = None
        ble_mac: str | None = None

        for state in afero_device.states:
            if state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.id):
                if isinstance(sensor, AferoBinarySensor):
                    binary_sensors[sensor.id] = sensor
                else:
                    sensors[sensor.id] = sensor
            elif state.functionClass == "wifi-mac-address":
                wifi_mac = state.value
            elif state.functionClass == "ble-mac-address":
                ble_mac = state.value

        self._items[afero_device.id] = Device(
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
                wifi_mac=wifi_mac,
                ble_mac=ble_mac,
            ),
        )
        return self._items[afero_device.id]

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
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)
        return updated_keys
