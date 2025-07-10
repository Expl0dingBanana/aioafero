"""Controller holding and managing Afero IoT resources of type `security-system`."""

import copy

from ...device import AferoDevice, get_function_from_device
from ...errors import DeviceNotFound
from ...util import process_function
from ..models import SecuritySystem, SecuritySystemPut, features
from ..models.resource import DeviceInformation, ResourceTypes
from .base import AferoBinarySensor, AferoSensor, BaseResourcesController, NumbersName


def get_sensor_ids(device) -> set[int]:
    """Determine available sensors from the states"""
    sensor_ids = set()
    for state in device.states:
        if state.functionInstance is None:
            continue
        if state.functionInstance.startswith("sensor-") and state.value is not None:
            sensor_id = int(state.functionInstance.split("-", 1)[1])
            sensor_ids.add(sensor_id)
    return sensor_ids


def generate_sensor_name(afero_device, sensor_id: int) -> str:
    return f"{afero_device.id}-sensor-{sensor_id}"


def get_valid_states(afero_states: list, sensor_id: int) -> list:
    """Find states associated with the specific sensor"""
    valid_states: list = []
    for state in afero_states:
        if (
            state.functionClass not in ["sensor-state", "sensor-config"]
            or state.value is None
        ):
            continue
        state_sensor_split = state.functionInstance.rsplit("-", 1)
        state_sensor_id = int(state_sensor_split[1])
        if state_sensor_id != sensor_id:
            continue
        valid_states.append(state)
    return valid_states


def security_system_callback(devices: list[AferoDevice]) -> list[AferoDevice]:
    multi_devs: list[AferoDevice] = []
    for afero_device in devices:
        if afero_device.device_class == "security-system":
            for sensor_id in get_sensor_ids(afero_device):
                cloned = copy.deepcopy(afero_device)
                cloned.device_id = generate_sensor_name(afero_device, sensor_id)
                cloned.id = generate_sensor_name(afero_device, sensor_id)
                cloned.device_class = ResourceTypes.SECURITY_SYSTEM_SENSOR.value
                cloned.friendly_name = (
                    f"{afero_device.friendly_name} - Sensor {sensor_id}"
                )
                cloned.states = get_valid_states(afero_device.states, sensor_id)
                cloned.is_multi = True
                multi_devs.append(cloned)
    return multi_devs


