"""Provides an interface for anonymizing data"""

__all__ = ["anonymize_devices", "anonymize_device"]

from dataclasses import asdict
from uuid import uuid4

from .device import AferoDevice, AferoState

ANONYMIZE_STATES: set[str] = {"wifi-ssid", "wifi-mac-address", "ble-mac-address"}

FNAME_IND: int = 0


def anonymize_devices(
    devices: list[AferoDevice], anon_name: bool = False
) -> list[dict]:
    """Remove identifying information from the device

    :param devices: List of devices to anonymize
    :param anon_name: If true, give each device a unique name
    """
    fake_devices = []
    parents = generate_parent_mapping(devices)
    device_links = {}
    for dev in devices:
        fake_devices.append(anonymize_device(dev, parents, device_links, anon_name))
    return fake_devices


def generate_parent_mapping(devices: list[AferoDevice]) -> dict:
    """Generate anonymize links between parents and children

    :param devices: List of devices to anonymize
    """
    mapping = {}
    for device in devices:
        if device.children:
            device.id = str(uuid4())
        new_children = []
        for child_id in device.children:
            new_uuid = str(uuid4())
            mapping[child_id] = {"parent": device.id, "new": new_uuid}
            new_children.append(new_uuid)
        device.children = new_children
    return mapping


def anonymize_device(
    dev: AferoDevice,
    parent_mapping: dict,
    device_links: dict,
    anon_name: bool,
) -> dict:
    fake_dev = asdict(dev)
    if anon_name:
        global FNAME_IND
        fake_dev["friendly_name"] = f"friendly-device-{FNAME_IND}"
        FNAME_IND += 1
    if dev.id in parent_mapping:
        fake_dev["id"] = parent_mapping[dev.id]["new"]
    else:
        fake_dev["id"] = str(uuid4())
    dev_link = dev.device_id
    if dev_link not in device_links:
        device_links[dev_link] = str(uuid4())
    fake_dev["device_id"] = device_links[dev_link]
    fake_dev["states"] = []
    for state in dev.states:
        fake_dev["states"].append(anonymize_state(state))
    return fake_dev


def anonymize_state(state: AferoState, only_geo: bool = False) -> dict:
    fake_state = asdict(state)
    fake_state["lastUpdateTime"] = 0
    if fake_state["functionClass"] == "geo-coordinates":
        fake_state["value"] = {"geo-coordinates": {"latitude": "0", "longitude": "0"}}
    elif not only_geo:
        if fake_state["functionClass"] in ANONYMIZE_STATES:
            fake_state["value"] = str(uuid4())
    return fake_state
