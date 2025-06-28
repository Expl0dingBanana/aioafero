"""Controller that holds top-level devices"""

from ...device import AferoDevice
from ..models.device import Device
from ..models.resource import DeviceInformation, ResourceTypes
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController
from .event import AferoEvent, EventType


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
    _known_parents: dict[str, str] = {}

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

    async def initialize(self) -> None:
        """Initialize controller by fetching all items for this resource type from bridge."""
        if self._initialized:
            return
        # Subscribe to polled data to find all top-level devices
        self._bridge.events.subscribe(
            self._process_polled_devices,
            event_filter=EventType.POLLED_DEVICES,
        )
        self._initialized = True

    async def _process_polled_devices(
        self, evt_type: EventType, evt_data: AferoEvent | None
    ) -> None:
        """Finds all top-level devices within the payload"""
        devices: list[AferoDevice] = evt_data["polled_devices"]
        parent_devices: list[AferoDevice] = self.get_filtered_devices(devices)
        processed: set[str] = set()
        for parent_device in parent_devices:
            evt = AferoEvent(
                type=EventType.RESOURCE_ADDED,
                device_id=parent_device.id,
                device=parent_device,
            )
            if parent_device.device_id not in self._known_parents:
                self._known_parents[parent_device.device_id] = parent_device.id
            else:
                evt["type"] = EventType.RESOURCE_UPDATED
            processed.add(parent_device.device_id)
            await self._handle_event(evt["type"], evt)
        for known_id in list(self._known_parents):
            if known_id not in processed:
                device_id = self._known_parents.pop(known_id)
                self._logger.info("Device %s was not polled. Removing", known_id)
                evt = AferoEvent(
                    type=EventType.RESOURCE_DELETED,
                    device_id=device_id,
                )
                await self._handle_event(evt["type"], evt)

    def get_filtered_devices(self, devices: list[AferoDevice]) -> list[AferoDevice]:
        """Find parent devices"""
        parents: dict = {}
        potential_parents: dict = {}
        for device in devices:
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
