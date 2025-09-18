"""Controls Hubspace devices on v1 API."""

__all__ = [
    "AferoBridgeV1",
    "AferoController",
    "AferoModelResource",
    "BaseResourcesController",
    "DeviceController",
    "FanController",
    "LightController",
    "LockController",
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
from typing import Any

import aiohttp
from aiohttp import web_exceptions
from securelogging import LogRedactorMessage, add_secret

from aioafero.device import AferoDevice, AferoResource, AferoState
from aioafero.errors import (
    AferoError,
    DeviceNotFound,
    ExceededMaximumRetries,
    InvalidAuth,
)

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
    """Controls Afero IoT devices on v1 API."""

    _web_session: aiohttp.ClientSession | None = None

    def __init__(
        self,
        username: str,
        password: str,
        refresh_token: str | None = None,
        session: aiohttp.ClientSession | None = None,
        polling_interval: int = 30,
        afero_client: str | None = "hubspace",
        hide_secrets: bool = True,
        poll_version: bool = True,
    ):
        """Create a bridge that communicates with Afero IoT API."""
        if hide_secrets:
            self.secret_logger = LogRedactorMessage
        else:
            self.secret_logger = passthrough
        self._close_session: bool = session is None
        self._web_session: aiohttp.ClientSession = session
        self._account_id: str | None = None
        self._afero_client: str = afero_client
        self._auth = AferoAuth(
            self,
            username,
            password,
            refresh_token=refresh_token,
            afero_client=afero_client,
            hide_secrets=hide_secrets,
        )
        self.logger = logging.getLogger(f"{__package__}-{afero_client}[{username}]")
        if len(self.logger.handlers) == 0:
            self.logger.addHandler(logging.StreamHandler())
        self._known_devs: dict[str, BaseResourcesController] = {}
        self._known_afero_devices: dict[str, str] = {}
        # Known running tasks
        self._scheduled_tasks: list[asyncio.Task] = []
        self._adhoc_tasks: list[asyncio.Task] = []
        # Data Updater
        self._events: EventStream = EventStream(self, polling_interval, poll_version)
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
        """Add a device to the list of known devices."""
        self._known_devs[device_id] = controller

    def get_device_controller(self, device_id: str) -> BaseResourcesController:
        """Get the controller for a given device."""
        try:
            return self._known_devs[device_id]
        except KeyError as err:
            raise DeviceNotFound(f"Unable to find device {device_id}") from err

    def remove_device(self, device_id: str) -> None:
        """Remove a device from the list of known devices."""
        with contextlib.suppress(KeyError):
            self._known_devs.pop(device_id)
        with contextlib.suppress(KeyError):
            self._known_afero_devices.pop(device_id)

    def add_afero_dev(self, device: AferoDevice, device_id: str | None = None) -> None:
        """Add a tracked afero device."""
        if not device_id:
            device_id = device.id
        self._known_afero_devices[device_id] = device

    def get_afero_device(self, device_id: str) -> AferoDevice | None:
        """Get the afero device for a given id."""
        try:
            return self._known_afero_devices[device_id]
        except KeyError as err:
            raise DeviceNotFound(f"Unable to find device for {device_id}") from err

    @property
    def account_id(self) -> str:
        """Get the account ID for the Afero IoT account."""
        return self._account_id

    @property
    def afero_client(self) -> str:
        """Get identifier for Afero system."""
        return self._afero_client

    def add_controller(self, name: str, controller_type: type) -> None:
        """Add a controller to the list of controllers."""
        self._controllers[name] = controller_type(self)
        setattr(self, name, self._controllers[name])

    def set_token_data(self, data: TokenData) -> None:
        """Set TokenData used for querying the API."""
        self._auth.set_token_data(data)

    def set_polling_interval(self, polling_interval: int) -> None:
        """Set the time between polling Afero API."""
        self._events.polling_interval = polling_interval

    def generate_api_url(self, endpoint: str) -> str:
        """Generate a URL for the Afero API."""
        endpoint = endpoint.removeprefix("/")
        return f"https://{v1_const.AFERO_CLIENTS[self._afero_client]['API_HOST']}/{endpoint}"

    async def close(self) -> None:
        """Close connection and cleanup."""
        for task in self._scheduled_tasks:
            task.cancel()
            await task
        self._scheduled_tasks = []
        await self.events.stop()
        if self._close_session and self._web_session:
            await self._web_session.close()
        self.logger.info("Connection to bridge closed.")

    def subscribe(
        self,
        callback: EventCallBackType,
    ) -> Callable:
        """Subscribe to status changes for all resources.

        Returns:
            function to unsubscribe.

        """
        unsubscribes = [
            controller.subscribe(callback) for controller in self.controllers
        ]

        def unsubscribe():
            for unsub in unsubscribes:
                unsub()

        return unsubscribe

    async def get_account_id(self) -> str:
        """Lookup the account ID associated with the login."""
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
            self._account_id = (
                json_data.get("accountAccess")[0].get("account").get("accountId")
            )
            add_secret(self._account_id)
        return self._account_id

    async def initialize(self) -> None:
        """Initialize the bridge for communication with Afero API."""
        if len(self._scheduled_tasks) == 0:
            await self.initialize_cleanup()
            await self.get_account_id()
            await asyncio.gather(
                *[
                    controller.initialize()
                    for controller in self._controllers.values()
                    if not controller.initialized
                ]
            )
            await self._events.initialize()

    async def fetch_data(self, version_poll=False) -> list[dict[Any, str]]:
        """Query the API."""
        self.logger.debug("Querying API for all data")
        headers = {
            "host": v1_const.AFERO_CLIENTS[self._afero_client]["API_DATA_HOST"],
        }
        params = {"expansions": "state,capabilities,semantics"}
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
        """Query the API for new device states."""
        self.logger.debug("Querying the API for updated states for %s", device_id)
        headers = {
            "host": v1_const.AFERO_CLIENTS[self._afero_client]["API_DATA_HOST"],
        }
        params = {"expansions": "state,capabilities,semantics"}
        url = self.generate_api_url(
            v1_const.AFERO_GENERICS["API_DEVICE_STATE_ENDPOINT"].format(
                self.account_id, device_id
            )
        )
        res = await self.request(
            "get",
            url,
            headers=headers,
            params=params,
        )
        res.raise_for_status()
        data = await res.json()
        states = []
        for state in data.get("values", []):
            try:
                states.append(AferoState(**state))
            except TypeError:
                continue
        return states

    async def get_device_version(self, device_id: str) -> dict:
        """Query the API for device version information."""
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
        """Make a request to any path with V2 request method (auth in header).

        Returns a generator with aiohttp ClientResponse.
        """
        if self._web_session is None:
            connector = aiohttp.TCPConnector(
                limit_per_host=3,
            )
            self._web_session = aiohttp.ClientSession(connector=connector)

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
        """Make request on the api and return response data."""
        retries = 0
        with self.secret_logger():
            self.logger.info("Making request [%s] to %s with %s", method, url, kwargs)
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
        """
        controller = self._known_devs.get(device_id)
        if not controller:
            raise DeviceNotFound(f"Unable to find device {device_id}")
        await controller.update(device_id, states=states)

    def get_headers(self, **kwargs):
        """Get default headers for an API call."""
        headers: dict[str, str] = {
            "user-agent": v1_const.AFERO_GENERICS["DEFAULT_USERAGENT"],
            "accept-encoding": "gzip",
        }
        headers.update(kwargs)
        return headers

    # Task management enables us to block until finished
    def add_job(self, task: asyncio.Task) -> None:
        """Add a job to be processed."""
        self._adhoc_tasks.append(task)

    async def async_block_until_done(self):
        """Sync call for ensuring all processing is done."""
        await asyncio.gather(*self._adhoc_tasks)
        await self.events.async_block_until_done()

    async def initialize_cleanup(self) -> None:
        """Create the job that removes finished tasks."""
        self._scheduled_tasks.append(asyncio.create_task(self.__cleanup_processor()))

    async def __cleanup_processor(self) -> None:
        """Remove finished tasks."""
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                for task in self._adhoc_tasks[:]:
                    if task.done():
                        self._adhoc_tasks.remove(task)
                await asyncio.sleep(1)
