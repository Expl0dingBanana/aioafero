Examples
========

Interactive shell
-----------------

Examples assume an asyncio REPL:

.. code-block:: bash

   python -m asyncio

Basic session
-------------

This walks through a minimal session: connect to your Hubspace/Afero account, wait until
devices are loaded, read state from a controller, send one command, and shut down
cleanly.

What happens during startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Construction** — ``AferoBridgeV1(...)`` stores credentials and options only; no
   network I/O runs yet.
2. **Initialize** — ``await bridge.initialize()`` logs in (unless ``refresh_token`` is supplied),
   resolves the account ID, registers each controller with ``EventStream``, and starts
   background tasks: discovery polling, periodic state polling, and the event processor.
3. **First discovery poll** — ``EventStream`` fetches the full device list from the REST
   API, parses ``AferoDevice`` payloads, runs any device-split callbacks, and queues
   ``RESOURCE_ADDED`` / ``RESOURCE_UPDATED`` events. Each controller builds its typed
   models (``Light``, ``Fan``, …) and caches them in memory.
4. **Block until ready** — ``await bridge.async_block_until_done()`` waits for startup tasks and the first
   poll to finish. After this returns, ``bridge.lights.get_device(...)`` and other
   controller lookups reflect the API state loaded during discovery.

If the account requires OTP, call ``await bridge.otp_login("<code>")`` when login fails
(see :doc:`bridge`).

Reading state and sending commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Read** — ``controller.get_device(device_id)`` returns the cached model from the last
  poll. Property access (``light.on``, ``fan.speed``, …) reads that in-memory snapshot.
  Changing attributes on the model does **not** write to the cloud.
* **Write** — call controller action methods (``turn_on``, ``set_state``, …). They send
  a REST request and merge the API response back into the model; see
  :doc:`controllers/index` for per-type methods.
* **List** — iterate ``bridge.lights.items()`` (or any controller) or inspect
  ``bridge.tracked_devices`` for IDs known to the bridge. Parent metadevices live on
  ``bridge.devices``.

State continues to refresh in the background while the bridge is open (every
``polling_interval`` seconds). To react to changes, see :ref:`subscribe-to-updates`.

.. code-block:: python

   from aioafero import v1
   import logging

   logging.getLogger("aioafero").setLevel(logging.DEBUG)

   bridge = v1.AferoBridgeV1(
       "user@example.com",
       "password",
       polling_interval=30,
   )
   await bridge.initialize()
   await bridge.async_block_until_done()

   # If OTP is enabled on the account:
   # await bridge.otp_login("123456")

   # See what loaded (use your device IDs from here)
   for light in bridge.lights.items():
       print(light.id, light.device_information.name)

   light = bridge.lights.get_device("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")
   print(light.on)  # cached snapshot from the last poll

   await bridge.lights.turn_on("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")
   await bridge.close()  # stop polling and release the HTTP session

.. _subscribe-to-updates:

Subscribe to updates
--------------------

aioafero does **not** receive live pushes from Hubspace/Afero. After
``initialize()``, ``EventStream`` runs a background poll every ``polling_interval``
seconds (default 30). When a poll returns new state, the bridge updates its in-memory
models and invokes your callback **locally** — a push onto your asyncio loop, not from
the cloud.

Typical sequence:

1. Poll completes and changed devices are queued on ``bridge.events``.
2. The matching controller merges API state into the cached model.
3. Your callback runs with ``(event_type, item)``.

``event_type`` is an :class:`~aioafero.types.EventType` (usually
``EventType.RESOURCE_UPDATED`` for state changes, ``RESOURCE_ADDED`` when discovery
finds a new device).

``item`` is the updated resource model from that controller (``Fan``, ``Light``,
``Switch``, …). Read current properties from ``item``; there is no separate
``updated_keys`` argument.

.. code-block:: python

   from aioafero import v1
   from aioafero.types import EventType

   bridge = v1.AferoBridgeV1("user@example.com", "password")
   await bridge.initialize()
   await bridge.async_block_until_done()

   async def on_update(event_type, item):
       if event_type != EventType.RESOURCE_UPDATED:
           return
       print(item.id, item)  # e.g. Fan model with merged state

   unsub = bridge.subscribe(on_update)

   # Callbacks keep firing while the bridge is open and polling runs.
   # ...
   unsub()  # stop receiving updates
   await bridge.close()

Subscribe to one controller or device:

.. code-block:: python

   from aioafero.types import EventType

   unsub = bridge.lights.subscribe(
       on_update,
       id_filter="84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6",
       event_filter=EventType.RESOURCE_UPDATED,
   )

``bridge.events.subscribe(...)`` is lower level (raw stream / auth events) and is
normally used inside the library, not by integrations.

Reuse a refresh token
---------------------

.. code-block:: python

   bridge = v1.AferoBridgeV1(
       "user@example.com",
       "password",
       refresh_token=saved_token,
   )
   await bridge.initialize()
   await bridge.async_block_until_done()

   # After a successful session:
   saved_token = bridge.refresh_token
