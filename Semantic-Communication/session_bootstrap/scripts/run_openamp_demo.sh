#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER="$PROJECT_ROOT/session_bootstrap/demo/openamp_control_plane_demo/server.py"
READINESS_CHECKER="$PROJECT_ROOT/session_bootstrap/scripts/check_openamp_demo_session_readiness.py"
READINESS_PASSWORD_ENV_VAR="OPENAMP_DEMO_READINESS_PASSWORD"
SERVER_SUFFIX="/session_bootstrap/demo/openamp_control_plane_demo/server.py"
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8079"
PORT_RECLAIM_TERM_WAIT_STEPS=10
PORT_RECLAIM_TERM_WAIT_SEC="0.1"
PORT_RECLAIM_KILL_WAIT_STEPS=50
PORT_RECLAIM_KILL_WAIT_SEC="0.1"

prompt_readiness_password() {
    local -n password_ref="$1"
    printf 'Readiness password: ' >&2
    if ! IFS= read -r -s password_ref; then
        printf '\nFailed to read readiness password from stdin.\n' >&2
        exit 1
    fi
    printf '\n' >&2
}

parse_bind_args() {
    local -n host_ref="$1"
    local -n port_ref="$2"
    shift 2

    host_ref="$DEFAULT_HOST"
    port_ref="$DEFAULT_PORT"

    while (($#)); do
        case "$1" in
            --host)
                if (($# >= 2)); then
                    host_ref="$2"
                    shift 2
                    continue
                fi
                break
                ;;
            --host=*)
                host_ref="${1#*=}"
                ;;
            --port)
                if (($# >= 2)); then
                    port_ref="$2"
                    shift 2
                    continue
                fi
                break
                ;;
            --port=*)
                port_ref="${1#*=}"
                ;;
            --)
                break
                ;;
        esac
        shift
    done
}

run_readiness_check_if_requested() {
    local -a readiness_args=()
    local readiness_requested=0
    local readiness_format="text"
    local prompt_password_requested=0
    local password_arg_provided=0

    while (($#)); do
        case "$1" in
            --check-readiness|--check-readiness-only)
                readiness_requested=1
                ;;
            --check-readiness-prompt-password)
                readiness_requested=1
                prompt_password_requested=1
                ;;
            --prompt-password)
                prompt_password_requested=1
                ;;
            --readiness-format)
                if (($# >= 2)); then
                    readiness_format="$2"
                    shift 2
                    continue
                fi
                break
                ;;
            --readiness-format=*)
                readiness_format="${1#*=}"
                ;;
            --probe-env|--host|--user|--password|--port|--env-file)
                if (($# >= 2)); then
                    if [[ "$1" == "--password" ]]; then
                        password_arg_provided=1
                    fi
                    readiness_args+=("$1" "$2")
                    shift 2
                    continue
                fi
                break
                ;;
            --probe-env=*|--host=*|--user=*|--password=*|--port=*|--env-file=*)
                if [[ "$1" == --password=* ]]; then
                    password_arg_provided=1
                fi
                readiness_args+=("$1")
                ;;
        esac
        shift
    done

    if ((readiness_requested)); then
        if ((prompt_password_requested && password_arg_provided)); then
            printf '%s\n' "Refusing to combine --prompt-password with explicit --password. Use one password input path." >&2
            exit 1
        fi
        if ((prompt_password_requested)); then
            local readiness_password=""
            prompt_readiness_password readiness_password
            exec env "$READINESS_PASSWORD_ENV_VAR=$readiness_password" \
                python3 "$READINESS_CHECKER" --format "$readiness_format" "${readiness_args[@]}"
        fi
        exec python3 "$READINESS_CHECKER" --format "$readiness_format" "${readiness_args[@]}"
    fi
}

run_server_with_prompt_password_if_requested() {
    local prompt_password_requested=0
    local -a server_args=()

    while (($#)); do
        case "$1" in
            --prompt-password)
                prompt_password_requested=1
                ;;
            --prompt-password-probe-startup)
                prompt_password_requested=1
                server_args+=("--probe-startup")
                ;;
            *)
                server_args+=("$1")
                ;;
        esac
        shift
    done

    if ((prompt_password_requested)); then
        local launch_password=""
        prompt_readiness_password launch_password
        exec env REMOTE_PASS="$launch_password" PHYTIUM_PI_PASSWORD="$launch_password" python3 "$SERVER" "${server_args[@]}"
    fi
}

