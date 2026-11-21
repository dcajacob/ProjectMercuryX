# Native Linux OpenGL port

This fork runs the original Project Mercury X v3.1 vessels, cockpit, scenery and
scenarios in the native cross-platform Orbiter engine. No Wine is involved.
Linux x86-64 is the first qualified target. Windows and macOS are not yet tested.

The source is GPL-3.0 as licensed in this GitHub repository. Original downloadable
assets have separate licenses and permissions; see chapter 9 of the original
manual. This repository does not relicense or vendor those assets. Download the
original distribution from https://www.orbiter-forum.com/resources/project-mercury-x.2666/download
and keep its documentation and credits when installing it locally.

## Build

Use a complete, matching Orbiter native source tree with native cockpit, OpenGL,
XRSound and reference-math support. The initial qualification uses the same source
snapshot as our NASSP Linux OpenGL runtime. Do not mix SDKs or disable admission
checks. `ORBITER_NATIVE_BUILD_CONFIGURATION` must match the engine configuration.

Before building the engine in an isolated source copy:

```sh
python3 Native/prepare-engine.py \
  "$ORBITER_SOURCE/Src/Orbiter/Production/NativeApplication.cpp" \
  "$ENGINE_SOURCE/Src/Orbiter/Production/NativeApplication.cpp"
patch -d "$ENGINE_SOURCE" -p1 < Native/thruster-removal.patch
patch -d "$ENGINE_SOURCE" -p1 < Native/initial-vessels.patch
```

The first script admits only real Mercury native modules and gives running
vessels their Space command before the convenience pause shortcut. Space resumes
when paused; Ctrl-P always pauses. The patch fixes invalidated iterators when
removing thrusters from groups during staging. These are actual Orbiter engine
changes, not replacement flight dynamics in the add-on. The OpenGL patch also
registers initial vessels immediately, so exterior vessels and pads appear on
the first frame instead of waiting for the Solar System visibility scan.

Build the engine with `ORBITER_BUILD_NATIVE_VESSELS`,
`ORBITER_BUILD_NATIVE_CELESTIAL_MODULES` and `ORBITER_BUILD_NATIVE_COCKPIT` enabled,
and build `OVP/OGLClient/Native` against that engine. Use the engine's pinned
reference-math, Lua, ImGui, ImPlot and renderer dependency archives.

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DORBITER_NATIVE_SOURCE_DIR="$ENGINE_SOURCE" \
  -DORBITER_NATIVE_BUILD_DIR="$ENGINE_BUILD"
