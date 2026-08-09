Conclave push channel
=====================

``aioafero`` 9.1 adds an optional Conclave push client that receives live device
state updates over Afero's account-scoped TLS socket. REST polling stays the
source of truth for discovery, writes, and slow reconciliation; Conclave is
**subscribe-only** and updates the same cached models REST polling uses.

Debug frame logging
-------------------

Decoded application frames are logged as JSON on
``aioafero.v1.conclave.frames`` at ``DEBUG`` (one object per message; heartbeats
are omitted). Raising that logger — or its parent ``aioafero`` — to ``DEBUG`` is
enough; no special handlers are required. Home Assistant integrations that
register ``aioafero`` under ``loggers`` pick this up when the user enables debug
logging for the integration.

Messages may include account and device identifiers — treat debug logs as
sensitive.

Buffered file capture
---------------------

:class:`~aioafero.v1.conclave.ConclaveFrameFileHandler` is a ``logging.Handler``
that buffers frame lines in memory and appends them to an NDJSON file when the
buffer fills (or on ``flush`` / ``close``):

.. code-block:: python

   from aioafero.v1.conclave import FRAME_LOGGER, attach_frame_capture

   handler = attach_frame_capture("conclave-frames.ndjson", buffer_size=32)
   # …run with enable_conclave=True…
   frames = handler.read_frames()  # flushes first
   FRAME_LOGGER.removeHandler(handler)
   handler.close()

With ``propagate=False`` (default in :func:`~aioafero.v1.conclave.attach_frame_capture`),
lines stay off parent loggers. Local ``scripts/afero_bridge.py`` enables this via
``capture_frames`` / ``capture_buffer`` in ``afero.yaml``.

Enabling Conclave
-----------------

Pass ``enable_conclave=True`` when constructing or opening the bridge:

.. code-block:: python

   bridge = v1.AferoBridgeV1(
       username,
       refresh_token,
       session=session,
       enable_conclave=True,
   )
   await bridge.initialize()
   await bridge.async_block_until_done()
   # ``bridge.conclave`` exposes the running client once the first poll completes.

``AferoBridgeV1.open(..., enable_conclave=True)`` forwards the flag through the
shorthand constructor. ``bridge.close()`` stops the Conclave client alongside
the rest of the bridge.

Lifecycle
---------

1. ``initialize()`` schedules a background task that waits for the first REST
   discovery poll (the discovery index and ``description.functions`` semantics
   are required to resolve push events).
2. The client requests a short-lived Conclave token via
   ``POST .../v1/accounts/{accountId}/conclaveAccess`` using the existing OAuth
   bearer token.
3. It opens a TLS socket to the returned ``host:port`` (typically
   ``conclave-stream1.afero.net:443``), sends an opening ``{}`` frame, and
   completes the handshake (``hello`` or ``tunnel`` — often zlib-compressed on
   first connect). It then logs in with the channel ID and the **short-lived
   Conclave access token** from step 2 (not the OAuth bearer) and waits for
   ``welcome``.
4. The server sends bare ``\n`` heartbeats (interval advertised in ``hello`` /
   ``welcome``, typically ~60 seconds). The client acknowledges each one. Push
   frames decode into ``attr_change`` / ``status_change`` events. Each one
   merges into the cached ``AferoDevice.states`` for the matching physical
   ``deviceId`` and the bridge dispatches the same ``EventType.RESOURCE_UPDATED``
   events that REST polling produces, so existing subscribers do not need to
   change.
5. On disconnect the client reconnects with exponential backoff, requesting a
   fresh ``conclaveAccess`` token each time.

Subscribers see push updates through the same ``bridge.subscribe`` /
``controller.subscribe`` API as REST updates. Call ``bridge.subscribe`` **after**
``await bridge.initialize()`` (only initialized controllers accept callbacks).

