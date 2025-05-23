import asyncio

import pytest

from aioafero.device import AferoState
from aioafero.v1.controllers import event
from aioafero.v1.controllers.device import DeviceController
from aioafero.v1.models.resource import DeviceInformation
from aioafero.v1.models.sensor import AferoBinarySensor, AferoSensor

from .. import utils

a21_light = utils.create_devices_from_data("light-a21.json")[0]
zandra_light = utils.create_devices_from_data("fan-ZandraFan.json")[1]
freezer = utils.create_devices_from_data("freezer.json")[0]
door_lock = utils.create_devices_from_data("door-lock-TBD.json")[0]


@pytest.fixture
def mocked_controller(mocked_bridge, mocker):
    mocker.patch("time.time", return_value=12345)
    controller = DeviceController(mocked_bridge)
    yield controller


@pytest.mark.asyncio
async def test_initialize_a21(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == a21_light.id
    assert dev.available is True
    assert dev.device_information == DeviceInformation(
        device_class=a21_light.device_class,
        default_image=a21_light.default_image,
        default_name=a21_light.default_name,
        manufacturer=a21_light.manufacturerName,
        model=a21_light.model,
        name=a21_light.friendly_name,
        parent_id=a21_light.device_id,
        wifi_mac="b31d2f3f-86f6-4e7e-b91b-4fbc161d410d",
        ble_mac="9c70c759-1d54-4f61-a067-bb4294bef7ae",
    )
    assert dev.sensors == {
        "wifi-rssi": AferoSensor(
            id="wifi-rssi",
            owner="dd883754-e9f2-4c48-b755-09bf6ce776be",
            _value=-50,
            instance=None,
            unit="dB",
        )
    }
    assert dev.binary_sensors == {}


@pytest.mark.asyncio
async def test_initialize_door_lock(mocked_controller):
    await mocked_controller.initialize_elem(door_lock)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == door_lock.id
    assert dev.available is True
    assert dev.device_information == DeviceInformation(
        device_class=door_lock.device_class,
        default_image=door_lock.default_image,
        default_name=door_lock.default_name,
        manufacturer=door_lock.manufacturerName,
        model=door_lock.model,
        name=door_lock.friendly_name,
        parent_id=door_lock.device_id,
        wifi_mac="6f6882f2-b35f-451f-bab1-4feafe33dbb3",
        ble_mac="1392f7cb-e23a-470e-b803-6be2e48ce5c0",
    )
    assert dev.sensors == {
        "battery-level": AferoSensor(
            id="battery-level",
            owner="698e8a63-e8cb-4335-ba6b-83ca69d378f2",
            _value=80,
            unit="%",
            instance=None,
        ),
    }
    assert dev.binary_sensors == {}


@pytest.mark.asyncio
async def test_initialize_binary_sensors(mocked_controller):
    await mocked_controller.initialize_elem(freezer)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == freezer.id
    assert dev.available is True
    assert dev.device_information == DeviceInformation(
        device_class=freezer.device_class,
        default_image=freezer.default_image,
        default_name=freezer.default_name,
        manufacturer=freezer.manufacturerName,
        model=freezer.model,
        name=freezer.friendly_name,
        parent_id=freezer.device_id,
        wifi_mac="351cccd0-87ff-41b3-b18c-568cf781d56d",
        ble_mac="c2e189e8-c80c-4948-9492-14ac390f480d",
    )
    assert dev.sensors == {
        "wifi-rssi": AferoSensor(
            id="wifi-rssi",
            owner="eacfca4b-4f4b-4ee2-aa64-e1052fa9cea7",
            _value=-71,
            instance=None,
            unit="dB",
        )
    }
    assert dev.binary_sensors == {
        "error|freezer-high-temperature-alert": AferoBinarySensor(
            id="error|freezer-high-temperature-alert",
            owner="eacfca4b-4f4b-4ee2-aa64-e1052fa9cea7",
            _value="normal",
            _error="alerting",
            instance="freezer-high-temperature-alert",
        ),
        "error|fridge-high-temperature-alert": AferoBinarySensor(
            id="error|fridge-high-temperature-alert",
            owner="eacfca4b-4f4b-4ee2-aa64-e1052fa9cea7",
            _value="alerting",
            _error="alerting",
            instance="fridge-high-temperature-alert",
        ),
        "error|mcu-communication-failure": AferoBinarySensor(
            id="error|mcu-communication-failure",
            owner="eacfca4b-4f4b-4ee2-aa64-e1052fa9cea7",
            _value="normal",
            _error="alerting",
            instance="mcu-communication-failure",
        ),
        "error|temperature-sensor-failure": AferoBinarySensor(
            id="error|temperature-sensor-failure",
            owner="eacfca4b-4f4b-4ee2-aa64-e1052fa9cea7",
            _value="normal",
            _error="alerting",
            instance="temperature-sensor-failure",
        ),
    }


@pytest.mark.parametrize(
    "filename, expected",
    [
        (
            "raw_hs_data.json",
            [
                "80c0d48afc5cea1a",
                "8ea6c4d8d54e8c6a",
                "8993cc7b5c18f066",
                "8ad8cc7b5c18ce2a",
            ],
        ),
        (
            "water-timer-raw.json",
            [
                "86114564-7acd-4542-9be9-8fd798a22b06",
            ],
        ),
    ],
)
def test_get_filtered_devices(filename, expected, mocked_controller, caplog):
    caplog.set_level(0)
    data = utils.get_raw_dump(filename)
    res = mocked_controller.get_filtered_devices(data)
    actual_devs = [x.device_id for x in res]
    assert len(actual_devs) == len(expected)
    for key in expected:
        assert key in actual_devs


@pytest.mark.asyncio
async def test_update_elem_sensor(mocked_controller):
    await mocked_controller.initialize_elem(a21_light)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == a21_light.id
    dev_update: utils.AferoDevice = utils.create_devices_from_data("light-a21.json")[0]
    unavail = utils.AferoState(
        functionClass="available",
        value=False,
    )
    utils.modify_state(dev_update, unavail)
    rssi = utils.AferoState(
        functionClass="wifi-rssi",
        value="40db",
    )
    utils.modify_state(dev_update, rssi)
    updates = await mocked_controller.update_elem(dev_update)
    assert dev.available is False
    assert dev.sensors["wifi-rssi"].value == 40
    assert updates == {"available", "sensor-wifi-rssi"}


@pytest.mark.asyncio
async def test_update_elem_binary_sensor(mocked_controller):
    await mocked_controller.initialize_elem(freezer)
    assert len(mocked_controller.items) == 1
    dev = mocked_controller.items[0]
    assert dev.id == freezer.id
    dev_update: utils.AferoDevice = utils.create_devices_from_data("freezer.json")[0]
    temp_sensor_failure = utils.AferoState(
        functionClass="error",
        functionInstance="temperature-sensor-failure",
        value="alerting",
    )
    utils.modify_state(dev_update, temp_sensor_failure)
    updates = await mocked_controller.update_elem(dev_update)
    assert dev.binary_sensors["error|temperature-sensor-failure"].value is True
    assert updates == {"binary-error|temperature-sensor-failure"}


@pytest.mark.asyncio
async def test_valve_emitting(bridge):
    dev_update = utils.create_devices_from_data("freezer.json")[0]
    add_event = {
        "type": "add",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    # Simulate a poll
    bridge.events.emit(event.EventType.RESOURCE_ADDED, add_event)
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.devices._items) == 1
    dev = bridge.devices._items[dev_update.id]
    assert dev.available
    assert dev.sensors["wifi-rssi"].value == -71
    assert dev.binary_sensors["error|temperature-sensor-failure"].value is False
    # Simulate an update
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="available",
            functionInstance=None,
            value=False,
        ),
    )
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="wifi-rssi",
            functionInstance=None,
            value=-42,
        ),
    )
    utils.modify_state(
        dev_update,
        AferoState(
            functionClass="error",
            functionInstance="temperature-sensor-failure",
            value="alerting",
        ),
    )
    update_event = {
        "type": "update",
        "device_id": dev_update.id,
        "device": dev_update,
    }
    bridge.events.emit(event.EventType.RESOURCE_UPDATED, update_event)
    # Bad way to check, but just wait a second so it can get processed
    await asyncio.sleep(1)
    assert len(bridge.devices._items) == 1
    dev = bridge.devices._items[dev_update.id]
    assert not dev.available
    assert dev.sensors["wifi-rssi"].value == -42
    assert dev.binary_sensors["error|temperature-sensor-failure"].value is True
