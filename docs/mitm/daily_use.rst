.. _mitm-daily:

Daily use
---------

Assumes :ref:`mitm-install-wsl` and :ref:`mitm-install-windows` are done. Replace
``pixel_api35`` with your AVD name (``emulator -list-avds`` on Windows).

Use :file:`scripts/adb.sh` for adb from WSL (:ref:`mitm-adb-wsl`). All commands below
run from the aioafero repo checkout in WSL unless noted.

.. _mitm-daily-checklist:

Every session
~~~~~~~~~~~~~

1. WSL — ``./scripts/mitmweb.sh up`` (:ref:`mitm-daily-mitmweb`)
2. Windows — boot the emulator with ``-writable-system`` (:ref:`mitm-daily-emulator`)
3. WSL — ``./scripts/inject-mitm-ca.sh`` (:ref:`ca-injection`; again after every emulator reboot)
4. WSL — push WireGuard config if needed (``./scripts/adb.sh push …``); emulator — turn the tunnel on (:ref:`wireguard-emulator`)
5. Emulator — open Hubspace, sign in, trigger a device action (:ref:`target-app`)
6. Browser (WSL or Windows) — http://127.0.0.1:8081/?token=aioafero

.. mermaid::

   flowchart TD
      mitm[WSL: mitmweb up]
      emuWin[Windows: emulator -writable-system]
      inject[WSL: inject-mitm-ca.sh]
      wg[WSL: adb.sh push + WireGuard on]
      app[Emulator: Hubspace traffic]
      ui[Browser: mitmweb UI]
      mitm --> emuWin --> inject --> wg --> app --> ui

.. _mitm-daily-mitmweb:

Start mitmweb (WSL)
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   ./scripts/mitmweb.sh up
   # UI: http://127.0.0.1:8081/?token=aioafero

Stop: ``./scripts/mitmweb.sh down``

Logs: ``./scripts/mitmweb.sh logs``

Compose file: :file:`docker/mitmweb/compose.yaml`. State lives in WSL ``~/.mitmproxy/``
(CA cert + WireGuard keys). ``./scripts/mitmweb.sh ca-path`` prints the cert path.

.. _mitm-daily-emulator:

Boot the emulator (Windows)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: doscon

   emulator -avd pixel_api35 -writable-system -no-snapshot

Wait for the home screen, then :ref:`ca-injection` from WSL.

.. _ca-injection:

Inject the mitmproxy CA (WSL)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Afero apps pin TLS. Install the mitmproxy CA as a **system trust anchor** and bind it
into the APEX conscrypt store (zygote + running apps). **Repeat after every emulator
reboot** — APEX bind mounts do not persist.

.. code-block:: bash

   ./scripts/inject-mitm-ca.sh

Waits for the emulator (90s timeout), then ``adb root`` → ``adb remount``, pushes
``~/.mitmproxy/mitmproxy-ca-cert.pem`` (or ``MITMPROXY_CERT``), runs
:file:`scripts/mitm-ca-inject-device.sh` on the device, force-stops Hubspace, and opens
http://mitm.it in Chrome (falls back to the default browser).

http://mitm.it only loads when WireGuard is **on** and connected — traffic must route through
mitmproxy (``DNS = 10.0.0.53`` requires an active tunnel). APEX injection already installs
the mitmproxy CA as a system trust anchor; mitm.it is a **tunnel verification** step, not a
user cert install. If the page fails, enable WireGuard (:ref:`wireguard-emulator`) and open
http://mitm.it again.

Override the cert path: ``MITMPROXY_CERT=/path/to/mitmproxy-ca-cert.pem ./scripts/inject-mitm-ca.sh``

Manual on-device steps: :file:`scripts/mitm-ca-inject-device.sh`.

.. _wireguard-emulator:

Connect WireGuard (WSL + emulator)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One-time setup (usually during :doc:`install`): create
``docker/mitmweb/emulator-wireguard.conf`` from mitmweb → **WireGuard** tab — see
**Endpoint** and **Config file** below. Each session: import is already on the device
unless you wiped data; toggle the tunnel **On**.

Push the config from WSL (skip if already imported):

.. code-block:: bash

   ./scripts/adb.sh push docker/mitmweb/emulator-wireguard.conf /sdcard/Download/aioafero-mitm.conf

