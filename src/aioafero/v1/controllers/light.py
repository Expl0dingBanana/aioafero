"""Controller holding and managing Hubspace resources of type `light`."""

from contextlib import suppress
import copy
from dataclasses import replace
import logging

from aioafero import device, errors
from aioafero.device import AferoDevice, AferoState
from aioafero.util import process_range
from aioafero.v1.models import features
from aioafero.v1.models.light import Light, LightChannel, LightPut
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .base import AferoBinarySensor, AferoSensor, BaseResourcesController, NumbersName
from .event import CallbackResponse

SPLIT_IDENTIFIER: str = "light"

logger = logging.getLogger(__name__)


def process_names(values: list[dict]) -> set[str]:
    """Extract unique names from the elements."""
    vals = set()
    for val in values:
        vals.add(val["name"])
    return vals


def generate_split_name(afero_device: AferoDevice, instance: str) -> str:
    """Generate the name for an instanced element."""
    return f"{afero_device.id}-{SPLIT_IDENTIFIER}-{instance}"


def _channel_brightness_instances(afero_dev: AferoDevice) -> set[str]:
    """Collect non-primary brightness instances from states, functions, and capabilities."""
    instances: set[str] = set()
    for state in afero_dev.states:
        if state.functionClass == "brightness" and state.functionInstance not in (
            None,
            "global",
            "primary",
        ):
            instances.add(state.functionInstance)
    for func in afero_dev.functions or []:
        instance = func.get("functionInstance")
        if func.get("functionClass") == "brightness" and instance not in (
            None,
            "global",
            "primary",
        ):
            instances.add(instance)
    for cap in getattr(afero_dev, "capabilities", None) or []:
        if cap.functionClass == "brightness" and cap.functionInstance not in (
            None,
            "global",
            "primary",
        ):
            instances.add(cap.functionInstance)
    return instances


def is_dual_channel_rgb_fixture(afero_dev: AferoDevice) -> bool:
    """Return True for RGB+WW fixtures with color and white brightness channels."""
    instances = _channel_brightness_instances(afero_dev)
    return "color" in instances and "white" in instances


def preferred_brightness_instance(afero_dev: AferoDevice) -> str | None:
    """Return the overall brightness instance for dual-channel lights."""
    instances = [
        state.functionInstance
        for state in afero_dev.states
        if state.functionClass == "brightness"
    ]
    if "primary" in instances:
        return "primary"
    if None in instances:
        return None
    return instances[-1] if instances else None


def should_use_brightness_state(afero_dev: AferoDevice, state: AferoState) -> bool:
    """Return whether a brightness state should populate Light.dimming."""
    if state.functionClass != "brightness":
        return True
    if afero_dev.split_identifier:
        return True
    if not is_dual_channel_rgb_fixture(afero_dev):
        return True
    return state.functionInstance == preferred_brightness_instance(afero_dev)


def resolve_brightness_instance(
    cur_item: Light,
    *,
    color_mode: str | None = None,
    color: tuple[int, int, int] | None = None,
    temperature: int | None = None,
    effect: str | None = None,
    channel: str | None = None,
) -> str | None:
    """Return the brightness functionInstance to PUT for dual-channel fixtures."""
    if not cur_item.is_dual_channel:
        return cur_item.dimming.function_instance if cur_item.dimming else None
    if channel in cur_item.channels:
        return channel
    if color is not None or effect is not None or color_mode in ("color", "sequence"):
        return "color" if "color" in cur_item.channels else None
    if temperature is not None or color_mode == "white":
        return "white" if "white" in cur_item.channels else None
    active_mode = color_mode
    if active_mode is None and cur_item.color_mode is not None:
        active_mode = cur_item.color_mode.mode
    if active_mode in ("color", "sequence") and "color" in cur_item.channels:
        return "color"
    if active_mode == "white" and "white" in cur_item.channels:
        return "white"
    return cur_item.dimming.function_instance if cur_item.dimming else "primary"


