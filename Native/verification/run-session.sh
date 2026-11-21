#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
runtime=$(realpath "$1")
mkdir -p -- "$2"
case_dir=$(realpath "$2")
ticks=$3
step=${4:-.0625}
render_every=${5:-257}
coast_ship=${6:-}
if [[ "$ticks" != launcher ]]; then
    # Invalidate a previous successful run before replacing any of its evidence.
    rm -f -- "$case_dir/runtime-provenance.json"
fi
pulse_dir=$(mktemp -d)
export PULSE_RUNTIME_PATH="$pulse_dir" PULSE_SERVER="unix:$pulse_dir/pulse.sock" PULSE_SINK=mercury_test
export LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=2 QT_QPA_PLATFORM=xcb XDG_SESSION_TYPE=x11
env DBUS_SESSION_BUS_ADDRESS="unix:path=$pulse_dir/no-session-bus" pulseaudio -n --daemonize=no --exit-idle-time=-1 --log-target=stderr \
    -L "module-native-protocol-unix socket=$pulse_dir/pulse.sock" \
    -L "module-null-sink sink_name=$PULSE_SINK" > "$case_dir/pulseaudio.log" 2>&1 &
pulse_pid=$!
trace_pid=
coast_dir=
provenance_tmp=
cleanup() {
    if [[ -n "$trace_pid" ]]; then
        kill "$trace_pid" 2>/dev/null || true
        wait "$trace_pid" 2>/dev/null || true
    fi
    if [[ -n "$coast_dir" ]]; then
        # Publish regular evidence files even if the simulator exited early.
        mkdir -p "$case_dir/evidence"
        if [[ -f "$coast_dir/capsule.csv" ]]; then
            mv -T "$coast_dir/capsule.csv" "$case_dir/evidence/flight-state.csv"
        fi
        find "$coast_dir" -maxdepth 1 -type f -exec mv -t "$case_dir/evidence" -- {} +
        rm -rf "$coast_dir"
    fi
    if [[ -n "$provenance_tmp" ]]; then rm -f -- "$provenance_tmp"; fi
    kill "$pulse_pid" 2>/dev/null || true
    wait "$pulse_pid" 2>/dev/null || true
    rm -rf "$pulse_dir"
}
trap cleanup EXIT
for attempt in {1..50}; do
    pactl info >/dev/null 2>&1 && break
    kill -0 "$pulse_pid" 2>/dev/null || break
    sleep .2
done
pactl info > "$case_dir/audio-server.txt" || { cat "$case_dir/pulseaudio.log"; exit 1; }
pactl set-sink-volume "$PULSE_SINK" 5%
volume=$(LC_ALL=C pactl get-sink-volume "$PULSE_SINK")
printf '%s\n' "$volume" >> "$case_dir/audio-server.txt"
[[ $(grep -oE '[0-9]+%' <<< "$volume" | sort -u) == 5% ]] || { echo "Unexpected sink volume: $volume" >&2; exit 1; }
if [[ "$ticks" == launcher ]]; then
    manifest=${MERCURY_LAUNCHER_MANIFEST:-"$runtime/qualification/launcher-manifest.json"}
    if [[ -z ${MERCURY_LAUNCHER_MANIFEST:-} && ! -e "$manifest" ]]; then
        manifest="$script_dir/launcher-manifest.json"
    fi
    env -u WAYLAND_DISPLAY -u LD_LIBRARY_PATH xvfb-run -a -s '-screen 0 1600x1000x24 +extension GLX' \
        python3 "$script_dir/launchpad.py" "$runtime" "$case_dir" "$manifest"
    exit
fi
cd "$case_dir"
provenance_tmp=$(mktemp "$case_dir/.runtime-provenance.XXXXXXXX")
python3 "$script_dir/runtime_provenance.py" start "$runtime" "$case_dir" "$provenance_tmp"
evidence=evidence
if [[ -n "$coast_ship" ]]; then
    # Up to 34 simulated hours. Keep every capsule sample and avoid filling
    # the runner with per-tick pad, spent-stage and callback diagnostics.
    coast_dir=$(mktemp -d "$case_dir/.coast-evidence.XXXXXXXX")
    evidence=$coast_dir
    for trace in application-lifecycle flight-animations flight-controls ground-math input-state \
                 lifetime-events production-state thrust-state vessel-callbacks; do
        ln -s /dev/null "$evidence/$trace.csv"
    done
    mkfifo "$evidence/flight-state.csv"
    LC_ALL=C awk -F, -v ship="$coast_ship" 'NR == 1 || $5 == ship' \
        "$evidence/flight-state.csv" > "$evidence/capsule.csv" &
    trace_pid=$!
fi
runner=()
engine="$runtime/engine/run-orbiter"
limits=(--ticks "$ticks" --run)
if [[ "${MERCURY_PAUSED:-0}" == 1 ]]; then limits=(--frames "$ticks"); fi
if [[ "${MERCURY_DEBUG:-0}" == 1 ]]; then
    runner=(gdb -batch -ex run -ex "bt 16" -ex "frame 0" -ex "info args" -ex "info locals" --args)
    engine="$runtime/engine/orbiter-production"
fi
env -u WAYLAND_DISPLAY LD_LIBRARY_PATH="$runtime/engine:$runtime/engine/native-lua" xvfb-run -a -s '-screen 0 1600x1000x24 +extension GLX' \
    "${runner[@]}" "$engine" --assets "$runtime/resources" --data "$runtime/celestial-data" \
    --modules "$runtime/engine/NativeModules" --planets "$runtime/planet-archives" --config "$runtime/Orbiter.cfg" \
    --xrsound-assets "$runtime/resources" --scenario input.scn --save saved.scn --replay replay.csv \
    "${limits[@]}" --fixed-step "$step" --render-every "$render_every" --evidence "$evidence" > console.log 2>&1
if [[ -n "$trace_pid" ]]; then
    wait "$trace_pid"
    trace_pid=
fi
python3 "$script_dir/runtime_provenance.py" finish "$runtime" "$case_dir" "$provenance_tmp"
