Authentication
==============

Hubspace accounts use OpenID Connect with refresh tokens. Import ``from aioafero import
v1`` — ``AferoAuth`` and ``TokenData`` live on ``aioafero.v1``; exceptions like
``OTPRequired`` are on ``aioafero.errors`` and the top-level package too.

Credential login uses :class:`~aioafero.v1.AferoAuth`. ``AferoBridgeV1`` only needs
tokens at runtime.

Two modes
---------

**First login** — ``AferoAuth.for_login(session, username, password)``, then
``login()`` or ``submit_otp()``. Save ``token_data.refresh_token``; you should not need
the password again.

**Normal use** — pass the saved ``refresh_token`` to ``AferoAuth`` or
``AferoBridgeV1``. Optionally pass a bearer ``token`` and ``token_expiration`` to skip
one refresh round-trip. Without ``token_expiration``, the library refreshes on first use.
OAuth responses use ``expires_in`` minus a 2-second buffer.

.. mermaid::

   flowchart TD
       login[for_login]
       submit[login / submit_otp]
       tokens[TokenData]
       bridge[AferoBridgeV1]
       api[token on API calls]

       login --> submit --> tokens --> bridge --> api
       submit -.->|OTP email| submit

HTTP session
------------

Both ``AferoAuth`` and ``AferoBridgeV1`` need an ``aiohttp.ClientSession``. Share one
between login and the bridge:

.. code-block:: python

   import aiohttp
   from aioafero import v1

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, USERNAME, PASSWORD)
   token_data = await auth.login()

   bridge = v1.AferoBridgeV1(USERNAME, token_data.refresh_token, session=session)
   await bridge.initialize()
   await bridge.close()
   await session.close()

If you pass ``session`` in, ``bridge.close()`` does not close it — you must. If you use
:meth:`~aioafero.v1.AferoBridgeV1.open` without ``session``, ``close()`` closes the
session ``open`` created.

Credential login
----------------

Without OTP, one ``login()`` call is enough:

.. code-block:: python

   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")
   token_data = await auth.login()

With OTP, ``login()`` accepts the password and raises :class:`~aioafero.errors.OTPRequired`.
Hubspace emails a code; collect it from the user and call ``submit_otp`` on the **same**
``AferoAuth`` instance (the library does not read email):

.. code-block:: python

   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")
   try:
       token_data = await auth.login()
   except v1.OTPRequired:
       token_data = await auth.submit_otp(input("Code from email: ").strip())

After the credential POST, aioafero clears the password from the auth object. Drop the
``for_login`` instance once you have ``TokenData``.

Wrong OTP raises :class:`~aioafero.errors.InvalidOTP`; you can retry ``submit_otp`` on
the same instance.

TokenData
---------

:class:`~aioafero.v1.TokenData` fields:

* ``token`` — bearer ID token for API ``Authorization`` headers
* ``access_token`` — OAuth access token from the token endpoint
* ``refresh_token`` — long-lived token for obtaining new bearer tokens
* ``expiration`` — Unix timestamp when the bearer token expires

During a bridge session, read the latest refresh token from ``bridge.refresh_token`` (it
may rotate). Update an existing bridge with
:meth:`~aioafero.v1.AferoBridgeV1.set_token_data`.

Runtime tokens
--------------

When you already have a refresh token:

.. code-block:: python

   bridge = v1.AferoBridgeV1(
       "user@example.com",
       saved_refresh_token,
       session=session,
       token=saved_bearer_token,  # optional
   )
   await bridge.initialize()

:meth:`~aioafero.v1.AferoAuth.token` refreshes automatically when ``expiration`` has
passed. A rejected refresh token raises :class:`~aioafero.errors.InvalidAuth` — run
``for_login`` again.

Configuration
-------------

``AferoAuth`` shares ``afero_client``, ``hide_secrets``, and ``client_name`` with
:class:`~aioafero.v1.AferoBridgeV1` (defaults: ``"hubspace"``, ``True``, ``"aioafero"``).
Bridge-only options (polling intervals, temperature unit, …): :doc:`bridge`.

Errors
------

* :class:`~aioafero.errors.OTPRequired` — password OK, need OTP
* :class:`~aioafero.errors.InvalidOTP` — wrong code
* :class:`~aioafero.errors.InvalidAuth` — bad credentials or dead refresh token
* :class:`~aioafero.errors.InvalidResponse` — unexpected response from auth host

More help: :doc:`troubleshooting`, :doc:`bridge`, :mod:`aioafero.v1.auth`.
