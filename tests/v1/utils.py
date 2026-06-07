import json
from pathlib import Path
from typing import Any

from aioafero.device import AferoCapability, AferoDevice, AferoState

current_path = Path(__file__).parent


def get_device_dump(file_name: str) -> Any:
    """Get a device dump

    :param file_name: Name of the file to load
    """
    with (current_path / "device_dumps" / file_name).open() as fh:
        return json.load(fh)


def get_raw_dump(file_name: str) -> Any:
    """Get a device dump

    :param file_name: Name of the file to load
    """
    with (current_path / "data" / file_name).open() as fh:
        return json.load(fh)


def create_devices_from_data(file_name: str) -> list[AferoDevice]:
    """Generate devices from a data dump

    :param file_name: Name of the file to load
    """
    devices = get_device_dump(file_name)
    return [create_device_from_data(device) for device in devices]


def create_device_from_data(device: dict) -> AferoDevice:
    device["states"] = [AferoState(**state) for state in device["states"]]
    device["capabilities"] = [
        AferoCapability(**cap) for cap in device.get("capabilities", [])
    ]
    if "children" not in device:
        device["children"] = []
    return AferoDevice(**device)


def modify_state(device: AferoDevice, new_state):
    for ind, state in enumerate(device.states):
        if state.functionClass != new_state.functionClass:
            continue
        if (
            new_state.functionInstance
            and new_state.functionInstance != state.functionInstance
        ):
            continue
        device.states[ind] = new_state
        break


def create_hs_raw_from_device(afero_dev: AferoDevice) -> dict:
    """Convert an AferoDevice to Hubspace data"""
    descr_device = {
        "defaultName": afero_dev.default_name,
        "deviceClass": afero_dev.device_class,
        "manufacturerName": afero_dev.manufacturerName,
        "model": afero_dev.model,
        "profileId": "6ea6d241-3909-4235-836d-c594ece2bb67",
        "type": "device",
    }
    description = {
        "createdTimestampMs": 0,
        "defaultImage": afero_dev.default_image,
        "descriptions": [],
        "device": descr_device,
        "functions": afero_dev.functions,
        "hints": [],
        "id": afero_dev.id,
        "updatedTimestampMs": 0,
        "version": 1,
    }
    return {
        "children": afero_dev.children,
        "createdTimestampMs": 0,
        "description": description,
        "deviceId": afero_dev.device_id,
        "friendlyDescription": "",
        "friendlyName": afero_dev.friendly_name,
        "id": afero_dev.id,
        "state": {
            "metadeviceId": afero_dev.id,
            "values": convert_states(afero_dev.states),
        },
        "typeId": "metadevice.device",
    }


def create_hs_raw_from_dump(file_name: str) -> list[dict]:
    """Generate a Hubspace payload from devices and save it to a file.

    Takes a device dump file, processes it into Hubspace format, and saves the
    result to a new JSON file with '-raw' suffix. The generated payload includes
    device details, descriptions, states and other metadata formatted for Hubspace.

    :param file_name: Name of the file that contains the dump
    :return: List of dictionaries containing the generated Hubspace payload
    """
    return [
        create_hs_raw_from_device(device)
        for device in create_devices_from_data(file_name)
    ]


def convert_states(states: list[AferoState]) -> list[dict]:
    """Convert the states from AferoState to raw.

    :param states: List of AferoState objects
    """
    return [
        {
            "functionClass": state.functionClass,
            "functionInstance": state.functionInstance,
            "lastUpdateTime": state.lastUpdateTime,
            "value": state.value,
        }
        for state in states
    ]
