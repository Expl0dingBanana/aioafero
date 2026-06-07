import asyncio
import ssl
from unittest.mock import AsyncMock

import pytest

from aioafero.errors import InvalidAuth
from aioafero.types import EventType
from aioafero.v1.conclave import client as client_module
from aioafero.v1.conclave.access import ConclaveAccess
from aioafero.v1.conclave.client import ConclaveStatus
from aioafero.v1.conclave.frames import HEARTBEAT_FRAME
from tests.v1.conclave.helpers import (
    ACCESS,
    FakeWriter,
    ScriptedReader,
    wire_frame,
    zlib_hello,
)


@pytest.mark.asyncio
async def test_connection_open_login_and_dispatch_loop(conclave_bridge):
    bridge, _, _ = conclave_bridge
    chunks = [
        zlib_hello(),
        wire_frame({"tunnel": {"version": "conclave 2.7.3"}}),
        wire_frame({"welcome": {"sessionId": 1, "channelId": "account-uuid"}}),
        wire_frame({"join": {"sessionId": 1, "type": "client"}}),
        b"\n",  # server heartbeat
        wire_frame(
            {
                "private": {
                    "sessionId": 0,
                    "event": "attr_change",
                    "data": {
                        "id": "8ad8cc7b5c18ce2a",
                        "attribute": {"id": 1, "data": "01", "value": "1"},
                    },
                }
            }
        ),
        wire_frame(
            {
                "private": {
                    "event": "status_change",
                    "data": {
                        "id": "8ad8cc7b5c18ce2a",
                        "status": {"available": False, "visible": False},
                    },
                }
            }
        ),
        # Drop in a noise frame that should be ignored.
        wire_frame({"foo": {"bar": 1}}),
        # Add a non-dict `private` payload — code should silently ignore it.
        wire_frame({"private": "string-not-dict"}),
        # And one with non-dict data.
        wire_frame({"private": {"event": "attr_change", "data": "nope"}}),
        # Lastly, an unhandled event type.
        wire_frame({"private": {"event": "weird", "data": {"id": "x"}}}),
    ]

    reader = ScriptedReader(chunks)
    writer = FakeWriter()

    async def fake_connect(_access):
        return reader, writer

    async def fake_request(_bridge, **_kwargs):
        return ACCESS

    conclave = client_module.ConclaveClient(
        bridge, connect=fake_connect, initial_backoff=0, max_backoff=0
    )

    # Patch the access helper inside the client module.
    original = client_module.request_conclave_access
    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    try:
        # Drive a single session synchronously instead of the reconnect loop.
        # The scripted reader returns EOF after the last chunk, which the
        # connection surfaces as ConnectionResetError — exactly how the
        # reconnect loop expects a server-side close.
        with pytest.raises(ConnectionResetError):
            await conclave._connect_and_serve()
    finally:
        client_module.request_conclave_access = original

    # Login JSON should have included channelId and the conclave token.
    written = writer.buffer.decode()
    assert '"channelId":"account-uuid"' in written
    assert '"accessToken":"conclave-token"' in written
    assert '"protocol":2' in written
    assert "{}" in written  # opening frame
    assert "\n" in written  # heartbeat ack

    # status_change in our scripted stream targeted an unknown device for the
    # mocked bridge, so just confirm the attr_change actually patched state.
    device = bridge.get_afero_device("8ad8cc7b5c18ce2a")
    fcs = {s.functionClass: s.value for s in device.states}
    assert fcs["power"] == "on"
    assert fcs.get("available") is False


@pytest.mark.asyncio
async def test_start_registers_task_on_bridge(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge, initial_backoff=0, max_backoff=0)
    await conclave.start()
    assert conclave._task in bridge._adhoc_tasks
    await conclave.stop()


