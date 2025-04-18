import pytest

from aioafero import util


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
