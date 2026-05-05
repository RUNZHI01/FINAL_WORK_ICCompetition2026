#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

SDK_ROOT_DEFAULT=/tmp/phytium-standalone-sdk
PATCH_FILE_DEFAULT="${REPO_ROOT}/session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch"
OPENAMP_DIR_REL=example/system/amp/openamp_for_linux
CONFIG_NAME=pe2204_aarch64_phytiumpi_openamp_core0
EXPECTED_ELF=pe2204_aarch64_phytiumpi_openamp_core0.elf

sdk_root="${SDK_ROOT_DEFAULT}"
patch_file="${PATCH_FILE_DEFAULT}"
mode="plan"

usage() {
  cat <<'EOF'
Usage:
  prepare_phytium_openamp_patch.sh [--sdk-root PATH] [--patch-file PATH] [--apply]

Defaults:
  --sdk-root   /tmp/phytium-standalone-sdk
  --patch-file /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch

Behavior:
  Default mode is plan-only:
    - check required paths
    - run git apply --check
    - print build commands

  With --apply:
    - apply the patch to the SDK tree if it is not already applied
    - do not build
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sdk-root)
      sdk_root="$2"
      shift 2
      ;;
    --patch-file)
      patch_file="$2"
      shift 2
      ;;
    --apply)
      mode="apply"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

openamp_dir="${sdk_root}/${OPENAMP_DIR_REL}"
config_path="${openamp_dir}/configs/${CONFIG_NAME}.config"

require_path() {
  local path="$1"
  local label="$2"
  if [[ ! -e "${path}" ]]; then
    printf 'ERROR: missing %s: %s\n' "${label}" "${path}" >&2
    exit 1
  fi
}

require_path "${sdk_root}" "SDK root"
require_path "${patch_file}" "patch file"
require_path "${openamp_dir}" "openamp_for_linux directory"
require_path "${config_path}" "PhytiumPi config"

if ! git -C "${sdk_root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'ERROR: %s is not a git working tree.\n' "${sdk_root}" >&2
  exit 1
fi

printf '[info] sdk_root=%s\n' "${sdk_root}"
printf '[info] patch_file=%s\n' "${patch_file}"
printf '[info] mode=%s\n' "${mode}"

if git -C "${sdk_root}" apply --reverse --check "${patch_file}" >/dev/null 2>&1; then
  patch_state="already_applied"
elif git -C "${sdk_root}" apply --check "${patch_file}" >/dev/null 2>&1; then
  patch_state="applicable"
else
  printf '[error] patch cannot be applied cleanly to %s\n' "${sdk_root}" >&2
  exit 1
fi

printf '[info] patch_state=%s\n' "${patch_state}"

if [[ "${mode}" == "apply" ]]; then
  if [[ "${patch_state}" == "already_applied" ]]; then
    printf '[info] patch is already present; skip apply.\n'
  else
    git -C "${sdk_root}" apply "${patch_file}"
    printf '[info] patch applied successfully.\n'
  fi
fi

printf '\n[build] run the following commands on the SDK tree:\n'
printf '  cd %s\n' "${openamp_dir}"
printf '  make load_kconfig LOAD_CONFIG_NAME=%s\n' "${CONFIG_NAME}"
printf '  make clean\n'
printf '  make all -j"$(nproc)"\n'
printf '\n[artifact] expected ELF:\n'
printf '  %s/%s\n' "${openamp_dir}" "${EXPECTED_ELF}"
printf '\n[optional] produce deployment-style name:\n'
printf '  cd %s\n' "${openamp_dir}"
printf '  make image USR_BOOT_DIR=/tmp/phytium_openamp_out\n'
printf '  ls -l /tmp/phytium_openamp_out/openamp_core0.elf\n'
printf '\n[deploy reminder]\n'
printf '  1. Copy the rebuilt ELF to the board and install it as /lib/firmware/openamp_core0.elf\n'
printf '  2. Restart /sys/class/remoteproc/remoteproc0/state\n'
printf '  3. Re-create /dev/rpmsg_ctrl0 and /dev/rpmsg0 via the board-side OpenAMP flow\n'
printf '  4. Run session_bootstrap/scripts/openamp_rpmsg_bridge.py to verify a real STATUS_RESP\n'
