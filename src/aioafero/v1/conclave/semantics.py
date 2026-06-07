"""Build a per-device attribute index from metadevice semantics.

Conclave ``attribute.id`` values map to ``deviceValues[].key`` in each device's
``description.functions[]`` semantics — **per-device-profile**, never a global
enum.

This module turns the cached ``AferoDevice.functions`` into a lookup index
keyed by ``str(attribute.id)``. The decoded ``(functionClass, functionInstance,
value)`` triple feeds straight back into the existing
:class:`~aioafero.device.AferoState` cache that REST polls already populate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from aioafero.device import AferoDevice


@dataclass(frozen=True)
class SemanticBinding:
    """One ``deviceValues[]`` entry from a metadevice's semantics.

    :param function_class: ``functionClass`` for the parent function
        (e.g. ``power``, ``brightness``, ``color-mode``).
    :param function_instance: Optional ``functionInstance``
        (e.g. ``light-power``, ``fan-power``).
    :param value_name: Name of the ``functions[].values[]`` entry
        (e.g. ``on``, ``off``, ``sequence``, ``hanukkah-fade``).
    :param device_value: Optional encoded value from ``deviceValues[].value``
        — set for enum mappings (e.g. color modes) and blob mappings
        (e.g. custom effect sequences); ``None`` for numeric/free-form values.
    """

    function_class: str
    function_instance: str | None
    value_name: str | None
    device_value: str | None


AttributeIndex = dict[str, list[SemanticBinding]]


def build_attribute_index(device: AferoDevice) -> AttributeIndex:
    """Walk ``device.functions`` and index attribute key → binding(s).

    Multiple bindings per key are normal (e.g. key ``1`` → power on/off with
    distinct ``deviceValue``; key ``5`` → multiple color modes).

    :param device: Discovered :class:`~aioafero.device.AferoDevice` with its
        ``functions`` populated (post REST discovery).

    :returns: Dict mapping ``str(attribute.id)`` to a list of
        :class:`SemanticBinding` entries in declaration order.
    """
    index: AttributeIndex = {}
    for func in device.functions or []:
        function_class = func.get("functionClass")
        if not function_class:
            continue
        function_instance = func.get("functionInstance")
        for value in func.get("values", []) or []:
            if not isinstance(value, dict):
                continue
            value_name = value.get("name")
            for dv in value.get("deviceValues", []) or []:
                if not isinstance(dv, dict) or dv.get("type") != "attribute":
                    continue
                key = dv.get("key")
                if key is None:
                    continue
                binding = SemanticBinding(
                    function_class=function_class,
                    function_instance=function_instance,
                    value_name=value_name,
                    device_value=_as_str(dv.get("value")),
                )
                index.setdefault(str(key), []).append(binding)
    return index


def resolve_binding(
    index: AttributeIndex,
    attribute_id: object,
    attribute_value: object,
    attribute_data: object | None = None,
) -> SemanticBinding | None:
    """Resolve a single push attribute to one :class:`SemanticBinding`.

    Resolution order:

    1. Look up bindings by ``str(attribute_id)``; return ``None`` if unknown.
    2. If exactly one binding is registered, use it (numeric / free-form
       attribute — value carries through unchanged).
    3. Otherwise, prefer a binding whose ``device_value`` matches the
       attribute's decoded ``value`` (enum keys like ``power``, ``color-mode``).
    4. Fall back to matching ``device_value`` against the raw ``data`` blob
       (used for ``color-sequence/custom`` on key ``300`` where Conclave pushes
       the encoded blob and the friendly name lives in semantics).
    """
    if attribute_id is None:
        return None
    bindings = index.get(str(attribute_id))
    if not bindings:
        return None
    if len(bindings) == 1:
        return bindings[0]
    for candidate in (_as_str(attribute_value), _as_str(attribute_data)):
        if candidate is None:
            continue
        matched = _binding_for_device_value(bindings, candidate)
        if matched is not None:
            return matched
    return bindings[0]


def coerce_rest_state_value(
    binding: SemanticBinding,
    attribute_value: object,
    attribute_data: object | None = None,
) -> object:
    """Translate a Conclave attribute payload into REST-shaped ``AferoState.value``.

    Conclave pushes decoded strings such as ``"0"`` / ``"1"`` for booleans and
    ``"4000"`` for color temperature. REST discovery and controllers expect
    semantic names (``"on"`` / ``"off"``) and suffixed units (``"4000K"``).
    """
    value_str = _as_str(attribute_value)
    data_str = _as_str(attribute_data)

    named = _semantic_value_name(binding, value_str, data_str)
    if named is not None:
        return named

    if binding.function_class in ("power", "toggle") and value_str in ("0", "1"):
        return "off" if value_str == "0" else "on"

    if (
        binding.function_class == "color-temperature"
        and value_str
        and value_str.isdigit()
    ):
        return f"{value_str}K"

    if binding.function_class == "brightness" and value_str and value_str.isdigit():
        return int(value_str)

    return attribute_value


def _binding_for_device_value(
    bindings: list[SemanticBinding],
    candidate: str,
) -> SemanticBinding | None:
    """Return the first binding whose ``device_value`` matches ``candidate``."""
    for binding in bindings:
        if binding.device_value is not None and _values_equal(
            binding.device_value, candidate
        ):
            return binding
    return None


def _semantic_value_name(
    binding: SemanticBinding,
    value_str: str | None,
    data_str: str | None,
) -> str | None:
    """Return the semantics ``value_name`` when a push matches ``device_value``."""
    if binding.device_value is None or binding.value_name is None:
        return None
    for candidate in (value_str, data_str):
        if candidate is not None and _values_equal(binding.device_value, candidate):
            return binding.value_name
    return None


def _as_str(value: object) -> str | None:
    """Convert an attribute or deviceValues payload into a comparable string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _values_equal(device_value: str, candidate: str) -> bool:
    """Case-insensitive equality (Conclave pushes mixed-case hex blobs)."""
    return device_value.lower() == candidate.lower()
