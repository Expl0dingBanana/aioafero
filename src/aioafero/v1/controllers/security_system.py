"""Controller holding and managing Afero IoT resources of type `security-system`."""

import asyncio
import copy

from aioafero.device import (
    AferoCapability,
    AferoDevice,
    AferoState,
    get_function_from_device,
)
from aioafero.errors import DeviceNotFound, SecuritySystemError
from aioafero.util import process_function
from aioafero.v1.models import SecuritySystem, SecuritySystemPut, features
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import AferoBinarySensor, AferoSensor, BaseResourcesController, NumbersName
from .event import CallbackResponse

SENSOR_SPLIT_IDENTIFIER = "sensor"
GENERIC_MODES = {0: "Off", 1: "On"}
TRIGGER_MODES = {
    0: "Off",
    1: "Home",
    2: "Away",
    3: "Home/Away",
}
KNOWN_SENSOR_MODELS = {
    1: "Motion Sensor",
    2: "Door/Window Sensor",
}
BYPASS_MODES = {
    0: "Off",
    1: "Manual",
    4: "On",
}

UPDATE_TIME = 3  # Seconds after performing an action to refresh state


def get_sensor_ids(device) -> set[int]:
    """Determine available sensors from the states."""
    sensor_ids = set()
    for state in device.states:
        if state.functionInstance is None:
            continue
        if state.functionInstance.startswith("sensor-") and state.value is not None:
            sensor_id = int(state.functionInstance.split("-", 1)[1])
            sensor_ids.add(sensor_id)
    return sensor_ids


def generate_sensor_name(afero_device, sensor_id: int) -> str:
    """Generate the name for an instanced element."""
    return f"{afero_device.id}-{SENSOR_SPLIT_IDENTIFIER}-{sensor_id}"


def get_valid_states(afero_states: list, sensor_id: int) -> list:
    """Find states associated with the specific sensor."""
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
        top_level_key = list(state.value.keys())[0]
        if state.functionClass == "sensor-state":
            valid_states.append(
                AferoState(
                    functionClass="battery-level",
                    functionInstance=None,
                    value=state.value[top_level_key]["batteryLevel"],
                )
            )
            valid_states.append(
                AferoState(
                    functionClass="tampered",
                    functionInstance=None,
                    value=GENERIC_MODES[state.value[top_level_key]["tampered"]],
                )
            )
            valid_states.append(
                AferoState(
                    functionClass="triggered",
                    functionInstance=None,
                    value=GENERIC_MODES[state.value[top_level_key]["triggered"]],
                )
            )
            valid_states.append(
                AferoState(
                    functionClass="available",
                    functionInstance=None,
                    value=not bool(state.value[top_level_key]["missing"]),
                )
            )
        else:
            valid_states.append(
                AferoState(
                    functionClass="chirpMode",
                    functionInstance=None,
                    value=GENERIC_MODES[state.value[top_level_key]["chirpMode"]],
                )
            )
            valid_states.append(
                AferoState(
                    functionClass="triggerType",
                    functionInstance=None,
                    value=TRIGGER_MODES[state.value[top_level_key]["triggerType"]],
                )
            )
            valid_states.append(
                AferoState(
                    functionClass="bypassType",
                    functionInstance=None,
                    value=BYPASS_MODES[state.value[top_level_key]["bypassType"]],
                )
            )
            valid_states.append(
                AferoState(
                    functionClass="top-level-key",
                    functionInstance=None,
                    value=top_level_key,
                )
            )
    return valid_states


def get_model_type(states: list[AferoState], sensor_id: int) -> str:
    """Get the model type from the state list."""
    for state in states:
        if state.functionClass not in ["sensor-state"] or state.value is None:
            continue
        state_sensor_split = state.functionInstance.rsplit("-", 1)
        state_sensor_id = int(state_sensor_split[1])
        if state_sensor_id != sensor_id:
            continue
        top_level_key = list(state.value.keys())[0]
        return KNOWN_SENSOR_MODELS.get(
            int(state.value[top_level_key]["deviceType"]), "Unknown"
        )
    return "Unknown"


