"""Client for Afero per-device schedules.

Schedules are not polled metadevices, so this is a thin client over the bridge's
authenticated ``request`` (like the account-id lookup) rather than a
``BaseResourcesController``. It targets
``/v1/accounts/{accountId}/metadevices/{deviceId}/schedules`` on the data-host
backend (addressed via the Host header, mirroring ``_fetch_device_states``).

Exposes get/create/delete plus an ``add_event`` convenience that merges a new
event into a device's existing schedule (each device typically holds a single
schedule object with multiple events).
"""

from typing import TYPE_CHECKING

from aioafero.v1 import v1_const
from aioafero.v1.models.schedules import DeviceSchedule, ScheduleEvent

if TYPE_CHECKING:
    from aioafero.v1 import AferoBridgeV1


class SchedulesController:
    """Manage per-device schedules."""

    def __init__(self, bridge: "AferoBridgeV1") -> None:
        """Initialize with the owning bridge (auth, account id, requests)."""
        self._bridge = bridge
        self._logger = bridge.logger.getChild("SchedulesController")

    def _url(self, device_id: str, schedule_id: str | None = None) -> str:
        if schedule_id is None:
            endpoint = v1_const.AFERO_GENERICS["API_DEVICE_SCHEDULES_ENDPOINT"].format(
                self._bridge.account_id, device_id
            )
        else:
            endpoint = v1_const.AFERO_GENERICS["API_DEVICE_SCHEDULE_ENDPOINT"].format(
                self._bridge.account_id, device_id, schedule_id
            )
        return self._bridge.generate_api_url(endpoint)

    def _headers(self) -> dict[str, str]:
        # Device resources are served by the data host, addressed via Host header.
        return {
            "host": v1_const.AFERO_CLIENTS[self._bridge._afero_client]["API_DATA_HOST"]
        }

    async def get_schedules(self, device_id: str) -> list[DeviceSchedule]:
        """List the schedule objects on a device."""
        res = await self._bridge.request("GET", self._url(device_id), headers=self._headers())
        res.raise_for_status()
        data = await res.json()
        return [DeviceSchedule.from_afero(s) for s in data or []]

    async def create_schedule(
        self, device_id: str, schedule: DeviceSchedule
    ) -> DeviceSchedule:
        """Create a schedule object on a device."""
        res = await self._bridge.request(
            "POST",
            self._url(device_id),
            headers=self._headers(),
            json=schedule.to_afero(),
        )
        res.raise_for_status()
        return DeviceSchedule.from_afero(await res.json())

    async def delete_schedule(self, device_id: str, schedule_id: str) -> None:
        """Delete a schedule object from a device."""
        res = await self._bridge.request(
            "DELETE", self._url(device_id, schedule_id), headers=self._headers()
        )
        res.raise_for_status()

    async def add_event(
        self, device_id: str, event: ScheduleEvent
    ) -> DeviceSchedule:
        """Add an event to a device's schedule, preserving existing events.

        A device holds a single schedule object, so this fetches the current
        events, deletes the existing object(s), and posts the merged set.
        """
        existing = await self.get_schedules(device_id)
        events: list[ScheduleEvent] = [e for sched in existing for e in sched.events]
        events.append(event)
        for sched in existing:
            if sched.schedule_id:
                await self.delete_schedule(device_id, sched.schedule_id)
        return await self.create_schedule(device_id, DeviceSchedule(events=events))
