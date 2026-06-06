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

Authentication failures
-----------------------

* ``InvalidAuth`` — credentials or refresh token rejected; re-login required.
* ``OTPRequired`` / ``InvalidOTP`` — call ``otp_login`` with a valid code.
* ``ExceededMaximumRetries`` — transient overload (429/503/504); bridge retries automatically.

Incorrect split-device state
----------------------------

Split entities share a parent metadevice ID for API updates. Ensure integrations use
each model's ``update_id`` (not ``id``) when debugging state writes. See
:doc:`device_splitting`.
