from dataclasses import replace

import pytest

from aioafero import anonomyize_data
from aioafero.device import AferoDevice, AferoState

POWER_STATE = {
    "functionClass": "power",
    "functionInstance": None,
    "value": "on",
    "lastUpdateTime": 0,
}
GEO_STATE = {
    "functionClass": "geo-coordinates",
    "functionInstance": None,
    "value": {"geo-coordinates": {"latitude": "5", "longitude": "5"}},
}
MAC_STATE = {
    "functionClass": "wifi-mac-address",
    "functionInstance": None,
    "value": "aa:bb:cc:dd:ee:ff",
}
child_dev_1 = AferoDevice(
    id="c-id-1",
    device_id="parent-1",
    model="test-c-dev-1",
    device_class="test-c-dev-1",
    default_name="test-c-dev-1",
    default_image="test-c-dev-1",
    friendly_name="test-c-dev-1",
    functions=[],
    states=[
        AferoState(**POWER_STATE),
        AferoState(**GEO_STATE),
        AferoState(**MAC_STATE),
    ],
    children=[],
    manufacturerName="test-manuf",
)
child_dev_2 = AferoDevice(
    id="c-id-2",
    device_id="parent-1",
    model="test-c-dev-2",
    device_class="test-c-dev-2",
    default_name="test-c-dev-2",
    default_image="test-c-dev-2",
    friendly_name="test-c-dev-2",
    functions=[],
    states=[
        AferoState(**POWER_STATE),
        AferoState(**GEO_STATE),
        AferoState(**MAC_STATE),
    ],
    children=[],
    manufacturerName="test-manuf",
)

parent_dev_1 = AferoDevice(
    id="p-id-1",
    device_id="parent-1",
    model="test-dev-1",
    device_class="test-dev-1",
    default_name="test-dev-1",
    default_image="test-dev-1",
    friendly_name="test-dev-1",
    functions=[],
    states=[
        AferoState(**POWER_STATE),
        AferoState(**GEO_STATE),
        AferoState(**MAC_STATE),
    ],
    children=[child_dev_1.id, child_dev_2.id],
    manufacturerName="test-manuf",
)


@pytest.fixture
def mock_uuid(mocker):
    calls = 0

    def get_uuid():
        nonlocal calls
        calls += 1
        if calls % 2:
            return "its-a-1"
        else:
            return "its-a-2"

    mocker.patch.object(anonomyize_data, "uuid4", side_effect=get_uuid)


@pytest.mark.parametrize(
    "state,only_geo,expected",
    [
        # Non-geo + only_geo
        (
            AferoState(
                functionClass="wifi-mac-address",
                functionInstance=None,
                value="aa:bb:cc:dd:ee:ff",
            ),
            True,
            {
                "functionClass": "wifi-mac-address",
                "functionInstance": None,
                "lastUpdateTime": 0,
                "value": "aa:bb:cc:dd:ee:ff",
            },
        ),
        # Non-geo + not only_geo
        (
            AferoState(
                functionClass="wifi-mac-address",
                functionInstance=None,
                value="aa:bb:cc:dd:ee:ff",
            ),
            False,
            {
                "functionClass": "wifi-mac-address",
                "functionInstance": None,
                "lastUpdateTime": 0,
                "value": "anon data",
            },
        ),
        # Geo data
        (
            AferoState(
                functionClass="geo-coordinates",
                functionInstance=None,
                value={"geo-coordinates": {"latitude": "5", "longitude": "5"}},
            ),
            False,
            {
                "functionClass": "geo-coordinates",
                "functionInstance": None,
                "lastUpdateTime": 0,
                "value": {"geo-coordinates": {"latitude": "0", "longitude": "0"}},
            },
        ),
        # Non-anon data
        (
            AferoState(
                functionClass="power",
                functionInstance=None,
                lastUpdateTime=12345,
                value="on",
            ),
            False,
            {
                "functionClass": "power",
                "functionInstance": None,
                "lastUpdateTime": 0,
                "value": "on",
            },
        ),
    ],
)
def test_anonymize_state(state, only_geo, expected, mocker):
    mocker.patch.object(anonomyize_data, "uuid4", return_value="anon data")
    assert anonomyize_data.anonymize_state(state, only_geo=only_geo) == expected


