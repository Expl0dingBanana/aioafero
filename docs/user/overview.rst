Overview
========

aioafero is an async Python client for the **Hubspace / Afero IoT cloud API**. It
authenticates to an account, discovers devices, keeps an in-memory copy of their state in
sync with the cloud, and exposes typed methods to read properties and send commands.

The library is **library-only** — it does not run inside Home Assistant or any other
host directly. Integrations such as
`Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_ install it
from PyPI and wrap it for their platform.

What the library does
---------------------

For one account, aioafero:

* **Authenticates** with a refresh token over HTTPS (obtained once via
  :doc:`auth`, or restored from storage).
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

Account access has two layers:

* **Authentication** — :class:`~aioafero.v1.AferoAuth` performs credential login
  (once) and refresh-token exchange at runtime. See :doc:`auth`.
* **Bridge** — ``AferoBridgeV1`` owns controllers, polling, and an HTTP ``session`` you
  pass at construction (or that :meth:`~aioafero.v1.AferoBridgeV1.open` creates).

.. mermaid::

   flowchart TD
       code["Your code"]
       auth["AferoAuth"]
       bridge["AferoBridgeV1"]
       controllers["Controllers (lights, fans, …)"]
       models["Resource models (cached state)"]
       events["EventStream"]
       cloud["Afero / Hubspace cloud"]

       code --> auth
       auth -->|"login / token refresh"| auth
       code --> bridge
       bridge --> controllers --> models
       bridge --> events -->|"periodic REST polls"| cloud

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

1. Log in with ``v1.AferoAuth`` (or reuse a saved refresh token); see :doc:`auth`.
2. Create ``AferoBridgeV1`` with ``username``, ``refresh_token``, and ``session``.
3. ``await bridge.initialize()`` — start controllers and background polling.
4. ``await bridge.async_block_until_done()`` — wait until the first discovery poll has
   populated controllers.
5. Read with ``bridge.<controller>.get_device(device_id)`` or list with
   ``bridge.<controller>.items()``.
6. Write with controller action methods (``turn_on``, ``set_state``, …).
7. Optionally ``bridge.subscribe(callback)`` to react to poll-driven updates.
8. ``await bridge.close()``, then ``await session.close()`` when you own the session.

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
* :doc:`auth` — login, tokens, OTP, and persistence
* :doc:`bridge` — configuration options and lifecycle detail
* :doc:`examples` — interactive session, subscribe, refresh tokens
* :doc:`controllers/index` — full controller list and action methods
