import asyncio
import dataclasses
import logging
from unittest.mock import AsyncMock

import pytest
from aiohttp.web_exceptions import HTTPForbidden, HTTPTooManyRequests

from aioafero import InvalidAuth
from aioafero.v1.controllers import event
from aioafero.v1.models.resource import ResourceTypes

from .. import utils

a21_light = utils.create_devices_from_data("light-a21.json")[0]
switch = utils.create_devices_from_data("switch-HPDA311CWB.json")[0]


@pytest.mark.asyncio
async def test_properties(bridge):
    stream = bridge.events
    assert len(stream._bg_tasks) == 2
    stream._status = event.EventStreamStatus.CONNECTING
    assert stream.connected is False
    assert stream.status == event.EventStreamStatus.CONNECTING
    stream._status = event.EventStreamStatus.CONNECTED
    assert stream.connected is True
    stream.polling_interval = 1
    assert stream._polling_interval == 1
    assert stream.polling_interval == 1


@pytest.mark.asyncio
async def test_initialize(bridge):
    stream = bridge.events
    assert len(stream._bg_tasks) == 2


@pytest.mark.asyncio
async def test_stop(bridge):
    stream = bridge.events
    await stream.stop()
    assert len(stream._bg_tasks) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call,event_filter,resource_filter,expected",
    [
        (min, None, None, (min, None, None)),
        (
            min,
            event.EventType.RESOURCE_UPDATED,
            max,
            (min, (event.EventType.RESOURCE_UPDATED,), (max,)),
        ),
        (
            min,
            (event.EventType.RESOURCE_UPDATED, event.EventType.RESOURCE_DELETED),
            max,
            (
                min,
                (event.EventType.RESOURCE_UPDATED, event.EventType.RESOURCE_DELETED),
                (max,),
            ),
        ),
    ],
)
async def test_subscribe(call, event_filter, resource_filter, expected, mocked_bridge):
    events = mocked_bridge.events
    unsub = events.subscribe(call, event_filter, resource_filter)
    assert callable(unsub)
    assert len(events._subscribers) == 1
    assert events._subscribers[0] == expected
    unsub()
    assert len(events._subscribers) == 0


@pytest.mark.asyncio
async def test_event_reader_dev_add(bridge, mocker):
    stream = bridge.events
    stream._subscribers = []
    await stream.stop()

    def afero_dev(dev):
        return dev

    mocker.patch.object(bridge, "fetch_data", AsyncMock(return_value=[a21_light]))
    mocker.patch.object(event, "get_afero_device", side_effect=afero_dev)
    await stream.initialize_reader()
    max_retry = 10
    retry = 0
    while True:
        if retry >= max_retry:
            raise AssertionError("Item never added")
        if stream._event_queue.qsize() == 0:
            retry += 1
            await asyncio.sleep(0.1)
        else:
            break
    assert stream._event_queue.qsize() != 0
    event_to_process = await stream._event_queue.get()
    assert event_to_process == {
        "type": event.EventType.RESOURCE_ADDED,
        "device_id": a21_light.id,
        "device": a21_light,
        "force_forward": False,
    }


@pytest.mark.asyncio
async def test_add_job(bridge, mocker):
    stream = bridge.events
    await stream.stop()
    stream.add_job(None)
    assert stream._event_queue.qsize() == 1


def gather_data_happy_path():
    yield []


def gather_data_timeout_gen():
    yield asyncio.TimeoutError("blah blah blah")
    yield []


def gather_data_error_gen():
    yield HTTPForbidden()
    yield []


def gather_data_multi_error_gen():
    yield HTTPForbidden()
    yield HTTPTooManyRequests()
    yield []


def gather_data_bad_collection():
    yield ValueError(["bad data"])
    yield []


