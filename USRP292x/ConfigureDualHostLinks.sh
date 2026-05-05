#!/usr/bin/env bash
set -euo pipefail

# Compatibility wrapper for the old dual-host-link entry.
# The canonical NetworkManager deployment script is now
# scripts/setup_usrp2922_network.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

exec "${PROJECT_ROOT}/scripts/setup_usrp2922_network.sh" local-loopback "$@"
