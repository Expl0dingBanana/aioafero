Bridge configuration and lifecycle
==================================

``AferoBridgeV1`` is the main entry point (``from aioafero import v1``). Login happens
first via :doc:`auth`; the bridge takes ``username``, ``refresh_token``, and ``session``.

Construction
------------

Required:

* ``username``
* ``refresh_token`` — from login or storage
* ``session`` — ``aiohttp.ClientSession``

Common options (``afero_client``, ``hide_secrets``, and ``client_name`` also apply to
:class:`~aioafero.v1.AferoAuth` — :doc:`auth`):

* ``token`` / ``token_expiration`` — skip initial refresh if the bearer is still valid
* ``afero_client`` — ``"hubspace"`` (default)
* ``polling_interval`` — state poll interval in seconds (default ``30``)
* ``discovery_interval`` — discovery poll interval in seconds (default ``3600``)
* ``temperature_unit`` — ``TemperatureUnit.CELSIUS`` or ``FAHRENHEIT``
* ``hide_secrets`` — redact sensitive log values (default ``True``)
* ``poll_version`` — fetch firmware version metadata (default ``True``)
* ``client_name`` — User-Agent token (default ``"aioafero"``)

``bridge.refresh_token`` tracks the current refresh token (including rotation).
``bridge.set_token_data(token_data)`` restores or updates tokens.

Lifecycle
---------

1. Log in and get ``token_data`` (:doc:`auth`).
2. ``bridge = v1.AferoBridgeV1(username, token_data.refresh_token, session=session)``.
3. ``await bridge.initialize()`` — start controllers and background polling.
4. ``await bridge.async_block_until_done()`` — wait for the first discovery poll.
5. Read and command via controllers.
6. ``await bridge.close()``. If you passed ``session``, close it yourself afterward.

Shorthand
~~~~~~~~~

``async with`` runs ``initialize`` on enter and ``close`` on exit:

.. code-block:: python

   async with v1.AferoBridgeV1(username, refresh_token, session=session) as bridge:
       await bridge.async_block_until_done()
       await bridge.lights.turn_on(device_id)

   await session.close()

:meth:`~aioafero.v1.AferoBridgeV1.open` can create a session when you omit ``session``.
In that case ``close()`` closes it:

.. code-block:: python

   bridge = await v1.AferoBridgeV1.open(username, refresh_token)
   await bridge.async_block_until_done()
   await bridge.lights.turn_on(device_id)
   await bridge.close()

Events
------

There is no WebSocket from the cloud. ``EventStream`` polls the REST API every
``polling_interval`` seconds, merges changes into controller models, and runs your
callbacks in-process:

1. ``fetch_all_device_states()`` runs on the timer.
2. Changes queue on ``bridge.events``.
3. Controllers update their models.
4. Callbacks receive ``(event_type, item)``.

``item`` is the typed model (``Fan``, ``Light``, …) after the merge. Callbacks can be
sync or ``async def``.

* ``bridge.subscribe(callback)`` — all controllers
* ``controller.subscribe(callback, id_filter=..., event_filter=...)`` — one controller or device

See :doc:`examples`.

Manual API access
-----------------

* ``await bridge.fetch_discovery_data()``
* ``await bridge.fetch_device_states(device_id)``
* ``await bridge.fetch_all_device_states()``
* ``await bridge.send_service_request(device_id, states)`` — low-level write

Full API: :doc:`../reference/index`.