bind_listener_conflicts() {
    local listener_addr="$1"
    local bind_host="$2"
    local bind_port="$3"

    case "$listener_addr" in
        "*:$bind_port"|0.0.0.0:"$bind_port"|[[]::[]]:"$bind_port"|[[]::ffff:0.0.0.0[]]:"$bind_port")
            return 0
            ;;
    esac

    case "$bind_host" in
        ""|0.0.0.0|::|[::])
            return 0
            ;;
        localhost)
            case "$listener_addr" in
                127.0.0.1:"$bind_port"|localhost:"$bind_port"|[[]::1[]]:"$bind_port")
                    return 0
                    ;;
            esac
            ;;
        127.0.0.1)
            case "$listener_addr" in
                127.0.0.1:"$bind_port"|localhost:"$bind_port")
                    return 0
                    ;;
            esac
            ;;
        ::1|[::1])
            case "$listener_addr" in
                [[]::1[]]:"$bind_port")
                    return 0
                    ;;
            esac
            ;;
        *)
            case "$listener_addr" in
                "$bind_host":"$bind_port"|[[]"$bind_host"[]]:"$bind_port")
                    return 0
                    ;;
            esac
            ;;
    esac

    return 1
}

cmdline_is_demo_server() {
    local cmdline="$1"
    [[ "$cmdline" == *"$SERVER"* ]] || [[ "$cmdline" == *"$SERVER_SUFFIX"* ]]
}

join_listener_addresses() {
    local joined=""
    local record

    for record in "$@"; do
        if [[ -n "$joined" ]]; then
            joined+=", "
        fi
        joined+="${record%%$'\t'*}"
    done

    printf '%s\n' "$joined"
}

join_values() {
    local joined=""
    local value

    for value in "$@"; do
        if [[ -n "$joined" ]]; then
            joined+=", "
        fi
        joined+="$value"
    done

    printf '%s\n' "$joined"
}

list_conflicting_listeners() {
    local line
    local listener_addr

    if ! command -v ss >/dev/null 2>&1; then
        return 0
    fi

    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        listener_addr="$(awk '{print $4}' <<<"$line")"
        [[ -n "$listener_addr" ]] || continue
        if bind_listener_conflicts "$listener_addr" "$REQUESTED_HOST" "$REQUESTED_PORT"; then
            printf '%s\t%s\n' "$listener_addr" "$line"
        fi
    done < <(ss -H -ltn "sport = :$REQUESTED_PORT" 2>/dev/null || true)
}

list_demo_processes_for_requested_bind() {
    local pid
    local cmdline
    local process_host
    local process_port
    local requested_bind_listener
    local -a argv

    case "$REQUESTED_HOST" in
        ""|0.0.0.0|::|[::])
            requested_bind_listener="0.0.0.0:$REQUESTED_PORT"
            ;;
        ::1|[::1])
            requested_bind_listener="[::1]:$REQUESTED_PORT"
            ;;
        *)
            requested_bind_listener="$REQUESTED_HOST:$REQUESTED_PORT"
            ;;
    esac

    while read -r pid cmdline; do
        [[ -n "${pid:-}" && -n "${cmdline:-}" ]] || continue
        cmdline_is_demo_server "$cmdline" || continue

        process_host="$DEFAULT_HOST"
        process_port="$DEFAULT_PORT"
        read -r -a argv <<<"$cmdline"
        parse_bind_args process_host process_port "${argv[@]}"

        if bind_listener_conflicts "$requested_bind_listener" "$process_host" "$process_port"; then
            printf '%s\t%s\t%s\t%s\n' "$pid" "$process_host" "$process_port" "$cmdline"
        fi
    done < <(ps -eo pid=,args=)
}

list_listener_owner_pids_for_requested_bind() {
    local line
    local pid=""
    local listener_addr

    if ! command -v lsof >/dev/null 2>&1; then
        return 0
    fi

    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        case "$line" in
            p*)
                pid="${line#p}"
                ;;
            n*)
                listener_addr="${line#n}"
                if [[ -n "$pid" ]] && bind_listener_conflicts "$listener_addr" "$REQUESTED_HOST" "$REQUESTED_PORT"; then
                    printf '%s\n' "$pid"
                fi
                ;;
        esac
    done < <(lsof -nP -iTCP:"$REQUESTED_PORT" -sTCP:LISTEN -Fpn 2>/dev/null || true)
}