def get_valid_functions(afero_functions: list, sensor_id: int) -> list:
    """Find functions associated with the specific sensor."""
    valid_functions: list = []
    for func in afero_functions:
        if func["functionClass"] not in ["sensor-state", "sensor-config"]:
            continue
        sensor_split = func["functionInstance"].rsplit("-", 1)
        state_sensor_id = int(sensor_split[1])
        if state_sensor_id != sensor_id:
            continue
        if func["functionClass"] == "sensor-config":
            valid_functions.append(
                {
                    "functionClass": "chirpMode",
                    "functionInstance": func["functionInstance"],
                    "type": "category",
                    "values": [{"name": x} for x in GENERIC_MODES.values()],
                }
            )
            valid_functions.append(
                {
                    "functionClass": "triggerType",
                    "functionInstance": func["functionInstance"],
                    "type": "category",
                    "values": [{"name": x} for x in TRIGGER_MODES.values()],
                }
            )
            valid_functions.append(
                {
                    "functionClass": "bypassType",
                    "functionInstance": func["functionInstance"],
                    "type": "category",
                    "values": [{"name": x} for x in BYPASS_MODES.values()],
                }
            )
    return valid_functions


def get_sensor_name(afero_capabilities: list[AferoCapability], sensor_id: int) -> str:
    """Get the Afero name for a specific sensor."""
    for capability in afero_capabilities:
        if (
            capability.functionClass != "sensor-state"
            or capability.functionInstance != f"sensor-{sensor_id}"
            or capability.options.get("name") is None
        ):
            continue
        return capability.options["name"]
    return f"Sensor {sensor_id}"


