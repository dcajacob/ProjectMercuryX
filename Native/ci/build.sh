#!/usr/bin/env bash
# Build a matching OpenGL host, Mercury modules, launcher and sound bridge.
set -euo pipefail
source_dir=$(realpath "$1")
work=$(realpath -m "$2")
repo=$(realpath "$(dirname "$0")/../..")
engine="$work/engine-build"
runtime="$work/runtime"
test "$(git -C "$source_dir" rev-parse HEAD)" = f37eeee6ec8a757c9daa07fff0eeeec704d1e655
# NASSP's shared host predates the merged Orbiter DelThruster fix. Apply only
# its vessel implementation from the reviewed commit to this disposable build.
fix=d60f20787d39936aba350f7ae27d280ce87b6cfb
git -C "$source_dir" diff "$fix^" "$fix" -- Src/Orbiter/Vessel.cpp | git -C "$source_dir" apply -
host="$source_dir/Src/Orbiter/Production/NativeApplication.cpp"
python3 "$repo/Native/prepare-engine.py" "$host" "$host"
git -C "$source_dir" apply "$repo/Native/initial-vessels.patch"
export CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL:-4}
base=(-G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
      '-DCMAKE_INSTALL_RPATH=$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..;$ORIGIN/native-lua')
python3 "$source_dir/Tests/Production/NativeScene/dependencies.py" --cache "$work/deps"
cmake -S "$source_dir/Src/Orbiter/Production" -B "$engine" "${base[@]}" \
    -DORBITER_BUILD_NATIVE_VESSELS=ON -DORBITER_BUILD_NATIVE_CELESTIAL_MODULES=ON \
    -DORBITER_BUILD_NATIVE_COCKPIT=ON -DORBITER_MATH_FORCE_SSE2=ON -DBUILD_TESTING=OFF \
    -DORBITER_NATIVE_UI_ARCHIVE="$work/deps/imgui.zip"
cmake --build "$engine" --target orbiter-production native_lua_inline native_lua_mfd orbiter_native_spice \
    orbiter_native_EarthAtmJ71G orbiter_native_EarthAtm2006 orbiter_native_MarsAtm2006
cmake -S "$source_dir/Src/Celbody/NativeEphemeris" -B "$work/ephemeris" "${base[@]}" -DORBITER_ENGINE_BUILD="$engine"
cmake --build "$work/ephemeris"
cmake -S "$source_dir/OVP/OGLClient/Native" -B "$work/renderer" "${base[@]}" \
    -DORBITER_ENGINE_BUILD="$engine" -DORBITER_RENDERER_DEPENDENCIES="$work/deps"
cmake --build "$work/renderer" --target orbiter_ogl_native
cmake -S "$source_dir/Utils/Launchpad" -B "$work/launcher" "${base[@]}" -DORBITER_GLFW_ARCHIVE="$work/deps/glfw.tar.gz"
cmake --build "$work/launcher" --target orbiter-launchpad
cmake -S "$repo" -B "$work/mercury" "${base[@]}" \
    -DORBITER_NATIVE_SOURCE_DIR="$source_dir" -DORBITER_NATIVE_BUILD_DIR="$engine"
cmake --build "$work/mercury"
python3 "$repo/Native/install-runtime.py" "$engine" "$work/mercury" "$runtime"
mkdir -p "$runtime/resources/Modules"
cp -a "$source_dir/OVP/OGLClient/shaders" "$runtime/resources/Modules/OGLClient"
cp "$work/launcher/orbiter-launchpad" "$runtime/engine/"
install -m755 "$repo/Native/ci/run-orbiter" "$runtime/engine/run-orbiter"
test "$(find "$runtime/engine/NativeModules/Vessel/ProjectMercury" -name '*.so' | wc -l)" -eq 15