@pytest.mark.asyncio
async def test_start_runs_until_stop(conclave_bridge):
    bridge, _, _ = conclave_bridge
    connect_calls: list[ConclaveAccess] = []
    completed = asyncio.Event()

    async def fake_connect(access):
        connect_calls.append(access)
        reader = ScriptedReader(
            [
                zlib_hello(),
                wire_frame({"welcome": {"sessionId": 1}}),
            ],
            hold_open=True,
        )
        completed.set()
        return reader, FakeWriter()

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge, connect=fake_connect, initial_backoff=0, max_backoff=0
    )
    await conclave.start()
    assert conclave.running is True
    # Calling start again must be a no-op.
    await conclave.start()
    # Wait for the connection to get past `welcome`.
    await asyncio.wait_for(completed.wait(), timeout=2)
    assert await conclave.wait_until_logged_in(timeout=2) is True
    assert conclave.logged_in is True
    await conclave.stop()
    assert conclave.running is False
    assert len(connect_calls) == 1


@pytest.mark.asyncio
async def test_wait_until_logged_in_times_out(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)
    assert await conclave.wait_until_logged_in(timeout=0.01) is False


@pytest.mark.asyncio
async def test_wait_until_logged_in_returns_immediately_when_already_set(
    conclave_bridge,
):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)
    conclave._logged_in.set()
    assert await conclave.wait_until_logged_in(timeout=0.01) is True


@pytest.mark.asyncio
async def test_stop_is_idempotent(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)
    # Stop without ever starting should be a no-op.
    await conclave.stop()


@pytest.mark.asyncio
async def test_reconnect_after_failure(conclave_bridge, caplog):
    bridge, _, _ = conclave_bridge
    attempts: list[int] = []

    async def fake_connect(_access):
        attempts.append(len(attempts))
        if len(attempts) == 1:
            raise OSError("connection refused")
        # Second attempt completes hello/welcome and then hangs.
        reader = ScriptedReader(
            [zlib_hello(), wire_frame({"welcome": {"sessionId": 2}})],
            hold_open=True,
        )
        return reader, FakeWriter()

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge, connect=fake_connect, initial_backoff=0.001, max_backoff=0.001
    )
    with caplog.at_level("DEBUG"):
        await conclave.start()
        # Give the loop time to attempt twice.
        for _ in range(50):
            if len(attempts) >= 2:
                break
            await asyncio.sleep(0.02)
        await conclave.stop()
    assert len(attempts) >= 2


@pytest.mark.asyncio
async def test_dispatch_loop_handles_non_private_and_non_dict_private(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)

    # Cover the "private" not-a-dict branch directly without driving a
    # full session.
    await conclave._handle_frame({"unrelated": "frame"})
    await conclave._handle_frame({"private": "not-a-dict"})
    await conclave._handle_frame({"private": {"event": "attr_change", "data": "x"}})
    await conclave._handle_frame({"private": {"event": "mystery", "data": {}}})


@pytest.mark.asyncio
async def test_run_forever_resets_backoff_after_clean_exit(
    conclave_bridge, monkeypatch
):
    bridge, _, _ = conclave_bridge
    serves = 0

    async def fake_connect_and_serve(self):
        nonlocal serves
        serves += 1
        if serves >= 2:
            self._stop_event.set()

    monkeypatch.setattr(
        client_module.ConclaveClient,
        "_connect_and_serve",
        fake_connect_and_serve,
    )
    conclave = client_module.ConclaveClient(bridge, initial_backoff=0, max_backoff=0)
    await conclave._run_forever()
    assert serves == 2


@pytest.mark.asyncio
async def test_sleep_with_stop_returns_early_on_stop(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)
    conclave._stop_event.set()
    await conclave._sleep_with_stop(10)


@pytest.mark.asyncio
async def test_connection_close_swallows_errors():
    class ExplodingWriter(FakeWriter):
        def close(self) -> None:
            raise RuntimeError("close failed")

        async def wait_closed(self) -> None:  # pragma: no cover - exercised
            raise RuntimeError("wait_closed failed")

    reader = ScriptedReader([])
    writer = ExplodingWriter()
    connection = client_module.ConclaveConnection(reader, writer, access=ACCESS)
    await connection.close()


@pytest.mark.asyncio
async def test_connection_read_timeout_surfaces_to_caller():
    reader = ScriptedReader([], hold_open=True)
    connection = client_module.ConclaveConnection(
        reader, FakeWriter(), access=ACCESS, read_timeout=0.01
    )
    with pytest.raises(TimeoutError):
        await connection.open_session()


