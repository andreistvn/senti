#!/bin/bash
#
# Shared by the start and stop scripts: finding and stopping a SentiNet service.
# Sourced, not run. Expects ROOT to be the repository root.
#
# A service is stopped by what it IS — a process matching the service's command
# and running from its directory in this repository — rather than only by the
# PID recorded when it was started. The recorded PID alone is not enough:
#   * `npm run dev` is npm -> sh -> node; killing npm and its direct child
#     leaves the node process (the actual dev server) running and holding its
#     port.
#   * Starting a service twice overwrites the PID file, so the first instance
#     can no longer be found at all.
# Both leave stray dashboards behind, and the next start lands on another port.

# What each service's process looks like (a pgrep -f pattern).
service_pattern() {
    case "$1" in
        admin_backend)                    echo "main\.py" ;;
        tray_app)                         echo "sentinet_tray\.py" ;;
        admin_dashboard|agent_dashboard)  echo "vite|npm run dev" ;;
    esac
}

# Every descendant of a PID, deepest first.
_descendants() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do
        _descendants "$child"
        echo "$child"
    done
}

_proc_cwd() {
    if [ -e "/proc/$1/cwd" ]; then
        readlink "/proc/$1/cwd" 2>/dev/null
    else
        lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'
    fi
}

# PIDs of every process belonging to a service: the recorded one, anything
# matching its pattern from its directory, and all of their descendants.
service_pids() {
    local name=$1 dir=$2
    local pid_file="/tmp/sentinet_${name}.pid"
    local pattern roots="" pid
    pattern="$(service_pattern "$name")"

    if [ -f "$pid_file" ]; then
        pid="$(cat "$pid_file" 2>/dev/null)"
        [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && roots="$roots $pid"
    fi
    if [ -n "$pattern" ]; then
        for pid in $(pgrep -f "$pattern" 2>/dev/null); do
            [ "$(_proc_cwd "$pid")" = "$ROOT/$dir" ] && roots="$roots $pid"
        done
    fi
    for pid in $roots; do
        _descendants "$pid"
        echo "$pid"
    done | sort -un
}

# Stop a service completely: ask politely, wait, then force whatever is left.
#   stop_service <name> <dir> [quiet]
stop_service() {
    local name=$1 dir=$2 quiet=${3:-}
    local pids pid waited=0 left=""
    pids="$(service_pids "$name" "$dir" | tr '\n' ' ')"
    rm -f "/tmp/sentinet_${name}.pid"

    if [ -z "${pids// /}" ]; then
        [ -z "$quiet" ] && echo "  $name is not running."
        return 0
    fi

    echo "  Stopping $name (PID ${pids% })..."
    kill $pids 2>/dev/null
    while [ "$waited" -lt 6 ]; do
        left=""
        for pid in $pids; do kill -0 "$pid" 2>/dev/null && left="$left $pid"; done
        [ -z "$left" ] && return 0
        sleep 0.5
        waited=$((waited + 1))
    done

    echo "  $name did not exit — forcing it (PID${left})..."
    kill -9 $left 2>/dev/null
    sleep 0.5
    for pid in $left; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  WARNING: could not stop $name process $pid. Run: kill -9 $pid"
        fi
    done
}
