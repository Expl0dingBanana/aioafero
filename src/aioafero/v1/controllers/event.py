"""Handle connecting to Afero IoT and distribute events."""

import asyncio
from asyncio.coroutines import iscoroutinefunction
from collections.abc import Callable
from enum import Enum
from types import NoneType
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from aiohttp.client_exceptions import ClientError
from aiohttp.web_exceptions import HTTPForbidden, HTTPTooManyRequests

from ...device import AferoDevice, get_afero_device
from ...errors import InvalidAuth
from ...types import EventType

if TYPE_CHECKING:  # pragma: no cover
    from .. import AferoBridgeV1


class BackoffException(Exception):
    """Exception raised when a backoff is required."""

    pass


class EventStreamStatus(Enum):
    """Status options of EventStream."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2


class AferoEvent(TypedDict):
    """Afero IoT Event message as emitted by the EventStream."""

    type: EventType  # = EventType (add, update, delete)
    device_id: NotRequired[str]  # ID for interacting with the device
    device: NotRequired[AferoDevice]  # Afero Device
    force_forward: NotRequired[bool]


EventCallBackType = Callable[[EventType, dict | None], None]
EventSubscriptionType = tuple[
    EventCallBackType,
    "tuple[EventType] | None",
    "tuple[ResourceTypes] | None",
]


class EventStream:

    def __init__(self, bridge: "AferoBridgeV1", polling_interval: int) -> None:
        """Initialize instance."""
        self._bridge = bridge
        self._listeners = set()
        self._event_queue = asyncio.Queue()
        self._status = EventStreamStatus.DISCONNECTED
        self._bg_tasks: list[asyncio.Task] = []
        self._subscribers: list[EventSubscriptionType] = []
        self._logger = bridge.logger.getChild("events")
        self._polling_interval: int = polling_interval

    @property
    def connected(self) -> bool:
        """Return bool if we're connected."""
        return self._status == EventStreamStatus.CONNECTED

    @property
    def status(self) -> EventStreamStatus:
        """Return connection status."""
        return self._status

    @property
    def polling_interval(self) -> int:
        return self._polling_interval

    @polling_interval.setter
    def polling_interval(self, polling_interval: int) -> None:
        self._polling_interval = polling_interval

    async def initialize(self) -> None:
        """Start the polling processes"""
        assert len(self._bg_tasks) == 0
        await self.initialize_reader()
        await self.initialize_processor()

    async def initialize_reader(self) -> None:
        self._bg_tasks.append(asyncio.create_task(self.__event_reader()))

    async def initialize_processor(self) -> None:
        self._bg_tasks.append(asyncio.create_task(self.__event_processor()))

    async def stop(self) -> None:
        """Stop listening for events."""
        for task in self._bg_tasks:
            task.cancel()
        self._status = EventStreamStatus.DISCONNECTED
        self._bg_tasks = []

    def subscribe(
        self,
        callback: EventCallBackType,
        event_filter: EventType | tuple[EventType] | None = None,
        resource_filter: tuple[str] | None = None,
    ) -> Callable:
        """
        Subscribe to events emitted

        Parameters:
            - `callback` - callback function to call when an event emits.
            - `event_filter` - Optionally provide an EventType as filter.
            - `resource_filter` - Optionally provide a ResourceType as filter.

        Returns:
            function to unsubscribe.
        """
        if not isinstance(event_filter, NoneType | tuple):
            event_filter = (event_filter,)
        if not isinstance(resource_filter, NoneType | tuple):
            resource_filter = (resource_filter,)
        subscription = (callback, event_filter, resource_filter)

        def unsubscribe():
            self._subscribers.remove(subscription)

        self._subscribers.append(subscription)
        return unsubscribe

    def add_job(self, event: AferoEvent) -> None:
        """Manually add a job to be processed."""
        self._event_queue.put_nowait(event)

    def emit(self, event_type: EventType, data: AferoEvent = None) -> None:
        """Emit event to all listeners."""
        for callback, event_filter, resource_filter in self._subscribers:
            try:
                if event_filter is not None and event_type not in event_filter:
                    continue
                if (
                    resource_filter is not None
                    and data is not None
                    and (
                        "device" in data
                        and data["device"]
                        and not any(
                            data["device"].device_class == res_filter
                            for res_filter in resource_filter
                        )
                    )
                ):
                    continue
                if iscoroutinefunction(callback):
                    asyncio.create_task(callback(event_type, data))
                else:
                    callback(event_type, data)
            except Exception:
                self._logger.exception("Unhandled exception. Please open a bug report")

    async def process_backoff(self, attempt: int) -> None:
        """Handle backoff timer for Afero IoT API

        :param attempt: Number of attempts
        :param reason: Reason why the backoff is occurring
        """
        backoff_time = min(attempt * self.polling_interval, 600)
        debug_message = f"Waiting {backoff_time} seconds before next poll"
        if attempt == 1:
            self._logger.info("Lost connection to the Afero IoT API.")
            self._logger.debug(debug_message)
        if self._status != EventStreamStatus.DISCONNECTED:
            self._status = EventStreamStatus.DISCONNECTED
            self.emit(EventType.DISCONNECTED)
        await asyncio.sleep(backoff_time)

    async def gather_data(self) -> list[dict[Any, str]]:
        """Gather all data from the Afero IoT API"""
        consecutive_http_errors = 0
        while True:
            try:
                data = await self._bridge.fetch_data()
            except asyncio.TimeoutError:
                self._logger.warning("Timeout when contacting Afero IoT API.")
                await self.process_backoff(consecutive_http_errors)
            except InvalidAuth:
                consecutive_http_errors += 1
                self._logger.warning("Invalid credentials provided.")
                await self.process_backoff(consecutive_http_errors)
            except (HTTPForbidden, HTTPTooManyRequests, ClientError):
                consecutive_http_errors += 1
                await self.process_backoff(consecutive_http_errors)
            except ValueError as err:
                self._logger.warning(
                    "Unexpected data from Afero IoT API, %s.", err.args[0]
                )
                consecutive_http_errors += 1
                await self.process_backoff(consecutive_http_errors)
            except Exception as err:
                self._logger.exception(
                    "Unknown error occurred. Please open a bug report."
                )
                raise err
            else:
                # Successful connection
                if consecutive_http_errors > 0:
                    self._logger.info("Reconnected to the Afero IoT API")
                    self.emit(EventType.RECONNECTED)
                elif self._status != EventStreamStatus.CONNECTED:
                    self._status = EventStreamStatus.CONNECTED
                    self.emit(EventType.CONNECTED)
                return data

    async def generate_events_from_data(self, data: list[dict[Any, str]]) -> None:
        """Process the raw Afero IoT data for emitting

        :param data: Raw data from Afero IoT
        """
        processed_ids = []
        skipped_ids = []
        for dev in data:
            device = get_afero_device(dev)
            if not device.device_class:
                continue
            event_type = EventType.RESOURCE_UPDATED
            if device.id not in self._bridge.tracked_devices:
                event_type = EventType.RESOURCE_ADDED
            self._event_queue.put_nowait(
                AferoEvent(
                    type=event_type,
                    device_id=device.id,
                    device=device,
                    force_forward=False,
                )
            )
            processed_ids.append(device.id)
        # Handle devices that did not report in from the API
        for dev_id in self._bridge.tracked_devices:
            if dev_id not in processed_ids + skipped_ids:
                self._event_queue.put_nowait(
                    AferoEvent(type=EventType.RESOURCE_DELETED, device_id=dev_id)
                )
                self._bridge.remove_device(dev_id)

    async def perform_poll(self) -> None:
        """Poll Afero IoT and generate the required events"""
        try:
            data = await self.gather_data()
        except Exception:
            self._status = EventStreamStatus.DISCONNECTED
            self.emit(EventType.DISCONNECTED)
        else:
            try:
                await self.generate_events_from_data(data)
            except Exception:
                self._logger.exception("Unable to process Afero IoT data. %s", data)

    async def __event_reader(self) -> None:
        """Poll the current states"""
        self._status = EventStreamStatus.CONNECTING
        while True:
            await self.perform_poll()
            await asyncio.sleep(self._polling_interval)

    async def process_event(self):
        try:
            event: AferoEvent = await self._event_queue.get()
            self.emit(event["type"], event)
        except Exception:
            self._logger.exception("Unhandled exception. Please open a bug report")

    async def __event_processor(self) -> None:
        """Process the Afero IoT devices"""
        while True:
            await self.process_event()
