"""Helpers for suppressing unchanged resource updates."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from aioafero.v1.models.features import DimmingFeature, OnFeature, OpenFeature


@runtime_checkable
class SupportsFeatureUpdateComparison(Protocol):
    """Resource that can resolve Put fields against cached state."""

    def feature_for_update_comparison(
        self, field_name: str, put_feature: Any | None
    ) -> Any | None:
        """Return the cached feature to compare with ``put_feature``."""


def default_feature_for_update_comparison(
    elem: Any, field_name: str, put_feature: Any | None
) -> Any | None:
    """Look up a dict-backed feature by instance when Put targets one entry."""
    current = getattr(elem, field_name, None)
    if isinstance(current, dict) and put_feature is not None:
        func_instance = getattr(put_feature, "func_instance", None)
        if func_instance in current:
            return current[func_instance]
        func_class = getattr(put_feature, "func_class", None)
        mapped_key = (func_class, func_instance)
        if mapped_key in current:
            return current[mapped_key]
    return current


def features_equivalent_for_update(
    put_feature: Any | None, cached_feature: Any | None
) -> bool:
    """Return True when Put would not change wire-relevant cached state.

    Compares semantic fields for common feature types so synthetic comparison
    objects (e.g. channel toggles) stay stable if dataclasses gain metadata.
    """
    if put_feature is cached_feature:
        return True
    if put_feature is None or cached_feature is None:
        return False
    if isinstance(put_feature, OnFeature) and isinstance(cached_feature, OnFeature):
        return (
            put_feature.on == cached_feature.on
            and put_feature.func_class == cached_feature.func_class
            and put_feature.func_instance == cached_feature.func_instance
        )
    if isinstance(put_feature, OpenFeature) and isinstance(cached_feature, OpenFeature):
        return (
            put_feature.open == cached_feature.open
            and put_feature.func_class == cached_feature.func_class
            and put_feature.func_instance == cached_feature.func_instance
        )
    if isinstance(put_feature, DimmingFeature) and isinstance(
        cached_feature, DimmingFeature
    ):
        return (
            put_feature.brightness == cached_feature.brightness
            and put_feature.func_instance == cached_feature.func_instance
        )
    return put_feature == cached_feature


def resolve_feature_for_update_comparison(
    elem: Any, field_name: str, put_feature: Any | None
) -> Any | None:
    """Resolve the cached feature to compare against a Put field."""
    if isinstance(elem, SupportsFeatureUpdateComparison):
        return elem.feature_for_update_comparison(field_name, put_feature)
    return default_feature_for_update_comparison(elem, field_name, put_feature)
