Split devices
=============

Some physical devices expose multiple controllable endpoints (multi-zone lights,
security sensors, portable AC power toggles). aioafero **splits** them into separate
logical devices so integrations can expose one entity per zone.

Not every device with more than one brightness control is split. RGB+WW fixtures such
as flushmounts and RGBCW strips expose separate ``color`` and ``white`` dimming
channels on **one** fixture; those stay a single light (see :ref:`dual-channel-lights`).

How splitting works
-------------------

1. During discovery, a controller's ``DEVICE_SPLIT_CALLBACKS`` transforms one
   ``AferoDevice`` into several clones with synthetic IDs.
2. Each clone gets a unique ``_id`` (for example ``{parent}-light-{instance}``).
3. ``split_identifier`` on the model enables ``StandardMixin`` properties:

   * ``id`` — the synthetic ID (entity identity)
   * ``update_id`` — parent metadevice ID used for API writes
   * ``instance`` — split instance name parsed from the synthetic ID

.. _dual-channel-lights:

Dual-channel RGB+WW lights
--------------------------

Some lights expose separate RGB and warm-white LED drivers on one metadevice. The API
uses distinct brightness ``functionInstance`` values — typically ``color``, ``white``,
and ``primary`` — while color controls (``color-rgb``, ``color-mode``,
``color-temperature``) often share a ``null`` instance across the whole fixture.

These fixtures are **not** split into ``{parent}-light-color`` / ``{parent}-light-white``
clones. Splitting would drop the shared null-instance color states and break RGB/CCT
control.

Detection is generic: a light is treated as dual-channel when it exposes both ``color``
and ``white`` brightness zones (from live states, function definitions, or capabilities).
True multi-zone lights such as main/trim recessed fixtures still split normally because
their zone names are not the ``color``/``white`` pair.

Integrations should expose **one** light entity and use the ``Light`` model helpers
described in :doc:`controllers/lights` for per-channel brightness and mode-aware writes.

Implementing a new split type
-----------------------------

On the **primary controller** (non-split class):

* Register a callback in ``DEVICE_SPLIT_CALLBACKS`` that returns
  ``CallbackResponse(split_devices=[...], remove_original=...)``.

On the **split model**:

* Use a unique synthetic ``_id``, not the parent metadevice ID.
* Set ``split_identifier`` consistently with the ID format.
* Inherit ``StandardMixin`` when the model needs ``update_id`` / ``instance``.

Existing split patterns
-----------------------

* **Lights** — true multi-zone ``light`` instances (for example ``main`` / ``trim``);
  parent may become a Wi-Fi metadata device. Dual-channel RGB+WW fixtures are excluded
  (see :ref:`dual-channel-lights`).
* **Portable ACs** — ``power`` toggle → ``bridge.switches``.
* **Exhaust fans** — toggles, fan, and light instances on one unit.
* **Security systems** — sensors extracted to ``bridge.security_systems_sensors``.

Pollers deduplicate by parent metadevice ID so split entities do not multiply API traffic.
State polls **merge** incoming rows into the cached ``AferoDevice`` by
``functionClass`` / ``functionInstance`` so partial responses do not drop other zones.
See :doc:`bridge`.