Emulator: WireGuard → **+** → **Import from file or archive** → ``Download/aioafero-mitm.conf`` → toggle **On**.

All emulator traffic routes through mitmproxy; no per-app HTTP proxy is needed.

**Endpoint:** mitmweb auto-detects an address for simple LAN setups; for WSL Docker +
a Windows emulator that value is usually wrong (``127.0.0.1`` or a Docker bridge IP). Use
an address the **emulator** can reach on UDP 51820 — for an emulator on the same Windows
host as Docker, that is ``10.0.2.2`` (Google's fixed emulator→host alias, not your LAN
IP). Allow UDP **51820** through the Windows firewall if the tunnel will not connect.

**Config file:** copy :file:`docker/mitmweb/emulator-wireguard.conf.example` to
``emulator-wireguard.conf``, fill ``PrivateKey`` and ``[Peer] PublicKey`` from mitmweb,
set ``Endpoint`` (see above). Gitignored — contains a private key.

Keys and the mitmproxy CA persist in ``~/.mitmproxy/`` across ``./scripts/mitmweb.sh down``
/ ``up`` — no re-import on a normal restart. Re-import or re-run inject only if the tunnel
fails or host/container files diverge (:ref:`mitm-troubleshooting`).

.. _target-app:

Use Hubspace and capture traffic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

App package: ``io.afero.partner.hubspace``. Sign in and toggle something.

Filter in mitmweb:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Host / path
     - Purpose
   * - ``accounts.hubspaceconnect.com``
     - OpenID login / token exchange
   * - ``api2.afero.net``
     - REST API
   * - ``semantics2.afero.net``
     - Device state / semantics
   * - ``metadevices``, ``state``, ``token``
     - Common path filters

.. _capture-export:

Capture and export
~~~~~~~~~~~~~~~~~~

In mitmweb:

1. Search flows by host or path.
2. Select a flow → **Request** / **Response** for JSON bodies.
3. **File → Save** (HAR) or copy bodies for test fixtures.

Before committing fixtures: redact tokens, IDs, and email; keep payloads small. HAR files
contain live credentials — do not attach them to public issues.

.. _mitm-troubleshooting:

Troubleshooting
~~~~~~~~~~~~~~~

Session and capture issues below. SDK, AVD, adb setup: :ref:`mitm-install-troubleshooting`
and :ref:`mitm-adb-wsl`.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Symptom
     - Fix
   * - No flows in mitmweb
     - WireGuard on; mitmweb running; trigger traffic in Hubspace; filter ``afero.net``. If the tunnel is down, see the WireGuard row below
   * - TLS errors in app
     - Re-run ``./scripts/inject-mitm-ca.sh`` (:ref:`ca-injection`)
   * - Flows stop after reboot
     - Re-run ``./scripts/inject-mitm-ca.sh``; reconnect WireGuard
   * - No device / inject times out
     - ``./scripts/adb.sh devices``; emulator up; :ref:`mitm-adb-wsl`
   * - Login works, no API calls
     - Filter ``afero.net``; trigger a device action in the app
   * - WireGuard tunnel fails (``rx`` **0 B**, ``InvalidAeadTag``, ``mitm.it`` DNS)
     - ``Endpoint = 10.0.2.2:51820`` (not ``127.0.0.1`` or the Docker bridge IP from mitmweb); allow Windows firewall UDP **51820**; tunnel **on**. Handshake still failing: re-import from mitmweb → **WireGuard** tab and compare interface/peer **public keys** with the emulator app. ``mitm.it`` only verifies the tunnel — APEX injection does not need it. See ``~/.mitmproxy`` sync below; re-run inject if the CA drifted
   * - ``~/.mitmproxy`` out of sync (WSL host vs container)
     - Compare ``md5sum ~/.mitmproxy/wireguard.conf`` with ``docker exec aioafero-mitmweb md5sum /home/mitmproxy/.mitmproxy/wireguard.conf`` (repeat for ``mitmproxy-ca-cert.pem``). If hashes differ: ``./scripts/mitmweb.sh down`` then ``up``, re-import WireGuard, re-run inject
   * - mitmweb **403**
     - Open http://127.0.0.1:8081/?token=aioafero
   * - ``adb root`` unavailable
     - **Google APIs** image (not Google Play); ``-writable-system`` — :ref:`mitm-install-windows`