@pytest.mark.asyncio
async def test_connection_handles_clean_close():
    reader = ScriptedReader([zlib_hello()])
    connection = client_module.ConclaveConnection(
        reader, FakeWriter(), access=ACCESS, read_timeout=0.5
    )
    # First call consumes the hello; second should observe EOF.
    hello = await connection.open_session()
    assert "hello" in hello
    with pytest.raises(ConnectionResetError):
        # No more bytes — login should fail with a reset.
        await connection.login()


@pytest.mark.asyncio
async def test_connection_login_buffers_pre_welcome_frames():
    chunks = [
        wire_frame({"tunnel": {"version": "2.7.3"}}),
        b"\n",  # mid-handshake heartbeat (gets dropped here)
        wire_frame({"welcome": {"sessionId": 9}}),
        wire_frame({"join": {"sessionId": 9, "type": "client"}}),
    ]
    reader = ScriptedReader(chunks)
    connection = client_module.ConclaveConnection(
        reader, FakeWriter(), access=ACCESS, read_timeout=0.5
    )
    # Pretend we already consumed the hello envelope.
    connection._decoder._expecting_zlib_prefix = False
    welcome = await connection.login()
    assert welcome["welcome"]["sessionId"] == 9

    frames = []
    async for frame in connection.iter_frames():
        if frame is HEARTBEAT_FRAME:
            continue
        frames.append(frame)
        break
    assert frames[0] == {"tunnel": {"version": "2.7.3"}}


@pytest.mark.asyncio
async def test_open_session_skips_pre_hello_heartbeats_and_buffers_noise():
    # All three chunks arrive after the decoder demoted out of zlib-mode;
    # the noise frame should be buffered for the dispatch loop and the
    # heartbeat skipped while open_session waits for ``hello``.
    chunks = [
        b"\n",
        wire_frame({"noise": {}}),
        wire_frame({"hello": {"version": "2.7.3"}}),
    ]
    reader = ScriptedReader(chunks)
    connection = client_module.ConclaveConnection(
        reader, FakeWriter(), access=ACCESS, read_timeout=0.5
    )
    connection._decoder._expecting_zlib_prefix = False
    hello = await connection.open_session()
    assert hello["hello"]["version"] == "2.7.3"
    assert any("noise" in pending for pending in connection._pending)


@pytest.mark.asyncio
async def test_dispatch_loop_returns_when_stop_event_set(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)
    conclave._stop_event.set()

    class StopAfterOneFrame:
        def __init__(self) -> None:
            self._yielded = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._yielded:
                raise StopAsyncIteration
            self._yielded = True
            return {"private": {"event": "ignored", "data": {}}}

    class FakeConnection:
        def iter_frames(self):
            return StopAfterOneFrame()

        async def send_heartbeat(self) -> None:  # pragma: no cover - not called
            raise AssertionError("send_heartbeat should not be called")

    await conclave._dispatch_loop(FakeConnection())


@pytest.mark.asyncio
async def test_connection_socket_closed_before_read():
    reader = ScriptedReader([], hold_open=True)
    connection = client_module.ConclaveConnection(
        reader, FakeWriter(), access=ACCESS, read_timeout=0.5
    )
    connection._decoder._expecting_zlib_prefix = False
    reader._hold_open = False
    with pytest.raises(ConnectionResetError, match="socket closed"):
        await connection._next_frame()


@pytest.mark.asyncio
async def test_send_heartbeat_fails_when_writer_raises(conclave_bridge):
    class BrokenWriter(FakeWriter):
        async def drain(self) -> None:
            raise OSError("broken pipe")

    reader = ScriptedReader([], hold_open=True)
    connection = client_module.ConclaveConnection(reader, BrokenWriter(), access=ACCESS)
    with pytest.raises(ConnectionResetError, match="write failed"):
        await connection.send_heartbeat()


