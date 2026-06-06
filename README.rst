========
aioafero
========

Async Python library for the Hubspace / Afero IoT cloud API. Discover devices,
poll state, and send commands through typed controllers on ``AferoBridgeV1``.

**Documentation:** https://aioafero.readthedocs.io/

.. image:: https://github.com/Expl0dingBanana/aioafero/actions/workflows/cicd.yaml/badge.svg?branch=main
   :target: https://github.com/Expl0dingBanana/aioafero/actions/workflows/cicd.yaml

.. image:: https://codecov.io/github/Expl0dingBanana/aioafero/graph/badge.svg?token=NP2RE4I4XK
   :target: https://codecov.io/github/Expl0dingBanana/aioafero

Installation
============

.. code-block:: bash

   pip install aioafero

For Home Assistant, use the `Hubspace integration <https://github.com/jdeath/Hubspace-Homeassistant>`_,
which installs this library from PyPI.

Quick start
===========

Examples assume an asyncio REPL (``python -m asyncio``).

.. code-block:: python

   from aioafero import v1

   bridge = v1.AferoBridgeV1("user@example.com", "password")
   await bridge.initialize()
   await bridge.async_block_until_done()

   light = bridge.lights.get_device("<device_id>")
   print(light.on)

   await bridge.lights.turn_on("<device_id>")
   await bridge.close()

See the `user guide <https://aioafero.readthedocs.io/en/latest/user/overview.html>`_ for
architecture, configuration, controllers, subscribe callbacks, and troubleshooting.

Contributing
============

Bug reports and pull requests are welcome on
`GitHub <https://github.com/Expl0dingBanana/aioafero/issues>`_.
See `CONTRIBUTING.md <https://github.com/Expl0dingBanana/aioafero/blob/main/CONTRIBUTING.md>`_
and the `contributing docs <https://aioafero.readthedocs.io/en/latest/contributing.html>`_.
