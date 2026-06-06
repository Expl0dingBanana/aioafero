Split devices
=============

Some physical devices expose multiple controllable endpoints (multi-zone lights,
security sensors, portable AC power toggles). aioafero **splits** them into separate
logical devices so integrations can expose one entity per zone.

How splitting works
-------------------

1. During discovery, a controller's ``DEVICE_SPLIT_CALLBACKS`` transforms one
   ``AferoDevice`` into several clones with synthetic IDs.
2. Each clone gets a unique ``_id`` (for example ``{parent}-light-{instance}``).
3. ``split_identifier`` on the model enables ``StandardMixin`` properties:

   * ``id`` — the synthetic ID (entity identity)
   * ``update_id`` — parent metadevice ID used for API writes
   * ``instance`` — split instance name parsed from the synthetic ID

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

* **Lights** — multi-zone ``light`` instances; parent may become a Wi-Fi metadata device.
* **Portable ACs** — ``power`` toggle → ``bridge.switches``.
* **Exhaust fans** — toggles, fan, and light instances on one unit.
* **Security systems** — sensors extracted to ``bridge.security_systems_sensors``.

Pollers deduplicate by parent metadevice ID so split entities do not multiply API traffic.
