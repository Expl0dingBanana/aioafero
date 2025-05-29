========
aioafero
========


    Connects to Afero cloud API and provides an easy way to interact
    with devices.


This project was designed to asynchronously connect to the Afero IOT API. It
has the ability to retrieve the devices and set new states.


.. image:: https://github.com/Expl0dingBanana/aioafero/actions/workflows/cicd.yaml/badge.svg?branch=main
   :target: https://github.com/Expl0dingBanana/aioafero/actions/workflows/cicd.yaml

.. image:: https://codecov.io/github/Expl0dingBanana/aioafero/graph/badge.svg?token=NP2RE4I4XK
   :target: https://codecov.io/github/Expl0dingBanana/aioafero

Overview
========
All data is stored within a "bridge" that knows of all of the devices aligned
with the Afero IOT account. This bridge contains multiple controllers for each
device type. These controllers know how to interact with the Afero IOT devices.
Each controller manages the device's states. To retrieve a device, you must
query ``bridge.<controller>.get_device(<device_id>)`` which will return
a model containing all the states. Any changes to the model will not
update Afero IOT as the correct call needs to be made.

Controllers
===========

The following controllers are implemented:

* ``bridge.devices``: Top-level devices (such as a ceiling-fan, or light that
   is not associated with another device). These entities also contain their
   respective sensors and binary sensors. This is purely an informational
   controller and cannot set any states.

* ``bridge.fans``: Any device that matches a fan. Can perform the following
  actions:

   * turn_on
   * turn_off
   * set_speed
   * set_direction
   * set_preset

* ``bridge.lights``: Any device that matches a fan. Can perform the following
  actions:

   * turn_on
   * turn_off
   * set_color_temperature
   * set_brightness
   * set_rgb
   * set_effect

* ``bridge.locks``: Any device that matches a lock. Can perform the following
  actions:

   * lock
   * unlock


* ``bridge.portable_acs``: Any device that matches a portable-ac. Can perform the following
  actions:

   * Everything is done through set_state

* ``bridge.switches``: Any device that matches a switch. Can perform the following
  actions:

   * turn_on
   * turn_off


* ``bridge.thermostats``: Any device that matches a thermostat. Can perform the following
  actions:

   * set_fan_mode
   * set_hvac_mode
   * set_target_temperature
   * set_temperature_range


* ``bridge.valves``: Any device that matches a valves. Can perform the following
  actions:

   * turn_on
   * turn_off


Example Usage
=============
All examples assume you entered the shell with ``python -m asyncio``

.. code-block:: python

    from aioafero import v1
    import logging
    logging.getLogger("aioafero").setLevel(logging.DEBUG)
    USERNAME="" # Afero IOT username
    PASSWORD="" # Afero IOT password
    POLLING_INTERVAL=30 # Number of seconds between polling cycles
    # Create the bridge
    bridge = v1.AferoBridgeV1(USERNAME, PASSWORD, polling_interval=POLLING_INTERVAL, hide_secrets=False)
    # Query the API and populate the controllers
    await bridge.initialize()
    # Turn on the light that matches id="84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6"
    await conn.lights.turn_off("84338ebe-7ddf-4bfa-9753-3ee8cdcc8da6")


Troubleshooting
===============

* Device shows incorrect model

  * Afero IoT does not always report all the pertinent information through the API.
    To resolve this, open a PR to ``src/aioafero/device.py`` and update the dataclass
    ``AferoDevice.__post_init__`` function to correctly identify the device.

* Afero IoT is slow to update

  * The API rate-limits request. If other things are hitting the API (such as the phone app
    or Home Assistant), you may need to stop using one to ensure a better connection.
