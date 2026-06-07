.. _mitm_testbed:

MITM capture setup
==================

Capture Hubspace HTTPS traffic (the same endpoints ``aioafero`` uses) with mitmweb in
WireGuard mode, a rooted Android emulator, and ``adb`` from WSL. Based on
`Hubspace-Homeassistant #198
<https://github.com/jdeath/Hubspace-Homeassistant/issues/198>`_; works around Android
API 35 cert pinning.

mitmweb and :file:`scripts/adb.sh` run in **WSL** (Windows ``adb.exe`` under the hood). The
**emulator** runs on Windows — :ref:`mitm-adb-wsl`.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Page
     - When to use it
   * - :doc:`install`
     - One-time setup — WSL Docker + openssl; Windows SDK (adb) + emulator; sideload WireGuard and Hubspace
   * - :doc:`daily_use`
     - Session workflow — WSL mitmweb + adb.sh; Windows emulator boot


.. toctree::
   :maxdepth: 1
   :titlesonly:
   :hidden:

   install
   daily_use

.. seealso::

   :doc:`../contributing`

   :doc:`../testing`

   `mitmproxy WireGuard mode <https://docs.mitmproxy.org/stable/concepts-modes/#wireguard>`_
