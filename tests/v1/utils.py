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


def ensure_states_sent(mocked_controller, expected_states):
    req = get_json_call(mocked_controller)["values"]
    assert len(req) == len(
        expected_states
    ), f"States Sent: {len(req)}. Expected: {len(expected_states)}. Actual: {req}"
    for state in expected_states:
        assert state in req, (
            f"Missing {state['functionClass']} / "
            f"{state['functionInstance']} for "
            f"{state['value']} in {req}"
        )


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
