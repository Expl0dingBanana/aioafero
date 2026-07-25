#!/usr/bin/env bash
# Start/stop mitmweb (WireGuard mode) for the aioafero MITM test bed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/docker/mitmweb/compose.yaml"

usage() {
  cat <<EOF
Usage: $(basename "$0") <up|down|logs|ps|ca-path>

  up       Pull image and start mitmweb (detached)
  down     Stop and remove the container
  logs     Follow container logs
  ps       Show container status
  ca-path  Print host path to mitmproxy-ca-cert.pem (WSL; used by inject-mitm-ca.sh)

Web UI:    http://127.0.0.1:8081/?token=aioafero
WireGuard: UDP 51820 — set emulator Endpoint to 10.0.2.2:51820

Docs: docs/mitm/index.rst
EOF
}

cmd="${1:-}"

case "${cmd}" in
  up)
    docker compose -f "${COMPOSE_FILE}" up -d --pull always
    echo "mitmweb: http://127.0.0.1:8081/?token=aioafero"
    echo "password (same as token query param): aioafero"
    ;;
  down)
    docker compose -f "${COMPOSE_FILE}" down
    ;;
  logs)
    docker compose -f "${COMPOSE_FILE}" logs -f mitmweb
    ;;
  ps)
    docker compose -f "${COMPOSE_FILE}" ps
    ;;
  ca-path)
    cert="${MITMPROXY_CONFIG_DIR:-${HOME}/.mitmproxy}/mitmproxy-ca-cert.pem"
    if [[ ! -f "${cert}" ]]; then
      echo "CA not found at ${cert}. Run: $(basename "$0") up" >&2
      exit 1
    fi
    echo "${cert}"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
