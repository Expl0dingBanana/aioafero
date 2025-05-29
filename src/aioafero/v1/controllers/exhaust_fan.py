"""Controller holding and managing Afero IoT resources of type `exhaust-fan`."""

from ...device import AferoDevice, get_function_from_device
from ...errors import DeviceNotFound
from ..models import features
from ..models.exhaust_fan import ExhaustFan, ExhaustFanPut
from ..models.features import NumbersFeature, SelectFeature
from ..models.resource import DeviceInformation, ResourceTypes
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController


class ExhaustFanController(BaseResourcesController[ExhaustFan]):
    """Controller holding and managing Afero IoT resources of type `exhaust-fan`.

    An exhaust fan tracks sensors, numbers, and selects. Toggles are controlled by
    SwitchController, fan is controlled by FanController, and light is controlled
    by LightController.
    """

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.EXHAUST_FAN]
    ITEM_CLS = ExhaustFan
    ITEM_MAPPING = {}
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {}
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "motion-detection": "motion-detected",
        "humidity-threshold-met": "above-threshold",
    }
    # Elements that map to numbers. func class / func instance to unit
    ITEM_NUMBERS: dict[tuple[str, str | None], str] = {
        ("auto-off-timer", "auto-off"): "seconds",
    }
    # Elements that map to selects. func class / func instance to name
    ITEM_SELECTS = {
        ("motion-action", "exhaust-fan"): "Motion Action",
        ("sensitivity", "humidity-sensitivity"): "Humidity Sensitivity",
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> ExhaustFan:
        """Initialize the element"""
        self._logger.info("Initializing %s", afero_device.id)
        available: bool = False
        numbers: dict[tuple[str, str], features.NumbersFeature] = {}
        selects: dict[tuple[str, str], features.SelectFeature] = {}
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        for state in afero_device.states:
            func_def = get_function_from_device(
                afero_device.functions, state.functionClass, state.functionInstance
            )
            if number := await self.initialize_number(func_def, state):
                numbers[number[0]] = number[1]
            elif select := await self.initialize_select(afero_device.functions, state):
                selects[select[0]] = select[1]
            elif state.functionClass == "available":
                available = state.value
            elif sensor := await self.initialize_sensor(state, afero_device.device_id):
                binary_sensors[sensor.id] = sensor

        self._items[afero_device.id] = ExhaustFan(
            afero_device.functions,
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
            ),
            numbers=numbers,
            selects=selects,
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        for state in afero_device.states:
            if state.functionClass == "available":
                if cur_item.available != state.value:
                    updated_keys.add("available")
                cur_item.available = state.value
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)
            elif update_key := await self.update_number(state, cur_item):
                updated_keys.add(update_key)
            elif update_key := await self.update_select(state, cur_item):
                updated_keys.add(update_key)
        return updated_keys

    async def set_state(
        self,
        device_id: str,
        numbers: dict[tuple[str, str], float] | None = None,
        selects: dict[tuple[str, str], str] | None = None,
    ) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = ExhaustFanPut()
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if numbers:
            for key, val in numbers.items():
                if key not in cur_item.numbers:
                    continue
                update_obj.numbers[key] = NumbersFeature(
                    value=val,
                    min=cur_item.numbers[key].min,
                    max=cur_item.numbers[key].max,
                    step=cur_item.numbers[key].step,
                    name=cur_item.numbers[key].name,
                    unit=cur_item.numbers[key].unit,
                )
        if selects:
            for key, val in selects.items():
                if key not in cur_item.selects:
                    continue
                update_obj.selects[key] = SelectFeature(
                    selected=val,
                    selects=cur_item.selects[key].selects,
                    name=cur_item.selects[key].name,
                )

        await self.update(device_id, obj_in=update_obj)
