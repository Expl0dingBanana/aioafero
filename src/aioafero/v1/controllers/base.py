import asyncio
import copy
import time
from asyncio.coroutines import iscoroutinefunction
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Generic, Iterator

from ...device import AferoDevice, AferoResource, AferoState, get_afero_device
from ...errors import DeviceNotFound, ExceededMaximumRetries
from .. import v1_const
from ..models.resource import ResourceTypes
from .event import AferoEvent, EventCallBackType, EventType

if TYPE_CHECKING:  # pragma: no cover
    from .. import AferoBridgeV1


EventSubscriptionType = tuple[
    EventCallBackType,
    "tuple[EventType] | None",
]

ID_FILTER_ALL = "*"


class BaseResourcesController(Generic[AferoResource]):
    """Base Controller for Afero IoT Cloud devices"""

    ITEM_TYPE_ID: ResourceTypes | None = None
    ITEM_TYPES: list[ResourceTypes] | None = None
    ITEM_CLS = None
    # functionClass map between controller -> Afero IoT Cloud
    ITEM_MAPPING: dict = {}

    def __init__(self, bridge: "AferoBridgeV1") -> None:
        """Initialize instance."""
        self._bridge = bridge
        self._items: dict[str, AferoResource] = {}
        self._logger = bridge.logger.getChild(self.ITEM_CLS.__name__)
        self._subscribers: dict[str, EventSubscriptionType] = {ID_FILTER_ALL: []}
        self._initialized: bool = False
        self._item_values = [x.value for x in self.ITEM_TYPES]

    def __getitem__(self, device_id: str) -> AferoResource:
        """Get item by device_id."""
        return self._items[device_id]

    def __iter__(self) -> Iterator[AferoResource]:
        """Iterate items."""
        return iter(self._items.values())

    def __contains__(self, device_id: str) -> bool:
        """Return bool if device_id is in items."""
        return device_id in self._items

    @property
    def items(self) -> list[AferoResource]:
        """Return all items for this resource."""
        return list(self._items.values())

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def _handle_event(
        self, evt_type: EventType, evt_data: AferoEvent | None
    ) -> None:
        """Handle incoming event for this resource"""
        if evt_data is None:
            return
        item_id = evt_data.get("device_id", None)
        cur_item = await self._handle_event_type(evt_type, item_id, evt_data)
        if cur_item:
            await self.emit_to_subscribers(evt_type, item_id, cur_item)

    async def _handle_event_type(
        self, evt_type: EventType, item_id: str, evt_data: AferoEvent
    ) -> AferoResource | None:
        """Determines what to do with the incoming event

        :param evt_type: Type of event
        :param item_id: ID of the item
        :param evt_data: Event data

        :return: Item after being processed
        """
        if evt_type == EventType.RESOURCE_ADDED:
            self._logger.info(
                "Initializing %s as a %s", evt_data["device"].id, self.ITEM_CLS.__name__
            )
            cur_item = await self.initialize_elem(evt_data["device"])
            self._items[item_id] = cur_item
            self._bridge.add_device(evt_data["device"].id, self)
        elif evt_type == EventType.RESOURCE_DELETED:
            cur_item = self._items.pop(item_id, evt_data)
            self._bridge.remove_device(evt_data["device_id"])
        elif evt_type == EventType.RESOURCE_UPDATED:
            # existing item updated
            try:
                cur_item = self.get_device(item_id)
            except DeviceNotFound:
                return
            if not await self.update_elem(evt_data["device"]) and not evt_data.get(
                "force_forward", False
            ):
                return
        else:
            # Skip all other events
            return
        return cur_item

    async def emit_to_subscribers(
        self, evt_type: EventType, item_id: str, item: AferoResource
    ):
        """Emit updates to subscribers

        :param evt_type: Type of event
        :param item_id: ID of the item
        :param item: Item to emit to subscribers
        """
        subscribers = (
            self._subscribers.get(item_id, []) + self._subscribers[ID_FILTER_ALL]
        )
        for callback, event_filter in subscribers:
            if event_filter is not None and evt_type not in event_filter:
                continue
            # dispatch the full resource object to the callback
            if iscoroutinefunction(callback):
                asyncio.create_task(callback(evt_type, item))
            else:
                callback(evt_type, item)

    def get_filtered_devices(self, initial_data: list[dict]) -> list[AferoDevice]:
        valid_devices: list[AferoDevice] = []
        for element in initial_data:
            if element["typeId"] != self.ITEM_TYPE_ID.value:
                self._logger.debug(
                    "TypeID [%s] does not match %s",
                    element["typeId"],
                    self.ITEM_TYPE_ID.value,
                )
                continue
            device = get_afero_device(element)
            if device.device_class not in self._item_values:
                self._logger.debug(
                    "Device Class [%s] is not contained in %s",
                    device.device_class,
                    self._item_values,
                )
                continue
            valid_devices.append(device)
        return valid_devices

    async def _get_valid_devices(self, initial_data: list[dict]) -> list[AferoDevice]:
        return self.get_filtered_devices(initial_data)

    async def initialize(self, initial_data: list[dict]) -> None:
        """Initialize controller by fetching all items for this resource type from bridge."""
        if self._initialized:
            return
        valid_devices: list[AferoDevice] = await self._get_valid_devices(initial_data)
        for device in valid_devices:
            await self._handle_event(
                EventType.RESOURCE_ADDED,
                AferoEvent(
                    type=EventType.RESOURCE_ADDED,
                    device_id=device.id,
                    device=device,
                ),
            )
        # subscribe to item updates
        res_filter = tuple(x.value for x in self.ITEM_TYPES)
        if res_filter:
            self._bridge.events.subscribe(
                self._handle_event,
                resource_filter=res_filter,
            )
        else:
            # Subscribe to all events
            self._bridge.events.subscribe(
                self._handle_event,
            )
        self._initialized = True

    async def initialize_elem(self, element: AferoDevice) -> None:  # pragma: no cover
        raise NotImplementedError("Class should implement initialize_elem")

    async def update_elem(self, element: AferoDevice) -> None:  # pragma: no cover
        raise NotImplementedError("Class should implement update_elem")

    def subscribe(
        self,
        callback: EventCallBackType,
        id_filter: str | tuple[str] | None = None,
        event_filter: EventType | tuple[EventType] | None = None,
    ) -> Callable:
        """
        Subscribe to status changes for this resource type.

        Parameters:
            - `callback` - callback function to call when an event emits.
            - `id_filter` - Optionally provide resource ID(s) to filter events for.
            - `event_filter` - Optionally provide EventType(s) as filter.

        Returns:
            function to unsubscribe.
        """
        if not isinstance(event_filter, None | list | tuple):
            event_filter = (event_filter,)

        if id_filter is None:
            id_filter = (ID_FILTER_ALL,)
        elif not isinstance(id_filter, list | tuple):
            id_filter = (id_filter,)

        subscription = (callback, event_filter)

        for id_key in id_filter:
            if id_key not in self._subscribers:
                self._subscribers[id_key] = []
            self._subscribers[id_key].append(subscription)

        # unsubscribe logic
        def unsubscribe():
            for id_key in id_filter:
                if id_key not in self._subscribers:
                    continue
                self._subscribers[id_key].remove(subscription)

        return unsubscribe

    async def _process_state_update(
        self, cur_item: AferoResource, device_id: str, states: list[dict]
    ) -> None:
        dev_states = []
        for state in states:
            dev_states.append(
                AferoState(
                    functionClass=state["functionClass"],
                    value=state["value"],
                    functionInstance=state.get("functionInstance"),
                    lastUpdateTime=int(datetime.now(timezone.utc).timestamp() * 1000),
                )
            )
        dummy_update = AferoDevice(
            id=device_id,
            device_id=cur_item.device_information.parent_id,
            model=cur_item.device_information.model,
            device_class=cur_item.device_information.device_class,
            default_image=cur_item.device_information.default_image,
            default_name=cur_item.device_information.default_name,
            friendly_name=cur_item.device_information.name,
            states=dev_states,
        )
        # Update now, but also trigger all chained updates
        await self.update_elem(dummy_update)
        self._bridge.events.add_job(
            AferoEvent(
                type=EventType.RESOURCE_UPDATED,
                device_id=device_id,
                device=dummy_update,
                force_forward=True,
            )
        )

    async def update_afero_api(self, device_id: str, states: list[dict]) -> bool:
        """Update Afero IoT API with the new states

        :param device_id: Afero IoT Device ID
        :param states: States to manually set

        :return: True if successful, False otherwise.
        """
        url = v1_const.AFERO_CLIENTS[self._bridge.afero_client]["DEVICE_STATE"].format(
            self._bridge.account_id, str(device_id)
        )
        headers = {
            "host": v1_const.AFERO_CLIENTS[self._bridge.afero_client]["DATA_HOST"],
            "content-type": "application/json; charset=utf-8",
        }
        payload = {"metadeviceId": str(device_id), "values": states}
        try:
            res = await self._bridge.request("put", url, json=payload, headers=headers)
        except ExceededMaximumRetries:
            self._logger.warning("Maximum retries exceeded for %s", device_id)
            return False
        else:
            # Bad states provided
            if res.status == 400:
                self._logger.warning(
                    "Invalid update provided for %s using %s", device_id, states
                )
                return False
        return True

    async def update(
        self,
        device_id: str,
        obj_in: Generic[AferoResource] = None,
        states: list[dict] | None = None,
    ) -> None:
        """Update Afero IoT with the new data

        :param device_id: Afero IoT Device ID
        :param obj_in: Afero IoT Resource elements to change
        :param states: States to manually set
        """
        try:
            cur_item = self.get_device(device_id)
        except DeviceNotFound:
            self._logger.info(
                "Unable to update device %s as it does not exist", device_id
            )
            return
        # Make a clone to restore if the update fails
        fallback = copy.deepcopy(cur_item)
        if obj_in:
            device_states = dataclass_to_afero(cur_item, obj_in, self.ITEM_MAPPING)
            if not device_states:
                self._logger.debug("No states to send. Skipping")
                return
            # Update the state of the item to match the new states
            update_dataclass(cur_item, obj_in)
        else:  # Manually setting states
            device_states = states
            await self._process_state_update(cur_item, device_id, states)
        # @TODO - Implement bluetooth logic for update
        if not await self.update_afero_api(device_id, device_states):
            self._items[device_id] = fallback

    def get_device(self, device_id) -> AferoResource:
        try:
            return self[device_id]
        except KeyError:
            raise DeviceNotFound(device_id)


