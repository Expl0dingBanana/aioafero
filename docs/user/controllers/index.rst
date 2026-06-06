Controllers
===========

Each attribute on ``AferoBridgeV1`` is an instance of one of these controllers. Detail
pages are generated from source with autodoc.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Bridge attribute
     - Controller class
   * - ``bridge.devices``
     - :doc:`devices`
   * - ``bridge.exhaust_fans``
     - :doc:`exhaust_fans`
   * - ``bridge.fans``
     - :doc:`fans`
   * - ``bridge.lights``
     - :doc:`lights`
   * - ``bridge.locks``
     - :doc:`locks`
   * - ``bridge.portable_acs``
     - :doc:`portable_acs`
   * - ``bridge.switches``
     - :doc:`switches`
   * - ``bridge.thermostats``
     - :doc:`thermostats`
   * - ``bridge.security_systems``
     - :doc:`security_systems`
   * - ``bridge.security_systems_keypads``
     - :doc:`security_systems_keypads`
   * - ``bridge.security_systems_sensors``
     - :doc:`security_systems_sensors`
   * - ``bridge.valves``
     - :doc:`valves`

.. toctree::
   :maxdepth: 1

   devices
   exhaust_fans
   fans
   lights
   locks
   portable_acs
   switches
   thermostats
   security_systems
   security_systems_keypads
   security_systems_sensors
   valves

.. seealso::

   :class:`~aioafero.v1.controllers.base.BaseResourcesController` — shared base class.

   :class:`~aioafero.v1.controllers.climate.ClimateController` — base for thermostats and
   portable ACs (not registered on the bridge directly).

   :doc:`../device_splitting` — how multi-entity devices are split across controllers.
