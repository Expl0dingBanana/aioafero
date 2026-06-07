API reference
=============

Module docs are generated from source on each build. Start with **All modules** below.

.. toctree::
   :maxdepth: 2

   All modules <../api/modules>

Core entry points
-----------------

* :mod:`aioafero.v1` — ``AferoBridgeV1``, ``AferoAuth`` (:doc:`../user/auth` and :doc:`../user/bridge`)
* :mod:`aioafero.device` — raw ``AferoDevice`` parsing and device typing
* :mod:`aioafero.errors` — exception hierarchy
* :mod:`aioafero.types` — ``TemperatureUnit``, ``EventType``

Controllers and models
----------------------

* :mod:`aioafero.v1.controllers` — device-type controllers (package)
* :mod:`aioafero.v1.models` — state models and feature types (package)

Utilities
---------

* :mod:`aioafero.anonymize_data` — redact device payloads for bug reports
* :mod:`aioafero.util` — shared helpers

.. note::

   ``ClimateController`` in ``aioafero.v1.controllers.climate`` is a base class for
   thermostats and portable ACs; it is not registered directly on the bridge.
