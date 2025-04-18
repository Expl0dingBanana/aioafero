from aioafero.v1.models.sensor import AferoSensor, AferoSensorError


def test_init_sensor():
    dev = AferoSensor(
        id="entity-1",
        owner="device-link",
        _value="cool",
        unit="beans",
    )
    assert dev.value == "cool"
    assert dev.unit == "beans"


def test_init_sensor_error():
    dev = AferoSensorError(
        id="entity-1",
        owner="device-link",
        _value="alerting",
        unit="beans",
    )
    assert dev.value is True
    dev.value = "normal"
    assert dev.value is False