@pytest.mark.asyncio
async def test_push_idle_timeout_ends_session(conclave_bridge, monkeypatch):
    bridge, _, _ = conclave_bridge
    now = {"t": 1000.0}
    monkeypatch.setattr(client_module.time, "monotonic", lambda: now["t"])

    class HeartbeatOnly:
        def __aiter__(self):
            return self

        async def __anext__(self):
            return HEARTBEAT_FRAME

    class FakeConnection:
        def iter_frames(self):
            return HeartbeatOnly()

        async def send_heartbeat(self) -> None:
            now["t"] += 31.0

    conclave = client_module.ConclaveClient(
        bridge, push_idle_timeout=30.0, reconcile_on_reconnect=False
    )
    conclave._last_private_at = 1000.0
    with pytest.raises(client_module.ConclavePushStaleError, match="No Conclave push"):
        await conclave._dispatch_loop(FakeConnection())


@pytest.mark.asyncio
async def test_reconcile_runs_after_failed_session(conclave_bridge, mocker):
    bridge, device, generate = conclave_bridge
    bridge.fetch_all_device_states = mocker.AsyncMock(return_value=[device])
    bridge.events.split_devices = mocker.AsyncMock(return_value=[device])

    conclave = client_module.ConclaveClient(
        bridge, reconcile_on_reconnect=True, initial_backoff=0, max_backoff=0
    )
    conclave._needs_reconcile = True

    async def fake_connect(_access):
        reader = ScriptedReader(
            [
                zlib_hello(),
                wire_frame({"welcome": {"sessionId": 1, "heartbeat": 60}}),
            ],
            hold_open=True,
        )
        return reader, FakeWriter()

    client_module.request_conclave_access = mocker.AsyncMock(return_value=ACCESS)
    conclave._connect = fake_connect
    await conclave.start()
    await asyncio.wait_for(conclave.wait_until_logged_in(), timeout=2)
    bridge.fetch_all_device_states.assert_awaited_once()
    generate.assert_awaited()
    await conclave.stop()


@pytest.mark.asyncio
async def test_push_stale_property(conclave_bridge, monkeypatch):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge, push_idle_timeout=10.0)
    assert conclave.push_stale is False
    conclave._logged_in.set()
    conclave._last_private_at = 1000.0
    monkeypatch.setattr(client_module.time, "monotonic", lambda: 1015.0)
    assert conclave.push_stale is True
    assert conclave.seconds_since_last_push == 15.0


@pytest.mark.asyncio
async def test_connection_status_emits_on_login_and_stop(conclave_bridge, mocker):
    bridge, _, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")

    async def fake_connect(_access):
        reader = ScriptedReader(
            [zlib_hello(), wire_frame({"welcome": {"sessionId": 1}})],
            hold_open=True,
        )
        return reader, FakeWriter()

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge, connect=fake_connect, initial_backoff=0, max_backoff=0
    )
    await conclave.start()
    assert await conclave.wait_until_logged_in(timeout=2) is True
    assert conclave.status == ConclaveStatus.CONNECTED
    assert conclave.connected is True

    emitted = [call.args[0] for call in emit.call_args_list]
    assert EventType.CONCLAVE_CONNECTING in emitted
    assert EventType.CONCLAVE_CONNECTED in emitted
    assert EventType.CONCLAVE_RECONNECTED not in emitted

    await conclave.stop()
    assert conclave.status == ConclaveStatus.DISCONNECTED
    assert conclave.connected is False
    emitted = [call.args[0] for call in emit.call_args_list]
    assert EventType.CONCLAVE_DISCONNECTED in emitted


@pytest.mark.asyncio
async def test_connection_status_emits_reconnected_after_failure(
    conclave_bridge, mocker
):
    bridge, _, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")
    attempts = 0

    async def fake_connect(_access):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("connection refused")
        reader = ScriptedReader(
            [zlib_hello(), wire_frame({"welcome": {"sessionId": 2}})],
            hold_open=True,
        )
        return reader, FakeWriter()

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge, connect=fake_connect, initial_backoff=0.001, max_backoff=0.001
    )
    await conclave.start()
    for _ in range(50):
        if attempts >= 2 and conclave.connected:
            break
        await asyncio.sleep(0.02)
    assert conclave.connected is True

    emitted = [call.args[0] for call in emit.call_args_list]
    assert EventType.CONCLAVE_CONNECTING in emitted
    assert EventType.CONCLAVE_DISCONNECTED in emitted
    assert EventType.CONCLAVE_RECONNECTED in emitted

    await conclave.stop()


