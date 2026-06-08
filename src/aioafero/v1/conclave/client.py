"""TLS client for the Conclave push channel."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
import contextlib
from enum import Enum
import ssl
import time
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import ClientError
from securelogging import remove_secret

from aioafero.errors import AferoError, InvalidAuth
from aioafero.types import EventType

from .access import ConclaveAccess, request_conclave_access
from .events import PRIVATE_EVENT_HANDLERS
from .frames import (
    HEARTBEAT_FRAME,
    ConclaveFrameDecoder,
    encode_frame,
    encode_heartbeat,
)
from .protocol import (
    HANDSHAKE_FRAME_KEYS,
    WELCOME_FRAME_KEY,
    build_login_frame,
    parse_private_frame,
    server_heartbeat_seconds,
)

if TYPE_CHECKING:  # pragma: no cover
    from aioafero.v1 import AferoBridgeV1

ConnectCallable = Callable[
    [ConclaveAccess], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]
]

FramePredicate = Callable[[dict], bool]

DEFAULT_READ_TIMEOUT = 75.0
DEFAULT_INITIAL_BACKOFF = 1.0
DEFAULT_MAX_BACKOFF = 60.0
READ_CHUNK_SIZE = 65536
WIRE_IDLE_HEARTBEAT_MULTIPLIER = 2.0


class ConclaveStatus(Enum):
    """Connection status of the Conclave push client."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class ConclavePushStaleError(ConnectionError):
    """Raised when the socket stays up but no ``private`` pushes arrive in time."""


