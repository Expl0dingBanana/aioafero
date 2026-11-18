Blinds
======

Roller shades behind a blinds gateway (for example Home Decorators Collection
smart roller shades). Each shade is its own ``blinds-zone`` device; the gateway
is a parent device on ``bridge.devices``.

``position`` runs from ``0`` (fully closed) to ``100`` (fully open). Shades move
in fixed steps (25 on Home Decorators Collection shades), so
:meth:`~aioafero.v1.controllers.blinds.BlindsController.set_state` snaps the
requested position to the nearest step.

To set a top or bottom limit: call ``start_limit_setting``, move the shade with
``move`` (``fine=True`` for small steps), then call ``confirm_limit``.

.. autoclass:: aioafero.v1.controllers.blinds.BlindsController
   :members:
   :show-inheritance:
   :inherited-members: get_device, subscribe, items
   :no-index:
