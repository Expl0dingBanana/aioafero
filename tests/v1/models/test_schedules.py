"""Tests for the per-device schedule data models."""

import json
from pathlib import Path

import pytest

from aioafero.v1.models.schedules import (
    DeviceSchedule,
    ScheduleEvent,
    normalize_days,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_normalize_days():
    assert normalize_days(["mon", "Wednesday", "FRI"]) == [
        "MONDAY",
        "WEDNESDAY",
        "FRIDAY",
    ]
    with pytest.raises(ValueError, match="Unknown day"):
        normalize_days(["Funday"])


def test_event_weekly_builder():
    ev = ScheduleEvent.weekly("spigot-1", 30, 5, 30, days=["mon", "wed", "fri"])
    assert ev.time_type == "ABSOLUTE"
    assert ev.days_of_week == ["MONDAY", "WEDNESDAY", "FRIDAY"]
    assert ev.function_class == "timer" and ev.function_instance == "spigot-1"
    # no days -> all 7
    assert len(ScheduleEvent.weekly("spigot-2", 10, 6, 0).days_of_week) == 7
    with pytest.raises(ValueError, match="hour must be"):
        ScheduleEvent.weekly("spigot-1", 5, 25, 0)


def test_event_to_afero():
    ev = ScheduleEvent.weekly("spigot-2", 30, 4, 0, days=["MON"])
    payload = ev.to_afero()
    assert payload["timeType"] == "ABSOLUTE"
    assert payload["daysOfWeek"] == ["MONDAY"]
    assert payload["hour"] == 4 and payload["minute"] == 0
    assert payload["semanticValues"] == [
        {"functionClass": "timer", "functionInstance": "spigot-2", "value": 30}
    ]
    assert "startDateLocal" not in payload


def test_event_periodic_round_trip():
    data = {
        "enabled": True,
        "timeType": "PERIODIC",
        "daysOfWeek": [],
        "utc": False,
        "intervalDays": 2,
        "hour": 0,
        "minute": 0,
        "startDateLocal": {"year": 2026, "month": 5, "day": 28, "hour": 1, "minute": 0},
        "semanticValues": [
            {"functionClass": "timer", "functionInstance": "spigot-1", "value": 60}
        ],
    }
    ev = ScheduleEvent.from_afero(data)
    assert ev.time_type == "PERIODIC"
    assert ev.interval_days == 2
    assert ev.start_date_local["day"] == 28
    assert ev.value == 60
    assert ev.to_afero()["startDateLocal"] == data["startDateLocal"]


def test_device_schedule_round_trip():
    data = {
        "id": "sch-1",
        "tag": '{"version":2}',
        "deviceAttributeId": 49002,
        "deviceAttributeData": "03FF04000134001E00",
        "events": [
            {
                "enabled": True,
                "timeType": "ABSOLUTE",
                "daysOfWeek": ["MONDAY", "WEDNESDAY"],
                "hour": 6,
                "minute": 30,
                "intervalDays": 0,
                "semanticValues": [
                    {"functionClass": "timer", "functionInstance": "spigot-2", "value": 20}
                ],
            }
        ],
    }
    sched = DeviceSchedule.from_afero(data)
    assert sched.schedule_id == "sch-1"
    assert sched.device_attribute_id == 49002
    assert sched.device_attribute_data == "03FF04000134001E00"
    assert len(sched.events) == 1
    assert sched.events[0].function_instance == "spigot-2"

    # to_afero omits scheduleId on create and never sends the derived hex
    create_payload = DeviceSchedule(events=sched.events).to_afero()
    assert "scheduleId" not in create_payload
    assert "deviceAttributeData" not in create_payload
    assert create_payload["events"][0]["semanticValues"][0]["value"] == 20


def test_from_afero_requires_semantic_values():
    with pytest.raises(ValueError, match="missing semanticValues"):
        ScheduleEvent.from_afero({"hour": 6, "minute": 0, "semanticValues": []})


def test_real_water_timer_schedule_dump_parses():
    """Parse a captured GET /schedules response from a live water timer.

    Confirms the model handles the real wire shape: one schedule object holding
    a mix of PERIODIC (every N days from a start date) and ABSOLUTE (weekly)
    events, and that re-creating it drops the server-derived fields.
    """
    raw = json.loads((DATA_DIR / "water-timer-schedules.json").read_text())
    schedules = [DeviceSchedule.from_afero(s) for s in raw]

    assert len(schedules) == 1
    sched = schedules[0]
    assert sched.schedule_id == "00000000-0000-4000-8000-000000000001"
    assert sched.device_attribute_id == 49002
    assert {e.time_type for e in sched.events} == {"PERIODIC", "ABSOLUTE"}

    periodic = next(e for e in sched.events if e.time_type == "PERIODIC")
    assert periodic.interval_days == 2
    assert periodic.start_date_local["hour"] == 1
    assert periodic.function_instance == "spigot-1"
    assert periodic.value == 60

    absolute = next(e for e in sched.events if e.time_type == "ABSOLUTE")
    assert absolute.hour == 4 and absolute.minute == 45
    assert len(absolute.days_of_week) == 7
    assert absolute.function_instance == "spigot-2"

    payload = DeviceSchedule(events=sched.events, tag=sched.tag).to_afero()
    assert "scheduleId" not in payload
    assert "deviceAttributeData" not in payload
    assert len(payload["events"]) == 2
    assert payload["events"][0]["startDateLocal"]["day"] == 28
