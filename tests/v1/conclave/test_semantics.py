from aioafero.device import AferoDevice
from aioafero.v1.conclave import semantics


def _device(functions: list[dict]) -> AferoDevice:
    return AferoDevice(
        id="dev",
        device_id="dev",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="f",
        functions=functions,
        states=[],
    )


def test_build_attribute_index_groups_by_key():
    device = _device(
        [
            {
                "functionClass": "power",
                "functionInstance": None,
                "values": [
                    {
                        "name": "on",
                        "deviceValues": [
                            {"type": "attribute", "key": "1", "value": "01"}
                        ],
                    },
                    {
                        "name": "off",
                        "deviceValues": [
                            {"type": "attribute", "key": "1", "value": "00"}
                        ],
                    },
                ],
            },
            {
                "functionClass": "brightness",
                "functionInstance": None,
                "values": [
                    {
                        "name": "brightness",
                        "deviceValues": [{"type": "attribute", "key": "2"}],
                    }
                ],
            },
        ]
    )
    index = semantics.build_attribute_index(device)
    assert set(index) == {"1", "2"}
    assert {b.value_name for b in index["1"]} == {"on", "off"}
    assert index["2"][0].function_class == "brightness"
    assert index["2"][0].device_value is None


def test_build_attribute_index_skips_missing_pieces():
    device = _device(
        [
            {"functionClass": None, "values": []},
            {
                "functionClass": "power",
                "values": [
                    {
                        "name": "on",
                        "deviceValues": [
                            {"type": "category", "key": "1"},
                            {"type": "attribute"},
                            {"type": "attribute", "key": "1"},
                        ],
                    }
                ],
            },
            {
                "functionClass": "noisy",
                "values": [None],
            },
        ]
    )
    index = semantics.build_attribute_index(device)
    assert list(index) == ["1"]
    assert len(index["1"]) == 1


def test_build_attribute_index_handles_missing_functions():
    device = _device([])
    device.functions = None  # type: ignore[assignment]
    assert semantics.build_attribute_index(device) == {}


def test_resolve_binding_single_binding_used_directly():
    index = {
        "4": [
            semantics.SemanticBinding(
                function_class="brightness",
                function_instance=None,
                value_name="brightness",
                device_value=None,
            )
        ]
    }
    binding = semantics.resolve_binding(index, "4", "40")
    assert binding is not None
    assert binding.function_class == "brightness"


def test_resolve_binding_picks_enum_match_via_value():
    bindings = [
        semantics.SemanticBinding("power", None, "off", "00"),
        semantics.SemanticBinding("power", None, "on", "01"),
    ]
    binding = semantics.resolve_binding({"1": bindings}, 1, "01")
    assert binding is bindings[1]


def test_resolve_binding_falls_back_to_data_for_blobs():
    bindings = [
        semantics.SemanticBinding(
            "color-sequence",
            "custom",
            "sleep",
            "0504008C0A280008078C0A05000000",
        ),
        semantics.SemanticBinding(
            "color-sequence",
            "custom",
            "rainbow",
            "DEADBEEF",
        ),
    ]
    # Conclave pushes the encoded blob as `value` (sometimes upper/lower mix);
    # match via the data field instead.
    binding = semantics.resolve_binding(
        {"300": bindings},
        "300",
        attribute_value=None,
        attribute_data="0504008c0a280008078c0a05000000",
    )
    assert binding is bindings[0]


def test_resolve_binding_returns_first_when_ambiguous():
    bindings = [
        semantics.SemanticBinding("power", None, "off", "00"),
        semantics.SemanticBinding("power", None, "on", "01"),
    ]
    binding = semantics.resolve_binding({"1": bindings}, "1", attribute_value=None)
    assert binding is bindings[0]


def test_resolve_binding_unknown_key_returns_none():
    assert semantics.resolve_binding({}, "1", "1") is None
    assert semantics.resolve_binding({"1": []}, "1", "1") is None
    assert semantics.resolve_binding({}, None, None) is None


def test_resolve_binding_coerces_non_string_values():
    bindings = [
        semantics.SemanticBinding("power", None, "off", "0"),
        semantics.SemanticBinding("power", None, "on", "1"),
    ]
    binding = semantics.resolve_binding({"1": bindings}, 1, 1)
    assert binding is bindings[1]


def test_coerce_rest_state_value_maps_power_and_color_temperature():
    on = semantics.SemanticBinding("power", None, "on", "01")
    assert semantics.coerce_rest_state_value(on, "1", "01") == "on"
    assert semantics.coerce_rest_state_value(on, "0", "00") == "off"
    cct = semantics.SemanticBinding("color-temperature", None, None, None)
    assert semantics.coerce_rest_state_value(cct, "4000", "A00F") == "4000K"
    bright = semantics.SemanticBinding("brightness", None, "brightness", None)
    assert semantics.coerce_rest_state_value(bright, "40", "28") == 40


def test_coerce_rest_state_value_uses_semantics_name_on_exact_match():
    white = semantics.SemanticBinding("color-mode", None, "white", "01")
    assert semantics.coerce_rest_state_value(white, "01", None) == "white"
    assert semantics.coerce_rest_state_value(white, None, "01") == "white"


def test_coerce_rest_state_value_passthrough_when_unmapped():
    speed = semantics.SemanticBinding("fan-speed", "fan-speed", None, None)
    assert semantics.coerce_rest_state_value(speed, "medium", None) == "medium"


def test_build_attribute_index_coerces_non_string_device_value():
    """deviceValues[].value occasionally comes back as int — coerce to str."""
    device = _device(
        [
            {
                "functionClass": "power",
                "values": [
                    {
                        "name": "on",
                        "deviceValues": [{"type": "attribute", "key": "1", "value": 1}],
                    },
                ],
            }
        ]
    )
    index = semantics.build_attribute_index(device)
    assert index["1"][0].device_value == "1"
