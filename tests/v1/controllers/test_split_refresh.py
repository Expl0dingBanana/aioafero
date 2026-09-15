"""Tests for split clone state refresh helpers."""

from aioafero.device import AferoDevice, AferoState, SplitDeviceId
from aioafero.v1.controllers import split_refresh


def test_refresh_split_clone_states_noop_without_split():
    parent = AferoDevice(
        id="parent",
        device_id="physical",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        states=[
            AferoState(functionClass="power", functionInstance="trim", value="off"),
        ],
    )
    clone = AferoDevice(
        id="orphan-id",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        states=[AferoState(functionClass="power", functionInstance=None, value="on")],
    )
    split_refresh.refresh_split_clone_states(parent, clone)
    assert clone.states[0].value == "on"


def test_refresh_split_clone_states_noop_for_unknown_split_type():
    parent = AferoDevice(
        id="parent",
        device_id="physical",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        states=[],
    )
    clone = AferoDevice(
        id=f"{parent.id}-custom-zone",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        split=SplitDeviceId(parent.id, "custom", "zone"),
        states=[],
    )
    split_refresh.refresh_split_clone_states(parent, clone)
    assert clone.states == []


def test_split_instance_from_device():
    device = AferoDevice(
        id="uuid-light-trim",
        device_id="physical",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        split=SplitDeviceId("uuid", "light", "trim"),
    )
    assert split_refresh.split_instance_from_device(device) == "trim"
    device.split = None
    assert split_refresh.split_instance_from_device(device) is None


def test_refresh_split_clone_states_filters_light_instance():
    parent = AferoDevice(
        id="8866648e-ef12-47b1-a7af-16c86214933e",
        device_id="physical",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="n",
        states=[
            AferoState(functionClass="power", functionInstance="trim", value="on"),
            AferoState(functionClass="power", functionInstance="other", value="off"),
        ],
    )
    clone = AferoDevice(
        id=f"{parent.id}-light-trim",
        device_id=parent.device_id,
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="Split light",
        states=[],
        split=SplitDeviceId(parent.id, "light", "trim"),
    )
    split_refresh.refresh_split_clone_states(parent, clone)
    assert len(clone.states) == 1
    assert clone.states[0].functionInstance == "trim"


def test_refresh_split_clone_states_filters_security_sensor():
    parent = AferoDevice(
        id="7f4e4c01-e799-45c5-9b1a-385433a78edc",
        device_id="physical",
        model="m",
        device_class="security-system",
        default_name="n",
        default_image="i",
        friendly_name="n",
        states=[
            AferoState(
                functionClass="sensor-state",
                functionInstance="sensor-12",
                value={
                    "cfg-12": {
                        "batteryLevel": 90,
                        "tampered": 0,
                        "triggered": 1,
                        "missing": 0,
                        "deviceType": 2,
                    }
                },
            ),
        ],
    )
    clone = AferoDevice(
        id=f"{parent.id}-sensor-12",
        device_id=f"{parent.id}-sensor-12",
        model="m",
        device_class="security-system-sensor",
        default_name="n",
        default_image="i",
        friendly_name="Sensor 12",
        states=[],
        split=SplitDeviceId(parent.id, "sensor", "12"),
    )
    split_refresh.refresh_split_clone_states(parent, clone)
    triggered = next(
        (state for state in clone.states if state.functionClass == "triggered"),
        None,
    )
    assert triggered is not None
    assert triggered.value == "On"