pid_is_in_list() {
    local needle="$1"
    shift
    local value

    for value in "$@"; do
        if [[ "$value" == "$needle" ]]; then
            return 0
        fi
    done

    return 1
}

demo_process_records_include_pid() {
    local needle="$1"
    shift
    local demo_record
    local pid
    local process_host
    local process_port
    local cmdline

    for demo_record in "$@"; do
        IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
        if [[ "$pid" == "$needle" ]]; then
            return 0
        fi
    done

    return 1
}

listeners_are_clearly_owned_by_demo_processes() {
    local -n listener_records_ref="$1"
    local -n demo_records_ref="$2"
    local listener_record
    local listener_addr
    local demo_record
    local covered
    local cover_count
    local listener_count
    local other_listener_record
    local pid
    local process_host
    local process_port
    local cmdline

    for listener_record in "${listener_records_ref[@]}"; do
        listener_addr="${listener_record%%$'\t'*}"
        covered=1
        cover_count=0
        listener_count=0
        for demo_record in "${demo_records_ref[@]}"; do
            IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
            if bind_listener_conflicts "$listener_addr" "$process_host" "$process_port"; then
                covered=0
                ((cover_count += 1))
            fi
        done
        for other_listener_record in "${listener_records_ref[@]}"; do
            if [[ "${other_listener_record%%$'\t'*}" == "$listener_addr" ]]; then
                ((listener_count += 1))
            fi
        done
        if ((covered || cover_count < listener_count)); then
            return 1
        fi
    done

    return 0
}

wait_for_conflicting_listeners_to_clear() {
    local steps="$1"
    local wait_sec="$2"
    local -n listener_records_ref="$3"
    local attempt

    for ((attempt = 0; attempt < steps; attempt++)); do
        mapfile -t listener_records_ref < <(list_conflicting_listeners)
        if ((${#listener_records_ref[@]} == 0)); then
            return 0
        fi
        sleep "$wait_sec"
    done

    return 1
}

reclaim_demo_listener_if_safe() {
    local -a conflicting_listeners=()
    local -a demo_processes=()
    local -a blocking_demo_processes=()
    local -a original_demo_pids=()
    local -a current_demo_processes=()
    local -a stubborn_demo_processes=()
    local -a listener_owner_pids=()
    local listener_record
    local demo_record
    local pid
    local process_host
    local process_port
    local cmdline
    local listener_summary=""
    local pid_summary=""

    mapfile -t conflicting_listeners < <(list_conflicting_listeners)
    if ((${#conflicting_listeners[@]} == 0)); then
        return 0
    fi

    mapfile -t demo_processes < <(list_demo_processes_for_requested_bind)
    if ((${#demo_processes[@]} == 0)); then
        listener_summary="$(join_listener_addresses "${conflicting_listeners[@]}")"
        printf 'Requested OpenAMP demo port %s is already in use at %s.\n' "$REQUESTED_PORT" "$listener_summary" >&2
        printf 'Refusing to stop a non-OpenAMP listener. Use --port or stop that service manually.\n' >&2
        exit 1
    fi

    mapfile -t listener_owner_pids < <(list_listener_owner_pids_for_requested_bind)
    if ((${#listener_owner_pids[@]} > 0)); then
        for pid in "${listener_owner_pids[@]}"; do
            if ! demo_process_records_include_pid "$pid" "${demo_processes[@]}"; then
                listener_summary="$(join_listener_addresses "${conflicting_listeners[@]}")"
                printf 'Requested OpenAMP demo port %s is already in use at %s.\n' "$REQUESTED_PORT" "$listener_summary" >&2
                printf 'Refusing to stop a non-OpenAMP listener. Use --port or stop that service manually.\n' >&2
                exit 1
            fi
        done
        for demo_record in "${demo_processes[@]}"; do
            IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
            if pid_is_in_list "$pid" "${listener_owner_pids[@]}"; then
                blocking_demo_processes+=("$demo_record")
            fi
        done
    else
        blocking_demo_processes=("${demo_processes[@]}")
    fi

    if ! listeners_are_clearly_owned_by_demo_processes conflicting_listeners blocking_demo_processes; then
        listener_summary="$(join_listener_addresses "${conflicting_listeners[@]}")"
        printf 'Requested OpenAMP demo port %s is already in use at %s.\n' "$REQUESTED_PORT" "$listener_summary" >&2
        printf 'Listener ownership is not clearly limited to %s.\n' "$SERVER" >&2
        printf 'Refusing to kill by port. Use --port or stop the other service manually.\n' >&2
        exit 1
    fi

    for demo_record in "${blocking_demo_processes[@]}"; do
        IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
        printf 'Reclaiming port %s from existing OpenAMP demo server PID %s with TERM.\n' "$REQUESTED_PORT" "$pid" >&2
        kill -TERM "$pid" 2>/dev/null || true
        original_demo_pids+=("$pid")
    done

    if wait_for_conflicting_listeners_to_clear "$PORT_RECLAIM_TERM_WAIT_STEPS" "$PORT_RECLAIM_TERM_WAIT_SEC" conflicting_listeners; then
        return 0
    fi

    pid_summary="$(join_values "${original_demo_pids[@]}")"
    listener_summary="$(join_listener_addresses "${conflicting_listeners[@]}")"
    printf 'Existing OpenAMP demo server PID(s) %s still hold port %s after TERM grace period (%s).\n' "$pid_summary" "$REQUESTED_PORT" "$listener_summary" >&2

    mapfile -t current_demo_processes < <(list_demo_processes_for_requested_bind)
    mapfile -t listener_owner_pids < <(list_listener_owner_pids_for_requested_bind)
    if ((${#listener_owner_pids[@]} > 0)); then
        for pid in "${listener_owner_pids[@]}"; do
            if ! pid_is_in_list "$pid" "${original_demo_pids[@]}"; then
                printf 'Refusing to escalate to KILL because the remaining listener is no longer the same OpenAMP demo server PID(s).\n' >&2
                exit 1
            fi
            if ! demo_process_records_include_pid "$pid" "${current_demo_processes[@]}"; then
                printf 'Refusing to escalate to KILL because listener ownership is no longer clearly limited to the same OpenAMP demo server PID(s).\n' >&2
                exit 1
            fi
        done
        for demo_record in "${current_demo_processes[@]}"; do
            IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
            if pid_is_in_list "$pid" "${listener_owner_pids[@]}"; then
                stubborn_demo_processes+=("$demo_record")
            fi
        done
    else
        for demo_record in "${current_demo_processes[@]}"; do
            IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
            if pid_is_in_list "$pid" "${original_demo_pids[@]}"; then
                stubborn_demo_processes+=("$demo_record")
            fi
        done
    fi

    if ((${#stubborn_demo_processes[@]} == 0)); then
        printf 'Refusing to escalate to KILL because the remaining listener is no longer the same OpenAMP demo server PID(s).\n' >&2
        exit 1
    fi

    if ! listeners_are_clearly_owned_by_demo_processes conflicting_listeners stubborn_demo_processes; then
        printf 'Refusing to escalate to KILL because listener ownership is no longer clearly limited to the same OpenAMP demo server PID(s).\n' >&2
        exit 1
    fi

    pid_summary=""
    for demo_record in "${stubborn_demo_processes[@]}"; do
        IFS=$'\t' read -r pid process_host process_port cmdline <<<"$demo_record"
        printf 'Escalating reclaim of port %s to KILL for existing OpenAMP demo server PID %s.\n' "$REQUESTED_PORT" "$pid" >&2
        kill -KILL "$pid" 2>/dev/null || true
        if [[ -n "$pid_summary" ]]; then
            pid_summary+=", "
        fi
        pid_summary+="$pid"
    done

    if wait_for_conflicting_listeners_to_clear "$PORT_RECLAIM_KILL_WAIT_STEPS" "$PORT_RECLAIM_KILL_WAIT_SEC" conflicting_listeners; then
        return 0
    fi

    listener_summary="$(join_listener_addresses "${conflicting_listeners[@]}")"
    printf 'Timed out waiting for existing OpenAMP demo server PID(s) %s to release port %s after KILL (%s).\n' "$pid_summary" "$REQUESTED_PORT" "$listener_summary" >&2
    exit 1
}

main() {
    run_readiness_check_if_requested "$@"
    parse_bind_args REQUESTED_HOST REQUESTED_PORT "$@"

    if [[ ! "$REQUESTED_PORT" =~ ^[0-9]+$ ]]; then
        run_server_with_prompt_password_if_requested "$@"
        exec python3 "$SERVER" "$@"
    fi

    reclaim_demo_listener_if_safe
    run_server_with_prompt_password_if_requested "$@"
    exec python3 "$SERVER" "$@"
}

main "$@"
