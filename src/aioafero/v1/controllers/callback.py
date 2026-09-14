"""Shared types for device-split callbacks (kept free of EventStream imports)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from aioafero.device import AferoDevice


class CallbackResponse(NamedTuple):
    """Callback response for DEVICE_SPLIT_CALLBACKS.

    :param split_devices: New devices that should be added to the overall list
    :param remove_original: Remove the original device from the list of devices
    """

    split_devices: Sequence[AferoDevice] = ()
    remove_original: bool = False