def resolve_color_mode(cur_item: Light, color_mode: str | None) -> str | None:
    """Return the color-mode to PUT for dual-channel fixtures.

    Exclusive ``color`` / ``white`` becomes ``mixed`` when another channel is
    already on, so the write does not shut off the other driver.
    """
    if (
        color_mode not in ("color", "white")
        or not cur_item.is_dual_channel
        or "mixed" not in (cur_item.color_modes or [])
    ):
        return color_mode
    if any(
        name != color_mode and ch.on is True for name, ch in cur_item.channels.items()
    ):
        return "mixed"
    return color_mode


def color_mode_after_channel_off(cur_item: Light, channel: str) -> str | None:
    """Return color-mode after turning ``channel`` off.

    When another channel remains on, switch to that exclusive mode (or
    ``mixed`` if more than one remains). When nothing remains on, return
    ``None`` so color-mode is left unchanged.
    """
    remaining = [
        name
        for name, ch in cur_item.channels.items()
        if name != channel and ch.on is True
    ]
    if len(remaining) == 1 and remaining[0] in ("color", "white"):
        return remaining[0]
    if len(remaining) > 1 and "mixed" in (cur_item.color_modes or []):
        return "mixed"
    return None


def apply_brightness_state_update(
    afero_device: AferoDevice,
    cur_item: Light,
    state: AferoState,
    updated_keys: set[str],
) -> None:
    """Apply an inbound brightness state to channels and/or overall dimming."""
    instance = state.functionInstance
    if cur_item.is_dual_channel and instance in cur_item.channels:
        new_val = int(state.value)
        channel = cur_item.channels[instance]
        if channel.brightness != new_val:
            channel.brightness = new_val
            updated_keys.add("channels")
    if not should_use_brightness_state(afero_device, state):
        return
    new_val = int(state.value)
    if cur_item.dimming.brightness != new_val:
        cur_item.dimming.brightness = new_val
        updated_keys.add("dimming")
    if cur_item.dimming.function_instance != instance:
        cur_item.dimming.function_instance = instance
        updated_keys.add("dimming")


def get_split_instances(
    afero_dev: AferoDevice,
) -> list[tuple[str, ResourceTypes]]:
    """Determine available instances from the states."""
    instances = set()
    lights = []
    toggles = []
    dual_channel = is_dual_channel_rgb_fixture(afero_dev)
    for state in afero_dev.states:
        # We do not want to add something that controls everything, but individual only
        # We should skip None as its typically a single instance
        if state.functionInstance in ["global", "primary", None]:
            continue
        if state.functionClass == "brightness":
            lights.append(state.functionInstance)
        elif state.functionClass == "toggle":
            toggles.append(state.functionInstance)
    # Dual-channel: stay one light; color/white toggles stay on Light.channels
    # (not Switch clones). True multi-zone (main/trim): split into lights.
    if len(lights) > 1 and not dual_channel:
        for light_instance in lights:
            instances.add((light_instance, ResourceTypes.LIGHT))
    for toggle_instance in toggles:
        if toggle_instance in [x[0] for x in instances]:
            continue
        if dual_channel and toggle_instance in ("color", "white"):
            continue
        instances.add((toggle_instance, ResourceTypes.SWITCH))
    return sorted(instances)


def state_belongs_to_light_instance(
    afero_dev: AferoDevice,
    state: AferoState,
    instance: str,
) -> bool:
    """Return whether a state belongs to a light zone instance."""
    if state.functionClass == "available":
        return True
    if state.functionInstance in (None, "global", "primary"):
        return False
    return state.functionInstance == instance


def state_matches_instance(afero_device: AferoDevice, state: AferoState) -> bool:
    """Return whether a state belongs to a split light instance."""
    if not afero_device.split_identifier:
        return True
    instance = afero_device.id.rsplit(f"-{afero_device.split_identifier}-", 1)[1]
    return state_belongs_to_light_instance(afero_device, state, instance)


def resolve_function_instance(afero_device: AferoDevice) -> str | None:
    """Return the functionInstance key for this light resource (split zone or single)."""
    if afero_device.split_identifier:
        return afero_device.id.rsplit(f"-{afero_device.split_identifier}-", 1)[1]
    for state in afero_device.states:
        if state.functionClass == "color-mode":
            return state.functionInstance
    return None