class SecuritySystemController(BaseResourcesController[SecuritySystem]):
    """Controller holding and managing Afero IoT resources of type `security-system`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.SECURITY_SYSTEM]
    ITEM_CLS = SecuritySystem
    ITEM_MAPPING = {"alarm_state": "alarm-state"}
    # Sensors map functionClass -> Unit
    ITEM_SENSORS: dict[str, str] = {
        "alarm-state": None,
        "history-event": None,
        "disarmed-by": None,
    }
    # Binary sensors map key -> alerting value
    ITEM_BINARY_SENSORS: dict[str, str] = {
        "battery-powered": "battery-powered",
    }
    # Elements that map to numbers. func class / func instance to NumbersName
    ITEM_NUMBERS: dict[tuple[str, str | None], NumbersName] = {
        ("arm-exit-delay", "away"): NumbersName(
            unit="seconds", display_name="Arm Exit Delay Away"
        ),
        ("arm-exit-delay", "stay"): NumbersName(
            unit="seconds", display_name="Arm Exit Delay Home"
        ),
        ("temporary-bypass-time", None): NumbersName(
            unit="seconds", display_name="Bypass Time"
        ),
        ("disarm-entry-delay", None): NumbersName(
            unit="seconds", display_name="Disarm Entry Delay"
        ),
        ("siren-alarm-timeout", None): NumbersName(
            unit="seconds", display_name="Siren Timeout"
        ),
    }
    # Elements that map to Select. func class / func instance to name
    ITEM_SELECTS = {
        ("song-id", "alarm"): "Alarm Noise",
        ("volume", "siren"): "Alarm Volume",
        ("bypass-allowed", None): "Enable Temporary Bypass",
        ("song-id", "chime"): "Chime Noise",
        ("volume", "chime"): "Chime Volume",
        ("volume", "entry-delay"): "Entry Delay Volume",
        ("volume", "exit-delay-away"): "Exit Delay Volume Away",
        ("volume", "exit-delay-stay"): "Exit Delay Volume Home",
        # ("dark-mode", None): "KeyPad Dark Mode",
        # ("song-id", "beep"): "KeyPad Noise",
    }
    # Split sensors from the primary payload
    DEVICE_SPLIT_CALLBACKS: dict[str, callable] = {
        ResourceTypes.SECURITY_SYSTEM_SENSOR.value: security_system_callback
    }

    async def disarm(self, device_id: str) -> None:
        """Disarm the system"""
        await self.set_state(device_id, mode="disarmed")

    async def arm_home(self, device_id: str) -> None:
        """Arms the system while someone is home"""
        await self.set_state(device_id, mode="arm-started-stay")

    async def arm_away(self, device_id: str) -> None:
        """Arms the system while no one is home"""
        await self.set_state(device_id, mode="arm-started-away")

    async def alarm_trigger(self, device_id: str) -> None:
        """Manually trigger the alarm"""
        await self.set_state(device_id, mode="alarming-sos")

    async def initialize_elem(self, afero_device: AferoDevice) -> SecuritySystem:
        """Initialize the element"""
        available: bool = False
        alarm_state: features.ModeFeature | None = None
        siren_action: features.SecuritySensorSirenFeature | None = None
        numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = {}
        selects: dict[tuple[str, str | None], features.SelectFeature] | None = {}
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        for state in afero_device.states:
            func_def = get_function_from_device(
                afero_device.functions, state.functionClass, state.functionInstance
            )
            if state.functionClass == "available":
                available = state.value
            elif state.functionClass == "alarm-state":
                alarm_state = features.ModeFeature(
                    mode=state.value,
                    modes=set(
                        process_function(afero_device.functions, state.functionClass)
                    ),
                )
            elif sensor := await self.initialize_sensor(state, afero_device.device_id):
                if isinstance(sensor, AferoBinarySensor):
                    binary_sensors[sensor.id] = sensor
                else:
                    sensors[sensor.id] = sensor
            elif number := await self.initialize_number(func_def, state):
                numbers[number[0]] = number[1]
            elif select := await self.initialize_select(afero_device.functions, state):
                selects[select[0]] = select[1]
            elif state.functionClass == "siren-action":
                try:
                    result_code = state.value["security-siren-action"]["resultCode"]
                    command = state.value["security-siren-action"]["command"]
                except TypeError:
                    result_code = None
                    command = None
                siren_action = features.SecuritySensorSirenFeature(
                    result_code=result_code,
                    command=command,
                )

        self._items[afero_device.id] = SecuritySystem(
            afero_device.functions,
            id=afero_device.id,
            available=available,
            sensors=sensors,
            binary_sensors=binary_sensors,
            numbers=numbers,
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
            alarm_state=alarm_state,
            siren_action=siren_action,
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
            elif state.functionClass == "alarm-state":
                if cur_item.alarm_state.mode != state.value:
                    updated_keys.add(state.functionClass)
                cur_item.alarm_state.mode = state.value
            elif update_key := await self.update_sensor(state, cur_item):
                updated_keys.add(update_key)
            elif update_key := await self.update_number(state, cur_item):
                updated_keys.add(update_key)
            elif update_key := await self.update_select(state, cur_item):
                updated_keys.add(update_key)
            elif state.functionClass == "siren-action":
                try:
                    result_code = state.value["security-siren-action"]["resultCode"]
                    command = state.value["security-siren-action"]["command"]
                except TypeError:
                    result_code = None
                    command = None
                if (
                    result_code != cur_item.siren_action.result_code
                    or command != cur_item.siren_action.command
                ):
                    cur_item.siren_action.result_code = result_code
                    cur_item.siren_action.command = command
                    updated_keys.add("siren-action")

        return updated_keys

    async def set_state(
        self,
        device_id: str,
        mode: str | None = None,
        numbers: dict[tuple[str, str | None], float] | None = None,
        selects: dict[tuple[str, str | None], str] | None = None,
    ) -> None:
        """Set supported feature(s) to fan resource."""
        update_obj = SecuritySystemPut()
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if mode is not None:
            update_obj.alarm_state = features.ModeFeature(
                mode=mode,
                modes=cur_item.alarm_state.modes,
            )
            if "-started-" in mode:
                update_obj.siren_action = features.SecuritySensorSirenFeature(
                    result_code=0,
                    command=4,
                )
            elif mode == "alarming-sos":
                update_obj.siren_action = features.SecuritySensorSirenFeature(
                    result_code=0,
                    command=5,
                )
            else:
                update_obj.siren_action = features.SecuritySensorSirenFeature(
                    result_code=None,
                    command=None,
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