class ConclaveConnection:
    """Single attempt at a Conclave socket session."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        access: ConclaveAccess,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
    ) -> None:
        """Bind a Conclave TLS stream to ``access`` credentials."""
        self._reader = reader
        self._writer = writer
        self._access = access
        self._read_timeout = read_timeout
        self._decoder = ConclaveFrameDecoder()
        self._pending: list[dict] = []

    @property
    def socket_closed(self) -> bool:
        """``True`` when the underlying stream has reached EOF."""
        return self._reader.at_eof()

    def set_read_timeout(self, timeout: float) -> None:
        """Update the per-read idle timeout (seconds)."""
        self._read_timeout = timeout

    async def open_session(self) -> dict:
        """Send the opening ``{}`` and return the handshake envelope."""
        await self._send({})
        return await self._read_until(
            lambda frame: any(key in frame for key in HANDSHAKE_FRAME_KEYS)
        )

    async def login(self) -> dict:
        """Send the ``login`` frame and return the ``welcome`` envelope."""
        await self._send(build_login_frame(self._access))
        return await self._read_until(lambda frame: WELCOME_FRAME_KEY in frame)

    async def iter_frames(self) -> AsyncIterator[dict]:
        """Yield frames from the connection until it closes."""
        for frame in self._pending:
            yield frame
        self._pending.clear()
        while True:
            yield await self._next_frame()

    async def send_heartbeat(self) -> None:
        r"""Send a bare ``\n`` heartbeat ack."""
        if self.socket_closed:
            raise ConnectionResetError("Conclave socket closed")
        try:
            self._writer.write(encode_heartbeat())
            await self._writer.drain()
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError) as err:
            raise ConnectionResetError("Conclave socket write failed") from err

    async def close(self) -> None:
        """Close the underlying writer (idempotent)."""
        with contextlib.suppress(Exception):
            self._writer.close()
        with contextlib.suppress(Exception):
            await self._writer.wait_closed()

    async def _send(self, payload: dict) -> None:
        self._writer.write(encode_frame(payload))
        await self._writer.drain()

    async def _read_until(self, predicate: FramePredicate) -> dict:
        """Return the first non-heartbeat frame matching ``predicate``."""
        while True:
            frame = await self._next_non_heartbeat_frame()
            if predicate(frame):
                return frame
            self._pending.append(frame)

    async def _next_non_heartbeat_frame(self) -> dict:
        """Read until a non-heartbeat frame is available."""
        while True:
            frame = await self._next_frame()
            if frame is not HEARTBEAT_FRAME:
                return frame

    async def _next_frame(self) -> dict:
        while True:
            for frame in self._decoder.feed(b""):
                return frame
            if self.socket_closed:
                raise ConnectionResetError("Conclave socket closed")
            async with asyncio.timeout(self._read_timeout):
                chunk = await self._reader.read(READ_CHUNK_SIZE)
            if not chunk:
                raise ConnectionResetError("Conclave socket closed")
            for frame in self._decoder.feed(chunk):
                return frame


class ConclaveClient:
    """Long-running Conclave push consumer for an :class:`AferoBridgeV1`."""

    def __init__(
        self,
        bridge: AferoBridgeV1,
        *,
        connect: ConnectCallable | None = None,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        max_backoff: float = DEFAULT_MAX_BACKOFF,
        push_idle_timeout: float | None = None,
        reconcile_on_reconnect: bool = True,
    ) -> None:
        """Attach a reconnecting Conclave consumer to ``bridge``.

        :param push_idle_timeout: When set, end the session if no ``private``
            push arrives within this many seconds while the socket is still
            receiving heartbeats. ``None`` disables (default). Use for zombie
            sessions where ``welcome`` succeeds but state pushes stop.
        :param reconcile_on_reconnect: After a failed session, run one REST
            state poll once login succeeds again.
        """
        self._bridge = bridge
        self._connect = connect or _default_connect
        self._read_timeout = read_timeout
        self._initial_backoff = initial_backoff
        self._max_backoff = max_backoff
        self._push_idle_timeout = push_idle_timeout
        self._reconcile_on_reconnect = reconcile_on_reconnect
        self._logger = bridge.logger.getChild("conclave")
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._logged_in = asyncio.Event()
        self._connection: ConclaveConnection | None = None
        self._needs_reconcile = False
        self._last_private_at: float | None = None
        self._status = ConclaveStatus.DISCONNECTED
        self._reconnect_pending = False

    @property
    def status(self) -> ConclaveStatus:
        """Return the current Conclave connection status."""
        return self._status

    @property
    def connected(self) -> bool:
        """``True`` when the push session has completed login.

        Prefer :attr:`logged_in` for socket-session liveness; ``connected``
        reflects the emitted lifecycle state used by ``bridge.events``.
        """
        return self._status == ConclaveStatus.CONNECTED

    @property
    def running(self) -> bool:
        """``True`` while the background run loop has not been stopped."""
        return self._task is not None and not self._task.done()

    @property
    def logged_in(self) -> bool:
        """``True`` after ``welcome`` until the socket session ends.

        Cleared before :attr:`connected` during teardown; use :attr:`status` for
        lifecycle callbacks on :attr:`~aioafero.v1.AferoBridgeV1.events`.
        """
        return self._logged_in.is_set()

    @property
    def seconds_since_last_push(self) -> float | None:
        """Seconds since the last handled ``private`` push, when logged in."""
        if not self.logged_in or self._last_private_at is None:
            return None
        return time.monotonic() - self._last_private_at

    @property
    def push_stale(self) -> bool:
        """``True`` when logged in and push idle exceeds ``push_idle_timeout``."""
        if self._push_idle_timeout is None or not self.logged_in:
            return False
        elapsed = self.seconds_since_last_push
        return elapsed is not None and elapsed > self._push_idle_timeout

    async def wait_until_logged_in(self, timeout: float = 60.0) -> bool:
        """Wait until a Conclave session completes login."""
        if self._logged_in.is_set():
            return True
        try:
            async with asyncio.timeout(timeout):
                await self._logged_in.wait()
        except TimeoutError:
            return False
        return True

    async def start(self) -> None:
        """Schedule the background reconnect loop (idempotent)."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_forever())
        self._bridge.add_job(self._task)

    async def stop(self) -> None:
        """Stop the loop and close any open connection (idempotent)."""
        self._stop_event.set()
        self._logged_in.clear()
        self._last_private_at = None
        connection = self._connection
        self._connection = None
        if connection is not None:
            await connection.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        self._reconnect_pending = False
        self._set_status(ConclaveStatus.DISCONNECTED, reconnect=False)

    def _set_status(self, status: ConclaveStatus, *, reconnect: bool = True) -> None:
        """Update status and emit the matching :class:`~aioafero.types.EventType`."""
        if self._status == status:
            return
        self._status = status
        if status == ConclaveStatus.CONNECTING:
            self._bridge.events.emit(EventType.CONCLAVE_CONNECTING)
        elif status == ConclaveStatus.CONNECTED:
            event = (
                EventType.CONCLAVE_RECONNECTED
                if self._reconnect_pending
                else EventType.CONCLAVE_CONNECTED
            )
            self._bridge.events.emit(event)
            self._reconnect_pending = False
        elif status == ConclaveStatus.DISCONNECTED:
            self._bridge.events.emit(EventType.CONCLAVE_DISCONNECTED)
            if reconnect and not self._stop_event.is_set():
                self._reconnect_pending = True

    async def _run_forever(self) -> None:
        backoff = self._initial_backoff
        while not self._stop_event.is_set():
            try:
                await self._connect_and_serve()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._needs_reconcile = True
                self._logger.exception("Conclave session failed; will reconnect")
            else:
                backoff = self._initial_backoff
            if self._stop_event.is_set():
                return
            await self._sleep_with_stop(backoff)
            backoff = min(backoff * 2, self._max_backoff)

    async def _sleep_with_stop(self, delay: float) -> None:
        """Sleep ``delay`` seconds, returning early if :meth:`stop` is called."""
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(delay):
                await self._stop_event.wait()

    async def _connect_and_serve(self) -> None:
        self._set_status(ConclaveStatus.CONNECTING)
        connection: ConclaveConnection | None = None
        access: ConclaveAccess | None = None
        try:
            access = await request_conclave_access(self._bridge)
            self._logger.debug(
                "Connecting to Conclave at %s:%s (ssl=%s)",
                access.host,
                access.port,
                access.ssl,
            )
            reader, writer = await self._connect(access)
            connection = ConclaveConnection(
                reader, writer, access=access, read_timeout=self._read_timeout
            )
            self._connection = connection
            handshake = await connection.open_session()
            self._logger.debug("Conclave handshake keys: %s", sorted(handshake))
            welcome = await connection.login()
            self._logger.debug(
                "Conclave welcome: %s", welcome.get(WELCOME_FRAME_KEY, {})
            )
            heartbeat = server_heartbeat_seconds(handshake, welcome)
            connection.set_read_timeout(
                max(self._read_timeout, heartbeat * WIRE_IDLE_HEARTBEAT_MULTIPLIER)
            )
            self._logged_in.set()
            self._last_private_at = time.monotonic()
            self._set_status(ConclaveStatus.CONNECTED)
            self._logger.info("Conclave session logged in; listening for push events")
            if self._reconcile_on_reconnect and self._needs_reconcile:
                await self._reconcile_rest_state()
                self._needs_reconcile = False
            try:
                await self._dispatch_loop(connection)
            finally:
                self._logged_in.clear()
                self._last_private_at = None
                self._set_status(ConclaveStatus.DISCONNECTED)
        except Exception:
            # Dispatch ``finally`` may have already emitted DISCONNECTED.
            if self._status in (ConclaveStatus.CONNECTING, ConclaveStatus.CONNECTED):
                self._set_status(ConclaveStatus.DISCONNECTED)
            raise
        finally:
            if connection is not None:
                await connection.close()
            if connection is not None and self._connection is connection:
                self._connection = None
            if access is not None:
                remove_secret(access.token)

    async def _reconcile_rest_state(self) -> None:
        """Run one REST state poll after a failed Conclave session."""
        self._logger.info(
            "Reconciling device state over REST after Conclave disconnect"
        )
        try:
            devices = await self._bridge.fetch_all_device_states()
        except (ClientError, TimeoutError, OSError, InvalidAuth, AferoError):
            self._logger.warning(
                "REST reconcile after Conclave disconnect failed",
                exc_info=True,
            )
            return
        for device in await self._bridge.events.split_devices(devices):
            try:
                await self._bridge.events.generate_events_from_update(device)
            except (TypeError, ValueError, KeyError, AttributeError):
                self._logger.debug(
                    "REST reconcile update failed for %s",
                    device.id,
                    exc_info=True,
                )

    async def _dispatch_loop(self, connection: ConclaveConnection) -> None:
        async for frame in connection.iter_frames():
            if frame is HEARTBEAT_FRAME:
                self._check_push_idle()
                await connection.send_heartbeat()
                continue
            await self._handle_frame(frame)
            if self._stop_event.is_set():
                return

    def _check_push_idle(self) -> None:
        """End the session when pushes stall but the socket still heartbeats."""
        if self._push_idle_timeout is None or self._last_private_at is None:
            return
        idle = time.monotonic() - self._last_private_at
        if idle > self._push_idle_timeout:
            raise ConclavePushStaleError(
                f"No Conclave push in {idle:.0f}s (limit {self._push_idle_timeout:.0f}s)"
            )

    async def _handle_frame(self, frame: dict) -> None:
        private = parse_private_frame(frame)
        if private is None:
            self._logger.debug(
                "Ignoring non-private Conclave frame keys: %s",
                sorted(frame),
            )
            return
        handler = PRIVATE_EVENT_HANDLERS.get(private.event)
        if handler is None:
            self._logger.debug("Unhandled Conclave private event: %s", private.event)
            return
        if await handler(self._bridge, private.data):
            self._last_private_at = time.monotonic()


async def _default_connect(
    access: ConclaveAccess,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Open a connection to the Conclave server."""
    if access.ssl:
        ctx = ssl.create_default_context()
        return await asyncio.open_connection(
            access.host,
            access.port,
            ssl=ctx,
            server_hostname=access.host,
        )
    return await asyncio.open_connection(access.host, access.port)
