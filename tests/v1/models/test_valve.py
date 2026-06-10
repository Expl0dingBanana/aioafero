import pytest

from aioafero.v1.models import features, DeviceInformation
from aioafero.v1.models.valve import Valve


@pytest.fixture
def populated_entity():
    return Valve(
        _id="entity-1",
        available=True,
        open={None: features.OpenFeature(open=True)},
        device_information=DeviceInformation(
            functions=[
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ]
        ),
    )


@pytest.fixture
def empty_entity():
    return Valve(
        _id="entity-1",
        available=True,
        open=None,
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.open[None].open is True


def test_init_empty(empty_entity):
    assert not empty_entity.open


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"


def test_rain_delay_defaults_none(empty_entity):
    assert empty_entity.rain_delay is None


def test_rain_delay_feature_api_value():
    feat = features.RainDelayFeature(active=True, pauses=[{"a": 1}])
    # api_value only toggles `active`; the pause array is app-managed.
    assert feat.api_value == {
        "functionClass": "schedule-pause",
        "functionInstance": "active",
        "value": "on",
    }
    feat.active = False
    assert feat.api_value["value"] == "off"


def test_rain_delay_pause_window_builder():
    w = features.RainDelayFeature.pause_window(1000, 2000)
    assert w == {"version": 1, "flags": 0, "startTime": 1000, "endTime": 2000}


def test_rain_delay_write_api_value():
    feat = features.RainDelayFeature(
        active=False,
        pause_windows=[{"version": 1, "flags": 0, "startTime": 10, "endTime": 20}],
    )
    val = feat.api_value
    assert isinstance(val, list) and len(val) == 2
    active, arr = val
    assert active == {"functionClass": "schedule-pause", "functionInstance": "active", "value": "on"}
    assert arr["functionInstance"] == "rain-delay"
    assert arr["value"]["schedule-pause-time-array"]["schedulePauseTimeArray"][0]["startTime"] == 10
    # empty windows -> clear (active off, empty array)
    clear = features.RainDelayFeature(active=True, pause_windows=[]).api_value
    assert clear[0]["value"] == "off"
    assert clear[1]["value"]["schedule-pause-time-array"]["schedulePauseTimeArray"] == []
