#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

reassemble() {
    local output="$1"
    local expected_sha256="$2"
    shift 2

    if [ "$#" -eq 0 ]; then
        echo "missing parts for ${output}" >&2
        exit 1
    fi

    cat "$@" > "${output}"
    actual_sha256="$(sha256sum "${output}" | awk '{print $1}')"
    if [ "${actual_sha256}" != "${expected_sha256}" ]; then
        echo "sha256 mismatch: ${output}" >&2
        echo "  expected: ${expected_sha256}" >&2
        echo "  actual:   ${actual_sha256}" >&2
        exit 1
    fi
    echo "ok: ${output}"
}

reassemble \
    "${SCRIPT_DIR}/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz" \
    "d434d475fdc4c20dfeb9db345c647033245b7a856de0bb6799c184f6232497df" \
    "${SCRIPT_DIR}"/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*

reassemble \
    "${SCRIPT_DIR}/runtime/mnn_py312.tar.gz" \
    "7f58094f51cd27b0832a14f22b721de9a53c554990cabe183b9960b67391b5da" \
    "${SCRIPT_DIR}"/runtime/mnn_py312.tar.gz.part-*

reassemble \
    "${SCRIPT_DIR}/usrp/uhd-images/uhd-images_4.6.0.0.tar.xz" \
    "a312587fbe9fffb6043cd96bae50ef283bb55a1e51e1435b5e4a350beb00e59d" \
    "${SCRIPT_DIR}"/usrp/uhd-images/uhd-images_4.6.0.0.tar.xz.part-*