@pytest.mark.asyncio
async def test_connection_status_emits_disconnected_on_connect_failure(
    conclave_bridge, mocker
):
    bridge, _, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")

    async def fake_connect(_access):
        raise OSError("connection refused")

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge, connect=fake_connect, initial_backoff=0.001, max_backoff=0.001
    )
    with pytest.raises(OSError):
        await conclave._connect_and_serve()

    emitted = [call.args[0] for call in emit.call_args_list]
    assert emitted == [
        EventType.CONCLAVE_CONNECTING,
        EventType.CONCLAVE_DISCONNECTED,
    ]
    assert conclave._reconnect_pending is True


@pytest.mark.asyncio
async def test_set_status_noop_when_unchanged(conclave_bridge, mocker):
    bridge, _, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")
    conclave = client_module.ConclaveClient(bridge)
    conclave._set_status(ConclaveStatus.DISCONNECTED)
    conclave._set_status(ConclaveStatus.DISCONNECTED)
    emit.assert_not_called()


@pytest.mark.asyncio
async def test_send_heartbeat_propagates_cancelled_error():
    class CancelWriter(FakeWriter):
        async def drain(self) -> None:
            raise asyncio.CancelledError

    reader = ScriptedReader([], hold_open=True)
    connection = client_module.ConclaveConnection(reader, CancelWriter(), access=ACCESS)
    with pytest.raises(asyncio.CancelledError):
        await connection.send_heartbeat()


@pytest.mark.asyncio
async def test_next_frame_raises_on_empty_chunk_before_eof():
    class EmptyChunkReader:
        def at_eof(self) -> bool:
            return False

        async def read(self, _size: int) -> bytes:
            return b""

    connection = client_module.ConclaveConnection(
        EmptyChunkReader(), FakeWriter(), access=ACCESS, read_timeout=0.5
    )
    connection._decoder._expecting_zlib_prefix = False
    with pytest.raises(ConnectionResetError, match="socket closed"):
        await connection._next_frame()


@pytest.mark.asyncio
async def test_seconds_since_last_push_none_when_timestamp_missing(conclave_bridge):
    bridge, _, _ = conclave_bridge
    conclave = client_module.ConclaveClient(bridge)
    conclave._logged_in.set()
    conclave._last_private_at = None
    assert conclave.seconds_since_last_push is None


@pytest.mark.asyncio
async def test_reconcile_fetch_failure_is_logged(conclave_bridge, mocker, caplog):
    bridge, _, _ = conclave_bridge
    bridge.fetch_all_device_states = mocker.AsyncMock(
        side_effect=TimeoutError("poll timed out")
    )
    conclave = client_module.ConclaveClient(bridge)
    with caplog.at_level("WARNING"):
        await conclave._reconcile_rest_state()
    bridge.fetch_all_device_states.assert_awaited_once()
    assert "REST reconcile after Conclave disconnect failed" in caplog.text


@pytest.mark.asyncio
async def test_reconcile_per_device_update_failure_is_logged(
    conclave_bridge, mocker, caplog
):
    bridge, device, generate = conclave_bridge
    bridge.fetch_all_device_states = mocker.AsyncMock(return_value=[device])
    bridge.events.split_devices = mocker.AsyncMock(return_value=[device])
    generate.side_effect = TypeError("bad device payload")
    conclave = client_module.ConclaveClient(bridge)
    with caplog.at_level("DEBUG"):
        await conclave._reconcile_rest_state()
    assert "REST reconcile update failed" in caplog.text


@pytest.mark.asyncio
async def test_connection_status_disconnected_when_reconcile_raises(
    conclave_bridge, mocker
):
    bridge, device, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")
    bridge.fetch_all_device_states = mocker.AsyncMock(return_value=[device])
    bridge.events.split_devices = mocker.AsyncMock(
        side_effect=RuntimeError("split failed")
    )

    async def fake_connect(_access):
        reader = ScriptedReader(
            [zlib_hello(), wire_frame({"welcome": {"sessionId": 1}})],
            hold_open=True,
        )
        return reader, FakeWriter()

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge,
        connect=fake_connect,
        reconcile_on_reconnect=True,
        initial_backoff=0,
        max_backoff=0,
    )
    conclave._needs_reconcile = True
    with pytest.raises(RuntimeError, match="split failed"):
        await conclave._connect_and_serve()

    emitted = [call.args[0] for call in emit.call_args_list]
    assert emitted == [
        EventType.CONCLAVE_CONNECTING,
        EventType.CONCLAVE_CONNECTED,
        EventType.CONCLAVE_DISCONNECTED,
    ]