@pytest.mark.parametrize(
    "device, device_links, parent_mapping, anon_name, expected",
    [
        # Anon name
        (
            replace(child_dev_1),
            {},
            {},
            True,
            {
                "friendly_name": "friendly-device-0",
                "id": "its-a-1",
                "device_id": "its-a-2",
                "states": [
                    POWER_STATE,
                    {
                        "functionClass": "geo-coordinates",
                        "functionInstance": None,
                        "lastUpdateTime": 0,
                        "value": {
                            "geo-coordinates": {"latitude": "0", "longitude": "0"}
                        },
                    },
                    {
                        "functionClass": "wifi-mac-address",
                        "functionInstance": None,
                        "lastUpdateTime": 0,
                        "value": "its-a-1",
                    },
                ],
            },
        ),
        # normal name
        (
            replace(child_dev_1),
            {child_dev_1.device_id: "anon-device-id"},
            {child_dev_1.id: {"parent": parent_dev_1.id, "new": "anon-id"}},
            False,
            {
                "friendly_name": child_dev_1.friendly_name,
                "id": "anon-id",
                "device_id": "anon-device-id",
                "states": [
                    POWER_STATE,
                    {
                        "functionClass": "geo-coordinates",
                        "functionInstance": None,
                        "lastUpdateTime": 0,
                        "value": {
                            "geo-coordinates": {"latitude": "0", "longitude": "0"}
                        },
                    },
                    {
                        "functionClass": "wifi-mac-address",
                        "functionInstance": None,
                        "lastUpdateTime": 0,
                        "value": "its-a-1",
                    },
                ],
            },
        ),
    ],
)
def test_anonymize_device(
    device, device_links, parent_mapping, anon_name, expected, mock_uuid
):
    anon_dev = anonomyize_data.anonymize_device(
        device, parent_mapping, device_links, anon_name
    )
    assert device.device_id in device_links
    for key, val in expected.items():
        assert key in anon_dev
        assert anon_dev[key] == val


@pytest.mark.parametrize(
    "devices, expected, new_children",
    [
        # No parents
        ([child_dev_1], {}, []),
        # Parents
        (
            [parent_dev_1, child_dev_1, child_dev_2],
            {
                "c-id-1": {"parent": "its-a-1", "new": "its-a-2"},
                "c-id-2": {"parent": "its-a-1", "new": "its-a-1"},
            },
            ["its-a-2", "its-a-1"],
        ),
    ],
)
def test_generate_parent_mapping(devices, expected, new_children, mock_uuid):
    assert anonomyize_data.generate_parent_mapping(devices) == expected
    if new_children:
        assert devices[0].children == new_children


@pytest.mark.parametrize("anon_name", [True, False])
def test_anonymize_devices(anon_name, mock_uuid):
    expected = [
        {
            "id": "its-a-1",
            "device_id": "its-a-2",
            "model": "test-dev-1",
            "device_class": "test-dev-1",
            "default_name": "test-dev-1",
            "default_image": "test-dev-1",
            "friendly_name": "test-dev-1",
            "functions": [],
            "states": [
                {
                    "functionClass": "power",
                    "value": "on",
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
                {
                    "functionClass": "geo-coordinates",
                    "value": {"geo-coordinates": {"latitude": "0", "longitude": "0"}},
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
                {
                    "functionClass": "wifi-mac-address",
                    "value": "its-a-1",
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
            ],
            "children": ["its-a-2", "its-a-1"],
            "manufacturerName": "test-manuf",
        },
        {
            "id": "its-a-2",
            "device_id": "its-a-2",
            "model": "test-c-dev-1",
            "device_class": "test-c-dev-1",
            "default_name": "test-c-dev-1",
            "default_image": "test-c-dev-1",
            "friendly_name": "test-c-dev-1",
            "functions": [],
            "states": [
                {
                    "functionClass": "power",
                    "value": "on",
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
                {
                    "functionClass": "geo-coordinates",
                    "value": {"geo-coordinates": {"latitude": "0", "longitude": "0"}},
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
                {
                    "functionClass": "wifi-mac-address",
                    "value": "its-a-1",
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
            ],
            "children": [],
            "manufacturerName": "test-manuf",
        },
        {
            "id": "its-a-2",
            "device_id": "its-a-2",
            "model": "test-c-dev-2",
            "device_class": "test-c-dev-2",
            "default_name": "test-c-dev-2",
            "default_image": "test-c-dev-2",
            "friendly_name": "test-c-dev-2",
            "functions": [],
            "states": [
                {
                    "functionClass": "power",
                    "value": "on",
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
                {
                    "functionClass": "geo-coordinates",
                    "value": {"geo-coordinates": {"latitude": "0", "longitude": "0"}},
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
                {
                    "functionClass": "wifi-mac-address",
                    "value": "its-a-1",
                    "lastUpdateTime": 0,
                    "functionInstance": None,
                },
            ],
            "children": [],
            "manufacturerName": "test-manuf",
        },
    ]
    if anon_name:
        expected[0]["friendly_name"] = "friendly-device-1"
        expected[1]["friendly_name"] = "friendly-device-2"
        expected[2]["friendly_name"] = "friendly-device-3"
    assert (
        anonomyize_data.anonymize_devices(
            [parent_dev_1, child_dev_1, child_dev_2], anon_name=anon_name
        )
        == expected
    )
