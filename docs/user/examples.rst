Examples
========

Interactive shell
-----------------

Examples assume an asyncio REPL:

.. code-block:: bash

   python -m asyncio

Basic session
-------------

This walks through a minimal session: log in, connect to your Hubspace/Afero account,
wait until devices are loaded, read state from a controller, send one command, and shut
down cleanly.

What happens during startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Login** — ``v1.AferoAuth.for_login`` exchanges credentials for ``TokenData``
   (refresh token and optional bearer token). No bridge exists yet.
2. **Construction** — ``AferoBridgeV1(username, refresh_token, ...)`` stores the token
   and options only; no network I/O runs yet.
3. **Initialize** — ``await bridge.initialize()`` refreshes the bearer token if needed,
   resolves the account ID, registers each controller with ``EventStream``, and starts
   background tasks: discovery polling, periodic state polling, and the event processor.
4. **First discovery poll** — ``EventStream`` fetches the full device list from the REST
   API, parses ``AferoDevice`` payloads, runs any device-split callbacks, and queues
   ``RESOURCE_ADDED`` / ``RESOURCE_UPDATED`` events. Each controller builds its typed
   models (``Light``, ``Fan``, …) and caches them in memory.
5. **Block until ready** — ``await bridge.async_block_until_done()`` waits for startup
   tasks and the first poll to finish. After this returns,
   ``bridge.lights.get_device(...)`` and other controller lookups reflect the API state
   loaded during discovery.

If the account uses OTP, ``login()`` raises :class:`~aioafero.errors.OTPRequired` after
the password is accepted; Hubspace emails a code and **you** must collect it from the
user before calling ``submit_otp`` (aioafero does not read email). See :doc:`auth`.

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

   import aiohttp
   from aioafero import v1
   import logging

   # Standalone scripts need a handler; integrations (e.g. Home Assistant) configure
   # logging themselves.
   logging.basicConfig(level=logging.INFO)
   logging.getLogger("aioafero").setLevel(logging.DEBUG)

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")
   try:
       token_data = await auth.login()
   except v1.OTPRequired:
       code = input("Enter the code from your email: ")
       token_data = await auth.submit_otp(code.strip())

   bridge = v1.AferoBridgeV1(
       "user@example.com",
       token_data.refresh_token,
       session=session,
       polling_interval=30,
   )
   await bridge.initialize()
   await bridge.async_block_until_done()

   # See what loaded (use your device IDs from here)
   for light in bridge.lights.items():
       print(light.id, light.device_information.name)

   light = bridge.lights.get_device("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")
   print(light.on)  # cached snapshot from the last poll

   await bridge.lights.turn_on("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")
   await bridge.close()
   await session.close()

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

   import aiohttp
   from aioafero import v1
   from aioafero.types import EventType

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")
   try:
       token_data = await auth.login()
   except v1.OTPRequired:
       code = input("Enter the code from your email: ")
       token_data = await auth.submit_otp(code.strip())

   bridge = v1.AferoBridgeV1(
       "user@example.com",
       token_data.refresh_token,
       session=session,
   )
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
   await session.close()

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

Skip password login when you have a saved refresh token (and optionally a still-valid
bearer token):

.. code-block:: python

   import aiohttp
   from aioafero import v1

   session = aiohttp.ClientSession()
   bridge = v1.AferoBridgeV1(
       "user@example.com",
       saved_refresh_token,
       session=session,
       token=saved_bearer_token,  # optional; skips refresh if not expired
   )
   await bridge.initialize()
   await bridge.async_block_until_done()

   # After a successful session (refresh token may rotate):
   saved_refresh_token = bridge.refresh_token

   await bridge.close()
   await session.close()