Connection status is exposed on the same :class:`~aioafero.v1.controllers.event.EventStream`
as REST polling. Subscribe with ``bridge.events.subscribe`` and filter for
``EventType.CONCLAVE_CONNECTING``, ``CONCLAVE_CONNECTED``, ``CONCLAVE_DISCONNECTED``,
and ``CONCLAVE_RECONNECTED``. The first three mirror REST ``CONNECTED`` /
``DISCONNECTED`` / ``RECONNECTED``; ``CONCLAVE_CONNECTING`` is emitted on each
reconnect attempt (REST tracks ``CONNECTING`` internally but does not emit it).
:attr:`~aioafero.v1.conclave.client.ConclaveClient.status`
and :attr:`~aioafero.v1.conclave.client.ConclaveClient.connected` mirror the live
session without subscribing.

How pushes are applied
----------------------

Conclave ``deviceId`` values are the physical device id (16 hex characters), not
always the metadevice UUID used as the REST cache key.
:meth:`~aioafero.v1.AferoBridgeV1.find_afero_devices_by_conclave_id` matches
``device.device_id`` so every cached metadevice on that radio receives the patch
(including split clones).

Each ``attr_change`` maps ``attribute.id`` through that device's
``description.functions`` semantics, coerces values into REST-shaped
``AferoState`` rows, and merges them into the cache. Split-light (and similar)
clones are refreshed from the parent before events fire. ``status_change`` updates
``available``, ``visible``, and ``direct`` only — not ``linked``, ``connected``, or
``rssi``.

Unknown attribute keys or unknown devices are logged at DEBUG and skipped; the
next discovery poll still reconciles state.

Inventory changes arrive on a separate ``public`` / ``invalidate`` envelope:

* ``kind: "remove"`` with ``target: "metadevices"`` or ``"devices"`` emits
  ``RESOURCE_DELETED`` for the matching metadevice and any split clones.
* ``kind: "add"`` with ``target: "metadevices"`` fetches that metadevice over REST
  (:meth:`~aioafero.v1.AferoBridgeV1.fetch_metadevice`) and emits
  ``RESOURCE_ADDED`` without treating other devices as deleted. A
  ``target: "devices"`` add is a no-op when the physical device is already
  cached; otherwise it triggers a discovery poll.
* Other invalidate kinds (``update``, …) are ignored for now.

Library layout
--------------

The ``aioafero.v1.conclave`` subpackage splits wire handling from bridge
integration:

* ``access`` — mint ``conclaveAccess`` tokens over REST
* ``protocol`` — login frame builder and ``private`` / ``public`` envelope parsing
* ``frames`` — incremental decoder (zlib prefix, JSON objects, ``\n`` heartbeats)
* ``semantics`` — per-device attribute index and REST value coercion
* ``events`` — apply pushes to the bridge cache and fan out controller events
* ``client`` — TLS session, reconnect loop, and dispatch to ``events``

See :doc:`../api/aioafero.v1.conclave` for the autodoc reference.

Limitations
-----------

* Conclave is **subscribe-only**. Writes still go through ``controller`` methods
  / ``bridge.send_service_request`` (REST).
* The client only resolves attributes that are present in the discovery
  ``description.functions`` semantics; unknown attribute IDs are ignored. A
  subsequent discovery poll picks up the missing semantic without user
  intervention.
* ``public`` / ``invalidate`` currently handles inventory ``add`` and ``remove``
  only; other kinds are ignored until modeled.
* The channel is best-effort. REST polling on ``polling_interval`` continues so
  any missed pushes are reconciled at the configured interval.
* After ``ConclaveClient.start()``, login must complete within 60 seconds or the
  bridge logs a warning and retries with backoff.
* A closed or stalled **wire** is detected automatically: EOF on read, failed
  heartbeat writes, or no server bytes for roughly **two heartbeat intervals**
  (from ``hello`` / ``welcome``, typically ~120s). The client reconnects with a
  fresh ``conclaveAccess`` token and, by default, runs one REST state poll to
  heal gaps.
* A **zombie** session (``welcome`` OK, heartbeats continue, but no ``private``
  pushes) is not visible from socket-closed checks alone. Pass
  ``push_idle_timeout=…`` to :class:`~aioafero.v1.conclave.client.ConclaveClient`
  when you need that case (e.g. long reconcile-only REST intervals in HA).
  :attr:`~aioafero.v1.conclave.client.ConclaveClient.push_stale` and
  :attr:`~aioafero.v1.conclave.client.ConclaveClient.seconds_since_last_push`
  expose push health for diagnostics.