def security_system_callback(afero_device: AferoDevice) -> CallbackResponse:
    """Convert an AferoDevice into multiple devices."""
    multi_devs: list[AferoDevice] = []
    if afero_device.device_class == "security-system":
        for sensor_id in get_sensor_ids(afero_device):
            cloned = copy.deepcopy(afero_device)
            cloned.device_id = generate_sensor_name(afero_device, sensor_id)
            cloned.id = generate_sensor_name(afero_device, sensor_id)
            cloned.split_identifier = SENSOR_SPLIT_IDENTIFIER
            cloned.device_class = ResourceTypes.SECURITY_SYSTEM_SENSOR.value
            cloned.friendly_name = f"{afero_device.friendly_name} - {get_sensor_name(afero_device.capabilities, sensor_id)}"
            cloned.states = get_valid_states(afero_device.states, sensor_id)
            cloned.functions = get_valid_functions(afero_device.functions, sensor_id)
            cloned.model = f"{afero_device.model} - {get_model_type(afero_device.states, sensor_id)}"
            multi_devs.append(cloned)
    return CallbackResponse(
        split_devices=multi_devs,
        remove_original=False,
    )


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

    async def disarm(self, device_id: str, disarm_pin: int) -> None:
        """Disarm the system."""
        await self.set_state(device_id, disarm_pin=disarm_pin)

    async def arm_home(self, device_id: str) -> None:
        """Arms the system while someone is home."""
        await self.set_state(device_id, command=4)

    async def arm_away(self, device_id: str) -> None:
        """Arms the system while no one is home."""
        await self.set_state(device_id, command=2)

    async def alarm_trigger(self, device_id: str) -> None:
        """Manually trigger the alarm."""
        await self.set_state(device_id, command=5)

    async def initialize_elem(self, afero_device: AferoDevice) -> SecuritySystem:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
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
            _id=afero_device.id,
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
                children=afero_device.children,
                functions=afero_device.functions,
            ),
            alarm_state=alarm_state,
            siren_action=siren_action,
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
            elif state.functionClass == "alarm-state":
                if cur_item.alarm_state.mode != state.value:
                    updated_keys.add(state.functionClass)
                cur_item.alarm_state.mode = state.value
            elif (
                (update_key := await self.update_sensor(state, cur_item))
                or (update_key := await self.update_number(state, cur_item))
                or (update_key := await self.update_select(state, cur_item))
            ):
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
        disarm_pin: int | None = None,
        command: int | None = None,
        numbers: dict[tuple[str, str | None], float] | None = None,
        selects: dict[tuple[str, str | None], str] | None = None,
    ) -> None:
        """Set supported feature(s) to Security System resource."""
        update_obj = SecuritySystemPut()
        force_mode = False
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if command is not None:
            force_mode = True
            if command != 5:
                await self.validate_arm_state(device_id, command)
            update_obj.siren_action = features.SecuritySensorSirenFeature(
                result_code=0,
                command=command,
            )
        if disarm_pin is not None:
            force_mode = True
            update_obj.disarm_pin = features.SecuritySystemDisarmPin(pin=disarm_pin)
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
        await self.update(
            device_id, obj_in=update_obj, send_duplicate_states=force_mode
        )
        # Ensure the correct pin was used
        if disarm_pin:
            await self.validate_disarm_pin(device_id)
        elif command:
            await self.refresh_alarm_state(device_id)

    async def refresh_alarm_state(self, device_id: str) -> None:
        """Refresh the alarm state after alarm state change command."""
        task = asyncio.create_task(asyncio.sleep(UPDATE_TIME))
        await task
        states = await self._bridge.fetch_device_states(device_id)
        device = self._bridge.get_afero_device(device_id)
        device.states = states
        await self._bridge.events.generate_events_from_update(device)

    async def validate_disarm_pin(self, device_id: str) -> None:
        """Ensure the system has switched to disarmed."""
        # alarm-state does not update immediately, so wait and recheck
        task = asyncio.create_task(asyncio.sleep(UPDATE_TIME))
        await task
        states = await self._bridge.fetch_device_states(device_id)
        for state in states:
            if state.functionClass != "alarm-state":
                continue
            if state.value != "disarmed":
                raise SecuritySystemError("Disarm PIN was not accepted")
        device = self._bridge.get_afero_device(device_id)
        device.states = states
        await self._bridge.events.generate_events_from_update(device)

    async def validate_arm_state(self, device_id: str, arm_type: int) -> bool:
        """Ensure the system can arm."""
        dev = self._bridge.get_afero_device(device_id)
        sensors_with_issues = []
        num_sensors = 0
        for child in dev.children:
            controller = self._bridge.get_device_controller(child)
            if type(controller).__name__ != "SecuritySystemSensorController":
                continue
            sensor = controller[child]
            if (
                # Generic Bypass
                sensor.selects.get(("bypassType", None)).selected in ["Manual", "On"]
                or
                # Arm Away Bypass
                (
                    arm_type == 2
                    and sensor.selects.get(("triggerType", None)).selected
                    not in ["Away", "Home/Away"]
                )
                or
                # Arm Home Bypass
                (
                    arm_type == 4
                    and sensor.selects.get(("triggerType", None)).selected
                    not in ["Home", "Home/Away"]
                )
            ):
                self._logger.debug("Bypassing sensor %s", sensor.id)
                continue
            if sensor.available is False:
                sensors_with_issues.append(
                    f"{sensor.device_information.name} (Unavailable)"
                )
            if sensor.binary_sensors.get("triggered|None").current_value == "On":
                sensors_with_issues.append(
                    f"{sensor.device_information.name} (Triggered)"
                )
            if sensor.binary_sensors.get("tampered|None").current_value == "On":
                sensors_with_issues.append(
                    f"{sensor.device_information.name} (Tampered)"
                )
            num_sensors += 1
        if sensors_with_issues:
            raise SecuritySystemError(
                f"Sensors are open or unavailable: {', '.join(sensors_with_issues)}"
            )
        if num_sensors == 0:
            raise SecuritySystemError(
                "No sensors are configured for the requested mode."
            )
        return True
