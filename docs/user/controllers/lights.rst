Lights
======

``bridge.lights`` owns ``Light`` models for on/off, dimming, color, color temperature,
and effects. Split main/trim zones appear as separate ``Light`` resources; dual-channel
RGB+WW fixtures stay as one light (see :doc:`../device_splitting`).

Dual-channel fixtures
---------------------

Fixtures with separate ``color`` and ``white`` brightness channels (RGBCW strips,
flushmounts, and similar) expose:

* ``Light.is_dual_channel`` — ``True`` when both channels are present
* ``Light.color_brightness`` / ``Light.white_brightness`` — last known per-channel levels
* ``Light.channel_brightness("color")`` / ``channel_brightness("white")`` — accessors for
  integrations
* ``Light.dimming`` — overall brightness; ``dimming.func_instance`` is usually
  ``"primary"`` and tracks which instance last updated the cached level

**Reading:** Subscribe to ``bridge.lights`` as usual. Use ``color_mode.mode`` together
with the per-channel brightness fields to reflect the active API mode (``color``,
``white``, ``mixed``, etc.).

**Writing:** ``LightController.set_state`` and ``set_brightness`` route dimming PUTs by
command context:

* RGB, effects, or ``color_mode="color"`` / ``"sequence"`` → ``color`` brightness
* CCT, ``color_mode="white"``, or white-only zones → ``white`` brightness
* Brightness-only updates follow the cached ``color_mode`` when no explicit mode is
  passed; ``mixed`` mode uses ``primary`` overall brightness

The outbound ``DimmingFeature.func_instance`` on the PUT selects the API brightness row.

Controller
----------

.. autoclass:: aioafero.v1.controllers.light.LightController
   :members:
   :show-inheritance:
   :inherited-members: get_device, subscribe, items
   :no-index:

Model
-----

.. autoclass:: aioafero.v1.models.light.Light
   :members:
   :show-inheritance:
   :no-index:
