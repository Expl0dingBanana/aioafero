Bridge configuration and lifecycle
==================================

``AferoBridgeV1`` is the main entry point (``from aioafero import v1``).

Construction
------------

Required:

* ``username`` — Afero-backed account username
* ``password`` — account password

Common optional arguments:

* ``afero_client`` — ``"hubspace"`` (default; only supported client)
* ``refresh_token`` — reuse a saved session and skip the initial login flow
* ``session`` — existing ``aiohttp.ClientSession`` (bridge closes it only if it created it)
* ``polling_interval`` — seconds between state polls (default ``30``)
* ``discovery_interval`` — seconds between device discovery polls (default ``3600``)
* ``temperature_unit`` — ``TemperatureUnit.CELSIUS`` (default) or ``FAHRENHEIT``
* ``hide_secrets`` — redact sensitive values from logs (default ``True``)
* ``poll_version`` — periodically fetch firmware version metadata (default ``True``)
* ``client_name`` — User-Agent token (default ``"aioafero"``)

After login, ``bridge.refresh_token`` holds the token for persistence. Restore a
saved session with ``bridge.set_token_data(token_data)``.

Lifecycle
---------

Typical async flow:

1. ``bridge = v1.AferoBridgeV1(...)``
2. ``await bridge.initialize()`` — starts controllers and background polling
3. ``await bridge.async_block_until_done()`` — wait for the first poll / init tasks
4. Use controllers to read state and send commands
5. ``await bridge.close()`` — stop polling and release the HTTP session

OTP
---

If the account has OTP enabled, call ``await bridge.otp_login("<code>")`` when login
requires it (after ``initialize()``).

Events
------

State updates are **not** pushed from the Afero cloud over a WebSocket. ``EventStream``
polls the REST API on a timer, merges changes into controller models, then **pushes
in-process** to any callbacks you register.

Polling loop (simplified):

1. Every ``polling_interval`` seconds, ``fetch_all_device_states()`` runs.
2. For each parent metadevice, returned states are **merged** into the cached
   ``AferoDevice`` (matched by ``functionClass`` and ``functionInstance``) rather than
   replacing the full ``states`` list. Partial poll payloads therefore do not drop
   other zones or dual-channel brightness rows.
3. Changed devices are queued on ``bridge.events``.
4. Each controller merges API data into its models (``update_elem``).
5. If something changed, registered callbacks run with ``(event_type, item)``.

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
* ``await bridge.fetch_all_device_states()`` — poll and merge states into the device
  cache (see polling loop above)
* ``await bridge.send_service_request(device_id, states)`` — low-level state write

See :doc:`../reference/index` for ``AferoBridgeV1`` autodoc.
