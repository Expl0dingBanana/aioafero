"""Controls Hubspace devices on v1 API."""

__all__ = [
    "AferoAuth",
    "AferoBridgeV1",
    "AferoController",
    "AferoModelResource",
    "BaseResourcesController",
    "DeviceController",
    "FanController",
    "LightController",
    "LockController",
    "OTPRequired",
    "PortableACController",
    "SecuritySystemController",
    "SecuritySystemKeypadController",
    "SecuritySystemSensorController",
    "SwitchController",
    "ThermostatController",
    "TokenData",
    "ValveController",
    "models",
]

import asyncio
from collections.abc import Callable, Generator
import contextlib
from contextlib import asynccontextmanager
import logging
from typing import Any, Self

import aiohttp
from aiohttp import web_exceptions
from securelogging import LogRedactorMessage, add_secret

from aioafero.device import AferoDevice, AferoResource, AferoState
from aioafero.errors import (
    AferoError,
    DeviceNotFound,
    ExceededMaximumRetries,
    InvalidAuth,
    OTPRequired,
)
from aioafero.types import TemperatureUnit

from . import models, v1_const
from .auth import AferoAuth, TokenData, passthrough
from .controllers.base import AferoBinarySensor, AferoSensor, BaseResourcesController
from .controllers.device import DeviceController
from .controllers.event import EventCallBackType, EventStream, EventType
from .controllers.exhaust_fan import ExhaustFanController
from .controllers.fan import FanController
from .controllers.light import LightController
from .controllers.lock import LockController
from .controllers.portable_ac import PortableACController
from .controllers.security_system import SecuritySystemController
from .controllers.security_system_keypad import SecuritySystemKeypadController
from .controllers.security_system_sensor import SecuritySystemSensorController
from .controllers.switch import SwitchController
from .controllers.thermostat import ThermostatController
from .controllers.valve import ValveController

type AferoModelResource = (
    models.Device
    | models.Fan
    | models.Light
    | models.Lock
    | models.Switch
    | models.Valve
    | models.Thermostat
    | AferoBinarySensor
    | AferoSensor
    | models.ExhaustFan
    | models.PortableAC
    | models.SecuritySystem
    | models.SecuritySystemSensor
)

type AferoController = (
    DeviceController
    | FanController
    | LightController
    | LockController
    | AferoSensor
    | SwitchController
    | ThermostatController
    | ValveController
    | ExhaustFanController
    | PortableACController
    | SecuritySystemController
    | SecuritySystemKeypadController
    | SecuritySystemSensorController
)


class AferoBridgeV1:
    """Controls Afero IoT devices on v1 API.

    This class serves as the main entry point for interacting with the Afero API.
    It handles authentication, device discovery, state management, and event handling.

    :param username: The username for the Afero-backed account (e.g., Hubspace).
    :param refresh_token: The OAuth refresh token for the account.
    :param token: An optional non-expired bearer token to skip the initial refresh.
    :param token_expiration: Unix timestamp when ``token`` expires (omit to refresh
        immediately on first API use).
    :param session: ``aiohttp.ClientSession`` for API and auth traffic (required).
    :param polling_interval: The interval in seconds between polling the Afero API
        for device state updates. Defaults to 30 seconds.
    :param discovery_interval: The interval in seconds between polling the Afero API
        for new devices. Defaults to 3600 seconds (1 hour).
    :param afero_client: The Afero client identifier (``"hubspace"``).
        Defaults to "hubspace".
    :param hide_secrets: If True, sensitive information will be redacted from logs.
        Defaults to True.
    :param poll_version: If True, device version information will be polled periodically.
        Defaults to True.
    :param client_name: A name for the client to be used in the User-Agent header.
        Defaults to "aioafero".
    :param temperature_unit: The desired temperature unit for API responses.
        Defaults to `TemperatureUnit.CELSIUS`.

    """

    def __init__(
        self,
        username: str,
        refresh_token: str,
        session: aiohttp.ClientSession,
        *,
        token: str | None = None,
        token_expiration: float | None = None,
        polling_interval: int = 30,
        discovery_interval: int = 3600,
        afero_client: str | None = "hubspace",
        hide_secrets: bool = True,
        poll_version: bool = True,
        client_name: str | None = "aioafero",
        temperature_unit: TemperatureUnit = TemperatureUnit.CELSIUS,
    ):
        """Initialize the AferoBridgeV1 instance.

        ``session`` is required. ``_close_session`` defaults to ``False``; only
        :meth:`open` sets it to ``True`` when it creates the session internally.
        """
        if hide_secrets:
            self.secret_logger = LogRedactorMessage
        else:
            self.secret_logger = passthrough
        self._close_session = False
        self._web_session = session
        self._account_id: str | None = None
        self._afero_client: str = afero_client
        self.client_name = client_name
        self._auth = AferoAuth(
            session,
            username,
            refresh_token,
            token=token,
            token_expiration=token_expiration,
            afero_client=afero_client,
            hide_secrets=hide_secrets,
            client_name=client_name,
        )
        self.temperature_unit = temperature_unit
        self.logger = logging.getLogger(f"{__package__}-{afero_client}[{username}]")
        self._known_devs: dict[str, BaseResourcesController] = {}
        self._known_afero_devices: dict[str, str] = {}
        # Known running tasks
        self._scheduled_tasks: list[asyncio.Task] = []
        self._adhoc_tasks: list[asyncio.Task] = []
        # Data Updater
        self._events: EventStream = EventStream(
            self, polling_interval, poll_version, discovery_interval=discovery_interval
        )
        # Data Controllers
        self._controllers: dict[str, BaseResourcesController] = {}
        self.add_controller("devices", DeviceController)
        self.add_controller("exhaust_fans", ExhaustFanController)
        self.add_controller("fans", FanController)
        self.add_controller("lights", LightController)
        self.add_controller("locks", LockController)
        self.add_controller("portable_acs", PortableACController)
        self.add_controller("security_systems", SecuritySystemController)
        self.add_controller("security_systems_keypads", SecuritySystemKeypadController)
        self.add_controller("security_systems_sensors", SecuritySystemSensorController)
        self.add_controller("switches", SwitchController)
        self.add_controller("thermostats", ThermostatController)
        self.add_controller("valves", ValveController)

    @property
    def refresh_token(self) -> str | None:
        """Get the current sessions refresh token."""
        return self._auth.refresh_token

    @property
    def events(self) -> EventStream:
        """Get the class that handles getting new data and notifying controllers."""
        return self._events

    @property
    def controllers(self) -> list:
        """Get a list of initialized controllers."""
        return [
            controller
            for controller in self._controllers.values()
            if controller.initialized
        ]

    @property
    def tracked_devices(self) -> set:
        """Get all tracked devices."""
        return set(self._known_devs.keys())

    def add_device(
        self, device_id: str, controller: BaseResourcesController[AferoResource]
    ) -> None:
        """Add a device to the list of known devices and map it to its controller.

        :param device_id: The unique identifier of the device.
        :param controller: The controller instance responsible for the device.
        """
        self._known_devs[device_id] = controller

    def get_device_controller(self, device_id: str) -> BaseResourcesController:
        """Get the controller for a given device."""
        try:
            return self._known_devs[device_id]
        except KeyError as err:
            raise DeviceNotFound(f"Unable to find device {device_id}") from err

    def remove_device(self, device_id: str) -> None:
        """Remove a device from the list of known devices.

        :param device_id: The unique identifier of the device to remove.
        """
        with contextlib.suppress(KeyError):
            self._known_devs.pop(device_id)
        with contextlib.suppress(KeyError):
            self._known_afero_devices.pop(device_id)

    def add_afero_dev(self, device: AferoDevice, device_id: str | None = None) -> None:
        """Add a raw AferoDevice object to the internal cache.

        :param device: The `AferoDevice` object to cache.
        :param device_id: The ID to use for caching. If None, `device.id` is used.
        """
        if not device_id:
            device_id = device.id
        self._known_afero_devices[device_id] = device

    def get_afero_device(self, device_id: str) -> AferoDevice | None:
        """Get the raw AferoDevice object for a given ID.

        :param device_id: The unique identifier of the device.

        :return: The `AferoDevice` object if found, otherwise raises `DeviceNotFound`.
        :raises DeviceNotFound: If the device with the given ID is not found.
        """
        try:
            return self._known_afero_devices[device_id]
        except KeyError as err:
            raise DeviceNotFound(f"Unable to find device for {device_id}") from err

    def resolve_metadevice_id(self, device_id: str) -> str:
        """Return the Afero API metadevice ID used for state queries and updates."""
        try:
            device = self.get_afero_device(device_id)
        except DeviceNotFound:
            return device_id
        if device.split_identifier:
            return device.id.rsplit(f"-{device.split_identifier}-", 1)[0]
        return device_id

    @property
    def account_id(self) -> str:
        """Get the account ID for the Afero IoT account."""
        return self._account_id

    @property
    def afero_client(self) -> str:
        """Get identifier for Afero system."""
        return self._afero_client

    def add_controller(self, name: str, controller_type: type) -> None:
        """Add and instantiate a controller.

        The instantiated controller will be available as an attribute on the bridge
        instance with the provided name.

        :param name: The attribute name for the controller on the bridge instance.
        :param controller_type: The class of the controller to instantiate.
        """
        self._controllers[name] = controller_type(self)
        setattr(self, name, self._controllers[name])

    def set_token_data(self, data: TokenData) -> None:
        """Set TokenData used for querying the API.

        :param data: The `TokenData` object to set.
        """
        self._auth.set_token_data(data)

    def set_polling_interval(self, polling_interval: int) -> None:
        """Set the time between polling Afero API.

        :param polling_interval: The polling interval in seconds.
        """
        self._events.polling_interval = polling_interval

    def generate_api_url(self, endpoint: str) -> str:
        """Generate a URL for the Afero API.

        :param endpoint: The API endpoint path.

        :return: The fully qualified API URL.
        """
        endpoint = endpoint.removeprefix("/")
        return f"https://{v1_const.AFERO_CLIENTS[self._afero_client]['API_HOST']}/{endpoint}"

    async def close(self) -> None:
        """Close connection and clean up resources."""
        for task in self._scheduled_tasks:
            task.cancel()
            await task
        self._scheduled_tasks = []
        await self.events.stop()
        if self._close_session and self._web_session:
            await self._web_session.close()
        self.logger.info("Connection to bridge closed.")

    async def __aenter__(self) -> Self:
        """Enter async context: ``await bridge.initialize()``."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context: ``await bridge.close()``."""
        await self.close()

    @classmethod
    async def open(
        cls,
        username: str,
        refresh_token: str,
        session: aiohttp.ClientSession | None = None,
        *,
        token: str | None = None,
        token_expiration: float | None = None,
        polling_interval: int = 30,
        discovery_interval: int = 3600,
        afero_client: str | None = "hubspace",
        hide_secrets: bool = True,
        poll_version: bool = True,
        client_name: str | None = "aioafero",
        temperature_unit: TemperatureUnit = TemperatureUnit.CELSIUS,
    ) -> Self:
        """Create a bridge, initialize it, and wait for the first poll to finish.

        Caller is responsible for ``await bridge.close()`` when not using ``async with``.

        If you use ``async with`` on a bridge returned from ``open``, ``__aenter__`` calls
        ``initialize()`` again but that is a no-op when polling tasks already exist;
        only ``__aexit__`` (``close()``) matters for cleanup.

        Args:
            username: Afero-backed account username.
            refresh_token: OAuth refresh token from login or storage.
            session: Optional shared ``aiohttp.ClientSession``.
            token: Optional non-expired bearer token.
            token_expiration: Unix timestamp when ``token`` expires.
            polling_interval: Seconds between state polls.
            discovery_interval: Seconds between discovery polls.
            afero_client: Afero client identifier (default ``hubspace``).
            hide_secrets: Redact sensitive values from logs.
            poll_version: Periodically fetch firmware version metadata.
            client_name: User-Agent token.
            temperature_unit: Unit for temperature API responses.

        Returns:
            Initialized bridge with controllers populated from the first discovery poll.

        """
        close_session = session is None
        if session is None:
            session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit_per_host=3)
            )
        bridge = cls(
            username,
            refresh_token,
            session,
            token=token,
            token_expiration=token_expiration,
            polling_interval=polling_interval,
            discovery_interval=discovery_interval,
            afero_client=afero_client,
            hide_secrets=hide_secrets,
            poll_version=poll_version,
            client_name=client_name,
            temperature_unit=temperature_unit,
        )
        bridge._close_session = close_session
        await bridge.initialize()
        await bridge.async_block_until_done()
        return bridge

    def subscribe(
        self,
        callback: EventCallBackType,
    ) -> Callable:
        """Register a callback for resource changes on all initialized controllers.

        The cloud API is polled on ``polling_interval``; when state changes, controllers
        merge updates and invoke ``callback(event_type, item)`` in-process. ``item`` is
        the controller's resource model (``Fan``, ``Light``, etc.).

        Args:
            callback: Called as ``callback(event_type, item)``. May be sync or async.

        Returns:
            Callable that removes this subscription from every controller.

        """
        unsubscribes = [
            controller.subscribe(callback) for controller in self.controllers
        ]

        def unsubscribe():
            for unsub in unsubscribes:
                unsub()

        return unsubscribe

    async def get_account_id(self) -> str:
        """Lookup the account ID associated with the login.

        :return: The account ID.
        :raises AferoError: If no account ID is found in the API response.
        """
        if not self._account_id:
            self.logger.debug("Querying API for account id")
            headers = {"host": v1_const.AFERO_CLIENTS[self._afero_client]["API_HOST"]}
            url = self.generate_api_url(v1_const.AFERO_GENERICS["ACCOUNT_ID_ENDPOINT"])
            with self.secret_logger():
                self.logger.debug(
                    "GETURL: %s, Headers: %s",
                    url,
                    headers,
                )
            res = await self.request(
                "GET",
                url,
                headers=headers,
            )
            res.raise_for_status()
            json_data = await res.json()
            if len(json_data) == 0 or len(json_data.get("accountAccess", [])) == 0:
                raise AferoError("No account ID found")
            account_id = (
                json_data.get("accountAccess")[0].get("account").get("accountId")
            )
            add_secret(account_id)
            self._account_id = account_id
        return self._account_id

    async def initialize(self) -> None:
        """Initialize the bridge for communication with Afero API.

        To ensure the bridge is fully initialized, call async_block_until_done().
        """
        if len(self._scheduled_tasks) == 0:
            await self.get_account_id()
            for controller in self._controllers.values():
                if controller.initialized:
                    continue
                self.add_job(asyncio.create_task(controller.initialize()))
            self.add_job(asyncio.create_task(self.initialize_cleanup()))
            self.add_job(asyncio.create_task(self.events.initialize()))
            self.add_job(asyncio.create_task(self.events.wait_for_first_poll()))

    async def fetch_discovery_data(self, version_poll=False) -> list[dict[Any, str]]:
        """Query the API for all device data.

        :param version_poll: If True, also poll for device version information.

        :return: A list of dictionaries, each representing a device.
        """
        task = asyncio.create_task(self._fetch_data(version_poll))
        self.add_job(task)
        await task
        return task.result()

    async def _fetch_data(self, version_poll=False) -> list[dict[Any, str]]:
        """Query the API."""
        self.logger.debug("Querying API for all data")
        headers = {
            "host": v1_const.AFERO_CLIENTS[self._afero_client]["API_DATA_HOST"],
        }
        params = {"expansions": "state,capabilities,semantics"}
        if self.temperature_unit == TemperatureUnit.FAHRENHEIT:
            params["units"] = self.temperature_unit.value
        url = self.generate_api_url(
            v1_const.AFERO_GENERICS["API_DEVICE_ENDPOINT"].format(self.account_id)
        )
        res = await self.request(
            "get",
            url,
            headers=headers,
            params=params,
        )
        res.raise_for_status()
        data = await res.json()
        if not isinstance(data, list):
            raise TypeError(data)
        if version_poll:
            devs = {}
            for dev in data:
                if dev.get("typeId") != "metadevice.device":
                    continue
                dev_id = dev.get("deviceId")
                if dev_id in devs:
                    dev["version_data"] = devs[dev_id]
                    continue
                dev["version_data"] = await self.get_device_version(dev_id)
                devs[dev_id] = dev["version_data"]

        return data

    async def fetch_device_states(self, device_id) -> list[dict[Any, str]]:
        """Query the API for new device states.

        :param device_id: The ID of the device to fetch states for.

        :return: A list of `AferoState` objects representing the device's states.
        """
        task = asyncio.create_task(self._fetch_device_states(device_id))
        self.add_job(task)
        await task
        return task.result()[1]

    async def fetch_all_device_states(self) -> list[AferoDevice]:
        """Query the API for all known device states.

        :return: A list of `AferoDevice` objects with updated states.
        """
        task = asyncio.create_task(self._fetch_all_device_states())
        self.add_job(task)
        await task
        return task.result()

    async def _fetch_all_device_states(self) -> list[AferoDevice]:
        """Query the API for all known device states."""
        # Split entities share a parent metadevice; poll each parent once.
        metadevice_ids = {
            self.resolve_metadevice_id(device_id) for device_id in self._known_devs
        }
        tasks = [
            self._fetch_device_states(metadevice_id) for metadevice_id in metadevice_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        updated_devices: list[AferoDevice] = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.warning("Unable to fetch states: %s", result)
                continue
            device_id, states = result
            try:
                device = self.get_afero_device(device_id)
            except DeviceNotFound:
                self.logger.warning("Device %s not found in cache", device_id)
                continue
            device.states = states
            updated_devices.append(device)
        return updated_devices

    async def _fetch_device_states(self, device_id) -> tuple[str, list[dict[Any, str]]]:
        """Query the API for new device states."""
        self.logger.debug("Querying the API for updated states for %s", device_id)
        headers = {
            "host": v1_const.AFERO_CLIENTS[self._afero_client]["API_DATA_HOST"],
        }
        url = self.generate_api_url(
            v1_const.AFERO_GENERICS["API_DEVICE_STATE_ENDPOINT"].format(
                self.account_id, device_id
            )
        )
        res = await self.request(
            "get",
            url,
            headers=headers,
        )
        res.raise_for_status()
        data = await res.json()
        states = []
        for state in data.get("values", []):
            try:
                states.append(AferoState(**state))
            except TypeError:
                continue
        return data["metadeviceId"], states

    async def get_device_version(self, device_id: str) -> dict:
        """Query the API for device version information.

        :param device_id: The ID of the device to get version info for.

        :return: A dictionary containing version information.
        """
        endpoint = v1_const.AFERO_GENERICS["API_DEVICE_VERSIONS_ENDPOINT"].format(
            self.account_id, device_id
        )
        url = self.generate_api_url(endpoint)
        res = await self.request("GET", url)
        res.raise_for_status()
        return await res.json()

    @asynccontextmanager
    async def create_request(
        self, method: str, url: str, include_token: bool, **kwargs
    ) -> Generator[aiohttp.ClientResponse, None, None]:
        """Create and manage an `aiohttp` request.

        This is an async context manager that attaches authentication headers when
        requested and yields the response from the bridge's session.

        :param method: The HTTP method (e.g., "GET", "POST").
        :param url: The URL for the request.
        :param include_token: If True, an Authorization header with a bearer token
            will be included.
        """
        extras = {}
        if include_token:
            try:
                extras["Authorization"] = f"Bearer {await self._auth.token()}"
            except InvalidAuth:
                self.events.emit(EventType.INVALID_AUTH)
                raise
        headers = self.get_headers(**extras)
        headers.update(kwargs.get("headers", {}))
        kwargs["headers"] = headers
        kwargs["ssl"] = True
        async with self._web_session.request(method, url, **kwargs) as res:
            yield res

    async def request(
        self, method: str, url: str, include_token: bool = True, **kwargs
    ) -> aiohttp.ClientResponse:
        """Make a request to the API with automatic retries.

        :param method: The HTTP method.
        :param url: The request URL.
        :param include_token: Whether to include the auth token. Defaults to True.

        :return: The `aiohttp.ClientResponse` object.
        :raises ExceededMaximumRetries: If the request fails after all retries.
        """
        retries = 0
        self.logger.info("Making request [%s] to %s", method, url)
        with self.secret_logger():
            self.logger.debug("Request kwargs: %s", kwargs)
        while retries < v1_const.MAX_RETRIES:
            retries += 1
            if retries > 1:
                retry_wait = 0.25 * retries
                await asyncio.sleep(retry_wait)
            async with self.create_request(
                method, url, include_token, **kwargs
            ) as resp:
                # 504 means the API is overloaded, back off a bit
                # 503 means the service is temporarily unavailable, back off a bit.
                # 429 means the bridge is rate limiting/overloaded, we should back off a bit.
                if resp.status in [429, 503, 504]:
                    continue
                # 403 is bad auth
                if resp.status == 403:
                    raise web_exceptions.HTTPForbidden
                await resp.read()
                return resp
        raise ExceededMaximumRetries("Exceeded maximum number of retries")

    async def send_service_request(self, device_id: str, states: list[dict[str, Any]]):
        """Manually send state requests to Afero IoT.

        :param device_id: ID for the device
        :param states: List of states to send

        :raises DeviceNotFound: If the device with the given ID is not found.
        """
        controller = self._known_devs.get(device_id)
        if not controller:
            raise DeviceNotFound(f"Unable to find device {device_id}")
        await controller.update(device_id, states=states)

    def get_headers(self, **kwargs):
        """Get default headers for an API call.

        :param kwargs: Additional headers to include.
        :return: A dictionary of headers.
        """
        headers: dict[str, str] = {
            "user-agent": v1_const.AFERO_GENERICS["DEFAULT_USERAGENT"].safe_substitute(
                client_name=self.client_name
            ),
            "accept-encoding": "gzip",
        }
        headers.update(kwargs)
        return headers

    # Task management enables us to block until finished
    def add_job(self, task: asyncio.Task) -> None:
        """Add a job to be processed."""
        self._adhoc_tasks.append(task)

    async def async_block_until_done(self):
        """Block until all ad-hoc and event queue tasks are completed."""
        await asyncio.gather(*self._adhoc_tasks)
        await self.events.async_block_until_done()

    async def initialize_cleanup(self) -> None:
        """Start the background task that cleans up completed ad-hoc tasks."""
        self._scheduled_tasks.append(asyncio.create_task(self.__cleanup_processor()))

    async def __cleanup_processor(self) -> None:
        """Periodically remove finished tasks from the ad-hoc task list."""
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                for task in self._adhoc_tasks[:]:
                    if task.done():
                        self._adhoc_tasks.remove(task)
                await asyncio.sleep(1)

    async def adjust_temperature_unit(
        self,
        temperature_unit: TemperatureUnit,
    ) -> None:
        """Adjust the temperature unit for API responses.

        :param temperature_unit: The desired temperature unit for API responses.
        """
        if self.temperature_unit != temperature_unit:
            self.temperature_unit = temperature_unit
            self.add_job(asyncio.create_task(self.events.perform_discovery_poll()))
