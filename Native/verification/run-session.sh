#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
runtime=$(realpath "$1")
mkdir -p -- "$2"
case_dir=$(realpath "$2")
ticks=$3
step=${4:-.0625}
render_every=${5:-257}
pulse_dir=$(mktemp -d)
export PULSE_RUNTIME_PATH="$pulse_dir" PULSE_SERVER="unix:$pulse_dir/pulse.sock" PULSE_SINK=mercury_test
export LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=2 QT_QPA_PLATFORM=xcb XDG_SESSION_TYPE=x11
env DBUS_SESSION_BUS_ADDRESS="unix:path=$pulse_dir/no-session-bus" pulseaudio -n --daemonize=no --exit-idle-time=-1 --log-target=stderr \
    -L "module-native-protocol-unix socket=$pulse_dir/pulse.sock" \
    -L "module-null-sink sink_name=$PULSE_SINK" > "$case_dir/pulseaudio.log" 2>&1 &
pulse_pid=$!
cleanup() { kill "$pulse_pid" 2>/dev/null || true; wait "$pulse_pid" 2>/dev/null || true; rm -rf "$pulse_dir"; }
trap cleanup EXIT
for attempt in {1..50}; do
    pactl info >/dev/null 2>&1 && break
    kill -0 "$pulse_pid" 2>/dev/null || break
    sleep .2
done
pactl info > "$case_dir/audio-server.txt" || { cat "$case_dir/pulseaudio.log"; exit 1; }
pactl set-sink-volume "$PULSE_SINK" 5%
pactl get-sink-volume "$PULSE_SINK" >> "$case_dir/audio-server.txt"
if [[ "$ticks" == launcher ]]; then
    env -u WAYLAND_DISPLAY -u LD_LIBRARY_PATH xvfb-run -a -s '-screen 0 1600x1000x24 +extension GLX' \
        python3 "$script_dir/launchpad.py" "$runtime" "$case_dir" "${MERCURY_LAUNCHER_MANIFEST:-$script_dir/launcher-manifest.json}"
    exit
fi
cd "$case_dir"
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
    "${limits[@]}" --fixed-step "$step" --render-every "$render_every" --evidence evidence > console.log 2>&1
