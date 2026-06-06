Authentication
==============

Hubspace / Afero accounts use OpenID Connect with refresh tokens. aioafero handles the
full login handshake in :class:`~aioafero.v1.AferoAuth` — separate from
``AferoBridgeV1``, which only needs tokens at runtime.

Import from the v1 namespace:

.. code-block:: python

   from aioafero import v1

``AferoAuth``, ``TokenData``, and ``OTPRequired`` are exported on ``aioafero.v1`` (not
the top-level ``aioafero`` package) so future API versions can ship their own auth flows.

Overview
--------

There are two ways to construct ``AferoAuth``:

**Credential login** (one-time or rare)

Use :meth:`~aioafero.v1.AferoAuth.for_login` when you have a username and password.
Call ``login()`` (or ``submit_otp()`` after OTP) to obtain :class:`~aioafero.v1.TokenData`.
Persist ``token_data.refresh_token`` — the password is not needed again.

**Runtime session** (normal operation)

Pass a saved ``refresh_token`` (and optionally a still-valid bearer ``token``) to
``AferoAuth`` or ``AferoBridgeV1``. The library refreshes the bearer token automatically
when it expires (from the API ``expires_in`` value, minus a 2-second buffer).

.. mermaid::

   flowchart TD
       login["for_login(session, user, password)"]
       submit["login() / submit_otp()"]
       tokens["TokenData"]
       persist["persist refresh_token"]
       bridge["AferoBridgeV1(user, refresh_token, session)"]
       init["bridge.initialize()"]
       api["auth.token() on each API call"]

       login --> submit --> tokens --> persist --> bridge --> init --> api
       submit -.->|"OTP: user enters emailed code"| submit

HTTP session
------------

``AferoAuth`` uses an ``aiohttp.ClientSession`` for OpenID and token-endpoint requests.
Pass the same session to ``AferoBridgeV1`` so login and API traffic share one connection
pool:

.. code-block:: python

   import aiohttp
   from aioafero import v1

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, USERNAME, PASSWORD)
   token_data = await auth.login()

   bridge = v1.AferoBridgeV1(USERNAME, token_data.refresh_token, session=session)
   await bridge.initialize()
   # ...
   await bridge.close()
   await session.close()

If you omit ``session`` on the bridge, it creates and owns its own session on
``initialize()`` and closes it on ``close()``.

Credential login
----------------

Accounts **without** OTP — a single ``login()`` call returns ``TokenData``:

.. code-block:: python

   import aiohttp
   from aioafero import v1

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")
   token_data = await auth.login()

   print(token_data.refresh_token)  # save for next run

Accounts **with** OTP — login is a **two-phase** flow. ``login()`` validates the
password, Hubspace/Afero **emails** a one-time code to the account, and
``submit_otp()`` sends that code to complete the handshake. aioafero does **not** read
email or generate the code; your application must collect it from the user (config-flow
step, CLI prompt, form field, etc.) and pass it to ``submit_otp``.

.. code-block:: python

   import aiohttp
   from aioafero import v1

   session = aiohttp.ClientSession()
   auth = v1.AferoAuth.for_login(session, "user@example.com", "password")

   try:
       token_data = await auth.login()
   except v1.OTPRequired:
       # Wait for the user to read the email and enter the code.
       # Keep the same auth instance — it holds partial login state in memory.
       code = input("Enter the code from your email: ")
       token_data = await auth.submit_otp(code.strip())

   print(token_data.refresh_token)

``login()`` and ``submit_otp()`` both return ``TokenData``. Store at least the refresh
token; you may also save the bearer ``token`` field to skip one refresh on the next
startup if it has not expired.

After the credential POST, aioafero clears the password from the ``AferoAuth`` instance.
Discard that login object once you have ``token_data`` — do not keep a ``for_login``
instance around for runtime. Your own local ``password`` variable is outside the
library's scope.

OTP
~~~

