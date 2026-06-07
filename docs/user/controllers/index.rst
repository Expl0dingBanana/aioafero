Controllers
===========

``bridge.lights``, ``bridge.fans``, and so on are controllers — typed models plus action
methods like ``turn_on`` and ``set_state``. Each page below is autodoc from source.
All inherit ``get_device``, ``items``, and ``subscribe`` from
:class:`~aioafero.v1.controllers.base.BaseResourcesController`.

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
   :hidden:

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
