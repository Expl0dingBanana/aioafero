import json
import os

import pytest

from aioafero import device

current_path = os.path.dirname(os.path.realpath(__file__))


with open(os.path.join(current_path, "v1", "data", "device_lock.json")) as fh:
    device_lock_response = json.load(fh)
    lock_dev = device.get_afero_device(device_lock_response[0])


@pytest.mark.parametrize(
    "afero_device,expected",
    [
        # Everything is set correctly
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "model",
                "device_class": "device_class",
                "default_name": "default_name",
                "default_image": "default_image",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "model",
                    "device_class": "device_class",
                    "default_name": "default_name",
                    "default_image": "default_image",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # DriskolFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-snyder-park-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "Driskol",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-snyder-park-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # VinwoodFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-vinings-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "Vinwood",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-vinings-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # ZandraFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "TBD",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-chandra-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "Zandra",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-chandra-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # NevaliFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "TBD",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-ac-cct-dardanus-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "Nevali",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-ac-cct-dardanus-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # TagerFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-slender-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "Tager",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-slender-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # Dimmer switch
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "dimmer",
                "device_class": "switch",
                "default_name": "default_name",
                "default_image": "ceiling-fan-slender-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [
                    device.AferoState(
                        **{
                            "functionClass": "brightness",
                            "functionInstance": None,
                            "lastUpdateTime": 1668551478232,
                            "value": 40,
                        }
                    )
                ],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "dimmer",
                    "device_class": "light",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-slender-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [
                        device.AferoState(
                            **{
                                "functionClass": "brightness",
                                "functionInstance": None,
                                "lastUpdateTime": 1668551478232,
                                "value": 40,
                            }
                        )
                    ],
                }
            ),
        ),
        # Glass door
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "glass-door",
                "device_class": "glass-door",
                "default_name": "default_name",
                "default_image": "glass-door-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [
                    device.AferoState(
                        **{
                            "functionClass": "power",
                            "functionInstance": None,
                            "lastUpdateTime": 1668551478232,
                            "value": "off",
                        }
                    )
                ],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "glass-door",
                    "device_class": "switch",
                    "default_name": "default_name",
                    "default_image": "glass-door-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [
                        device.AferoState(
                            **{
                                "functionClass": "power",
                                "functionInstance": None,
                                "lastUpdateTime": 1668551478232,
                                "value": "off",
                            }
                        )
                    ],
                    "manufacturerName": "Feather River Doors",
                }
            ),
        ),
        # Exhaust fan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "glass-door",
                "device_class": "exhaust-fan",
                "default_name": "default_name",
                "default_image": "fan-exhaust-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [
                    device.AferoState(
                        **{
                            "functionClass": "power",
                            "functionInstance": None,
                            "lastUpdateTime": 1668551478232,
                            "value": "off",
                        }
                    )
                ],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "BF1112",
                    "device_class": "exhaust-fan",
                    "default_name": "default_name",
                    "default_image": "fan-exhaust-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [
                        device.AferoState(
                            **{
                                "functionClass": "power",
                                "functionInstance": None,
                                "lastUpdateTime": 1668551478232,
                                "value": "off",
                            }
                        )
                    ],
                    "manufacturerName": None,
                }
            ),
        ),
        # 12A19060WRGBWH2
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "glass-door",
                "device_class": "light",
                "default_name": "default_name",
                "default_image": "a19-e26-color-cct-60w-smd-frosted-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [
                    device.AferoState(
                        **{
                            "functionClass": "power",
                            "functionInstance": None,
                            "lastUpdateTime": 1668551478232,
                            "value": "off",
                        }
                    )
                ],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "12A19060WRGBWH2",
                    "device_class": "light",
                    "default_name": "default_name",
                    "default_image": "a19-e26-color-cct-60w-smd-frosted-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [
                        device.AferoState(
                            **{
                                "functionClass": "power",
                                "functionInstance": None,
                                "lastUpdateTime": 1668551478232,
                                "value": "off",
                            }
                        )
                    ],
                    "manufacturerName": None,
                }
            ),
        ),
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "glass-door",
                "device_class": "light",
                "default_name": "default_name",
                "default_image": "slide-dimmer-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [
                    device.AferoState(
                        **{
                            "functionClass": "power",
                            "functionInstance": None,
                            "lastUpdateTime": 1668551478232,
                            "value": "off",
                        }
                    )
                ],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "HPDA110NWBP",
                    "device_class": "light",
                    "default_name": "default_name",
                    "default_image": "slide-dimmer-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [
                        device.AferoState(
                            **{
                                "functionClass": "power",
                                "functionInstance": None,
                                "lastUpdateTime": 1668551478232,
                                "value": "off",
                            }
                        )
                    ],
                    "manufacturerName": None,
                }
            ),
        ),
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "TBD",
                "device_class": "switch",
                "default_name": "default_name",
                "default_image": "smart-switch-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [
                    device.AferoState(
                        **{
                            "functionClass": "power",
                            "functionInstance": None,
                            "lastUpdateTime": 1668551478232,
                            "value": "off",
                        }
                    )
                ],
            },
            device.AferoDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "HPSA11CWB",
                    "device_class": "switch",
                    "default_name": "default_name",
                    "default_image": "smart-switch-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [
                        device.AferoState(
                            **{
                                "functionClass": "power",
                                "functionInstance": None,
                                "lastUpdateTime": 1668551478232,
                                "value": "off",
                            }
                        )
                    ],
                    "manufacturerName": None,
                }
            ),
        ),
    ],
)
def test_AferoDevice(afero_device, expected):
    assert device.AferoDevice(**afero_device) == expected


