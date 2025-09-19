"""Controller holding and managing Afero IoT resources of type `security-system-keypad`."""

from aioafero.device import AferoDevice
from aioafero.errors import DeviceNotFound
from aioafero.v1.models import SecuritySystemKeypad, SecuritySystemKeypadPut, features
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import AferoBinarySensor, BaseResourcesController


class SecuritySystemKeypadController(BaseResourcesController[SecuritySystemKeypad]):
    """Controller holding and managing Afero IoT resources of type `security-system-keypad`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.SECURITY_SYSTEM_KEYPAD]
    ITEM_CLS = SecuritySystemKeypad
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "tamper-detection": "tampered",
    }
    # Elements that map to Select. func class / func instance to name
    ITEM_SELECTS = {
        ("volume", "buzzer-volume"): "Buzzer Volume",
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> SecuritySystemKeypad:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        available: bool = False
        selects: dict[tuple[str, str | None], features.SelectFeature] | None = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        for state in afero_device.states:
            if state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.device_id):
                binary_sensors[sensor.id] = sensor
            elif select := await self.initialize_select(afero_device.functions, state):
                selects[select[0]] = select[1]

        self._items[afero_device.id] = SecuritySystemKeypad(
            _id=afero_device.id,
            available=available,
            binary_sensors=binary_sensors,
            selects=selects,
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
        """Update the Security System with the latest API data.

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
            elif (
                (update_key := await self.update_sensor(state, cur_item))
                or (update_key := await self.update_number(state, cur_item))
                or (update_key := await self.update_select(state, cur_item))
            ):
                updated_keys.add(update_key)

        return updated_keys

    async def set_state(
        self,
        device_id: str,
        selects: dict[tuple[str, str | None], str] | None = None,
    ) -> None:
        """Set supported feature(s) to Security System resource."""
        update_obj = SecuritySystemKeypadPut()
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
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
