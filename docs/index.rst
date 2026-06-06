========
aioafero
========

Async Python library for the Afero / Hubspace cloud API.

This package enables async access to Hubspace (Afero cloud) accounts. Credential login
lives in :doc:`user/auth`; runtime access uses ``AferoBridgeV1`` with a refresh token.

The library is **library-only** — Home Assistant integrations such as
`Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_ consume
it from PyPI.

**Documentation:** https://aioafero.readthedocs.io/

Quick links
===========

.. toctree::
   :maxdepth: 2
   :caption: User guide

   user/overview
   user/installation
   user/auth
   user/bridge
   user/controllers/index
   user/examples
   user/troubleshooting
   user/device_splitting

.. toctree::
   :maxdepth: 2
   :caption: Contributing

   contributing
   testing

.. toctree::
   :maxdepth: 2
   :caption: API reference

   reference/index

.. toctree::
   :maxdepth: 1
   :caption: Project info

   changelog
   license
   authors

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
