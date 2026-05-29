"""Tests for the per-device schedule data models."""

import pytest

from aioafero.v1.models.schedules import (
    DeviceSchedule,
    ScheduleEvent,
    normalize_days,
)


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
