=========
Changelog
=========

Version 3.3.5
=============

 * Fix an issue where auth could produce a UHE

Version 3.3.4
=============

 * Fix an issue in thermostats where they incorrectly stated support for auto

Version 3.3.3
=============

 * Fix an issue in thermostats where the target_temperature could cause a UHE

Version 3.3.2
=============

 * Fix an issue in thermostats where the target_temperature always
   returned celsius

Version 3.3.1
=============

 * Enable switch for Portable AC
 * Fix an issue where setting temps did not follow the step
 * Fix an issue where portable AC's timer did not turn it on

Version 3.3.0
=============

 * Add Portable AC device class

Version 3.2.2
=============

 * Solidify bridge API so Home Assistant tests do not
   call any private methods

Version 3.2.1
=============

 * Fix a regression around battery sensor not showing

Version 3.2.0
=============

 * Fully implement exhaust fans

Version 3.1.1
=============

 * Add a secret that was missing

Version 3.1.0
=============

 * Hide secrets in logs by default

Version 3.0.2
=============

 * Fix an issue where thermostats would set the incorrect target temperature
   if the mode changed at the same time

Version 3.0.1
=============

 * Fix an issue where thermostats would state invalid modes

Version 3.0.0
=============

 * API Break: Binary Sensors / Sensors may no longer be included under the Device Resource
 * Binary Sensors / Sensors are now included with the most logical parent

Version 2.0.1
=============

 * Add support for thermostats

Version 2.0.1
=============

 * Add support for determining if "white" is a supported option for lights

Version 2.0.0
=============

 * Migration from aiohubspace to aioafero to support the Aefro IoT Cloud

Version 1.2.0
=============

 * Enable auth to re-use a previously generated token

Version 1.1.3
=============

 * Fix an issue where devices could be properly identified

Version 1.1.2
=============

 * Fix an issue where water valves were showing as fans

Version 1.1.1
=============

 * Fix an issue where 500's could stop polling

Version 1.1.0
=============

 * Added an event type for invalid auth during token refresh
 * Added a check to ensure the token is valid during refresh time. If invalid,
   the event invalid_auth is emitted.

Version 1.0.4
=============

 * Add additional logging around issues when querying Hubspace API


Version 1.0.3
=============

 * Fixed an issue where a new device could be generated prior to an element


Version 1.0.2
=============

 * Fixed an issue where an updated sensor could use an incorrect value


Version 1.0.1
=============

 * Fixed an issue where passwords could be logged to debug logs


Version 1.0.0
=============

 * Solidify API
 * Fix an issue where the loop would break during collection
 * Increase code coverage


Version 0.7.0
=============

 * Add support for glass-doors


Version 0.6.4
=============

 * Fix an issue where locks were not being managed by LockController
 * Fix an issue with Fans not correctly setting presets
 * Less greedy updates - Only forward updates if something has changed
   on the resource
 * Create additional unit tests to ensure functionality


Version 0.6.3
=============

 * Fix an issue with Binary sensors to ensure the state is obvious


Version 0.6.2
=============

 * Fix an issue with fan's preset not correctly identifying its state


Version 0.6.1
=============

 * Fix an issue with binary sensors to ensure they return True / False


Version 0.6.0
=============

 * Add the ability to send raw states to Hubspace and have the tracked device update


Version 0.5.1
=============

 * Fixed an issue where the account ID wouldnt be set during a partial initialization


Version 0.5.0
=============

 * Only emit updates to subscribers if values have changed
 * Fixed an issue where the logger was always in debug


Version 0.4.1
=============

 * Adjusted logic for how HubspaceDevice modified models
 * Fixed an issue around Device initialization


Version 0.4.0
=============

 * Added tracking for BLE and MAC addresses
 * Added binary sensors


Version 0.3.7
=============

 * Fixed an issue around subscribers with deletion


Version 0.3.6
=============

 * Fixed an issue around switches not properly subscribing to updates
 * Fixed an issue where Hubspace could return a session reauth token when preparing a new session
 * Added models for HPSA11CWB and HPDA110NWBP


Version 0.3.0
=============

 * Fixed an issue around subscribers with deletion



Version 0.2
===========

 * Added support for Binary Sensors
 * Fixed an issue where a dimmer switch could not be dimmed


Version 0.2
===========

 * Added support for Sensors


Version 0.1
===========

 * Initial implementation
 * Rename from hubspace_async to aiohubspace
 * Utilize the concept of a bridge instead of raw connection
