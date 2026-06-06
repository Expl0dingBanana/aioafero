Troubleshooting
===============

Device shows incorrect model
----------------------------

Afero IoT does not always report enough metadata for automatic classification.
Open a PR against ``src/aioafero/device.py`` and update ``AferoDevice.__post_init__``
so the device maps to the correct ``device_class``.

Slow or stale updates
---------------------

The API rate-limits requests. Concurrent clients (phone app, Home Assistant, scripts)
compete for the same quota. Reduce polling frequency with ``polling_interval`` or
limit concurrent integrations.

No log output when debugging
----------------------------

aioafero does not attach logging handlers. In a standalone script, configure the stdlib
logger before raising levels — for example ``logging.basicConfig(level=logging.INFO)`` and
``logging.getLogger("aioafero").setLevel(logging.DEBUG)``. See :doc:`examples`.
Integrations such as Home Assistant configure ``aioafero`` loggers via their own logging
setup.

Authentication failures
-----------------------

* ``InvalidAuth`` — credentials or refresh token rejected. Run a full login again with
  ``v1.AferoAuth.for_login`` and replace the stored ``refresh_token`` (see :doc:`auth`).
* ``OTPRequired`` / ``InvalidOTP`` — during setup, the account emailed a one-time code.
  Collect it from the user and call ``auth.submit_otp`` on the same ``v1.AferoAuth``
  instance (aioafero does not read email; see :doc:`auth`).
* ``ExceededMaximumRetries`` — transient overload (429/503/504); bridge retries automatically.

Incorrect split-device state
----------------------------

Split entities share a parent metadevice ID for API updates. Ensure integrations use
each model's ``update_id`` (not ``id``) when debugging state writes. See
:doc:`device_splitting`.
