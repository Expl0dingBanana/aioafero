.. _mitm-install:

First-time install
------------------

.. _mitm-install-overview:

Overview
~~~~~~~~

.. mermaid::

   flowchart LR
      emu[Android emulator<br/>Windows SDK]
      mitm[mitmweb Docker<br/>WSL :8081/:51820]
      cloud[Afero cloud<br/>api2.afero…]
      emu -->|WireGuard<br/>10.0.2.2:51820| mitm
      mitm -->|HTTPS| cloud

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Where
     - Install
   * - **WSL**
     - Docker Desktop integration; mitmweb; :file:`scripts/adb.sh` (:ref:`mitm-adb-wsl`); daily scripts
   * - **Windows**
     - JDK, Android SDK CLI (includes ``adb.exe``); ``emulator.exe`` (boot the AVD)

Use a throwaway emulator — captures include ``refresh_token`` values.

.. _mitm-install-wsl:

WSL — Docker and mitmweb
~~~~~~~~~~~~~~~~~~~~~~~~

Requires **Docker Desktop** with WSL integration enabled.

From the aioafero repo root in WSL:

.. code-block:: bash

   ./scripts/mitmweb.sh up

Wraps :file:`docker/mitmweb/compose.yaml` (``down``, ``logs``, and ``ca-path`` subcommands
are available too).

* **Web UI:** http://127.0.0.1:8081/?token=aioafero
* **WireGuard:** UDP ``51820/udp`` (``/udp`` mapping is required)
* **State:** ``~/.mitmproxy/`` bind-mounted into the container (see :ref:`mitm-troubleshooting`
  if host and container files diverge after a container restart)

First ``up`` creates the mitmproxy CA and WireGuard keys. Copy client keys from mitmweb
→ **WireGuard** tab into :file:`docker/mitmweb/emulator-wireguard.conf` (see
:ref:`wireguard-emulator`).

.. _mitm-adb-wsl:

WSL — adb to the Windows emulator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The emulator runs on Windows and registers with **Windows** ``adb.exe`` (installed with
:ref:`android-sdk-manual-zip` under ``%LOCALAPPDATA%\\Android\\platform-tools``). Do
**not** install ``adb`` from ``apt`` in WSL — that starts a separate Linux server and
will not list the emulator.

Run adb **from WSL** via :file:`scripts/adb.sh` so commands share repo paths with
mitmweb (``~/.mitmproxy``, ``docker/mitmweb/``, etc.). The script wraps Windows
``adb.exe``.

One-time WSL packages (for :file:`scripts/inject-mitm-ca.sh` only — not for ``adb`` itself):

.. code-block:: bash

   sudo apt install openssl

Verify after the Windows SDK and emulator steps (:ref:`mitm-install-windows`):

.. code-block:: bash

   ./scripts/adb.sh devices

Expect ``emulator-5554   device`` (or similar) with the emulator home screen up.

**Optional** — shorter commands in every shell (``~/.bashrc``):

.. code-block:: bash

   export ADB="/mnt/c/Users/<you>/AppData/Local/Android/platform-tools/adb.exe"
   alias adb="$ADB"

If :file:`scripts/adb.sh devices` is empty while the emulator UI is up, on Windows:
``adb kill-server`` then ``adb start-server``, then retry ``./scripts/adb.sh devices``.

.. _mitm-install-windows:

Windows — host tools, SDK, and emulator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SDK setup runs on **Windows** (cmd or PowerShell) and installs ``adb.exe``. Daily adb
from **WSL** uses :file:`scripts/adb.sh` — :ref:`mitm-adb-wsl`.

.. _windows-package-managers:

Host packages (winget)
^^^^^^^^^^^^^^^^^^^^^^

Run from an elevated PowerShell; reopen the shell after installing.

.. code-block:: powershell

   winget install -e --id Docker.DockerDesktop
   winget install -e --id Microsoft.OpenJDK.17
   winget install -e --id ShiningLight.OpenSSL.Light

.. list-table::
   :header-rows: 1
   :widths: 22 28 50

   * - Tool
     - winget id
     - Notes
   * - Docker Desktop
     - ``Docker.DockerDesktop``
     - Enable WSL integration in Settings
   * - JDK 17
     - ``Microsoft.OpenJDK.17``
     - Required for ``sdkmanager``
   * - OpenSSL
     - ``ShiningLight.OpenSSL.Light``
     - Optional on Windows; WSL ``openssl`` is used by :file:`scripts/inject-mitm-ca.sh`
   * - Android SDK CLI
     - —
     - Manual zip below — **not** winget ``Google.AndroidCLI``
   * - Android Studio
     - ``Google.AndroidStudio``
     - Optional GUI

Chocolatey alternatives: ``docker-desktop``, ``Temurin17``, ``openssl.light``.

.. _android-sdk-manual-zip:

Android command-line tools (manual zip)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download **Command line tools only** for Windows from
`developer.android.com/studio#command-line-tools-only
<https://developer.android.com/studio#command-line-tools-only>`_.

