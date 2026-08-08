Lights
======

``bridge.lights`` owns ``Light`` models for on/off, dimming, color, color temperature,
and effects. Split main/trim zones appear as separate ``Light`` resources (see
:doc:`../device_splitting`).

Night-light color-mode
----------------------

Some fixtures (e.g. Hampton Bay Penrose) expose ``night-light`` as a ``color-mode``
value with the ``no-brightness`` category hint. That is distinct from any nightlight
*sequence* effect.

* ``"night-light" in Light.color_modes`` — capability check
* ``Light.color_mode_hints`` / ``color_mode_has_hint()`` — API category hints
* ``set_state(..., color_mode="night-light")`` — omit brightness; select mode before
  power when turning on from off (aborting if that PUT fails); never send a
  color-mode change with turn-off. Leave night-light with a separate
  ``set_state(..., color_mode=...)`` while on, or ``set_state(on=False)``.


Dual-channel RGB+WW fixtures
----------------------------

Fixtures with separate ``color`` and ``white`` brightness channels (RGBCW strips,
flushmounts, and similar) always stay one combined ``Light``. Capability is detected
from the device; aioafero does not split color/white into separate light resources.
Integrations that want dual entities create them themselves.

Combined fixtures expose:

* ``Light.channels`` — map of instance name → ``LightChannel`` (brightness + on)
* ``Light.is_dual_channel``
* ``Light.channel_brightness(name)`` / ``Light.channel_on(name)``
* ``Light.dimming`` — overall brightness (usually ``primary``)

Color/white toggles are tracked on ``Light.channels`` only — they are not cloned
into Switch resources.

See ``is_dual_channel_rgb_fixture``. True multi-zone fixtures (main/trim) still
split into separate lights; see ``get_split_instances``.

**Color modes:** Afero exposes ``color-mode`` values such as ``color``,
``white``, ``sequence``, and (on these fixtures) ``mixed``.
``mixed`` is a single color-mode controller that keeps both the RGB and white
drivers active together — not a separate HA entity, and not the same idea as
``is_dual_channel`` (which describes the hardware: independent color/white
brightness and toggles).

**Writing:** ``set_state`` routes dimming by command context on combined fixtures
(RGB → ``color``, CCT → ``white``). Pass ``channel="color"|"white"`` to toggle that
channel (instead of primary power) and to route brightness to that channel when
``color_mode`` is omitted. Turning a channel **off** moves ``color-mode`` to the
remaining channel when one is still on (so leaving ``mixed`` becomes exclusive
``color`` or ``white``). Exclusive ``color`` / ``white`` color-mode requests
resolve to ``mixed`` when another channel is already on (``LightChannel.on is True``),
so the PUT does not shut off the other driver. Unknown ``channel`` values are ignored
(with a log) rather than falling through to primary power.

Controller
----------

.. autoclass:: aioafero.v1.controllers.light.LightController
   :members:
   :show-inheritance:
   :inherited-members: get_device, subscribe, items
   :no-index:

Model
-----

.. autoclass:: aioafero.v1.models.light.LightChannel
   :members:
   :no-index:

.. autoclass:: aioafero.v1.models.light.Light
   :members:
   :show-inheritance:
   :no-index:
