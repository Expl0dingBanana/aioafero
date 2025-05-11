from aioafero.v1.models.sensor import AferoBinarySensor, AferoSensor


def test_init_sensor():
    dev = AferoSensor(
        id="entity-1",
        owner="device-link",
        _value="cool",
        unit="beans",
    )
    assert dev.value == "cool"
    assert dev.unit == "beans"


def test_init_mapped_sensor_error():
    dev = AferoBinarySensor(
        id="entity-1",
        owner="device-link",
        _value="alerting",
        _error="alerting",
    )
    assert dev.value is True
    dev.value = "normal"
    assert dev.value is False
