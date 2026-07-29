"""Tests for update duplicate-suppression helpers."""

from aioafero.v1.models import features
from aioafero.v1.models.light import Light, LightChannel
from aioafero.v1.models.resource import DeviceInformation
from aioafero.v1.models.update_comparison import (
    SupportsFeatureUpdateComparison,
    default_feature_for_update_comparison,
    features_equivalent_for_update,
    resolve_feature_for_update_comparison,
)


def test_default_dict_lookup_by_instance():
    elem = type(
        "E",
        (),
        {
            "on": {
                "zone-1": features.OnFeature(
                    on=True, function_class="toggle", function_instance="zone-1"
                )
            }
        },
    )()
    put = features.OnFeature(on=True, function_class="toggle", function_instance="zone-1")
    assert default_feature_for_update_comparison(elem, "on", put) is elem.on["zone-1"]


def test_default_dict_lookup_by_class_instance_tuple():
    """Numbers-style caches key by (functionClass, functionInstance)."""
    key = ("toggle", "zone-1")
    cached = features.OnFeature(on=True, function_class="toggle", function_instance="zone-1")
    elem = type("E", (), {"on": {key: cached}})()
    put = features.OnFeature(on=True, function_class="toggle", function_instance="zone-1")
    assert default_feature_for_update_comparison(elem, "on", put) is cached


def test_features_equivalent_identity_and_none():
    feat = features.OnFeature(on=True, function_class="power", function_instance=None)
    assert features_equivalent_for_update(feat, feat)
    assert not features_equivalent_for_update(feat, None)
    assert not features_equivalent_for_update(None, feat)


def test_features_equivalent_ignores_dimming_supported():
    put = features.DimmingFeature(
        function_class="brightness",
        brightness=40, supported=[1, 100], function_instance="color"
    )
    cached = features.DimmingFeature(
        function_class="brightness",
        brightness=40, supported=[0, 100], function_instance="color"
    )
    assert features_equivalent_for_update(put, cached)


def test_features_equivalent_open_and_fallback():
    open_a = features.OpenFeature(open=True, function_class="toggle", function_instance="s1")
    open_b = features.OpenFeature(open=True, function_class="toggle", function_instance="s1")
    open_c = features.OpenFeature(open=False, function_class="toggle", function_instance="s1")
    assert features_equivalent_for_update(open_a, open_b)
    assert not features_equivalent_for_update(open_a, open_c)
    assert features_equivalent_for_update({"a": 1}, {"a": 1})
    assert not features_equivalent_for_update({"a": 1}, {"a": 2})


def test_resolve_falls_back_without_protocol():
    elem = type(
        "E",
        (),
        {
            "on": {
                None: features.OnFeature(
                    on=False, function_class="power", function_instance=None
                )
            }
        },
    )()
    put = features.OnFeature(on=False, function_class="power", function_instance=None)
    assert resolve_feature_for_update_comparison(elem, "on", put) is elem.on[None]


def test_light_protocol_and_channel_toggle_gate():
    light = Light(
        _id="x",
        available=True,
        on=features.OnFeature(on=True, function_class="power", function_instance=None),
        dimming=features.DimmingFeature(
            function_class="brightness",
            brightness=50, supported=[1, 100], function_instance="primary"
        ),
        channels={
            "color": LightChannel(brightness=40, on=True),
            "white": LightChannel(brightness=10, on=False),
        },
        device_information=DeviceInformation(),
    )
    assert isinstance(light, SupportsFeatureUpdateComparison)
    toggle = features.OnFeature(on=True, function_class="toggle", function_instance="color")
    cached = resolve_feature_for_update_comparison(light, "on", toggle)
    assert features_equivalent_for_update(toggle, cached)
    # Primary power must not be remapped through channels.
    power = features.OnFeature(on=True, function_class="power", function_instance=None)
    assert resolve_feature_for_update_comparison(light, "on", power) is light.on
    # Explicit None instance must not match a bogus channels[None] entry.
    light.channels[None] = LightChannel(brightness=1, on=False)
    assert resolve_feature_for_update_comparison(light, "on", power) is light.on
    del light.channels[None]
    # Unknown channel on does not suppress.
    light.channels["color"].on = None
    assert resolve_feature_for_update_comparison(light, "on", toggle) is None
