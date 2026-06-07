"""Verify the Conclave wiring on :class:`AferoBridgeV1`."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from aioafero.v1 import AferoBridgeV1, ConclaveClient


def test_find_afero_devices_by_conclave_id_matches_physical_device_id(
    mocked_bridge, conclave_bridge
):
    """Cached metadevice UUIDs must still resolve Conclave physical deviceId."""
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge.add_afero_dev(device)
    matches = bridge.find_afero_devices_by_conclave_id(device.device_id)
    assert matches == [device]


def test_find_afero_devices_by_conclave_id_deduplicates_shared_object(
    mocked_bridge, conclave_bridge
):
    """The same AferoDevice cached under two keys is returned once."""
    bridge, device, _ = conclave_bridge
    bridge._known_afero_devices.clear()
    bridge._known_afero_devices[device.id] = device
    bridge._known_afero_devices[device.device_id] = device
    matches = bridge.find_afero_devices_by_conclave_id(device.device_id)
    assert matches == [device]


def test_conclave_property_default_is_none(mocked_bridge):
    assert mocked_bridge.conclave is None
    assert mocked_bridge._enable_conclave is False


def test_conclave_constructor_flag_is_stored(aio_sess):
    bridge = AferoBridgeV1(
        "user",
        "mock-refresh-token",
        session=aio_sess,
        enable_conclave=True,
    )
    assert bridge._enable_conclave is True
    assert bridge.conclave is None


@pytest.mark.asyncio
async def test_start_conclave_after_poll_warns_when_login_times_out(
    mocked_bridge, mocker, caplog
):
    mocked_bridge._enable_conclave = True
    mocker.patch.object(ConclaveClient, "start", AsyncMock())
    mocker.patch.object(
        ConclaveClient, "wait_until_logged_in", AsyncMock(return_value=False)
    )
    with caplog.at_level("WARNING"):
        await mocked_bridge._start_conclave_after_poll()
    assert "Conclave login did not complete" in caplog.text


@pytest.mark.asyncio
async def test_start_conclave_after_poll_waits_for_login(mocked_bridge, mocker):
    mocked_bridge._enable_conclave = True
    fake_wait = AsyncMock(return_value=True)
    mocker.patch.object(ConclaveClient, "wait_until_logged_in", fake_wait)
    mocker.patch.object(ConclaveClient, "start", AsyncMock())
    await mocked_bridge._start_conclave_after_poll()
    fake_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_conclave_after_poll_creates_client_and_starts(
    mocked_bridge, mocker
):
    """Initialize-time wiring should create and start a ConclaveClient."""
    mocked_bridge._enable_conclave = True
    # The fixture already marked first poll as completed.
    fake_start = AsyncMock()
    fake_stop = AsyncMock()
    mocker.patch.object(ConclaveClient, "start", fake_start)
    mocker.patch.object(ConclaveClient, "stop", fake_stop)
    mocker.patch.object(
        ConclaveClient, "wait_until_logged_in", AsyncMock(return_value=True)
    )
    await mocked_bridge._start_conclave_after_poll()
    assert isinstance(mocked_bridge.conclave, ConclaveClient)
    fake_start.assert_awaited_once()
    # If invoked again (e.g. retry), the same client instance is reused.
    first = mocked_bridge.conclave
    await mocked_bridge._start_conclave_after_poll()
    assert mocked_bridge.conclave is first
    assert fake_start.await_count == 2


@pytest.mark.asyncio
async def test_initialize_schedules_conclave_when_enabled(mocked_bridge, mocker):
    """``initialize`` should queue the Conclave start task when enabled."""
    mocked_bridge._enable_conclave = True
    # Pretend the bridge has not yet been initialized.
    mocked_bridge._scheduled_tasks = []
    starter = mocker.patch.object(
        mocked_bridge, "_start_conclave_after_poll", AsyncMock()
    )
    mocker.patch.object(mocked_bridge, "get_account_id", AsyncMock())
    await mocked_bridge.initialize()
    await mocked_bridge.async_block_until_done()
    starter.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_stops_conclave_and_clears_reference(mocked_bridge):
    """``bridge.close()`` must stop the running Conclave client and clear it."""
    stop = AsyncMock()
    client = Mock(spec=ConclaveClient)
    client.stop = stop
    mocked_bridge._conclave = client
    await mocked_bridge.close()
    stop.assert_awaited_once()
    assert mocked_bridge.conclave is None


@pytest.mark.asyncio
async def test_close_clears_conclave_even_if_stop_raises(mocked_bridge):
    """A failure stopping Conclave must not leak the reference."""
    stop = AsyncMock(side_effect=RuntimeError("boom"))
    client = Mock(spec=ConclaveClient)
    client.stop = stop
    mocked_bridge._conclave = client
    with pytest.raises(RuntimeError, match="boom"):
        await mocked_bridge.close()
    assert mocked_bridge.conclave is None


@pytest.mark.asyncio
async def test_open_passes_enable_conclave_through(mocker):
    """``AferoBridgeV1.open`` should forward ``enable_conclave`` to the constructor."""
    init = mocker.patch.object(AferoBridgeV1, "initialize", AsyncMock())
    block = mocker.patch.object(AferoBridgeV1, "async_block_until_done", AsyncMock())
    bridge = await AferoBridgeV1.open(
        "user", "mock-refresh-token", enable_conclave=True
    )
    assert bridge._enable_conclave is True
    init.assert_awaited_once()
    block.assert_awaited_once()
    await bridge.close()
    # Make sure no dangling Conclave task survived close.
    assert bridge.conclave is None
    await asyncio.sleep(0)
