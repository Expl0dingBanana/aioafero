import json
import os
from typing import Any

from aioafero.device import AferoDevice, AferoState

current_path: str = os.path.dirname(os.path.realpath(__file__))


def get_device_dump(file_name: str) -> Any:
    """Get a device dump

    :param file_name: Name of the file to load
    """
    with open(os.path.join(current_path, "device_dumps", file_name), "r") as fh:
        return json.load(fh)


def get_raw_dump(file_name: str) -> Any:
    """Get a device dump

    :param file_name: Name of the file to load
    """
    with open(os.path.join(current_path, "data", file_name), "r") as fh:
        return json.load(fh)


def create_devices_from_data(file_name: str) -> list[AferoDevice]:
    """Generate devices from a data dump

    :param file_name: Name of the file to load
    """
    devices = get_device_dump(file_name)
    processed = []
    for device in devices:
        processed.append(create_device_from_data(device))
    return processed


def create_device_from_data(device: dict) -> AferoDevice:
    processed_states = []
    for state in device["states"]:
        processed_states.append(AferoState(**state))
    device["states"] = processed_states
    if "children" not in device:
        device["children"] = []
    return AferoDevice(**device)


def get_json_call(mocked_controller):
    mocked_controller._bridge.request.assert_called_once()
    call = mocked_controller._bridge.request.call_args_list[0][1]
    assert "json" in call
    return call["json"]


def ensure_states_sent(mocked_controller, expected_states, device_id=None):
    req = get_json_call(mocked_controller)
    assert len(req["values"]) == len(
        expected_states
    ), f"States Sent: {len(req)}. Expected: {len(expected_states)}. Actual: {req}"
    for state in expected_states:
        assert state in req["values"], (
            f"Missing {state['functionClass']} / "
            f"{state['functionInstance']} for "
            f"{state['value']} in {req}"
        )
    if device_id:
        assert req["metadeviceId"] == device_id


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


def create_hs_raw_from_dump(file_name: str) -> list[dict]:
    """Generate a Hubspace payload from devices and save it to a file.

    Takes a device dump file, processes it into Hubspace format, and saves the
    result to a new JSON file with '-raw' suffix. The generated payload includes
    device details, descriptions, states and other metadata formatted for Hubspace.

    :param file_name: Name of the file that contains the dump
    :return: List of dictionaries containing the generated Hubspace payload
    """
    hs_raw: list[dict] = []
    for device in create_devices_from_data(file_name):
        descr_device = {
            "defaultName": device.default_name,
            "deviceClass": device.device_class,
            "manufacturerName": device.manufacturerName,
            "model": device.model,
            "profileId": "6ea6d241-3909-4235-836d-c594ece2bb67",
            "type": "device",
        }
        description = {
            "createdTimestampMs": 0,
            "defaultImage": device.default_image,
            "descriptions": [],
            "device": descr_device,
            "functions": device.functions,
            "hints": [],
            "id": device.id,
            "updatedTimestampMs": 0,
            "version": 1,
        }
        hs_raw.append(
            {
                "children": device.children,
                "createdTimestampMs": 0,
                "description": description,
                "deviceId": device.device_id,
                "friendlyDescription": "",
                "friendlyName": device.friendly_name,
                "id": device.id,
                "state": {
                    "metadeviceId": device.id,
                    "values": convert_states(device.states),
                },
                "typeId": "metadevice.device",
            }
        )
    return hs_raw


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
