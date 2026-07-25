#!/usr/bin/env bash
# adb from WSL against the Windows emulator (Windows platform-tools adb.exe).
#
#   ./scripts/adb.sh devices
#   ./scripts/adb.sh push docker/mitmweb/emulator-wireguard.conf /sdcard/Download/foo.conf
#
# Sourced by inject-mitm-ca.sh. Optional ~/.bashrc:
#   export ADB="/mnt/c/Users/<you>/AppData/Local/Android/platform-tools/adb.exe"
#   alias adb="$ADB"

find_windows_adb_exe() {
  local user candidate

  if [[ -n "${WINDOWS_ADB:-}" && -f "${WINDOWS_ADB}" ]]; then
    echo "${WINDOWS_ADB}"
    return 0
  fi

  user="$(cmd.exe /c 'echo %USERNAME%' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "$user" ]]; then
    candidate="/mnt/c/Users/${user}/AppData/Local/Android/platform-tools/adb.exe"
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  fi

  for candidate in /mnt/c/Users/*/AppData/Local/Android/platform-tools/adb.exe; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

adb_local_path() {
  local path="$1"
  if [[ "${ADB:-}" == *adb.exe* || "${ADB:-}" == *adb.EXE* ]]; then
    if [[ "$path" != /mnt/* ]]; then
      wslpath -w "$path"
      return
    fi
  fi
  echo "$path"
}

adb_devices() {
  # Windows adb.exe uses CRLF; strip \r so parsers see "device" not "device\r".
  "${ADB}" devices 2>/dev/null | tr -d '\r'
}

adb_has_device() {
  adb_devices | awk 'NR>1 && $2=="device" { found=1 } END { exit !found }'
}

setup_windows_adb() {
  if [[ -n "${ADB:-}" && "${ADB}" != "adb" ]]; then
    if [[ -f "${ADB}" ]] || command -v "${ADB}" >/dev/null 2>&1; then
      export ADB
      return 0
    fi
  fi

  local win_adb
  if ! win_adb="$(find_windows_adb_exe)"; then
    echo "ERROR: Windows adb.exe not found (finish SDK platform-tools — docs/mitm/install.rst)." >&2
    echo "Or set ADB=/mnt/c/Users/<you>/AppData/Local/Android/platform-tools/adb.exe" >&2
    return 1
  fi

  "${win_adb}" kill-server >/dev/null 2>&1 || true
  "${win_adb}" start-server >/dev/null 2>&1
  export ADB="${win_adb}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  set -euo pipefail
  setup_windows_adb
  if [[ $# -gt 0 && "$1" == "push" && $# -ge 2 ]]; then
    set -- push "$(adb_local_path "$2")" "${@:3}"
  fi
  exec "${ADB}" "$@"
fi
