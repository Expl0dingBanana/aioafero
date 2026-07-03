# Design draft: integrating `SchedulesController` with the polling/event model

Status: **draft for maintainer review** (PR #64 follow-up). No source files changed.

## Context

PR #64 added `SchedulesController` at `src/aioafero/v1/controllers/schedules.py`. It is
currently a **thin request client**: `get_schedules` / `create_schedule` /
`delete_schedule` / `add_event` issue authenticated HTTP calls and return
`DeviceSchedule` objects (`schedules.py:52-99`). It does not:

- cache schedules,
- poll/refresh them on a timer, or
- emit add/update/delete events to subscribers,

the way every other resource controller does via `BaseResourcesController`
(`base.py:53`).

The maintainer asked us to integrate schedules with the library's polling/event model
(suggesting maybe an hourly refresh) and is undecided whether the controller should
inherit `BaseResourcesController`.

### Why schedules are different from every other resource (the load-bearing facts)

These constraints drive the whole decision. Each is grounded in code I read:

1. **Schedules are not metadevices and are not in the global device-state dump.**
   The discovery poll (`AferoBridgeV1._fetch_data`, `__init__.py:402-436`) and the
   device-state poll (`_fetch_all_device_states` →`_fetch_device_states`,
   `__init__.py:460-506`) both hit `API_DEVICE_ENDPOINT` /
   `API_DEVICE_STATE_ENDPOINT`. Schedules live behind a **separate endpoint** —
   `API_DEVICE_SCHEDULES_ENDPOINT` = `/v1/accounts/{}/metadevices/{}/schedules`
   (`v1_const.py:37`) — and must be fetched **per device** (`schedules.py:35-57`).
   There is no payload field anywhere in the existing poll that carries schedules.

2. **They are served by the data host via the `Host` header**, exactly like
   `_fetch_device_states` and `BaseResourcesController.update_afero_api`
   (`schedules.py:46-50`, mirrors `base.py:464-467` and `__init__.py:485-487`).
   That part is already shared infrastructure, so either approach reuses
   `bridge.request(...)` cleanly.

3. **The base controller's whole intake path assumes an `AferoDevice` with
   `states`.** `_handle_event` reads `evt_data["device"]` and routes it through
   `initialize_elem(element: AferoDevice)` / `update_elem(element: AferoDevice)`
   (`base.py:108-161`, `358-374`). Those events are produced exclusively by
   `EventStream.generate_events_from_data` from the device dump
   (`event.py:361-402`). A schedule is a `DeviceSchedule` (`models/schedules.py:141`),
   not an `AferoDevice` with `functionClass`-shaped `states`, so it never enters that
   pipeline.

4. **`id` semantics are awkward.** `BaseResourcesController` keys `self._items` by the
   metadevice id (`base.py:140`, `base.py:81-83`). A schedule's own id is
   `DeviceSchedule.schedule_id` (server-assigned, `models/schedules.py:146`,
   `from_afero` maps `data["id"]`, line 171), and a single device "typically holds a
   single schedule object with multiple events" (`schedules.py:9-11`). So the natural
   cache key is the **device id**, and the value is a *list* of schedules — not the
   1-resource-per-id model the base class enforces.

The cleanest available reuse is the **subscriber + event-dispatch machinery**
(`emit_to_subscribers`, `subscribe`, `EventType`), which is decoupled from the device
pipeline and can be reused verbatim. Both approaches below reuse it.

---

## Approach A — dedicated controller with a periodic refresh (recommended)

Keep `SchedulesController` standalone (NOT a `BaseResourcesController`). Add an internal
cache keyed by device id, a configurable refresh interval (default `3600`s), a
background asyncio task started during bridge init, a `subscribe()` method copied from
the base controller's semantics, and cache accessors. It emits the same `EventType`
values (`RESOURCE_ADDED` / `RESOURCE_UPDATED` / `RESOURCE_DELETED`) through the same
subscriber pattern as `BaseResourcesController.emit_to_subscribers` (`base.py:163-182`).

### Code

```python
"""Client for Afero per-device schedules (with periodic refresh + events)."""

import asyncio
from asyncio.coroutines import iscoroutinefunction
from collections.abc import Callable
import contextlib
from typing import TYPE_CHECKING

from aioafero.types import EventType
from aioafero.v1 import v1_const
from aioafero.v1.controllers.base import EventSubscriptionType, ID_FILTER_ALL
from aioafero.v1.models.schedules import (
    DEFAULT_SCHEDULE_TAG,
    DeviceSchedule,
    ScheduleEvent,
)

if TYPE_CHECKING:
    from aioafero.v1 import AferoBridgeV1

DEFAULT_SCHEDULE_REFRESH_INTERVAL = 3600


class SchedulesController:
    """Manage per-device schedules with caching, refresh, and events."""

    def __init__(
        self,
        bridge: "AferoBridgeV1",
        refresh_interval: int = DEFAULT_SCHEDULE_REFRESH_INTERVAL,
    ) -> None:
        self._bridge = bridge
        self._logger = bridge.logger.getChild("SchedulesController")
        self._refresh_interval = refresh_interval
        # device_id -> schedules currently on that device
        self._items: dict[str, list[DeviceSchedule]] = {}
        self._subscribers: dict[str, list[EventSubscriptionType]] = {
            ID_FILTER_ALL: []
        }
        self._initialized = False
        self._refresh_task: asyncio.Task | None = None

    # ---- public read surface -------------------------------------------------

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def items(self) -> dict[str, list[DeviceSchedule]]:
        """All cached schedules keyed by device id."""
        return dict(self._items)

    def __getitem__(self, device_id: str) -> list[DeviceSchedule]:
        return self._items.get(device_id, [])

    def __contains__(self, device_id: str) -> bool:
        return device_id in self._items

    # ---- subscription (mirrors BaseResourcesController.subscribe) -------------

    def subscribe(
        self,
        callback: Callable,
        id_filter: str | tuple[str] | None = None,
        event_filter: EventType | tuple[EventType] | None = None,
    ) -> Callable:
        """Subscribe to schedule add/update/delete events."""
        if not isinstance(event_filter, (type(None), list, tuple)):
            event_filter = (event_filter,)
        if id_filter is None:
            id_filter = (ID_FILTER_ALL,)
        elif not isinstance(id_filter, (list, tuple)):
            id_filter = (id_filter,)
        subscription = (callback, event_filter)
        for id_key in id_filter:
            self._subscribers.setdefault(id_key, []).append(subscription)

        def unsubscribe():
            for id_key in id_filter:
                with contextlib.suppress(ValueError, KeyError):
                    self._subscribers[id_key].remove(subscription)

        return unsubscribe

    async def emit_to_subscribers(
        self, evt_type: EventType, device_id: str, schedules: list[DeviceSchedule]
    ) -> None:
        """Dispatch an event for a device's schedules (see base.py:163-182)."""
        subscribers = (
            self._subscribers.get(device_id, []) + self._subscribers[ID_FILTER_ALL]
        )
        for callback, event_filter in subscribers:
            if event_filter is not None and evt_type not in event_filter:
                continue
            if iscoroutinefunction(callback):
                self._bridge.add_job(
                    asyncio.create_task(callback(evt_type, schedules))
                )
            else:
                callback(evt_type, schedules)

    # ---- lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Prime the cache for known devices and start the refresh loop."""
        if self._initialized:
            return
        # Only refresh schedules for devices that actually support them
        # (water timers today). Refresh once up front so consumers get a
        # populated cache after the bridge's first poll.
        await self.refresh()
        self._refresh_task = asyncio.create_task(self.__refresh_loop())
        self._bridge.track_scheduled_task(self._refresh_task)  # see lifecycle note
        self._initialized = True

    async def __refresh_loop(self) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                await asyncio.sleep(self._refresh_interval)
                with contextlib.suppress(Exception):
                    await self.refresh()

    def _schedule_device_ids(self) -> list[str]:
        """Devices that can hold schedules. Today: tracked water-timer valves."""
        return [valve.id for valve in self._bridge.valves]

    async def refresh(self, device_ids: list[str] | None = None) -> None:
        """Re-fetch schedules for the given (or all known) devices and emit diffs."""
        targets = device_ids if device_ids is not None else self._schedule_device_ids()
        for device_id in targets:
            try:
                latest = await self.get_schedules(device_id)
            except Exception as err:  # network / auth / 4xx
                self._logger.warning(
                    "Unable to refresh schedules for %s: %s", device_id, err
                )
                continue
            await self._apply_refresh(device_id, latest)
        # Devices that dropped out of the tracked set get a delete.
        for stale_id in set(self._items) - set(targets):
            self._items.pop(stale_id, None)
            await self.emit_to_subscribers(
                EventType.RESOURCE_DELETED, stale_id, []
            )

    async def _apply_refresh(
        self, device_id: str, latest: list[DeviceSchedule]
    ) -> None:
        previous = self._items.get(device_id)
        if previous is None:
            self._items[device_id] = latest
            await self.emit_to_subscribers(
                EventType.RESOURCE_ADDED, device_id, latest
            )
        elif previous != latest:  # dataclass __eq__ gives a deep compare
            self._items[device_id] = latest
            await self.emit_to_subscribers(
                EventType.RESOURCE_UPDATED, device_id, latest
            )

    def _url(self, device_id, schedule_id=None):
        ...  # unchanged from current schedules.py:35-44

    def _headers(self):
        ...  # unchanged from current schedules.py:46-50

    async def get_schedules(self, device_id: str) -> list[DeviceSchedule]:
        ...  # unchanged from current schedules.py:52-57

    async def create_schedule(self, device_id, schedule):
        result = ...  # current schedules.py:59-70 body
        # Write-through: refresh just this device so subscribers see the change
        # immediately instead of waiting up to refresh_interval.
        await self.refresh(device_ids=[device_id])
        return result

    async def delete_schedule(self, device_id, schedule_id):
        ...  # current schedules.py:72-77 body
        await self.refresh(device_ids=[device_id])

    async def add_event(self, device_id, event):
        ...  # current schedules.py:79-99 body (calls create/delete, which refresh)
```

Two small bridge touch-points are required (called out as open questions, but trivial):

- `AferoBridgeV1.initialize` already loops controllers and calls `controller.initialize()`
  (`__init__.py:382-385`) — but `self.schedules` is **not** in `self._controllers`
  (`__init__.py:184` sets it as a bare attribute). Either add it to `_controllers` via
  `add_controller("schedules", SchedulesController)` (so init + the `controllers`
  property pick it up automatically, `__init__.py:197-203`) or explicitly
  `await self.schedules.initialize()` in `AferoBridgeV1.initialize`.
- `close()` cancels `self._scheduled_tasks` (`__init__.py:313-318`). The refresh task
  must land in that list — exposed above as a hypothetical
  `bridge.track_scheduled_task(...)`; equivalently append directly to
  `self._scheduled_tasks` or register via `initialize_cleanup`'s pattern.

### How a consumer (Home Assistant) subscribes and gets updates

```python
def on_schedules(evt_type, schedules):  # schedules: list[DeviceSchedule]
    ...
unsub = bridge.schedules.subscribe(on_schedules, id_filter=valve_id)
current = bridge.schedules[valve_id]  # immediate cached read
```

Identical ergonomics to `bridge.valves.subscribe(...)`. The only difference HA sees is
that the callback payload is `list[DeviceSchedule]` rather than a single resource — a
direct consequence of fact (4). `bridge.subscribe(...)` (the all-controllers helper,
`__init__.py:324-342`) would need schedules added to `self.controllers` to be included;
otherwise per-controller subscription works today.

### Bridge lifecycle

- **init:** one eager `refresh()` so the cache is warm, then the refresh loop. Fits
  alongside the existing `add_job(asyncio.create_task(controller.initialize()))` fan-out
  (`__init__.py:382-385`).
- **first poll ordering:** `refresh()` depends on `self._bridge.valves` being populated,
  which only happens after the first discovery poll
  (`event.py:404-416`, `RESOURCE_ADDED` → `initialize_elem`). Safest is to do the eager
  refresh lazily on first loop tick, or to subscribe to `bridge.valves` `RESOURCE_ADDED`
  and prime that device's schedules then (best-of-both; see open questions).
- **close:** refresh task cancelled with the other scheduled tasks (`__init__.py:313-318`).

### Pros

- Honors all four constraints above with zero violence to the base class.
- Cache shape (`device_id -> list[DeviceSchedule]`) matches reality (one device, one
  schedule object, many events).
- Refresh interval is independent of `polling_interval`/`discovery_interval`; an hourly
  schedule refresh does not add N per-device HTTP calls to the 30s state poll.
- Write-through on create/delete gives consumers instant feedback without waiting an hour.
- The existing thin-client methods are reused verbatim; lowest regression surface.

### Cons

- Duplicates ~30 lines of `subscribe`/`emit_to_subscribers` from `base.py:163-182, 376-414`.
  (Mitigate by importing `ID_FILTER_ALL`/`EventSubscriptionType` from `base`, as shown,
  or by factoring a tiny `SubscriberMixin` — see open questions.)
- A second polling cadence to reason about and document.
- `bridge.subscribe()` (all-controllers) won't include schedules unless schedules is
  registered in `self._controllers`.

### Test implications

- New unit tests in `tests/v1/controllers/test_schedules.py` (file already exists):
  feed two successive `get_schedules` fixtures, assert ADDED then UPDATED then DELETED
  are emitted with the right payloads; assert `refresh` swallows per-device errors and
  continues; assert write-through refresh fires after create/delete.
- Use a fake/looped bridge with `refresh_interval=0`-ish and drive `refresh()` directly
  rather than sleeping on the real loop (mirror how `test_event.py` drives the processor).
- No change to other controllers' tests → **regression risk is low**.

### Migration / regression risk

- **Low.** Public method signatures of the thin client are unchanged; new behavior is
  additive (cache + events + loop). Only new bridge wiring is the init/close hookup.

---

## Approach B — inherit `BaseResourcesController`

Make schedules a first-class resource: `class SchedulesController(BaseResourcesController[DeviceSchedule])`.
This is where the friction lives. Concretely:

### Where it fights the base class

1. **Intake path is device-dump-only.** `initialize()` subscribes to the event stream
   filtered by `ITEM_TYPES` resource values (`base.py:209-226`), and events arrive only
   from `generate_events_from_data` parsing the metadevice dump (`event.py:361-402`).
   Schedules are **never** in that dump (fact 1). So `_handle_event` /
   `_handle_event_type` (`base.py:108-161`) would never fire for schedules. We'd have to
   **manufacture synthetic `AferoEvent`s** ourselves and inject them via
   `bridge.events.add_job(...)` — i.e. rebuild Approach A's refresh loop *anyway*, just
   feeding it through the device pipeline.

2. **`initialize_elem`/`update_elem` expect an `AferoDevice` with `states`.**
   Their signatures are `(element: AferoDevice)` and they read `functionClass`-shaped
   states (`base.py:358-374`, see `ValveController.initialize_elem` `valve.py:87-151`).
   A `DeviceSchedule` (`models/schedules.py:141`) has no `states`, no `functionClass`, no
   `device_information`. To satisfy the base class we'd have to wrap each schedule in a
   fake `AferoDevice` and re-derive it back out — pure impedance-matching with no payoff.
   Worse, `_process_state_update` and `update()` (`base.py:416-447`, `488-530`) assume
   `cur_item.device_information` and call `update_afero_api` with
   `functionClass`/`value` state dicts — none of which a schedule has.

3. **One-item-per-id vs list-per-device.** `self._items[item_id] = cur_item` stores a
   single resource per id (`base.py:140`). Schedules are a *list* per device (fact 4).
   We'd either flatten to one `DeviceSchedule` per device (lossy if a device ever has >1)
   or key by `schedule_id` (server-assigned, unknown until after fetch — and `add_event`
   deletes+recreates objects, so ids churn on every edit, `schedules.py:94-98`).

4. **Host-header fetch.** Resources fetched per-device on the data host
   (fact 2) — the base class only knows how to *write* to the data host
   (`update_afero_api`, `base.py:449-486`); it has no per-resource GET path. We'd add one
   regardless.

5. **`get_filtered_devices` / `ITEM_TYPE_ID` / `ITEM_TYPES` don't apply.** They filter
   the device dump by `typeId`/`deviceClass` (`base.py:184-204`). Schedules have neither.
   These class attributes would be dead/misleading.

### Sketch (showing the awkwardness)

```python
class SchedulesController(BaseResourcesController[DeviceSchedule]):
    ITEM_TYPE_ID = ResourceTypes.DEVICE   # misleading: schedules aren't devices
    ITEM_TYPES = [ResourceTypes.WATER_TIMER]
    ITEM_CLS = DeviceSchedule             # has no .device_information / .states

    async def initialize(self) -> None:
        # CANNOT just call super().initialize(): that subscribes to the device
        # event stream, which never carries schedules. Must run our own loop.
        if self._initialized:
            return
        self._initialized = True
        asyncio.create_task(self.__refresh_loop())  # same loop as Approach A

    async def initialize_elem(self, element):  # element is NOT an AferoDevice here
        # We'd have to invent an AferoDevice wrapper upstream so the base
        # _handle_event_type path (base.py:132-141) can call this. Net: we fake
        # a device, store one schedule, and lose the list-per-device shape.
        ...

    async def update_elem(self, element):
        ...  # same impedance mismatch
```

Effectively Approach B re-implements Approach A's refresh loop **and** pays an
adapter tax to shoehorn `DeviceSchedule` through an `AferoDevice`-shaped pipeline.

### How a consumer subscribes

Same `subscribe(callback, id_filter=..., event_filter=...)` surface for free
(`base.py:376-414`) — this is the *one* genuine win. But the payload delivered through
`emit_to_subscribers` (`base.py:163-182`) is a single `cur_item`, so the list-per-device
reality is already broken at the seam.

### Bridge lifecycle

Would register naturally via `add_controller("schedules", ...)` and be picked up by
`AferoBridgeV1.initialize` (`__init__.py:382-385`) and the `controllers` property
(`__init__.py:197-203`) — a real ergonomic plus. But `super().initialize()` can't be
used as-is (point 1), so most of that benefit is notional.

### Pros

- `subscribe()` / `emit_to_subscribers` / `items` / `__getitem__` inherited.
- Auto-registration + inclusion in `bridge.subscribe()` and `bridge.controllers`.
- "Looks like" every other controller to a casual reader.

### Cons

- Must override/bypass `initialize`, `initialize_elem`, `update_elem`, `update`,
  `_handle_event` — i.e. most of the class — so the inheritance is mostly inert.
- Forces a fake-`AferoDevice` adapter and a one-item-per-id model that doesn't match the
  data (facts 3-4).
- Dead/misleading class attributes (`ITEM_TYPE_ID`, `ITEM_TYPES`, `ITEM_MAPPING`).
- Higher cognitive load: future maintainers will expect base-class semantics that don't
  hold for schedules.

### Test implications

- Must construct fixtures that thread schedules through the synthetic-`AferoDevice`
  adapter; tests assert on base-class internals (`_items`, `_handle_event`) that the real
  data flow never exercises → brittle.
- Risk of accidentally re-enabling the device-stream subscription and double-handling.

### Migration / regression risk

- **Moderate.** Touches shared base-class assumptions; a careless `super().initialize()`
  would subscribe schedules to the device event stream and could mis-handle unrelated
  device events. More surface to get wrong.

---

## Recommendation

**Adopt Approach A.** Keep `SchedulesController` standalone, add a device-keyed cache,
an independent (default `3600`s) refresh loop, a `subscribe()`/`emit_to_subscribers`
pair that reuses the existing `EventType` + subscriber dispatch contract
(`base.py:163-182`, `types.py:9-13`), and write-through refresh on create/delete.

Rationale: schedules violate every structural assumption `BaseResourcesController` is
built on — they're not metadevices, not in the device dump, fetched per-device on the
data host, and are a list-per-device rather than one-resource-per-id (facts 1-4).
Approach B inherits the class but then overrides almost all of it and adds an
`AferoDevice` adapter, so it pays the cost of inheritance for almost none of the benefit.
Approach A keeps the proven thin client intact and layers exactly the missing pieces
(cache + events + timer), reusing the genuinely reusable part — the subscriber/event
machinery — by import rather than inheritance.

If duplicating ~30 lines of subscriber code is the sticking point, factor a small
`SubscriberMixin` out of `BaseResourcesController` (`subscribe`, `emit_to_subscribers`,
`_subscribers`, `ID_FILTER_ALL`) that both the base controller and `SchedulesController`
share — best of both without forcing the device pipeline onto schedules.

## Open questions for the maintainer

1. **Registration:** register schedules via `add_controller("schedules", ...)` (so it's
   in `bridge.controllers` and `bridge.subscribe()`), or keep it as the current bare
   `self.schedules` attribute and wire init/close explicitly? The former is tidier but
   means schedules show up in any code that iterates `bridge.controllers` expecting
   `BaseResourcesController`-shaped objects.
2. **Refresh trigger:** pure timer (default 3600s), or also prime/refresh a device's
   schedules reactively when `bridge.valves` emits `RESOURCE_ADDED`? The reactive hook
   avoids the first-poll ordering issue and gives instant warm cache.
3. **Which devices get scheduled refresh?** Confirm the device set — today only water
   timers (`ResourceTypes.WATER_TIMER`, `valve.py:48`) are known to carry schedules.
   Should `_schedule_device_ids()` be driven by a capability check rather than hardcoding
   valves?
4. **Callback payload shape:** is `list[DeviceSchedule]` per device acceptable to HA, or
   does the integration want one event per `DeviceSchedule`/per `ScheduleEvent`?
5. **Write-through vs eventual:** OK to auto-`refresh()` the single device after
   create/delete (one extra GET per mutation) for immediate subscriber feedback, or
   prefer to wait for the next timer tick?
6. **Shared subscriber code:** acceptable to extract a `SubscriberMixin` from
   `BaseResourcesController`, or keep the ~30 lines duplicated in `SchedulesController`?
7. **Default interval as a bridge param?** Should `refresh_interval` be plumbed through
   `AferoBridgeV1.__init__` next to `polling_interval`/`discovery_interval`
   (`__init__.py:124-137`) so consumers can tune it, or stay a controller-local constant?
