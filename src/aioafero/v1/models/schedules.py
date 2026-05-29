"""Representation of Afero per-device schedules.

These are recurring on-device events (stored in a device attribute, encoded by
the backend), exposed at ``/v1/accounts/{accountId}/metadevices/{deviceId}/schedules``
on the data-host backend. A device holds one (or more) ``DeviceSchedule``
objects, each with a list of ``ScheduleEvent``s. An event runs a device function
(e.g. a water timer's ``timer``/``spigot-1`` for N minutes) at a time, either on
fixed ``daysOfWeek`` (ABSOLUTE) or every ``intervalDays`` (PERIODIC).

Wire payloads use camelCase; these dataclasses use snake_case with
``to_afero``/``from_afero`` converters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Day-of-week enum used by the event ``daysOfWeek`` array.
DAYS_OF_WEEK: tuple[str, ...] = (
    "SUNDAY",
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
)
# Opaque tag the app stores on each schedule object; round-tripped on create.
DEFAULT_SCHEDULE_TAG = '{"version":2,"outlet":null,"weekly":null,"index":null}'


def normalize_days(days) -> list[str]:
    """Coerce day names/abbreviations (any case) into the Afero enum.

    Raises ValueError on an unknown day so a typo fails loudly.
    """
    out: list[str] = []
    for day in days or []:
        code = str(day).strip().upper()[:3]
        full = next((d for d in DAYS_OF_WEEK if d.startswith(code)), None)
        if full is None:
            raise ValueError(f"Unknown day of week: {day!r}")
        if full not in out:
            out.append(full)
    return out


@dataclass
class ScheduleEvent:
    """A single recurring action within a schedule."""

    function_instance: str  # e.g. "spigot-1"
    value: Any  # the value to set (e.g. timer minutes)
    hour: int
    minute: int
    function_class: str = "timer"
    days_of_week: list[str] = field(default_factory=list)  # ABSOLUTE
    time_type: str = "ABSOLUTE"  # or "PERIODIC"
    interval_days: int = 0  # PERIODIC: run every N days
    start_date_local: dict | None = None  # PERIODIC: {year,month,day,hour,minute}
    enabled: bool = True
    utc: bool = False

    def to_afero(self) -> dict[str, Any]:
        """Value to send to the Afero API (server assigns ids)."""
        payload: dict[str, Any] = {
            "enabled": self.enabled,
            "timeType": self.time_type,
            "daysOfWeek": list(self.days_of_week),
            "utc": self.utc,
            "intervalDays": self.interval_days,
            "hour": self.hour,
            "minute": self.minute,
            "semanticValues": [
                {
                    "functionClass": self.function_class,
                    "functionInstance": self.function_instance,
                    "value": self.value,
                }
            ],
        }
        if self.start_date_local is not None:
            payload["startDateLocal"] = self.start_date_local
        return payload

    @classmethod
    def from_afero(cls, data: dict) -> ScheduleEvent:
        """Build from an Afero API event object."""
        sv = (data.get("semanticValues") or [{}])[0]
        return cls(
            function_instance=sv.get("functionInstance"),
            value=sv.get("value"),
            function_class=sv.get("functionClass", "timer"),
            hour=data.get("hour", 0),
            minute=data.get("minute", 0),
            days_of_week=list(data.get("daysOfWeek", [])),
            time_type=data.get("timeType", "ABSOLUTE"),
            interval_days=data.get("intervalDays", 0),
            start_date_local=data.get("startDateLocal"),
            enabled=data.get("enabled", True),
            utc=data.get("utc", False),
        )

    @classmethod
    def weekly(
        cls,
        function_instance: str,
        value: Any,
        hour: int,
        minute: int,
        days=None,
        function_class: str = "timer",
        enabled: bool = True,
    ) -> ScheduleEvent:
        """Convenience builder for an ABSOLUTE weekly event (all days if none)."""
        if not 0 <= hour <= 23:
            raise ValueError(f"hour must be 0-23, got {hour}")
        if not 0 <= minute <= 59:
            raise ValueError(f"minute must be 0-59, got {minute}")
        resolved = normalize_days(days) if days else list(DAYS_OF_WEEK)
        return cls(
            function_instance=function_instance,
            value=value,
            hour=hour,
            minute=minute,
            function_class=function_class,
            days_of_week=resolved,
            enabled=enabled,
        )


@dataclass
class DeviceSchedule:
    """A schedule object on a device, holding one or more events."""

    events: list[ScheduleEvent] = field(default_factory=list)
    schedule_id: str | None = None
    tag: str = DEFAULT_SCHEDULE_TAG
    # Set by the backend; read-only for callers.
    device_attribute_id: int | None = None
    device_attribute_data: str | None = None

    def to_afero(self) -> dict[str, Any]:
        """Value to send to the Afero API. ``scheduleId`` is omitted on create;
        ``deviceAttributeData`` is derived by the backend from ``events``."""
        payload: dict[str, Any] = {
            "tag": self.tag,
            "events": [e.to_afero() for e in self.events],
        }
        if self.schedule_id is not None:
            payload["scheduleId"] = self.schedule_id
        return payload

    @classmethod
    def from_afero(cls, data: dict) -> DeviceSchedule:
        """Build from an Afero API schedule object."""
        return cls(
            events=[ScheduleEvent.from_afero(e) for e in data.get("events", [])],
            schedule_id=data.get("id"),
            tag=data.get("tag", DEFAULT_SCHEDULE_TAG),
            device_attribute_id=data.get("deviceAttributeId"),
            device_attribute_data=data.get("deviceAttributeData"),
        )