@pytest.mark.parametrize(
    "afero_device,expected_attrs",
    [
        # Validate when values are missing
        (
            {},
            {
                "id": None,
                "device_id": None,
                "model": None,
                "device_class": None,
                "default_name": None,
                "default_image": None,
                "friendly_name": None,
                "functions": [],
            },
        ),
        # Ensure values are properly parsed
        (
            device_lock_response[0],
            {
                "id": "5a5d5e04-a6ad-47c0-b9f4-b9fe5c049ef4",
                "device_id": "0123f95ec14bdb23",
                "model": "Keypad Deadbolt Lock",
                "device_class": "door-lock",
                "default_name": "Keypad Deadbolt Lock",
                "default_image": "keypad-deadbolt-lock-icon",
                "friendly_name": "Friendly Name 2",
                "functions": device_lock_response[0]["description"]["functions"],
            },
        ),
    ],
)
def test_get_afero_device(afero_device, expected_attrs):
    dev = device.get_afero_device(afero_device)
    for key, val in expected_attrs.items():
        assert (
            getattr(dev, key) == val
        ), f"Key {key} did not match, {getattr(dev, key)} != {val}"


@pytest.mark.parametrize(
    "data,expected_attrs",
    [
        # verify defaults
        (
            {
                "functionClass": "class",
                "value": "beans",
            },
            {
                "functionClass": "class",
                "value": "beans",
                "functionInstance": None,
                "lastUpdateTime": None,
            },
        ),
        # verify defaults
        (
            {
                "functionClass": "class",
                "value": "beans",
                "functionInstance": "beans",
                "lastUpdateTime": 4,
            },
            {
                "functionClass": "class",
                "value": "beans",
                "functionInstance": "beans",
                "lastUpdateTime": 4,
            },
        ),
    ],
)
def test_AferoState(data, expected_attrs):
    elem = device.AferoState(**data)
    for key, val in expected_attrs.items():
        assert getattr(elem, key) == val


def test_AferoDevice_hash():
    dev = device.get_afero_device(device_lock_response[0])
    hash_check = {dev: True}
    assert dev in hash_check


@pytest.mark.parametrize(
    "functions, func_class, func_instance, expected",
    [
        ([], "cool", "beans", None),
        (lock_dev.functions, "lock-pin", None, None),
        (lock_dev.functions, "lock-pin", "lock-pin-9", lock_dev.functions[19]),
    ],
)
def test_get_function_from_device(functions, func_class, func_instance, expected):
    assert (
        device.get_function_from_device(functions, func_class, func_instance)
        == expected
    )
