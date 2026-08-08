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

Next steps
----------

* :doc:`auth` — log in and persist refresh tokens
* :doc:`examples` — minimal interactive session
* :doc:`overview` — how the bridge and controllers fit together

Contributors: see :doc:`../contributing` for doc layout and how to build the Sphinx site
locally.
