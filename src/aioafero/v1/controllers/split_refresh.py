"""Refresh filtered states on split clones after the parent metadevice changes.

Split callbacks already build clones with filtered states during discovery. After
an in-place parent patch (REST write echo or Conclave push), existing clones must
be re-filtered from the parent before ``RESOURCE_UPDATE_RESPONSE`` events fire.

Controller imports are deferred so this module cannot participate in an import
cycle with :mod:`event` / :mod:`base` (those controllers import ``event``).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from aioafero.device import AferoDevice, AferoState

SplitStateRefresher = Callable[[AferoDevice, str], list[AferoState]]


def _refresh_security_sensor_states(
    parent: AferoDevice, instance: str
) -> list[AferoState]:
    from .security_system import (  # noqa: PLC0415 - deferred to break import cycles
        get_valid_states as security_sensor_valid_states,
    )

    return security_sensor_valid_states(parent.states, int(instance))


@lru_cache(maxsize=1)
def _split_state_refreshers() -> dict[str, SplitStateRefresher]:
    """Build the refresher map once controllers have finished importing."""
    # Deferred imports: controllers import ``event``, which imports this module.
    from .exhaust_fan import (  # noqa: PLC0415
        SPLIT_IDENTIFIER as EXHAUST_FAN_SPLIT,
        get_valid_states as exhaust_fan_valid_states,
    )
    from .light import (  # noqa: PLC0415
        SPLIT_IDENTIFIER as LIGHT_SPLIT,
        get_valid_states as light_valid_states,
    )
    from .portable_ac import (  # noqa: PLC0415
        SPLIT_IDENTIFIER as PORTABLE_AC_SPLIT,
        get_valid_states as portable_ac_valid_states,
    )
    from .security_system import SENSOR_SPLIT_IDENTIFIER  # noqa: PLC0415

    return {
        LIGHT_SPLIT: light_valid_states,
        SENSOR_SPLIT_IDENTIFIER: _refresh_security_sensor_states,
        EXHAUST_FAN_SPLIT: exhaust_fan_valid_states,
        PORTABLE_AC_SPLIT: lambda parent, _instance: portable_ac_valid_states(parent),
    }


def split_instance_from_device(device: AferoDevice) -> str | None:
    """Return the split-zone instance key for a clone."""
    if device.split is None:
        return None
    return device.split.instance


def refresh_split_clone_states(parent: AferoDevice, clone: AferoDevice) -> None:
    """Copy filtered parent states onto a split clone before emitting events."""
    instance = split_instance_from_device(clone)
    if instance is None or not clone.split_identifier:
        return
    refresher = _split_state_refreshers().get(clone.split_identifier)
    if refresher is None:
        return
    clone.states = refresher(parent, instance)