SDK root: ``%LOCALAPPDATA%\Android``. Expected layout:

.. code-block:: text

   %LOCALAPPDATA%\Android\
     cmdline-tools\latest\bin\sdkmanager.bat
     platform-tools\adb.exe
     emulator\emulator.exe
     system-images\…

**One-time setup (PowerShell):**

.. code-block:: powershell

   $SDK = "$env:LOCALAPPDATA\Android"
   $env:ANDROID_HOME = $SDK
   $env:ANDROID_SDK_ROOT = $SDK
   New-Item -ItemType Directory -Force -Path "$SDK\cmdline-tools\latest" | Out-Null

   cd $env:TEMP
   curl.exe -LO https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip
   tar -xf commandlinetools-win-11076708_latest.zip
   Copy-Item -Recurse -Force cmdline-tools\* "$SDK\cmdline-tools\latest\"

   sdkmanager --sdk_root=$SDK --licenses
   sdkmanager --sdk_root=$SDK `
     "platform-tools" `
     "emulator" `
     "platforms;android-35" `
     "system-images;android-35;google_apis;x86_64"

   Test-Path "$SDK\system-images\android-35\google_apis\x86_64\system.img"

.. _windows-path:

Add Android tools to User Path (once)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Win → **environment variables** → **User variables**.
2. **New:** ``ANDROID_HOME`` and ``ANDROID_SDK_ROOT`` → ``%LOCALAPPDATA%\Android``
3. Edit **Path** → add:

   .. code-block:: text

      %LOCALAPPDATA%\Android\platform-tools
      %LOCALAPPDATA%\Android\emulator
      %LOCALAPPDATA%\Android\cmdline-tools\latest\bin

4. **OK**, then open a **new** PowerShell window.

Verify in PowerShell: ``emulator -list-avds``, ``sdkmanager --version``, ``adb version``.
After :ref:`mitm-adb-wsl`, verify from WSL: ``./scripts/adb.sh devices``.

Optional PowerShell one-liner to set the same values:
:ref:`windows-path-script` in the install troubleshooting section.

.. _android-sdk-cli:

Create the AVD (once)
^^^^^^^^^^^^^^^^^^^^^

Use a **Google APIs** image (not Google Play) so ``adb root`` works with
``-writable-system``.

.. code-block:: powershell

   $SDK = "$env:LOCALAPPDATA\Android"
   $env:ANDROID_HOME = $SDK
   $env:ANDROID_SDK_ROOT = $SDK

   avdmanager delete avd -n pixel_api35   # ignore if missing
   avdmanager create avd `
     -n pixel_api35 `
     -k "system-images;android-35;google_apis;x86_64" `
     -d pixel_7

If ``pixel_7`` is unavailable, omit ``-d`` or pick a device from ``avdmanager list device``.

Boot once to confirm (Windows): ``emulator -avd pixel_api35 -writable-system -no-snapshot``.
Then verify root from WSL (:ref:`rooted-emulator`).

.. _rooted-emulator:

Root and writable system
^^^^^^^^^^^^^^^^^^^^^^^^

From WSL (emulator running on Windows):

.. code-block:: bash

   ./scripts/adb.sh wait-for-device
   ./scripts/adb.sh root
   ./scripts/adb.sh remount
   ./scripts/adb.sh shell id -u    # expect 0

If ``adb root`` fails on a **Google Play** image, recreate the AVD with ``google_apis``
or use Magisk (`rootAVD guide
<https://brutsecurity.medium.com/how-to-root-your-android-emulator-hack-yourself-with-burp-suite-manually-like-a-legend-ef4fbe28ceab>`_).

Daily sessions use :file:`scripts/inject-mitm-ca.sh` instead of running these commands
by hand (:ref:`ca-injection`).

WireGuard and Hubspace APKs
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Not on winget — sideload once:

* **WireGuard:** download from https://download.wireguard.com/android-client/ then
  from WSL: ``./scripts/adb.sh install /mnt/c/path/to/com.wireguard.android-*.apk``
* **Hubspace:** :ref:`hubspace-apk` (``.apkm`` bundle via APKMirror Installer)

Emulator keyboard (once)
^^^^^^^^^^^^^^^^^^^^^^^^

If the PC keyboard does not type into the emulator:

1. Extended controls (⋯) → **Settings → General** → **Send keyboard shortcuts to** →
   **Virtual device**
2. In ``%USERPROFILE%\.android\avd\<name>.avd\config.ini`` (emulator stopped):

   .. code-block:: ini

      hw.keyboard = yes
      hw.mainKeys = no

When install is complete, use :ref:`mitm-daily-checklist` for each capture session.
WireGuard one-time setup: :ref:`wireguard-emulator` in :doc:`daily_use`.

.. _hubspace-apk:

Hubspace (APKM via APKMirror Installer)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Google APIs images have no Play Store. Hubspace on APKMirror is usually an ``.apkm``
bundle — plain ``adb install`` fails with ``INSTALL_FAILED_MISSING_SPLIT``.

**One-time — APKMirror Installer**

1. Download `APKMirror Installer (Official)
   <https://www.apkmirror.com/apk/apkmirror/apkmirror-installer-official/>`_ (the **APK**
   variant, not APKM).
2. From WSL: ``./scripts/adb.sh install /mnt/c/path/to/apkmirror-installer.apk``

**Each Hubspace update**

1. Download from `APKMirror — Hubspace
   <https://www.apkmirror.com/apk/afero/hubspace/>`_ (``.apkm``).
2. Push (destination must include the filename):

   .. code-block:: bash

      ./scripts/adb.sh push /mnt/c/path/to/hubspace.apkm /sdcard/Download/hubspace.apkm

3. On the emulator: **APKMirror Installer** → select the ``.apkm`` → **Install app**.

If install fails: ``./scripts/adb.sh uninstall io.afero.partner.hubspace`` and retry.

.. _mitm-install-troubleshooting:

Install troubleshooting
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Symptom
     - Fix
   * - ``sdkmanager`` / ``emulator`` not found
     - :ref:`windows-path`; new PowerShell window; ``Test-Path`` on ``adb.exe``
   * - ``adb devices`` empty in WSL (bare ``adb``)
     - Do not use ``apt`` adb — :file:`scripts/adb.sh devices` (:ref:`mitm-adb-wsl`); Windows: ``adb kill-server`` then ``adb start-server``
   * - ``scripts/adb.sh``: adb.exe not found
     - Finish :ref:`android-sdk-manual-zip` / :ref:`windows-path`; check ``Test-Path`` on ``adb.exe``
   * - ``Could not determine SDK root``
     - ``sdkmanager --sdk_root=%LOCALAPPDATA%\Android …``
   * - ``--sdk_root`` invalid for ``avdmanager``
     - Set ``ANDROID_HOME`` / ``ANDROID_SDK_ROOT`` only; no ``--sdk_root`` on ``avdmanager``
   * - **Cannot find AVD system path** / ``Sdk\Sdk\system-images``
     - ``avdmanager delete avd -n pixel_api35``; unify SDK root; recreate AVD
   * - Files under ``Android\Sdk\`` instead of ``Android\``
     - Move ``emulator``, ``platform-tools``, ``platforms``, ``system-images`` up one level
   * - ``where sdkmanager`` → 0-byte stub in ``C:\Users\…\``
     - ``del C:\Users\<user>\sdkmanager``; use manual zip
   * - winget ``Google.AndroidCLI`` installed wrong tool
     - Skip it; use :ref:`android-sdk-manual-zip` (classic ``sdkmanager``)
   * - ``tar: Failed to open 'commandlinetools-win-*_latest.zip'``
     - Use exact filename ``commandlinetools-win-11076708_latest.zip`` (Windows ``tar``)
   * - ``JAVA_HOME is not set``
     - Install JDK 17; reopen shell
   * - ``openssl`` not found (inject script)
     - ``sudo apt install openssl`` in WSL
   * - ``adb install`` ``INSTALL_FAILED_MISSING_SPLIT``
     - :ref:`hubspace-apk` — use APKMirror Installer
   * - Emulator very slow
     - ``emulator -accel-check``; enable WHPX / Hyper-V

.. _windows-path-script:

Optional — set User Path from PowerShell
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: powershell

   $SDK = "$env:LOCALAPPDATA\Android"
   [Environment]::SetEnvironmentVariable("ANDROID_HOME", $SDK, "User")
   [Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $SDK, "User")
   $paths = @(
     "$SDK\platform-tools",
     "$SDK\emulator",
     "$SDK\cmdline-tools\latest\bin"
   )
   $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
   foreach ($p in $paths) {
     if ($userPath -notlike "*$p*") { $userPath = "$userPath;$p" }
   }
   [Environment]::SetEnvironmentVariable("Path", $userPath.TrimStart(";"), "User")

.. _windows-clean-install:

Clean install from scratch (Windows cmd)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If paths are mixed (``Android\Sdk\Sdk\…``, stale AVDs). **Close the emulator first.**

.. code-block:: doscon

   taskkill /IM emulator.exe /F 2>nul
   taskkill /IM qemu-system-x86_64.exe /F 2>nul
   rmdir /s /q "%LOCALAPPDATA%\Android"
   rmdir /s /q "%USERPROFILE%\.android"
   del "%USERPROFILE%\sdkmanager" 2>nul
   rmdir /s /q "%USERPROFILE%\AppData\AndroidCLI" 2>nul

Remove User ``ANDROID_HOME`` / ``ANDROID_SDK_ROOT`` / Android ``Path`` entries if set.
Open a new shell, then follow :ref:`android-sdk-manual-zip` through :ref:`android-sdk-cli`.