cmake --build build --parallel
python3 Native/install-runtime.py "$ENGINE_BUILD" build "$RUNTIME"
python3 Native/stage-assets.py ProjectMercuryX-download.zip "$RUNTIME"
```

`RUNTIME` is a private copy of an Orbiter native runtime, with its normal
`launch-orbiter` entry point, launcher profile, stock resources, celestial data,
planet tiles, keymap and runtime libraries. Set its active modules list to the
plugins you actually installed; Mercury requires native XRSound, which the engine
loads automatically. The add-on build also builds that actual XRSound plugin with
a small SDK/ABI-checked client export for Mercury's OrbiterSound callouts.

Fifteen modules are built: Redstone, Atlas, Little Joe, Scout, their boosters,
LC-5, LC-14, the Little Joe ramp, escape tower, drogue cover, main chute and
inert separated parts. The old standalone `MercuryOnlyCapsule.cpp` is not built:
the released standalone capsule configurations use the Atlas module instead.
Jupiter/Titan scenarios additionally require Multistage2015, which is not ported
by this work.

## Launch and fly

Run `launch-orbiter`, select **Project Mercury → Historical launch scenarios**,
choose a mission and click Launch. Resize, pause/resume and Ctrl-S quicksave use
the normal launcher and native engine. Press **P** to start the launch autopilot.
For the original countdown scenarios, wait 60 simulated seconds before pressing
P. Atlas includes the pad hold-down interval.

**Space** commands the Mercury retrosequence in free flight, with the normal
30-second delay before retrofire. **Ctrl-P** pauses. The original panel switches,
ASCS modes, staging controls, mission targeting and manuals still apply. There is
no new flight model or scripted trajectory correction in this port.

## GitHub Actions

Every pull request to `codex/native-linux-opengl` runs **Native Linux OpenGL**.
The build uses NASSP’s pinned shared Orbiter source, applies the merged Orbiter
`DelThruster` fix and the Mercury host integration in the CI checkout, and builds
the matching SDK, OpenGL client, launcher, XRSound bridge and all 15 vessel modules.

The flight job downloads the original Mercury distribution from the publisher,
checks its SHA-256, and flies the nine replays listed below. The cockpit checks
use the Friendship 7 pre-retro save produced by that run. The launcher opens the
six original missions and all nine generated saves. Every session runs under Xvfb
and Mesa software OpenGL with its own PulseAudio null sink verified at 5%.

The Actions run publishes the measured flight results, cockpit event times,
launcher results and audio logs in `mercury-flight-evidence`. The workflow also
runs after a merge and can be started from the Actions tab.

## Verification

`verification/run-session.sh RUNTIME CASE TICKS [STEP] [RENDER_EVERY]` replays
`CASE/input.scn` and `CASE/replay.csv`, writes the final save, native flight
telemetry, renderer evidence and XRSound log. It uses an isolated PulseAudio null
sink at 5% and an Xvfb X11 display. It never changes the desktop volume.
Required tools: Python 3, Xvfb, xauth, xwininfo, libX11, libXtst, PulseAudio and
pactl, plus Pillow for screenshots. The `launcher` mode checks all six original historical scenarios and nine verified saves through
the normal GUI, verifies native modules, resizes, resumes, quicksaves and exits.

See `verification/results.json` for the measured qualification results and scope.

To test the RETRO SEQ cockpit button with the verified Friendship 7 pre-retro
save, run the following command with a fresh output directory. It checks a
same-frame click, a two-second hold, and a click outside the button against
the three retro motor cover releases.

```sh
python3 Native/verification/retro-panel.py "$PACKAGE" \
  "$PACKAGE/resources/Scenarios/Mercury - Native Linux Saves/05 Friendship 7 - before retrosequence.scn" \
  "$CHECKS/retro-panel"
```


The initial qualification passed **9 flight replays and 15 launcher checks**:

| Mission | Flight coverage |
| --- | --- |
| Freedom 7 | Original launch, linked ascent save, retrosequence, reentry, chutes and splashdown |
| Liberty Bell 7 | Continuous original launch through retrosequence, reentry, chutes and splashdown |
| Friendship 7 | Original Atlas ascent, Earth orbit, 15,100-second coast, retrosequence, reentry and splashdown on one linked save chain |
| Aurora 7, Sigma 7, Faith 7 | Original Atlas ascent and orbital insertion |

Every original historical scenario and all nine generated checkpoint saves also
passed launch paused, resize to 1180×720, keyboard resume, quicksave and clean
exit from the normal launcher. Both exterior and cockpit images were inspected.
The tests use software OpenGL (Mesa llvmpipe) with actual Orbiter vessel modules,
physics, textures and original launch-pad meshes.

The generated package has **Mercury - Native Linux Saves** alongside the original
**Project Mercury** scenarios. `05 Friendship 7 - before retrosequence` begins at
MET 4:25:36; the verified replay advances 414 seconds, presses Space at 4:32:30,
and allows the normal 30-second delay before retrofire. Ctrl-P pauses without
commanding the spacecraft. Original assets and generated saves stay in the local
package; the fork contains source, checksums, replay tooling and measured results.

This is initial Linux qualification. Complete Aurora 7, Sigma 7 and Faith 7
missions, Little Joe/Scout flights, Windows/macOS builds, and historical numerical
parity remain unqualified. The original source's flight-history summary resets
across reloads; trajectory qualification therefore uses the native telemetry and
linked save chain rather than treating that summary as a continuous flight log.


To reproduce the flight suite and package from a staged private runtime:

```sh
python3 Native/verification/run-suite.py "$RUNTIME" "$REPLAYS"
python3 Native/package-runtime.py "$RUNTIME" "$REPLAYS" "$PACKAGE"
MERCURY_LAUNCHER_MANIFEST="$PACKAGE/qualification/launcher-manifest.json" \
  Native/verification/run-session.sh "$PACKAGE" "$CHECKS" launcher
```

The package helper excludes unrelated Apollo resources from a reused NASSP
runtime template. It keeps the original Mercury asset documentation, GPL source
license, asset attribution and separate save/scenario licensing. It refuses to
overwrite an existing package. `Native/verification/results.json` records the
initial qualified build; a newly built package receives its own measured report.