def update_dataclass(elem: AferoResource, update_vals: dataclass):
    """Updates the element with the latest changes"""
    for f in fields(update_vals):
        cur_val = getattr(update_vals, f.name, None)
        elem_val = getattr(elem, f.name)
        if cur_val is None:
            continue
        # Special processing for dicts
        if isinstance(elem_val, dict):
            cur_val = {getattr(cur_val, "func_instance", None): cur_val}
            getattr(elem, f.name).update(cur_val)
        else:
            setattr(elem, f.name, cur_val)


def dataclass_to_afero(
    elem: AferoResource, cls: dataclass, mapping: dict
) -> list[dict]:
    """Convert the current state to be consumed by Afero IoT"""
    states = []
    for f in fields(cls):
        cur_val = getattr(cls, f.name, None)
        if cur_val is None:
            continue
        if cur_val == getattr(elem, f.name, None):
            continue
        api_key = mapping.get(f.name, f.name)
        new_val = cur_val.api_value
        if not isinstance(new_val, list):
            new_val = [new_val]
        for val in new_val:
            if hasattr(f, "func_instance"):
                instance = getattr(cur_val, "func_instance", None)
            elif hasattr(elem, "get_instance"):
                instance = elem.get_instance(api_key)
            else:
                instance = None
            new_state = {
                "functionClass": api_key,
                "functionInstance": instance,
                "lastUpdateTime": int(time.time()),
                "value": None,
            }
            if isinstance(val, dict):
                new_state.update(val)
            else:
                new_state["value"] = val
            states.append(new_state)
    return states
