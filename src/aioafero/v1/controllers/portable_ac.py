"""Controller holding and managing Afero IoT resources of type `portable-air-conditioner`."""

import copy

from aioafero.device import AferoDevice
from aioafero.errors import DeviceNotFound
from aioafero.v1.models import features
from aioafero.v1.models.portable_ac import PortableAC, PortableACPut
from aioafero.v1.models.resource import DeviceInformation, ResourceTypes

from .climate import ClimateController
from .event import CallbackResponse

SPLIT_IDENTIFIER: str = "portable-ac"


def generate_split_name(afero_device: AferoDevice, instance: str) -> str:
    """Generate the name for an instanced element."""
    return f"{afero_device.id}-{SPLIT_IDENTIFIER}-{instance}"


def get_valid_states(afero_dev: AferoDevice) -> list:
    """Find states associated with the element."""
    return [
        state
        for state in afero_dev.states
        if state.functionClass in ["available", "power"]
    ]


def portable_ac_callback(afero_device: AferoDevice) -> CallbackResponse:
    """Convert an AferoDevice into multiple devices."""
    multi_devs: list[AferoDevice] = []
    if afero_device.device_class == ResourceTypes.PORTABLE_AC.value:
        instance = "power"
        cloned = copy.deepcopy(afero_device)
        cloned.id = generate_split_name(afero_device, instance)
        cloned.split_identifier = SPLIT_IDENTIFIER
        cloned.friendly_name = f"{afero_device.friendly_name} - {instance}"
        cloned.states = get_valid_states(afero_device)
        cloned.device_class = ResourceTypes.SWITCH.value
        cloned.children = []
        multi_devs.append(cloned)
    return CallbackResponse(
        split_devices=multi_devs,
        remove_original=False,
    )


class PortableACController(ClimateController[PortableAC]):
    """Controller holding and managing Afero IoT resources of type `portable-air-conditioner`."""

    ITEM_TYPE_ID = ResourceTypes.DEVICE
    ITEM_TYPES = [ResourceTypes.PORTABLE_AC]
    ITEM_CLS = PortableAC
    ITEM_MAPPING = {
        "hvac_mode": "mode",
    }
    # Elements that map to Select. func class / func instance to name
    ITEM_SELECTS = {
        ("fan-speed", "ac-fan-speed"): "Fan Speed",
        ("sleep", None): "Sleep Mode",
        ("air-swing", None): "Swing",
    }
    DEVICE_SPLIT_CALLBACKS: dict[str, callable] = {
        ResourceTypes.PORTABLE_AC.value: portable_ac_callback
    }

    async def initialize_elem(self, afero_device: AferoDevice) -> PortableAC:
        """Initialize the element.

        :param afero_device: Afero Device that contains the updated states

        :return: Newly initialized resource
        """
        climate_data = await self.initialize_climate_elem(afero_device)

        self._items[afero_device.id] = PortableAC(
            _id=afero_device.id,
            available=climate_data["available"],
            current_temperature=climate_data["current_temperature"],
            hvac_mode=climate_data["hvac_mode"],
            target_temperature_heating=climate_data["target_temperature_heating"],
            target_temperature_cooling=climate_data["target_temperature_cooling"],
            numbers={},
            selects=climate_data["selects"],
            binary_sensors={},
            sensors={},
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
        )
        return self._items[afero_device.id]

    async def update_elem(self, afero_device: AferoDevice) -> set:
        """Update the Portable AC with the latest API data.

        :param afero_device: Afero Device that contains the updated states

        :return: States that have been modified
        """
        return await self.update_climate_elem(afero_device)

    async def set_state(self, device_id: str, **kwargs) -> None:
        """Set supported feature(s) to portable ac resource."""
        update_obj = PortableACPut()
        hvac_mode: str | None = kwargs.get("hvac_mode")
        target_temperature: float | None = kwargs.get("target_temperature")
        selects: dict[tuple[str, str | None], str] | None = kwargs.get("selects", {})
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info("Unable to find device %s", device_id)
            return
        if hvac_mode:
            if hvac_mode in cur_item.hvac_mode.supported_modes:
                update_obj.hvac_mode = features.HVACModeFeature(
                    mode=hvac_mode,
                    modes=cur_item.hvac_mode.modes,
                    previous_mode=cur_item.hvac_mode.mode,
                    supported_modes=cur_item.hvac_mode.supported_modes,
                )
            else:
                self._logger.debug(
                    "Unknown hvac mode %s. Available modes: %s",
                    hvac_mode,
                    ", ".join(sorted(cur_item.hvac_mode.modes)),
                )
        if target_temperature is not None:
            kwargs["target_temperature_cooling"] = kwargs.pop("target_temperature")

        for key, val in selects.items():
            if key not in cur_item.selects:
                continue
            update_obj.selects[key] = features.SelectFeature(
                selected=val,
                selects=cur_item.selects[key].selects,
                name=cur_item.selects[key].name,
            )
        await self.set_climate_state(device_id, update_obj, **kwargs)