def _color_mode_function_values(afero_device: AferoDevice) -> list[dict]:
    """Return the ``values`` list for this zone's color-mode function."""
    instance = resolve_function_instance(afero_device)
    for function in afero_device.functions:
        if function.get("functionClass") != "color-mode":
            continue
        if function.get("functionInstance") == instance:
            return list(function.get("values", []))
    for function in afero_device.functions:
        if function.get("functionClass") == "color-mode":
            return list(function.get("values", []))
    return []


def get_color_modes_for_device(afero_device: AferoDevice) -> list[str]:
    """Return supported color-mode names for this zone's color-mode function."""
    return [value["name"] for value in _color_mode_function_values(afero_device)]


def get_color_mode_hints_for_device(afero_device: AferoDevice) -> dict[str, list[str]]:
    """Return category hints keyed by color-mode name (e.g. ``no-brightness``)."""
    return {
        value["name"]: list(value["hints"])
        for value in _color_mode_function_values(afero_device)
        if value.get("name") and value.get("hints")
    }


def get_valid_states(
    afero_dev: AferoDevice,
    instance: str,
) -> list:
    """Find states associated with the specific instance."""
    return [
        state
        for state in afero_dev.states
        if state_belongs_to_light_instance(afero_dev, state, instance)
    ]


def light_callback(afero_device: AferoDevice) -> CallbackResponse:
    """Convert an AferoDevice into multiple devices."""
    multi_devs: list[AferoDevice] = []
    remove_parent: bool = False
    instances = get_split_instances(afero_device)
    logger.debug("Light instances found: %s", instances)
    light_instances = [x[0] for x in instances if x[1] == ResourceTypes.LIGHT]
    children: list[str] = []
    if afero_device.device_class == ResourceTypes.LIGHT.value:
        for instance, resource_type in instances:
            instance_name = instance or "primary"
            cloned = copy.deepcopy(afero_device)
            cloned.device_class = resource_type.value
            cloned.id = generate_split_name(afero_device, instance)
            cloned.split_identifier = SPLIT_IDENTIFIER
            cloned.friendly_name = f"{afero_device.friendly_name} - {instance_name}"
            cloned.states = get_valid_states(afero_device, instance)
            cloned.children = []
            multi_devs.append(cloned)
            children.append(cloned.id)
    if len(light_instances) > 1 and None not in light_instances:
        remove_parent = True
        cloned = copy.deepcopy(afero_device)
        valid_states = [
            state
            for state in afero_device.states
            if state.functionClass
            in [
                "available",
                "wifi-ssid",
                "wifi-rssi",
                "wifi-steady-state",
                "wifi-setup-state",
                "wifi-mac-address",
                "ble-mac-address",
            ]
        ]
        cloned.states = valid_states
        cloned.children = children
        cloned.device_class = "parent-device"
        multi_devs.append(cloned)
    return CallbackResponse(
        split_devices=multi_devs,
        remove_original=remove_parent,
    )


