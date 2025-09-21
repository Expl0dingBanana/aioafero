"""Controller holding and managing Afero IoT resources of type `security-system`."""

from aioafero.device import AferoDevice
from aioafero.errors import DeviceNotFound
from aioafero.v1.models import SecuritySystemSensor, SecuritySystemSensorPut, features
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import AferoBinarySensor, AferoSensor, BaseResourcesController
from .security_system import (
    BYPASS_MODES,
    GENERIC_MODES,
    SENSOR_SPLIT_IDENTIFIER,
    TRIGGER_MODES,
)


class SecuritySystemSensorController(BaseResourcesController[SecuritySystemSensor]):
    """Controller holding and managing Afero IoT `security-system` for the sensors."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.SECURITY_SYSTEM_SENSOR]
    ITEM_CLS = SecuritySystemSensor
    ITEM_MAPPING = {}

    SENSOR_TYPES = {
        1: "Motion Sensor",
        2: "Door/Window Sensor",
    }

    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "tampered": "On",
        "triggered": "On",
    }
    # Elements that map to selects. func class / func instance to name
    ITEM_SELECTS = {
        ("chirpMode", None): "Chime",
        ("triggerType", None): "Alarming State",
        ("bypassType", None): "Bypass",
    }

    async def initialize_elem(self, device: AferoDevice):
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        available: bool = False
        numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = {}
        selects: dict[tuple[str, str | None], features.SelectFeature] | None = {}
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        device_type: int | None = None
        config_key: str | None = None
        for state in device.states:
            if select := await self.initialize_select(device.functions, state):
                selects[select[0]] = select[1]
            elif state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, device.id):
                # Security System Sensors only have binary sensors
                binary_sensors[sensor.id] = sensor
            elif state.functionClass == "top-level-key":
                config_key = state.value
        self._items[device.id] = SecuritySystemSensor(
            _id=device.id,
            split_identifier=SENSOR_SPLIT_IDENTIFIER,
            config_key=config_key,
            available=available,
            sensors=sensors,
            binary_sensors=binary_sensors,
            numbers=numbers,
            selects=selects,
            device_information=DeviceInformation(
                device_class=device.device_class,
                default_image=device.default_image,
                default_name=device.default_name,
                manufacturer=device.manufacturerName,
                model=self.SENSOR_TYPES.get(device_type, "Unknown"),
                name=device.friendly_name,
                parent_id=device.device_id,
                functions=device.functions,
            ),
        )
        return self._items[device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set[str]:
        """Update the Security System Sensor with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        for state in afero_device.states:
            if state.functionClass == "available":
                if cur_item.available != state.value:
                    updated_keys.add("available")
                cur_item.available = state.value
            elif (update_key := await self.update_sensor(state, cur_item)) or (
                update_key := await self.update_select(state, cur_item)
            ):
                updated_keys.add(update_key)
        return updated_keys

    async def set_state(
        self,
        device_id: str,
        selects: dict[tuple[str, int | None], str] | None = None,
    ) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = SecuritySystemSensorPut()
        try:
            cur_item: SecuritySystemSensor = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if selects:
            chirp_modes = {y: x for x, y in GENERIC_MODES.items()}
            trigger_types = {y: x for x, y in TRIGGER_MODES.items()}
            bypass_types = {y: x for x, y in BYPASS_MODES.items()}
            # Load the current values as it all needs to be sent
            select_vals = {
                "chirpMode": chirp_modes[
                    cur_item.selects.get(("chirpMode", None)).selected
                ],
                "triggerType": trigger_types[
                    cur_item.selects.get(("triggerType", None)).selected
                ],
                "bypassType": bypass_types[
                    cur_item.selects.get(("bypassType", None)).selected
                ],
            }
            for select, select_val in selects.items():
                if select[0] == "chirpMode":
                    select_vals["chirpMode"] = chirp_modes[select_val]
                elif select[0] == "triggerType":
                    select_vals["triggerType"] = trigger_types[select_val]
                elif select[0] == "bypassType":
                    select_vals["bypassType"] = bypass_types[select_val]
                else:
                    continue
            update_obj.sensor_config = features.SecuritySensorConfigFeature(
                sensor_id=cur_item.instance, key_name=cur_item.config_key, **select_vals
            )
            await self.update(cur_item.id, obj_in=update_obj)
