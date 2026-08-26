"""Refresh filtered states on split clones after the parent metadevice changes.

Split callbacks already build clones with filtered states during discovery. After
an in-place parent patch (REST write echo or Conclave push), existing clones must
be re-filtered from the parent before ``RESOURCE_UPDATE_RESPONSE`` events fire.
"""

from __future__ import annotations

from collections.abc import Callable

from aioafero.device import AferoDevice, AferoState

from .exhaust_fan import (
    SPLIT_IDENTIFIER as EXHAUST_FAN_SPLIT,
    get_valid_states as exhaust_fan_valid_states,
)
from .light import (
    SPLIT_IDENTIFIER as LIGHT_SPLIT,
    get_valid_states as light_valid_states,
)
from .portable_ac import (
    SPLIT_IDENTIFIER as PORTABLE_AC_SPLIT,
    get_valid_states as portable_ac_valid_states,
)
from .security_system import (
    SENSOR_SPLIT_IDENTIFIER,
    get_valid_states as security_sensor_valid_states,
)

SplitStateRefresher = Callable[[AferoDevice, str], list[AferoState]]


def _refresh_security_sensor_states(
    parent: AferoDevice, instance: str
) -> list[AferoState]:
    return security_sensor_valid_states(parent.states, int(instance))


SPLIT_STATE_REFRESHERS: dict[str, SplitStateRefresher] = {
    LIGHT_SPLIT: light_valid_states,
    SENSOR_SPLIT_IDENTIFIER: _refresh_security_sensor_states,
    EXHAUST_FAN_SPLIT: exhaust_fan_valid_states,
    PORTABLE_AC_SPLIT: lambda parent, _instance: portable_ac_valid_states(parent),
}


def split_instance_from_device(device: AferoDevice) -> str | None:
    """Return the split-zone instance key encoded in a clone metadevice id."""
    if not device.split_identifier:
        return None
    marker = f"-{device.split_identifier}-"
    if marker not in device.id:
        return None
    return device.id.rsplit(marker, 1)[1]


def refresh_split_clone_states(parent: AferoDevice, clone: AferoDevice) -> None:
    """Copy filtered parent states onto a split clone before emitting events."""
    instance = split_instance_from_device(clone)
    if instance is None or not clone.split_identifier:
        return
    refresher = SPLIT_STATE_REFRESHERS.get(clone.split_identifier)
    if refresher is None:
        return
    clone.states = refresher(parent, instance)
