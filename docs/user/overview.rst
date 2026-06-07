Overview
========

aioafero is an async Python client for the Hubspace / Afero cloud API. You log in once,
get a refresh token, then use ``AferoBridgeV1`` to discover devices, poll their state,
and send commands through typed controllers.

This is a library, not a Home Assistant integration.
`Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_ and other
hosts install it from PyPI and wrap it for their platform.

Architecture
------------

Your application touches :class:`~aioafero.v1.AferoAuth` only to **get a refresh token**
(:doc:`auth`). After that, your code talks to :class:`~aioafero.v1.AferoBridgeV1` for
devices, commands, and subscriptions (:doc:`bridge`). The bridge embeds its own
``AferoAuth`` and refreshes bearer tokens on API calls — you do not run a refresh loop
in application code.

Both entry points can share one ``aiohttp.ClientSession`` (or one that
:meth:`~aioafero.v1.AferoBridgeV1.open` creates for you).

.. mermaid::

   flowchart TD
       code[Your code]
       auth[AferoAuth]
       bridge[AferoBridgeV1]
       controllers[Controllers]
       models[Cached models]
       events[EventStream]
       cloud[Afero / Hubspace cloud]

       code -->|1. login once| auth
       auth -->|get tokens| cloud
       code -->|2. refresh_token + day-to-day API| bridge
       bridge --> controllers --> models
       bridge --> events
       bridge -->|HTTPS<br/>refresh internal| cloud
       events -->|poll| cloud
       events -->|3. subscribe callbacks| code

``bridge.lights``, ``bridge.fans``, and the other controller attributes are how you read
state and call actions. Model objects (``Light``, ``Fan``, …) mirror the last poll or
command response — changing a field on the model does not write to the cloud.

There is no cloud WebSocket. ``EventStream`` polls on a timer, updates models, and runs
your ``bridge.subscribe`` callbacks in-process — push-like notifications back into your
code, not from the cloud. See :doc:`bridge` for intervals and lifecycle.

Typical session
---------------

Examples use ``from aioafero import v1``; names below are the same types on ``v1``.

1. ``AferoAuth.for_login`` → ``login()`` / ``submit_otp()`` → save ``refresh_token``
   (:doc:`auth`).
2. ``AferoBridgeV1(username, refresh_token, session=session)``.
3. ``await bridge.initialize()`` then ``await bridge.async_block_until_done()``.
4. Use ``bridge.<controller>`` to read and command devices (:doc:`controllers/index`).
5. ``await bridge.close()``; ``await session.close()`` if you created the session.

Runnable scripts: :doc:`examples`.

Some hardware shows up as multiple logical devices (multi-zone lights, security sensors,
portable AC power toggles). See :doc:`device_splitting`.

Other useful attributes: ``bridge.events``, ``bridge.refresh_token`` (may rotate),
``bridge.tracked_devices``, ``bridge.devices`` (parent metadevices, read-only).
