import pytest

from aioafero import util

from .v1 import utils

thermostat = utils.create_devices_from_data("thermostat.json")[0]


@pytest.mark.parametrize(
    "vals, percentage, expected, err",
    [
        ([], None, None, True),
        ([1, 2, 3], 50, 2, False),
        ([1, 2, 3], 101, 3, False),
    ],
)
def test_percentage_to_ordered_list_item(vals, percentage, expected, err):
    if not err:
        assert util.percentage_to_ordered_list_item(vals, percentage) == expected
    else:
        with pytest.raises(ValueError):
            util.percentage_to_ordered_list_item(vals, percentage)


@pytest.mark.parametrize(
    "vals, value, expected, err",
    [
        ([1, 2, 3], 4, None, True),
        ([1, 2, 3], 2, 66, False),
    ],
)
def test_ordered_list_item_to_percentage(vals, value, expected, err):
    if not err:
        assert util.ordered_list_item_to_percentage(vals, value) == expected
    else:
        with pytest.raises(ValueError):
            util.ordered_list_item_to_percentage(vals, value)


@pytest.mark.parametrize(
    "range_vals, expected",
    [
        ({"range": {"min": 100, "max": 100, "step": 1}}, [100]),
        ({"range": {"min": 0, "max": 100, "step": 1}}, list(range(0, 101, 1))),
        ({"range": {"min": 0, "max": 100, "step": 3}}, list(range(0, 100, 3)) + [100]),
    ],
)
def test_process_range(range_vals, expected):
    assert util.process_range(range_vals) == expected


@pytest.mark.parametrize(
    "functions, func_class, func_instance, expected",
    [
        # None
        ([], "cool", None, []),
        (
            thermostat.functions,
            "temperature",
            "safety-mode-max-temp",
            [
                29.5,
                30.0,
                30.5,
                31.0,
                31.5,
                32.0,
                32.5,
                33.0,
                33.5,
                34.0,
                34.5,
                35.0,
                35.5,
                36.0,
                36.5,
                37,
            ],
        ),
        (thermostat.functions, "temperature-units", None, ["fahrenheit", "celsius"]),
        # Not processable
        (thermostat.functions, "preset", "preset-1", []),
    ],
)
def test_process_function(functions, func_class, func_instance, expected):
    assert (
        util.process_function(functions, func_class, func_instance=func_instance)
        == expected
    )


@pytest.mark.parametrize(
    "celsius, fahrenheit",
    [
        (22, 72),
        (23, 73),
        (24, 75),
        (24.5, 76),
    ],
)
def test_calculate_hubspace_fahrenheit(celsius, fahrenheit):
    assert util.calculate_hubspace_fahrenheit(celsius) == fahrenheit


@pytest.mark.parametrize(
    "celsius, fahrenheit",
    [
        (22, 72),
        (23, 73),
        (24, 75),
        (24.5, 76),
    ],
)
def test_calculate_hubspace_celsius(celsius, fahrenheit):
    assert util.calculate_hubspace_celsius(fahrenheit) == celsius
