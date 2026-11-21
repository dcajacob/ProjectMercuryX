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
checks its SHA-256, and flies the 15 replays listed below. The cockpit checks
use the Friendship 7 pre-retro save produced by that run. The launcher opens the
six original missions and all 15 generated saves. Every session runs under Xvfb
and Mesa software OpenGL with its own PulseAudio null sink verified at 5%.

The reload checks follow each Atlas recovery target from the original Aurora 7,
Sigma 7 and Faith 7 scenarios through their generated saves. On Faith 7 they
interrupt the retrosequence and compare the motor firings after reload with
the uninterrupted flight. Older saves are still readable. Regenerate old
checkpoints from the original mission to recover target or countdown data
that the previous version omitted.

Every flight records the native runtime and module hashes, including the Atlas
and Redstone libraries. Packaging checks each replay record against the supplied
build and its input, controls and final save. A missing record or changed binary
requires a fresh run. The launcher check uses the manifest generated in the
package; set `MERCURY_LAUNCHER_MANIFEST` to select a different one.

The Actions run publishes the measured flight and reload results, cockpit event
times, binary hashes, launcher results and audio logs in `mercury-flight-evidence`. The workflow also
runs after a merge and can be started from the Actions tab.

## Verification

`verification/run-session.sh RUNTIME CASE TICKS [STEP] [RENDER_EVERY]` replays
`CASE/input.scn` and `CASE/replay.csv`, writes the final save, native flight
telemetry, renderer evidence and XRSound log. It uses an isolated PulseAudio null
sink at 5% and an Xvfb X11 display. It never changes the desktop volume.
Required tools: Python 3, Xvfb, xauth, xwininfo, libX11, libXtst, PulseAudio and
pactl, plus Pillow for screenshots. With the generated package manifest, `launcher` mode checks all six original historical scenarios and 15 verified saves through
the normal GUI, verifies native modules, resizes, resumes, quicksaves and exits.

Each package contains its measured results in `qualification/results.json`. The same
report is available in the Actions artifact as `flight-results.json`.

To test the RETRO SEQ cockpit button with the verified Friendship 7 pre-retro
save, run the following command with a fresh output directory. It checks a
same-frame click, a two-second hold, and a click outside the button against
the three retro motor cover releases.

```sh
python3 Native/verification/retro-panel.py "$PACKAGE" \
  "$PACKAGE/resources/Scenarios/Mercury - Native Linux Saves/05 Friendship 7 - before retrosequence.scn" \
  "$CHECKS/retro-panel"
```


The suite covers **15 flight replays and 21 launcher checks**.

| Mission | Flight coverage |
| --- | --- |
| Freedom 7 | Original launch, linked ascent save, retrosequence, reentry, chutes and splashdown |
| Liberty Bell 7 | Continuous original launch through retrosequence, reentry, chutes and splashdown |
| Friendship 7 | Original Atlas ascent, Earth orbit, 15,100-second coast, retrosequence, reentry and splashdown on one linked save chain |
| Aurora 7, Sigma 7, Faith 7 | Each original Atlas ascent and insertion save, linked coast to the pre-retro checkpoint, three retro motor firings, reentry, drogue, main chute and ocean contact |

The launcher opens each original scenario and generated checkpoint paused, resizes
to 1180×720, resumes with the keyboard, quicksaves and exits.
The tests use software OpenGL (Mesa llvmpipe) with actual Orbiter vessel modules,
physics, textures and original launch-pad meshes.

The generated package has **Mercury - Native Linux Saves** alongside the original
**Project Mercury** scenarios. `05 Friendship 7 - before retrosequence` begins at
MET 4:25:36; the verified replay advances 414 seconds, presses Space at 4:32:30,
and allows the normal 30-second delay before retrofire. Ctrl-P pauses without
commanding the spacecraft. Original assets and generated saves stay in the local
package; the fork contains source, checksums, replay tooling and measured results.

For Aurora 7, Sigma 7 and Faith 7, select saves **10–15** for the pre-retro and
splashdown checkpoints. Each replay coasts at a 0.125-second physics step, reloads
its own checkpoint, then uses the normal Space command and a 0.0625-second step
for entry. Aurora 7 and Sigma 7 command retrosequence at 04:32:36.5 and
08:51:30 mission elapsed time, following the
[NASA Historical Data Book, volume II](https://www.nasa.gov/wp-content/uploads/2023/04/sp-4012v2.pdf).
The verifier checks the 30-second delay, five-second motor spacing, post-burn
perigee below 60 km, both chutes and first ocean contact.

**Faith 7 recovery.** Save 09 is the verified insertion orbit. Its apogee is
298 km and its inclination is 28.96°. The original mission description gives
267 km and 32.55°. At the historical 33:58:59 command the simulated capsule
splashed down at 28.9193° N, 142.5729° E, 3,988 km from the ship. The panel
had no solution on that pass. The linked replay uses the preceding Pacific
pass. Open save 14 at 32:21:40 and press Space at the panel's retrosequence
time (32:34:04 on the verified save). The capsule fires all three motors and
splashes down near 27.13° N, 176.71° W. The target in the original scenario is
27.377° N, 176.588° W.

CI reads the Atlas panel's geographic solution at the end of the coast and
fails if the panel gives no upcoming time. It measures the great-circle miss
from the focus capsule's first ocean contact to the original scenario target.
The 50 km regression limit applies to this native Faith 7 replay. The report
includes the command time, target, first-contact coordinates and miss distance.

The replays fly nominal controls. Historical equipment failures, landing-site
accuracy for other missions, Little Joe/Scout flights, Windows/macOS builds and
historical numerical parity remain unqualified. The original source's flight-history summary resets
across reloads; trajectory qualification therefore uses the native telemetry and
linked save chain rather than treating that summary as a continuous flight log.


To reproduce the flight suite and package from a staged private runtime:

```sh
python3 Native/verification/run-suite.py "$RUNTIME" "$REPLAYS"
python3 Native/package-runtime.py "$RUNTIME" "$REPLAYS" "$PACKAGE"
python3 Native/verification/reload-state.py "$RUNTIME" "$REPLAYS" "$CHECKS/reload-state"
Native/verification/run-session.sh "$PACKAGE" "$CHECKS/launcher" launcher
```

The package helper excludes unrelated Apollo resources from a reused NASSP
runtime template. It keeps the original Mercury asset documentation, GPL source
license, asset attribution and separate save/scenario licensing. It refuses to
overwrite an existing package. `Native/verification/results.json` records the
initial qualified build; a newly built package receives its own measured report.
