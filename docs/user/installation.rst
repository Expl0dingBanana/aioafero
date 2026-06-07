Installation
============

PyPI
----

.. code-block:: bash

   pip install aioafero

Requires **Python 3.12+**.

From source (development)
-------------------------

.. code-block:: bash

   git clone https://github.com/Expl0dingBanana/aioafero.git
   cd aioafero
   uv sync --extra test

Home Assistant
--------------

Install the `Hubspace integration <https://github.com/jdeath/Hubspace-Homeassistant>`_.
It declares ``aioafero`` as a runtime requirement in its manifest; you do not install
this package separately inside HA.

Next: :doc:`overview`, :doc:`auth`, :doc:`examples`, :doc:`bridge`. Contributors:
:doc:`../contributing`.