class LightController(BaseResourcesController[Light]):
    """Light devices on ``bridge.lights`` (including split zones)."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.LIGHT]
    ITEM_CLS = Light
    ITEM_NUMBERS: dict[tuple[str, str | None], NumbersName] = {
        ("speed", "color-sequence"): NumbersName(
            unit="speed", display_name="Effect Speed"
        ),
    }
    DEVICE_SPLIT_CALLBACKS: dict[str, callable] = {
        ResourceTypes.LIGHT.value: light_callback,
    }

    async def turn_on(self, device_id: str) -> None:
        """Turn on the light.

        Args:
            device_id: Device ID from this controller.

        """
        await self.set_state(device_id, on=True)

    async def turn_off(self, device_id: str) -> None:
        """Turn off the light.

        Args:
            device_id: Device ID from this controller.

        """
        await self.set_state(device_id, on=False)

    async def set_color_temperature(self, device_id: str, temperature: int) -> None:
        """Set color temperature or white mode when CCT is unavailable.

        Args:
            device_id: Device ID from this controller.
            temperature: Color temperature in kelvin.

        """
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if cur_item.color_temperature is not None:
            await self.set_state(
                device_id, on=True, temperature=temperature, color_mode="white"
            )
        elif cur_item.supports_color_white:
            self._logger.info(
                "Device %s has no color-temperature function; ignoring %d K",
                device_id,
                temperature,
            )
            await self.set_white(device_id, on=True)
        else:
            self._logger.info(
                "Device %s does not support color temperature or white mode", device_id
            )

    async def set_white(
        self,
        device_id: str,
        *,
        on: bool | None = True,
        brightness: int | None = None,
    ) -> None:
        """Set white mode without a color-temperature function.

        Args:
            device_id: Device ID from this controller.
            on: Power state (defaults to ``True``).
            brightness: Brightness percentage when ``on`` is ``True``.

        """
        await self.set_state(
            device_id, on=on, color_mode="white", brightness=brightness
        )

    async def set_brightness(self, device_id: str, brightness: int) -> None:
        """Set brightness, turning the light on if needed.

        Args:
            device_id: Device ID from this controller.
            brightness: Brightness percentage.

        """
        await self.set_state(device_id, on=True, brightness=brightness)

    async def set_rgb(self, device_id: str, red: int, green: int, blue: int) -> None:
        """Set RGB color, turning the light on if needed.

        Args:
            device_id: Device ID from this controller.
            red: Red channel ``0``–``255``.
            green: Green channel ``0``–``255``.
            blue: Blue channel ``0``–``255``.

        """
        await self.set_state(
            device_id, on=True, color=(red, green, blue), color_mode="color"
        )

    async def set_effect(self, device_id: str, effect: str) -> None:
        """Set a color sequence effect, turning the light on if needed.

        Args:
            device_id: Device ID from this controller.
            effect: Effect name from the model's ``effect.effects`` list.

        """
        await self.set_state(device_id, on=True, effect=effect, color_mode="sequence")

    async def initialize_elem(self, afero_device: AferoDevice) -> Light:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        available: bool = False
        on: features.OnFeature | None = None
        color_temp: features.ColorTemperatureFeature | None = None
        color: features.ColorFeature | None = None
        color_mode: features.ColorModeFeature | None = None
        dimming: features.DimmingFeature | None = None
        effect: features.EffectFeature | None = None
        sensors: dict[str, AferoSensor] = {}
        binary_sensors: dict[str, AferoBinarySensor] = {}
        numbers: dict[tuple[str, str | None], features.NumbersFeature] = {}
        dual_channel = is_dual_channel_rgb_fixture(afero_device)
        channels: dict[str, LightChannel] = {}
        color_seq_states: dict[str | None, AferoState] = {}
        if dual_channel:
            for name in _channel_brightness_instances(afero_device):
                channels[name] = LightChannel()
        for state in afero_device.states:
            func_def = device.get_function_from_device(
                afero_device.functions, state.functionClass, state.functionInstance
            )
            if state.functionClass == "power" or (
                afero_device.split_identifier and state.functionClass == "toggle"
            ):
                on = features.OnFeature(
                    on=state.value == "on",
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif state.functionClass == "color-temperature":
                if len(func_def["values"]) > 1:
                    avail_temps = process_color_temps(func_def["values"])
                else:
                    avail_temps = process_range(func_def["values"][0])
                prefix = "K" if func_def.get("type", None) != "numeric" else ""
                current_temp = state.value
                if isinstance(current_temp, str) and current_temp.endswith("K"):
                    current_temp = current_temp[:-1]
                color_temp = features.ColorTemperatureFeature(
                    temperature=int(current_temp),
                    supported=avail_temps,
                    prefix=prefix,
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif state.functionClass == "brightness":
                instance = state.functionInstance
                if dual_channel and instance in channels:
                    channels[instance].brightness = int(state.value)
                if should_use_brightness_state(afero_device, state):
                    temp_bright = process_range(func_def["values"][0])
                    dimming = features.DimmingFeature(
                        brightness=int(state.value),
                        supported=temp_bright,
                        function_class=state.functionClass,
                        function_instance=state.functionInstance,
                    )
            elif state.functionClass == "color-sequence":
                color_seq_states[state.functionInstance] = state
            elif state.functionClass == "color-rgb":
                color = features.ColorFeature(
                    red=state.value["color-rgb"].get("r", 0),
                    green=state.value["color-rgb"].get("g", 0),
                    blue=state.value["color-rgb"].get("b", 0),
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif state.functionClass == "color-mode":
                color_mode = features.ColorModeFeature(
                    mode=state.value,
                    function_class=state.functionClass,
                    function_instance=state.functionInstance,
                )
            elif state.functionClass == "available":
                available = state.value
            elif dual_channel and state.functionClass == "toggle":
                instance = state.functionInstance
                if instance in channels:
                    channels[instance].on = state.value == "on"
            if number := await self.initialize_number(func_def, state):
                numbers[number[0]] = number[1]

        effects = process_effects(afero_device.functions)
        current_effect = resolve_effect_value(effects, color_seq_states)
        if current_effect is not None:
            preset_state = color_seq_states["preset"]
            effect = features.EffectFeature(
                effect=current_effect,
                effects=effects,
                function_class=preset_state.functionClass,
                function_instance=preset_state.functionInstance,
            )

        supported_color_modes = get_color_modes_for_device(afero_device)
        color_mode_hints = get_color_mode_hints_for_device(afero_device)

        self._items[afero_device.id] = Light(
            _id=afero_device.id,
            available=available,
            split_identifier=afero_device.split_identifier,
            channels=channels,
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
            on=on,
            dimming=dimming,
            color_mode=color_mode,
            color_temperature=color_temp,
            color=color,
            color_modes=supported_color_modes,
            color_mode_hints=color_mode_hints or None,
            effect=effect,
            numbers=numbers,
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        """Update the Light with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        cur_item = self.get_device(afero_device.id)
        updated_keys = set()
        color_seq_states: dict[str | None, AferoState] = {}
        for state in afero_device.states:
            # Split clones are pre-filtered in light_callback; this guards other paths.
            if not state_matches_instance(afero_device, state):
                continue
            if state.functionClass == "power" or (
                afero_device.split_identifier and state.functionClass == "toggle"
            ):
                new_val = state.value == "on"
                if cur_item.on.on != new_val:
                    cur_item.on.on = new_val
                    updated_keys.add("on")
            elif state.functionClass == "color-temperature":
                if cur_item.color_temperature is None:
                    continue
                current_temp = state.value
                if isinstance(current_temp, str) and current_temp.endswith("K"):
                    current_temp = current_temp[:-1]
                new_val = int(current_temp)
                if cur_item.color_temperature.temperature != new_val:
                    cur_item.color_temperature.temperature = new_val
                    updated_keys.add("color_temperature")
            elif state.functionClass == "brightness":
                apply_brightness_state_update(
                    afero_device, cur_item, state, updated_keys
                )
            elif state.functionClass == "color-sequence":
                color_seq_states[state.functionInstance] = state
            elif state.functionClass == "color-rgb":
                color_red = state.value["color-rgb"].get("r", 0)
                color_green = state.value["color-rgb"].get("g", 0)
                color_blue = state.value["color-rgb"].get("b", 0)
                if (
                    cur_item.color.red != color_red
                    or cur_item.color.green != color_green
                    or cur_item.color.blue != color_blue
                ):
                    cur_item.color.red = color_red
                    cur_item.color.green = color_green
                    cur_item.color.blue = color_blue
                    updated_keys.add("color")
            elif state.functionClass == "color-mode":
                if cur_item.color_mode.mode != state.value:
                    cur_item.color_mode.mode = state.value
                    updated_keys.add("color_mode")
            elif state.functionClass == "toggle":
                instance = state.functionInstance
                if instance in cur_item.channels:
                    new_val = state.value == "on"
                    if cur_item.channels[instance].on != new_val:
                        cur_item.channels[instance].on = new_val
                        updated_keys.add("channels")
            elif state.functionClass == "available":
                if cur_item.available != state.value:
                    cur_item.available = state.value
                    updated_keys.add("available")
            elif (update_key := await self.update_number(state, cur_item)) or (
                update_key := await self.update_select(state, cur_item)
            ):
                updated_keys.add(update_key)

        # Several states hold the effect, but its always derived from the preset functionInstance
        return updated_keys.union(
            await self.update_elem_color(cur_item, color_seq_states)
        )

    async def update_elem_color(
        self,
        cur_item: Light,
        color_seq_states: dict[str | None, AferoState],
    ) -> set:
        """Perform the update for effects."""
        if cur_item.effect is None:
            return set()
        new_effect = resolve_effect_value(cur_item.effect.effects, color_seq_states)
        if new_effect is None or cur_item.effect.effect == new_effect:
            return set()
        cur_item.effect.effect = new_effect
        return {"effect"}

    async def set_state(
        self,
        device_id: str,
        *,
        on: bool | None = None,
        temperature: int | None = None,
        brightness: int | None = None,
        color_mode: str | None = None,
        color: tuple[int, int, int] | None = None,
        effect: str | None = None,
        force_white_mode: int | None = None,
        numbers: dict[tuple[str, str | None], float] | None = None,
        channel: str | None = None,
    ) -> None:
        """Update light state in the cloud.

        Args:
            device_id: Device ID from this controller.
            on: Power state.
            temperature: Color temperature in kelvin.
            brightness: Brightness percentage.
            color_mode: API color mode (``white``, ``color``, ``sequence``,
                ``night-light``, etc.).
            color: RGB tuple ``(red, green, blue)``.
            effect: Named color sequence effect.
            force_white_mode: Brightness to apply after forcing white mode.
            numbers: Number features keyed by ``(functionClass, functionInstance)``.
            channel: When set, target that dual-channel instance (``color`` /
                ``white``): ``on`` uses the channel toggle, and brightness is
                routed to that channel when ``color_mode`` is omitted. Turning
                a channel off also moves ``color-mode`` to the remaining
                channel when one is still on. Unknown channel names are
                ignored (logged) and do not fall through to primary power.

        ``no-brightness`` modes omit brightness and, when turning on from off,
        select the mode before power (aborting if that PUT fails). Turn-off
        never includes a color-mode change.

        """
        update_obj = LightPut()
        try:
            cur_item = self.get_device(device_id)
        except errors.DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        channel_requested = channel is not None
        channel_valid = bool(channel and channel in cur_item.channels)
        if channel_requested and not channel_valid:
            self._logger.warning(
                "Ignoring unknown light channel %r for device %s",
                channel,
                device_id,
            )
            channel = None
        if on is False and (color_mode is not None or force_white_mode is not None):
            self._logger.warning(
                "Ignoring color-mode changes while turning off %s "
                "(color_mode=%s, force_white_mode=%s)",
                device_id,
                color_mode,
                force_white_mode,
            )
            color_mode = None
            force_white_mode = None
        no_brightness = color_mode is not None and cur_item.color_mode_has_hint(
            color_mode, "no-brightness"
        )
        if no_brightness:
            brightness = None
        if (
            on is True
            and not cur_item.is_on
            and no_brightness
            and cur_item.color_mode is not None
        ):
            mode_res = await self.update(
                device_id,
                obj_in=LightPut(
                    color_mode=replace(cur_item.color_mode, mode=color_mode)
                ),
                send_duplicate_states=True,
            )
            if not mode_res:
                self._logger.warning(
                    "Failed to select color-mode %s before power-on for %s; "
                    "aborting turn-on",
                    color_mode,
                    device_id,
                )
                return
        if on is not None:
            if channel_valid:
                update_obj.on = features.OnFeature(
                    on=on,
                    function_class="toggle",
                    function_instance=channel,
                )
            elif not channel_requested:
                # Only touch primary power when the caller did not intend a
                # channel toggle (unknown channel= must not fall through).
                update_obj.on = replace(cur_item.on, on=on)
        if force_white_mode is not None:
            update_obj.color_mode = replace(cur_item.color_mode, mode="white")
            update_obj.dimming = replace(cur_item.dimming, brightness=force_white_mode)
            send_duplicate_states = True
        else:
            send_duplicate_states = _populate_light_put(
                update_obj,
                cur_item,
                on=on,
                temperature=temperature,
                brightness=brightness,
                color_mode=color_mode,
                color=color,
                effect=effect,
                numbers=numbers,
                channel=channel,
                channel_valid=channel_valid,
            )
        await self.update(
            device_id, obj_in=update_obj, send_duplicate_states=send_duplicate_states
        )


def _populate_light_put(
    update_obj: LightPut,
    cur_item: Light,
    *,
    on: bool | None,
    temperature: int | None,
    brightness: int | None,
    color_mode: str | None,
    color: tuple[int, int, int] | None,
    effect: str | None,
    numbers: dict[tuple[str, str | None], float] | None,
    channel: str | None,
    channel_valid: bool,
) -> bool:
    """Apply non-force-white fields to ``update_obj``.

    Returns:
        Whether duplicate states must be sent for this update.

    """
    send_duplicate_states = False
    if numbers:
        for key, val in numbers.items():
            if key not in cur_item.numbers:
                continue
            update_obj.numbers[key] = replace(
                cur_item.numbers[key],
                value=val,
            )
    if temperature is not None and cur_item.color_temperature is not None:
        adjusted_temp = min(
            cur_item.color_temperature.supported,
            key=lambda x: abs(x - temperature),
        )
        update_obj.color_temperature = replace(
            cur_item.color_temperature,
            temperature=adjusted_temp,
        )
        if color_mode is None:
            color_mode = "white"
    elif temperature is not None and cur_item.supports_color_white:
        if color_mode is None:
            color_mode = "white"
    channel_turning_off = channel_valid and on is False
    if channel_valid and color_mode is None:
        if channel_turning_off:
            color_mode = color_mode_after_channel_off(cur_item, channel)
        else:
            color_mode = "color" if channel == "color" else "white"
    # Route brightness using the intended exclusive mode before upgrading to
    # mixed (so RGB still dims the color channel while both channels stay on).
    brightness_color_mode = color_mode
    if color_mode is not None and not channel_turning_off:
        color_mode = resolve_color_mode(cur_item, color_mode)
    if brightness is not None and cur_item.dimming is not None:
        update_obj.dimming = replace(
            cur_item.dimming,
            brightness=brightness,
            function_instance=resolve_brightness_instance(
                cur_item,
                color_mode=brightness_color_mode,
                color=color,
                temperature=temperature,
                effect=effect,
                channel=channel if channel_valid else None,
            ),
        )
    if color is not None and cur_item.color is not None:
        update_obj.color = replace(
            cur_item.color, red=color[0], green=color[1], blue=color[2]
        )
    if color_mode is not None and cur_item.color_mode is not None:
        update_obj.color_mode = replace(cur_item.color_mode, mode=color_mode)
        # No-CCT zones that support white (e.g. accent trim with RGB) must always
        # PUT color-mode white when requested. Skipping unchanged fields leaves the
        # device in RGB when cache is stale or the user re-selects white in HA.
        if (
            color_mode == "white"
            and cur_item.color_temperature is None
            and cur_item.supports_color_white
        ):
            send_duplicate_states = True
    if effect is not None and cur_item.effect is not None:
        update_obj.effect = replace(cur_item.effect, effect=effect)
    return send_duplicate_states


def process_color_temps(color_temps: dict) -> list[int]:
    """Determine the supported color temps.

    :param color_temps: Result from functions["values"]
    """
    supported_temps = []
    for temp in color_temps:
        color_temp = temp["name"]
        if isinstance(color_temp, str) and color_temp.endswith("K"):
            color_temp = color_temp[0:-1]
        supported_temps.append(int(color_temp))
    return sorted(supported_temps)


def process_effects(functions: list[dict]) -> dict[str, set]:
    """Determine the supported effects."""
    supported_effects = {}
    for function in functions:
        if function["functionClass"] == "color-sequence":
            supported_effects[function["functionInstance"]] = set(
                process_names(function["values"])
            )
    # custom shouldn't be a value in preset
    with suppress(KeyError):
        supported_effects["preset"].remove("custom")
    return supported_effects


def resolve_effect_value(
    effects: dict[str, set[str]],
    states: dict[str | None, AferoState],
) -> str | None:
    """Resolve the active effect from plural color-sequence states."""
    preset_state = states.get("preset")
    if preset_state is None or not isinstance(preset_state.value, str):
        return None
    preset_value = preset_state.value
    if preset_value in effects.get("preset", ()):
        return preset_value
    selected_state = states.get(preset_value)
    if selected_state is None or not isinstance(selected_state.value, str):
        return None
    return selected_state.value
