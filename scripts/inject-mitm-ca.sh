#!/usr/bin/env bash
# Inject mitmproxy CA into a rooted Android emulator (APEX / zygote bind mount).
# Run from WSL after the emulator is booted with -writable-system on Windows.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=adb.sh
source "${ROOT}/scripts/adb.sh"

INJECT_SH="${ROOT}/scripts/mitm-ca-inject-device.sh"
HUBSPACE_PKG="io.afero.partner.hubspace"
MITMPROXY_CERT="${MITMPROXY_CERT:-${MITMPROXY_CONFIG_DIR:-${HOME}/.mitmproxy}/mitmproxy-ca-cert.pem}"

setup_windows_adb

if [[ ! -f "${INJECT_SH}" ]]; then
  echo "ERROR: missing ${INJECT_SH}" >&2
  exit 1
fi

if [[ ! -f "${MITMPROXY_CERT}" ]]; then
  echo "ERROR: CA not found at ${MITMPROXY_CERT}" >&2
  echo "Start mitmweb first: ./scripts/mitmweb.sh up" >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl not found in WSL (sudo apt install openssl)" >&2
  exit 1
fi

HASH="$(openssl x509 -inform PEM -subject_hash_old -in "${MITMPROXY_CERT}" | head -1)"
CACERT="${HASH}.0"

wait_for_adb_device() {
  local timeout_secs="${ADB_WAIT_TIMEOUT:-90}"
  local elapsed=0

  echo "Waiting for device (${timeout_secs}s) — ./scripts/adb.sh devices to check..."

  while (( elapsed < timeout_secs )); do
    if adb_has_device; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  echo "ERROR: No device after ${timeout_secs}s. Emulator up? ./scripts/adb.sh devices" >&2
  exit 1
}

wait_for_adb_device

echo "Enabling root adbd..."
"${ADB}" root
sleep 2
wait_for_adb_device

echo "Remounting /system writable..."
"${ADB}" remount

if [[ "$("${ADB}" shell id -u | tr -d '\r')" != "0" ]]; then
  echo "ERROR: adb shell is not root. Use a Google APIs image and -writable-system." >&2
  exit 1
fi

echo "Pushing mitmproxy CA as ${CACERT}..."
"${ADB}" push "$(adb_local_path "${MITMPROXY_CERT}")" "/data/local/tmp/${CACERT}"

echo "Running APEX / zygote injection..."
"${ADB}" push "$(adb_local_path "${INJECT_SH}")" /data/local/tmp/mitm-ca-inject-device.sh
"${ADB}" shell "chmod 755 /data/local/tmp/mitm-ca-inject-device.sh && CACERT=${CACERT} sh /data/local/tmp/mitm-ca-inject-device.sh"

echo "Force-stopping ${HUBSPACE_PKG}..."
"${ADB}" shell am force-stop "${HUBSPACE_PKG}"

echo "Opening http://mitm.it in Chrome (WireGuard must be on for the page to load)..."
if ! "${ADB}" shell am start -a android.intent.action.VIEW -d 'http://mitm.it/' \
  -n com.android.chrome/com.google.android.apps.chrome.Main >/dev/null 2>&1; then
  "${ADB}" shell am start -a android.intent.action.VIEW -d 'http://mitm.it/'
fi

echo "Done."
echo "System CA injected. Confirm http://mitm.it shows the mitmproxy cert page (WireGuard on)."
echo "APEX injection already trusts the CA — mitm.it is a tunnel check, not a cert install step."