def gather_data_invalid_auth():
    yield InvalidAuth()
    yield []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, response_gen, expected_messages, expected_error, expected_emits",
    [
        # Successful with no issues
        (
            event.EventStreamStatus.CONNECTING,
            gather_data_happy_path,
            [],
            None,
            [event.EventType.CONNECTED],
        ),
        # Successful but already connected
        (
            event.EventStreamStatus.CONNECTED,
            gather_data_happy_path,
            [],
            None,
            [],
        ),
        # Timeout error
        (
            event.EventStreamStatus.CONNECTING,
            gather_data_timeout_gen,
            ["Timeout when contacting Afero IoT API"],
            None,
            [event.EventType.DISCONNECTED, event.EventType.CONNECTED],
        ),
        # Unknown error
        (event.EventStreamStatus.CONNECTING, None, ["kaboom"], KeyError("kaboom"), []),
        # Retry error
        (
            event.EventStreamStatus.CONNECTING,
            gather_data_error_gen,
            ["seconds before next poll", "Lost connection to the Afero IoT API"],
            None,
            [event.EventType.DISCONNECTED, event.EventType.RECONNECTED],
        ),
        # Ensure the messages only appears once
        (
            event.EventStreamStatus.CONNECTING,
            gather_data_multi_error_gen,
            ["Lost connection to the Afero IoT API"],
            None,
            [event.EventType.DISCONNECTED, event.EventType.RECONNECTED],
        ),
        # Data comes back incorrectly from Hubspace
        (
            event.EventStreamStatus.CONNECTING,
            gather_data_bad_collection,
            ["Unexpected data from Afero IoT API, ['bad data']"],
            None,
            [event.EventType.DISCONNECTED, event.EventType.RECONNECTED],
        ),
        # Invalid refresh token
        (
            event.EventStreamStatus.CONNECTING,
            gather_data_invalid_auth,
            ["Invalid credentials provided."],
            None,
            [event.EventType.DISCONNECTED, event.EventType.RECONNECTED],
        ),
    ],
)
async def test_gather_data(
    status,
    response_gen,
    expected_messages,
    expected_error,
    expected_emits,
    bridge,
    mocker,
    caplog,
):
    caplog.set_level(logging.DEBUG)
    stream = bridge.events
    stream.polling_interval = 0.0
    await stream.stop()
    stream._status = status

    if response_gen:
        mocker.patch.object(
            bridge,
            "fetch_data",
            side_effect=response_gen(),
        )
    else:
        mocker.patch.object(
            bridge,
            "fetch_data",
            side_effect=expected_error,
        )
    emit_calls = mocker.patch.object(stream, "emit")
    if response_gen:
        await stream.gather_data()
    else:
        with pytest.raises(expected_error.__class__):
            await stream.gather_data()
    assert emit_calls.call_count == len(expected_emits)
    for index, emit in enumerate(expected_emits):
        assert emit_calls.call_args_list[index][0][0] == emit, f"Issue at index {index}"
    for message in expected_messages:
        assert message in caplog.text
        assert caplog.text.count(message) == 1


