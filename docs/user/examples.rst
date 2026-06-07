Examples
========

Run these in an asyncio REPL (``python -m asyncio``). Login flow: :doc:`auth`. Polling
and cleanup: :doc:`bridge`.

.. _examples-basic-session:

Basic session
-------------

Replace the sample device ID with one from ``bridge.lights.items`` (or another
controller).

.. code-block:: python

   import aiohttp
   from aioafero import v1
   import logging

   logging.basicConfig(level=logging.INFO)
   logging.getLogger("aioafero").setLevel(logging.DEBUG)
   log = logging.getLogger(__name__)

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

   for light in bridge.lights.items:
       log.info("%s %s", light.id, light.device_information.name)

   light = bridge.lights.get_device("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")
   log.info("on=%s", light.on)

   await bridge.lights.turn_on("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")
   await bridge.close()
   await session.close()

.. _subscribe-to-updates:

Subscribe to updates
--------------------

Use the same login pattern as :ref:`examples-basic-session` if your account requires OTP.

Callbacks run when a controller model changes — after a REST poll by default, or
immediately when Conclave push is enabled (:doc:`conclave`). ``event_type`` is an
:class:`~aioafero.types.EventType`; ``item`` is the updated model.

.. code-block:: python

   import aiohttp
   from aioafero import v1
   from aioafero.types import EventType
   import logging

   logging.basicConfig(level=logging.INFO)
   logging.getLogger("aioafero").setLevel(logging.DEBUG)
   log = logging.getLogger(__name__)

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")
   try:
       token_data = await auth.login()
   except v1.OTPRequired:
       code = input("Enter the code from your email: ")
       token_data = await auth.submit_otp(code.strip())

   bridge = v1.AferoBridgeV1("user@example.com", token_data.refresh_token, session=session)
   await bridge.initialize()
   await bridge.async_block_until_done()

   async def on_update(event_type, item):
       if event_type != EventType.RESOURCE_UPDATED:
           return
       log.info("%s %s", item.id, item)

   unsub = bridge.subscribe(on_update)
   # ...
   unsub()
   await bridge.close()
   await session.close()

Filter to one device:

.. code-block:: python

   from aioafero.types import EventType

   unsub = bridge.lights.subscribe(
       on_update,
       id_filter="84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6",
       event_filter=EventType.RESOURCE_UPDATED,
   )

Reuse a refresh token
---------------------

.. code-block:: python

   import aiohttp
   from aioafero import v1

   session = aiohttp.ClientSession()
   bridge = v1.AferoBridgeV1(
       "user@example.com",
       saved_refresh_token,
       session=session,
       token=saved_bearer_token,  # optional
   )
   await bridge.initialize()
   await bridge.async_block_until_done()

   saved_refresh_token = bridge.refresh_token  # may have rotated
   await bridge.close()
   await session.close()

Conclave push (optional)
------------------------

For live updates without waiting for the REST poll interval, enable Conclave on
the bridge. Setup, lifecycle, and the ``conclave_watch`` debug script are in
:doc:`conclave`. The subscribe pattern above is unchanged — pass
``enable_conclave=True`` and use the same ``bridge.subscribe`` / controller
callbacks:

.. code-block:: python

   from aioafero.types import EventType

   bridge = v1.AferoBridgeV1(
       "user@example.com",
       token_data.refresh_token,
       session=session,
       enable_conclave=True,
   )
   await bridge.initialize()
   await bridge.async_block_until_done()
   # bridge.conclave is set once the first discovery poll and login complete.

   def on_event(event_type, _data):
       if event_type in (
           EventType.CONCLAVE_CONNECTED,
           EventType.CONCLAVE_DISCONNECTED,
       ):
           print(event_type)

   bridge.events.subscribe(
       on_event,
       event_filter=(
           EventType.CONCLAVE_CONNECTING,
           EventType.CONCLAVE_CONNECTED,
           EventType.CONCLAVE_DISCONNECTED,
           EventType.CONCLAVE_RECONNECTED,
       ),
   )
   unsub = bridge.subscribe(on_update)
