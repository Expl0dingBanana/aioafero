Bridge configuration and lifecycle
==================================

``AferoBridgeV1`` is the main entry point (``from aioafero import v1``).

Authentication
--------------

Login is handled by :class:`~aioafero.v1.AferoAuth` before the bridge is
constructed. The bridge only needs a **refresh token** (and optionally a still-valid
bearer ``token``) — not a password. See :doc:`auth` for login, OTP, token persistence,
and refresh behavior.

Construction
------------

Required:

* ``username`` — Afero-backed account username
* ``refresh_token`` — OAuth refresh token from login (or a saved token)
* ``session`` — ``aiohttp.ClientSession`` for API and auth traffic

Common optional arguments:

* ``token`` — non-expired bearer token; skips the initial refresh if still valid
* ``token_expiration`` — Unix timestamp when ``token`` expires (omit to refresh on first use)
* ``afero_client`` — ``"hubspace"`` (default; only supported client)
* ``polling_interval`` — seconds between state polls (default ``30``)
* ``discovery_interval`` — seconds between device discovery polls (default ``3600``)
* ``temperature_unit`` — ``TemperatureUnit.CELSIUS`` (default) or ``FAHRENHEIT``
* ``hide_secrets`` — redact sensitive values from logs (default ``True``)
* ``poll_version`` — periodically fetch firmware version metadata (default ``True``)
* ``client_name`` — User-Agent token (default ``"aioafero"``)

After a running session, ``bridge.refresh_token`` reflects the current refresh token
(including any rotation). Restore tokens with ``bridge.set_token_data(token_data)``.

Lifecycle
---------

Typical async flow:

1. Log in with ``v1.AferoAuth`` and obtain ``token_data`` (:doc:`auth`)
2. ``bridge = v1.AferoBridgeV1(username, token_data.refresh_token, session=session)``
3. ``await bridge.initialize()`` — starts controllers and background polling
4. ``await bridge.async_block_until_done()`` — wait for the first poll / init tasks
5. Use controllers to read state and send commands
6. ``await bridge.close()`` — stop polling. Does **not** close ``session`` when you
   passed it to ``__init__``; call ``await session.close()`` yourself (see :doc:`auth`
   and :doc:`examples`). When using :meth:`~aioafero.v1.AferoBridgeV1.open` without
   ``session``, ``close()`` also closes the session ``open`` created.

Shorthand patterns
~~~~~~~~~~~~~~~~~~

**Async context manager** — runs ``initialize`` on enter and ``close`` on exit. Call
``async_block_until_done()`` inside the block when you need populated controllers:

.. code-block:: python

   async with v1.AferoBridgeV1(username, refresh_token, session=session) as bridge:
       await bridge.async_block_until_done()
       await bridge.lights.turn_on(device_id)

   await session.close()  # required when you passed session=

**``AferoBridgeV1.open``** — construct with an optional ``session``; when omitted,
``open`` creates one and ``close()`` closes it. After ``open``, ``async with bridge``
is optional: ``__aenter__`` is a no-op for initialization (already done); ``__aexit__``
runs ``close()``:

.. code-block:: python

   bridge = await v1.AferoBridgeV1.open(username, refresh_token, session=session)
   async with bridge:
       await bridge.lights.turn_on(device_id)

   await session.close()  # when you passed session= to open()

Prefer explicit cleanup when you supplied ``session``:

.. code-block:: python

   session = aiohttp.ClientSession()
   bridge = await v1.AferoBridgeV1.open(username, refresh_token, session=session)
   await bridge.lights.turn_on(device_id)
   await bridge.close()
   await session.close()

Or let ``open`` own the session (no ``session`` argument):

.. code-block:: python

   bridge = await v1.AferoBridgeV1.open(username, refresh_token)
   await bridge.lights.turn_on(device_id)
   await bridge.close()  # also closes the session open created

Events
------

State updates are **not** pushed from the Afero cloud over a WebSocket. ``EventStream``
polls the REST API on a timer, merges changes into controller models, then **pushes
in-process** to any callbacks you register.

Polling loop (simplified):

1. Every ``polling_interval`` seconds, ``fetch_all_device_states()`` runs.
2. Changed devices are queued on ``bridge.events``.
3. Each controller merges API data into its models (``update_elem``).
4. If something changed, registered callbacks run with ``(event_type, item)``.

``item`` is the controller's typed model (``Fan``, ``Light``, etc.) after the merge.
Callbacks may be sync or ``async def``; async handlers are scheduled as tasks on the
bridge event loop.

* ``bridge.events`` — ``EventStream`` (polling, discovery, auth events)
* ``bridge.subscribe(callback)`` — same callback on every initialized controller
* ``controller.subscribe(callback, id_filter=..., event_filter=...)`` — scoped updates

See :doc:`examples` for a full subscribe example.

Manual API access
-----------------

Advanced callers can use:

* ``await bridge.fetch_discovery_data()`` — full discovery payload
* ``await bridge.fetch_device_states(device_id)``
* ``await bridge.fetch_all_device_states()``
* ``await bridge.send_service_request(device_id, states)`` — low-level state write

See :doc:`../reference/index` for ``AferoBridgeV1`` autodoc.
