Blinds
======

To set a top or bottom limit: call ``start_limit_setting``, move the blinds with
``move`` (``fine=True`` for small steps), then call ``confirm_limit``.

.. autoclass:: aioafero.v1.controllers.blinds.BlindsController
   :members:
   :show-inheritance:
   :inherited-members: get_device, subscribe, items
   :no-index:

Blinds Gateways
===============

.. autoclass:: aioafero.v1.controllers.blinds.BlindsGatewayController
   :members:
   :show-inheritance:
   :inherited-members: get_device, subscribe, items
   :no-index:
