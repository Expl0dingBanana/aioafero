from unittest.mock import AsyncMock

import pytest

from aioafero.device import AferoDevice


@pytest.fixture
def conclave_bridge(mocked_bridge):
    """A mocked bridge with a single DL1-shaped Afero device registered.

    ``device_id`` is the physical Conclave id (16 hex chars); ``functions[]``
    carry the per-profile attribute keys used to resolve push ``attribute.id``
    values.
    """
    device = AferoDevice(
        id="dev-meta",
        device_id="8ad8cc7b5c18ce2a",
        model="m",
        device_class="light",
        default_name="n",
        default_image="i",
        friendly_name="DL1",
        functions=[
            {
                "functionClass": "power",
                "functionInstance": None,
                "values": [
                    {
                        "name": "off",
                        "deviceValues": [
                            {"type": "attribute", "key": "1", "value": "00"}
                        ],
                    },
                    {
                        "name": "on",
                        "deviceValues": [
                            {"type": "attribute", "key": "1", "value": "01"}
                        ],
                    },
                ],
            },
            {
                "functionClass": "brightness",
                "functionInstance": None,
                "values": [
                    {
                        "name": "brightness",
                        "deviceValues": [{"type": "attribute", "key": "2"}],
                    }
                ],
            },
        ],
        states=[],
    )
    mocked_bridge.add_afero_dev(device, device.device_id)
    generate = AsyncMock()
    mocked_bridge.events.generate_events_from_update = generate
    return mocked_bridge, device, generate
