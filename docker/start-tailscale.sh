#!/usr/bin/env bash
set -euo pipefail

SOCKET="${TAILSCALE_SOCKET:-/var/run/tailscale/tailscaled.sock}"
STATE_DIR="${TS_STATE_DIR:-${TAILSCALE_STATE_DIR:-/var/lib/tailscale}}"
HOSTNAME="${TS_HOSTNAME:-${TAILSCALE_HOSTNAME:-iccomp-demo}}"
AUTHKEY="${TS_AUTHKEY:-${TAILSCALE_AUTHKEY:-}}"
ACCEPT_DNS="${TS_ACCEPT_DNS:-${TAILSCALE_ACCEPT_DNS:-false}}"
ACCEPT_ROUTES="${TS_ACCEPT_ROUTES:-${TAILSCALE_ACCEPT_ROUTES:-true}}"
EXTRA_ARGS="${TS_EXTRA_ARGS:-${TAILSCALE_EXTRA_ARGS:-}}"
LOGIN_MODE="${TS_LOGIN_MODE:-${TAILSCALE_LOGIN_MODE:-authkey}}"
LOGIN_WAIT_SEC="${TS_LOGIN_WAIT_SEC:-${TAILSCALE_LOGIN_WAIT_SEC:-30}}"

log() {
    printf '[tailscale] %s\n' "$*"
}

die() {
    printf '[tailscale] %s\n' "$*" >&2
    exit 1
}

command -v tailscaled >/dev/null 2>&1 || die "tailscaled is not installed"
command -v tailscale >/dev/null 2>&1 || die "tailscale is not installed"

if [ ! -c /dev/net/tun ]; then
    die "/dev/net/tun is missing. Start the container with --device=/dev/net/tun and --cap-add=NET_ADMIN."
fi

mkdir -p "$(dirname "${SOCKET}")" "${STATE_DIR}"

if ! pgrep -x tailscaled >/dev/null 2>&1; then
    log "starting tailscaled with kernel networking"
    tailscaled \
        --socket="${SOCKET}" \
        --state="${STATE_DIR}/tailscaled.state" \
        --tun=tailscale0 &
fi

for _ in $(seq 1 30); do
    if tailscale --socket="${SOCKET}" version >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

if ! tailscale --socket="${SOCKET}" version >/dev/null 2>&1; then
    die "tailscaled did not become ready"
fi

up_args=(
    "--hostname=${HOSTNAME}"
    "--accept-dns=${ACCEPT_DNS}"
    "--accept-routes=${ACCEPT_ROUTES}"
)

is_logged_in() {
    tailscale --socket="${SOCKET}" status --peers=false >/dev/null 2>&1
}

if [ -n "${AUTHKEY}" ]; then
    up_args+=("--auth-key=${AUTHKEY}")
elif ! is_logged_in; then
    if [ "${LOGIN_MODE}" = "interactive" ]; then
        log "not logged in; tailscale up will print a browser login URL"
    else
        log "waiting up to ${LOGIN_WAIT_SEC}s for saved Tailscale state"
        deadline=$((SECONDS + LOGIN_WAIT_SEC))
        while [ "${SECONDS}" -lt "${deadline}" ]; do
            if is_logged_in; then
                break
            fi
            sleep 1
        done
        if ! is_logged_in; then
            die "not logged in. Set TS_AUTHKEY/TAILSCALE_AUTHKEY, reuse an authenticated state volume, or set TS_LOGIN_MODE=interactive for manual browser login."
        fi
    fi
fi

if [ -n "${EXTRA_ARGS}" ]; then
    # shellcheck disable=SC2206
    extra_args_split=(${EXTRA_ARGS})
    up_args+=("${extra_args_split[@]}")
fi

log "joining tailnet as ${HOSTNAME}"
tailscale --socket="${SOCKET}" up "${up_args[@]}"

log "tailscale ipv4: $(tailscale --socket="${SOCKET}" ip -4 2>/dev/null || printf 'unavailable')"

if [ -n "${TAILSCALE_PING_TARGET:-}" ]; then
    log "checking ${TAILSCALE_PING_TARGET}"
    tailscale --socket="${SOCKET}" ping --timeout=5s "${TAILSCALE_PING_TARGET}" || true
fi
