Overview
========

aioafero is an async Python client for the **Hubspace / Afero IoT cloud API**. It logs
into an account, discovers devices, keeps an in-memory copy of their state in sync with
the cloud, and exposes typed methods to read properties and send commands.

The library is **library-only** — it does not run inside Home Assistant or any other
host directly. Integrations such as
`Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_ install it
from PyPI and wrap it for their platform.

What the library does
---------------------

For one account, aioafero:

* **Authenticates** with username/password (or a saved refresh token) over HTTPS.
* **Discovers** devices from the cloud API and classifies them by type (light, fan,
  thermostat, …).
* **Polls** device state on a timer — the API is REST-based; there is no persistent
  WebSocket push from the cloud.
* **Parses** raw API payloads into Python models with typed properties (on/off,
  brightness, HVAC mode, …).
* **Sends commands** back through the same REST API when you call controller action
  methods (``turn_on``, ``set_state``, and so on).
* **Notifies subscribers** in-process when polled state changes (optional; see
  :doc:`examples`).

How it fits together
--------------------

Everything for an account hangs off a single **bridge** — ``AferoBridgeV1``. The bridge
owns the HTTP session, auth tokens, and background tasks.

.. code-block:: text

   Your code
       │
       ▼
   AferoBridgeV1  ──►  Controllers (lights, fans, …)
       │                      │
       │                      ▼
       │                 Resource models (cached state)
       │
       ▼
   EventStream  ──►  periodic REST polls  ──►  Afero / Hubspace cloud

**EventStream** runs discovery and state polling in the background. When a poll returns
new data, it queues events; each **controller** merges updates into its models and can
invoke any callbacks you registered.

**Controllers** are the public API surface for a device class — ``bridge.lights``,
``bridge.fans``, ``bridge.thermostats``, and so on. Each controller knows how to
interpret API fields for that type and which commands are valid.

**Models** (``Light``, ``Fan``, ``Thermostat``, …) are snapshots of the last known state.
They are updated by polls and by command responses; changing a model attribute yourself
does not write to the cloud.

Typical session flow
--------------------

1. Create ``AferoBridgeV1`` with credentials.
2. ``await bridge.initialize()`` — start auth, controllers, and background polling.
3. ``await bridge.async_block_until_done()`` — wait until the first discovery poll has
   populated controllers.
4. Read with ``bridge.<controller>.get_device(device_id)`` or list with
   ``bridge.<controller>.items()``.
5. Write with controller action methods (``turn_on``, ``set_state``, …).
6. Optionally ``bridge.subscribe(callback)`` to react to poll-driven updates.
7. ``await bridge.close()`` when finished.

Some physical devices are **split** into multiple logical endpoints (multi-zone lights,
security sensors, portable AC power toggles). The bridge handles that during discovery;
see :doc:`device_splitting`.

Key bridge attributes
---------------------

Besides the controller attributes (``bridge.lights``, ``bridge.fans``, …):

* ``bridge.events`` — ``EventStream``; polling, discovery, and internal dispatch
* ``bridge.refresh_token`` — token to persist after login
* ``bridge.tracked_devices`` — device IDs currently known to the bridge
* ``bridge.devices`` — parent / metadevice records (read-only)

Next steps
----------

* :doc:`installation` — install from PyPI or a local checkout
* :doc:`bridge` — configuration options and lifecycle detail
* :doc:`examples` — interactive session, subscribe, refresh tokens
* :doc:`controllers/index` — full controller list and action methods