@pytest.mark.asyncio
async def test_generate_events_from_data(bridge, mocker):
    stream = bridge.events
    await stream.stop()
    a21_light = utils.create_devices_from_data("light-a21.json")[0]
    switch = utils.create_devices_from_data("switch-HPDA311CWB.json")[0]
    bridge._known_devs = {
        switch.id: bridge.switches,
        "doesnt_exist_list": bridge.lights,
    }
    bad_switch = dataclasses.replace(switch)
    bad_switch.device_class = ""
    mocker.patch.object(event, "get_afero_device", side_effect=lambda x: x)
    await stream.generate_events_from_data([a21_light, switch, bad_switch])
    assert stream._event_queue.qsize() == 3
    assert await stream._event_queue.get() == {
        "type": event.EventType.RESOURCE_ADDED,
        "device_id": a21_light.id,
        "device": a21_light,
        "force_forward": False,
    }
    assert await stream._event_queue.get() == {
        "type": event.EventType.RESOURCE_UPDATED,
        "device_id": switch.id,
        "device": switch,
        "force_forward": False,
    }
    assert await stream._event_queue.get() == {
        "type": event.EventType.RESOURCE_DELETED,
        "device_id": "doesnt_exist_list",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "gather_data_return,gather_data_side_effect,"
        "generate_events_from_data_side_effect,expected_emits,expected_queue"
    ),
    [
        # Happy path
        (
            [a21_light, switch],
            None,
            [],
            [],
            [
                {
                    "type": event.EventType.RESOURCE_ADDED,
                    "device_id": a21_light.id,
                    "device": a21_light,
                    "force_forward": False,
                },
                {
                    "type": event.EventType.RESOURCE_UPDATED,
                    "device_id": switch.id,
                    "device": switch,
                    "force_forward": False,
                },
                {
                    "type": event.EventType.RESOURCE_DELETED,
                    "device_id": "doesnt_exist_list",
                },
            ],
        ),
        # Issue collecting data
        (None, KeyError, None, [event.EventType.DISCONNECTED], []),
        # Issue processing collected data
        (None, None, KeyError, [], []),
    ],
)
async def test_perform_poll(
    gather_data_return,
    gather_data_side_effect,
    generate_events_from_data_side_effect,
    expected_emits,
    expected_queue,
    bridge,
    mocker,
):
    stream = bridge.events
    await stream.stop()
    if gather_data_side_effect:
        mocker.patch.object(stream, "gather_data", side_effect=gather_data_side_effect)
    else:
        mocker.patch.object(
            stream, "gather_data", AsyncMock(return_value=gather_data_return)
        )
    if generate_events_from_data_side_effect:
        mocker.patch.object(
            stream,
            "generate_events_from_data",
            side_effect=generate_events_from_data_side_effect,
        )

    bridge._known_devs = {
        switch.id: bridge.switches,
        "doesnt_exist_list": bridge.lights,
    }
    emit_calls = mocker.patch.object(stream, "emit")
    mocker.patch.object(event, "get_afero_device", side_effect=lambda x: x)

    await stream.perform_poll()
    assert emit_calls.call_count == len(expected_emits)
    for index, emit in enumerate(expected_emits):
        assert emit_calls.call_args_list[index][0][0] == emit, f"Issue at index {index}"
    assert stream._event_queue.qsize() == len(expected_queue)
    for index, event_to_process in enumerate(expected_queue):
        assert (
            await stream._event_queue.get() == event_to_process
        ), f"Issue at index {index}"


@pytest.mark.asyncio
async def test_event_reader_dev_update(bridge, mocker):
    stream = bridge.events
    bridge.lights.initialize({})
    await bridge.lights.initialize_elem(a21_light)
    bridge.add_device(a21_light.id, bridge.lights)
    await stream.stop()

    mocker.patch.object(stream, "gather_data", AsyncMock(return_value=[a21_light]))
    mocker.patch.object(event, "get_afero_device", side_effect=lambda x: x)
    await stream.initialize_reader()
    max_retry = 10
    retry = 0
    while True:
        if retry >= max_retry:
            raise AssertionError("Item never added")
        if stream._event_queue.qsize() == 0:
            retry += 1
            await asyncio.sleep(0.1)
        else:
            break
    assert stream._event_queue.qsize() != 0
    event_to_process = await stream._event_queue.get()
    assert event_to_process == {
        "type": event.EventType.RESOURCE_UPDATED,
        "device_id": a21_light.id,
        "device": a21_light,
        "force_forward": False,
    }


@pytest.mark.asyncio
async def test_event_reader_dev_delete(bridge, mocker):
    stream = bridge.events
    bridge.lights.initialize({})
    bridge.lights.initialize_elem(a21_light)
    bridge.add_device(a21_light.id, bridge.lights)
    await stream.stop()

    def afero_dev(dev):
        return dev

    mocker.patch.object(bridge, "fetch_data", AsyncMock(return_value=[]))
    mocker.patch.object(event, "get_afero_device", side_effect=afero_dev)
    await stream.initialize_reader()
    max_retry = 10
    retry = 0
    while True:
        if retry >= max_retry:
            raise AssertionError("Item never added")
        if stream._event_queue.qsize() == 0:
            retry += 1
            await asyncio.sleep(0.1)
        else:
            break
    assert stream._event_queue.qsize() != 0
    event_to_process = await stream._event_queue.get()
    assert event_to_process == {
        "type": event.EventType.RESOURCE_DELETED,
        "device_id": a21_light.id,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pop_event,has_exception",
    [
        (
            {
                "type": event.EventType.RESOURCE_UPDATED,
                "device_id": a21_light.id,
                "device": a21_light,
                "force_forward": False,
            },
            False,
        ),
        (
            {
                "type": event.EventType.RESOURCE_UPDATED,
                "device_id": a21_light.id,
                "device": a21_light,
                "force_forward": False,
            },
            True,
        ),
    ],
)
async def test_process_event(pop_event, has_exception, bridge, mocker, caplog):
    stream = bridge.events
    await stream.stop()
    await stream._event_queue.put(pop_event)
    if not has_exception:
        emit_calls = mocker.patch.object(stream, "emit")
        await stream.process_event()
        assert emit_calls.call_count == 1
    else:
        mocker.patch.object(stream, "emit", side_effect=KeyError)
        await stream.process_event()
        assert "Unhandled exception. Please open a bug report" in caplog.text