@pytest.mark.asyncio
async def test_stop_during_connecting_emits_disconnected_once(conclave_bridge, mocker):
    bridge, _, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")
    connect_started = asyncio.Event()

    async def slow_connect(_access):
        connect_started.set()
        await asyncio.Event().wait()

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(
        bridge, connect=slow_connect, initial_backoff=0, max_backoff=0
    )
    await conclave.start()
    await asyncio.wait_for(connect_started.wait(), timeout=2)
    assert conclave.status == ConclaveStatus.CONNECTING
    await conclave.stop()
    assert conclave._reconnect_pending is False
    emitted = [call.args[0] for call in emit.call_args_list]
    assert emitted.count(EventType.CONCLAVE_DISCONNECTED) == 1


def test_connection_set_read_timeout_updates_idle_window():
    connection = client_module.ConclaveConnection(
        ScriptedReader([], hold_open=True), FakeWriter(), access=ACCESS
    )
    connection.set_read_timeout(120.0)
    assert connection._read_timeout == 120.0


@pytest.mark.asyncio
async def test_reconcile_invalid_auth_failure_is_logged(
    conclave_bridge, mocker, caplog
):
    bridge, _, _ = conclave_bridge
    bridge.fetch_all_device_states = mocker.AsyncMock(side_effect=InvalidAuth())
    conclave = client_module.ConclaveClient(bridge)
    with caplog.at_level("WARNING"):
        await conclave._reconcile_rest_state()
    assert "REST reconcile after Conclave disconnect failed" in caplog.text


@pytest.mark.asyncio
async def test_stop_without_start_emits_no_status_events(conclave_bridge, mocker):
    bridge, _, _ = conclave_bridge
    emit = mocker.spy(bridge.events, "emit")
    conclave = client_module.ConclaveClient(bridge)
    await conclave.stop()
    emit.assert_not_called()


@pytest.mark.asyncio
async def test_default_connect_uses_tls_when_ssl_enabled(mocker):
    fake = mocker.patch(
        "asyncio.open_connection", AsyncMock(return_value=("reader", "writer"))
    )
    result = await client_module._default_connect(ACCESS)
    fake.assert_awaited_once()
    host, port = fake.await_args.args[:2]
    assert host == ACCESS.host
    assert port == ACCESS.port
    assert fake.await_args.kwargs["server_hostname"] == ACCESS.host
    assert isinstance(fake.await_args.kwargs["ssl"], ssl.SSLContext)
    assert result == ("reader", "writer")


@pytest.mark.asyncio
async def test_default_connect_skips_tls_when_ssl_disabled(mocker):
    fake = mocker.patch(
        "asyncio.open_connection", AsyncMock(return_value=("reader", "writer"))
    )
    access = ConclaveAccess(
        host=ACCESS.host,
        port=ACCESS.port,
        ssl=False,
        compression=False,
        token="t",
        channel_id="c",
    )
    result = await client_module._default_connect(access)
    fake.assert_awaited_once_with(access.host, access.port)
    assert "ssl" not in fake.await_args.kwargs
    assert result == ("reader", "writer")


@pytest.mark.asyncio
async def test_connect_and_serve_removes_conclave_token_secret(conclave_bridge, mocker):
    bridge, _, _ = conclave_bridge
    remove = mocker.patch("aioafero.v1.conclave.client.remove_secret")

    async def fake_connect(_access):
        raise OSError("connection refused")

    client_module.request_conclave_access = AsyncMock(return_value=ACCESS)
    conclave = client_module.ConclaveClient(bridge, connect=fake_connect)
    with pytest.raises(OSError):
        await conclave._connect_and_serve()
    remove.assert_called_once_with(ACCESS.token)