When OTP is enabled on the account, ``login()`` raises :class:`~aioafero.errors.OTPRequired`
after the password is accepted. The library has already stored the partial OpenID session
on that ``AferoAuth`` instance (``_otp_data``); call ``submit_otp`` on the **same**
instance once you have the code — do not create a new ``for_login`` unless login timed
out or failed.

What aioafero does **not** do:

* Send or receive email
* Poll an inbox for the code
* Block until a code arrives

What **you** must provide:

* A way for the user to enter the emailed code (integrations typically add a second
  setup step after ``OTPRequired``)
* The same ``AferoAuth`` object between ``login()`` and ``submit_otp()``

On a wrong code, :class:`~aioafero.errors.InvalidOTP` is raised. The partial session is
updated so you can prompt again without restarting ``for_login``.

TokenData
---------

:class:`~aioafero.v1.TokenData` is a ``NamedTuple`` returned by login and refresh
operations:

* ``token`` — bearer ID token sent in API ``Authorization`` headers
* ``access_token`` — OAuth access token from the token endpoint
* ``refresh_token`` — long-lived token used to obtain new bearer tokens
* ``expiration`` — Unix timestamp when the bearer token should be refreshed

The bridge reads tokens through its internal ``AferoAuth``. After a running session you
can read the latest refresh token from ``bridge.refresh_token`` (it may rotate on
refresh).

Runtime tokens
--------------

When you already have a refresh token, construct the bridge directly — no password and
no ``for_login``:

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
   # ...
   await bridge.close()
   await session.close()

If ``token`` is provided and not expired, the first API call skips a refresh round-trip.
Otherwise ``AferoAuth.token()`` exchanges the refresh token for a new bearer token
automatically.

Restore or update tokens on an existing bridge with
:meth:`~aioafero.v1.AferoBridgeV1.set_token_data`.

Token refresh
-------------

:meth:`~aioafero.v1.AferoAuth.token` returns the current bearer token, refreshing
it when ``expiration`` has passed. Refresh uses only the stored refresh token — there is
no password fallback.

If the refresh token is rejected, :class:`~aioafero.errors.InvalidAuth` is raised and the
caller must run a full login again via ``for_login``.

Bridge integration
------------------

``AferoBridgeV1`` creates an internal ``AferoAuth`` from ``username``, ``refresh_token``,
and optional ``token``. You do not need a separate auth object for normal bridge use
after the initial login.

Typical integration pattern (e.g. Home Assistant):

1. **Setup** — ``for_login`` → ``login()`` / ``submit_otp()`` → save ``refresh_token``
   in config storage.
2. **Runtime** — ``AferoBridgeV1(username, refresh_token)`` on every start; never persist
   the password.
3. **Re-auth** — if ``InvalidAuth`` occurs at runtime, prompt the user to log in again
   and replace the stored refresh token.

See :doc:`bridge` for bridge construction options and lifecycle.

Configuration
-------------

``AferoAuth.for_login`` and runtime construction accept:

* ``afero_client`` — ``"hubspace"`` (default; only supported client today)
* ``hide_secrets`` — redact tokens from debug logs via ``securelogging`` (default ``True``)
* ``client_name`` — substituted into the User-Agent string (default ``"aioafero"``)

Errors
------

* :class:`~aioafero.errors.OTPRequired` — password accepted; OTP code needed
* :class:`~aioafero.errors.InvalidOTP` — wrong OTP; retry ``submit_otp``
* :class:`~aioafero.errors.InvalidAuth` — bad credentials or expired refresh token
* :class:`~aioafero.errors.InvalidResponse` — unexpected HTML/JSON from auth host

See :doc:`troubleshooting` for operational guidance.

API reference
-------------

Autodoc: :mod:`aioafero.v1` (``AferoAuth``, ``TokenData`` are exported on the package;
implementation module :mod:`aioafero.v1.auth`).
