"""Tests for the SchedulesController (per-device schedule client)."""

import pytest
from aioresponses import CallbackResult

from aioafero.v1 import v1_const
from aioafero.v1.models.schedules import DeviceSchedule, ScheduleEvent

DATA_HOST = v1_const.AFERO_CLIENTS["hubspace"]["API_DATA_HOST"]


def make_resp(mocker, json_data=None, status=200):
    resp = mocker.MagicMock()
    resp.status = status
    resp.raise_for_status = mocker.MagicMock()
    resp.json = mocker.AsyncMock(return_value=json_data)
    return resp


def raw_schedule(sched_id, instance, minutes, hour, minute):
    return {
        "id": sched_id,
        "tag": '{"version":2}',
        "deviceAttributeId": 49002,
        "deviceAttributeData": "03FF04000134001E00",
        "events": [
            {
                "enabled": True,
                "timeType": "ABSOLUTE",
                "daysOfWeek": ["MONDAY"],
                "hour": hour,
                "minute": minute,
                "intervalDays": 0,
                "semanticValues": [
                    {"functionClass": "timer", "functionInstance": instance, "value": minutes}
                ],
            }
        ],
    }


@pytest.fixture
def sched(mocked_bridge):
    return mocked_bridge.schedules


@pytest.mark.asyncio
async def test_get_schedules(sched, mocker):
    sched._bridge.request = mocker.AsyncMock(
        return_value=make_resp(mocker, [raw_schedule("sch-1", "spigot-2", 30, 4, 0)])
    )
    out = await sched.get_schedules("dev-1")
    assert len(out) == 1 and out[0].schedule_id == "sch-1"
    assert out[0].events[0].function_instance == "spigot-2"
    method, url = sched._bridge.request.call_args.args
    assert method == "GET"
    assert url.endswith("/v1/accounts/mocked-account-id/metadevices/dev-1/schedules")
    # routed to the data host via the Host header
    assert sched._bridge.request.call_args.kwargs["headers"]["host"] == DATA_HOST


@pytest.mark.asyncio
async def test_create_schedule(sched, mocker):
    sched._bridge.request = mocker.AsyncMock(
        return_value=make_resp(mocker, raw_schedule("sch-new", "spigot-1", 20, 6, 0))
    )
    obj = DeviceSchedule(events=[ScheduleEvent.weekly("spigot-1", 20, 6, 0, days=["MON"])])
    result = await sched.create_schedule("dev-1", obj)
    assert result.schedule_id == "sch-new"
    method, url = sched._bridge.request.call_args.args
    assert method == "POST"
    assert url.endswith("/v1/accounts/mocked-account-id/metadevices/dev-1/schedules")
    body = sched._bridge.request.call_args.kwargs["json"]
    assert "scheduleId" not in body
    assert body["events"][0]["semanticValues"][0]["functionInstance"] == "spigot-1"


@pytest.mark.asyncio
async def test_delete_schedule(sched, mocker):
    sched._bridge.request = mocker.AsyncMock(return_value=make_resp(mocker, None, status=200))
    await sched.delete_schedule("dev-1", "sch-1")
    method, url = sched._bridge.request.call_args.args
    assert method == "DELETE"
    assert url.endswith("/v1/accounts/mocked-account-id/metadevices/dev-1/schedules/sch-1")


@pytest.mark.asyncio
async def test_add_event_merges(sched, mocker):
    # GET existing (1 event) -> DELETE it -> POST merged (2 events)
    sched._bridge.request = mocker.AsyncMock(
        side_effect=[
            make_resp(mocker, [raw_schedule("sch-old", "spigot-1", 20, 22, 0)]),  # GET
            make_resp(mocker, None, status=200),  # DELETE
            make_resp(mocker, raw_schedule("sch-new", "spigot-2", 30, 5, 30)),  # POST
        ]
    )
    new_ev = ScheduleEvent.weekly("spigot-2", 30, 5, 30)
    await sched.add_event("dev-1", new_ev)
    assert sched._bridge.request.await_count == 3
    # The POST body should carry BOTH the preserved + the new event
    post_call = sched._bridge.request.await_args_list[2]
    assert post_call.args[0] == "POST"
    instances = [
        sv["functionInstance"]
        for e in post_call.kwargs["json"]["events"]
        for sv in e["semanticValues"]
    ]
    assert instances == ["spigot-1", "spigot-2"]


@pytest.mark.asyncio
async def test_create_schedule_e2e(bridge_with_acct, mock_aioresponse, mocker):
    """Full stack: real request -> bearer + data-host Host header -> JSON body."""
    bridge = bridge_with_acct
    mocker.patch.object(bridge, "_account_id", "acct-1")
    url = bridge.generate_api_url(
        v1_const.AFERO_GENERICS["API_DEVICE_SCHEDULES_ENDPOINT"].format("acct-1", "dev-1")
    )
    captured = {}

    def cb(called_url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        captured["body"] = kwargs.get("json")
        return CallbackResult(status=200, payload=raw_schedule("sch-9", "spigot-2", 30, 5, 30))

    mock_aioresponse.post(url, callback=cb)
    obj = DeviceSchedule(events=[ScheduleEvent.weekly("spigot-2", 30, 5, 30)])
    result = await bridge.schedules.create_schedule("dev-1", obj)

    assert result.schedule_id == "sch-9"
    assert captured["headers"].get("Authorization") == "Bearer mock-token"
    assert captured["headers"].get("host") == DATA_HOST
    assert captured["body"]["events"][0]["hour"] == 5