@pytest.mark.asyncio
async def test___event_processor(bridge, mocker):
    stream = bridge.events
    emit = mocker.patch.object(stream, "emit")
    exp_event = event.AferoEvent(
        type=event.EventType.RESOURCE_DELETED, device_id="1234"
    )
    stream._event_queue.put_nowait(exp_event)
    await stream.initialize_processor()
    max_retry = 10
    retry = 0
    while True:
        if retry >= max_retry:
            raise AssertionError("Item never removed")
        if stream._event_queue.qsize() == 1:
            retry += 1
            await asyncio.sleep(0.1)
        else:
            break
    assert stream._event_queue.qsize() == 0
    emit.assert_called_once_with(exp_event["type"], exp_event)


@pytest.mark.asyncio
@pytest.mark.parametrize("is_coroutine", [True, False])
@pytest.mark.parametrize(
    "event_type, event_filter, expected",
    [
        (event.EventType.RESOURCE_ADDED, (event.EventType.RESOURCE_ADDED,), True),
        (event.EventType.RESOURCE_UPDATED, (event.EventType.RESOURCE_ADDED,), False),
    ],
)
async def test_emit_event_type(
    event_type, event_filter, expected, is_coroutine, bridge, mocker
):
    stream = bridge.events
    stream._subscribers = []
    await stream.stop()

    event_to_emit = event.AferoEvent(
        type=event_type, device_id=a21_light.id, device=a21_light
    )

    callback = mocker.AsyncMock() if is_coroutine else mocker.Mock()
    stream.subscribe(callback, event_filter=event_filter)
    stream.emit(event_type, event_to_emit)
    if expected:
        callback.assert_called_once()
    else:
        callback.assert_not_called()


@pytest.mark.asyncio
async def test_emit_invalid_auth(bridge, mocker):
    stream = bridge.events
    stream._subscribers = []
    await stream.stop()
    callback = mocker.AsyncMock()
    event_type = event.EventType.INVALID_AUTH
    stream.subscribe(callback, event_filter=(event_type,))
    event_to_emit = event.AferoEvent(type=event_type)
    stream.emit(event_type, event_to_emit)
    callback.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("is_coroutine", [True, False])
@pytest.mark.parametrize(
    "device, resource_filter, expected",
    [
        (a21_light, (ResourceTypes.LIGHT,), True),
        (a21_light, (ResourceTypes.FAN,), False),
        (
            switch,
            (
                ResourceTypes.LIGHT,
                ResourceTypes.FAN,
            ),
            True,
        ),
    ],
)
async def test_emit_resource_filter(
    device, resource_filter, expected, is_coroutine, bridge, mocker
):
    stream = bridge.events
    await stream.stop()

    event_to_emit = event.AferoEvent(
        type=event.EventType.RESOURCE_UPDATED, device_id=device.id, device=device
    )

    callback = mocker.AsyncMock() if is_coroutine else mocker.Mock()
    res_filter = tuple(x.value for x in resource_filter)
    stream.subscribe(callback, resource_filter=res_filter)
    stream.emit(event.EventType.RESOURCE_UPDATED, event_to_emit)
    if expected:
        callback.assert_called_once()
    else:
        callback.assert_not_called()


@pytest.mark.asyncio
async def test_emit_resource_filter_exception(bridge, caplog):
    stream = bridge.events
    event_to_emit = event.AferoEvent(
        type=event.EventType.RESOURCE_UPDATED,
        device_id="cool_id",
        device="im not a hubspace device",
    )
    stream.subscribe(min, resource_filter=(ResourceTypes.LIGHT.value,))
    stream.emit(event.EventType.RESOURCE_UPDATED, event_to_emit)
    assert "Unhandled exception. Please open a bug report" in caplog.text
