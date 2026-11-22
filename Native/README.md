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
For Aurora 7, press **P** 57 seconds into the countdown (T−3). The verified
replays for the other missions press **P** after 60 seconds.

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
pactl, plus Pillow for screenshots. With the generated package manifest, `launcher` mode checks all six historical launch scenarios and 15 verified saves through
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
| Aurora 7, Sigma 7, Faith 7 | Each historical Atlas ascent and insertion save, linked coast to the pre-retro checkpoint, three retro motor firings, reentry, drogue, main chute and ocean contact |

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

**Atlas insertion and recovery.** Launch Aurora 7, Sigma 7 or Faith 7 from LC-14
with **P** at the end of the original countdown. The publisher's three mission
histories specify 32.55° inclination. Their scenario inputs supply geographic
recovery coordinates and omit the ascent inclination, which lets Mercury use
the recovery position to choose the launch plane. Asset staging adds
`INCLINATION 32.55` to the nominal and possible-failures launch scenarios.
The landing computer keeps each scenario's original recovery coordinates.

CI flies the nominal scenarios at the normal launcher's 60 Hz rate through
insertion, coasts from the resulting save at 8 Hz with nonspherical Earth
gravity, then reloads the coast save and flies retrofire and entry at 60 Hz.
Saves **07–09** open in Earth orbit. CI checks equatorial inclination
(32.55° ± 0.10°) and measures altitude extrema above mean Earth radius on the
first coast orbit. The time between consecutive apogees provides the period.
The perigee, apogee and period tolerances are 3 km, 5 km and 10 s, respectively.

| Mission and recovery pass | Reference orbit, km | Reference period | Pre-retro / splashdown saves | Verified Space command, MET | First contact from scenario target / CI limit |
|---|---:|---:|---|---:|---:|
| Aurora 7, orbit 3 | 160.84 × 268.55 | 88 min 32 s | 10 / 11 | 04:33:12 | 66.6 / 50 km (fails) |
| Sigma 7, orbit 6 | 161.00 × 283.04 | 88 min 55 s | 12 / 13 | 08:51:21 | 45.4 / 50 km |
| Faith 7, orbit 22 | 161.42 × 266.99 | 88 min 45 s | 14 / 15 | 33:59:09 | 33.3 / 50 km |

From each pre-retro save, press **Space** at the displayed cockpit retrosequence
time. CI reads the panel at the checkpoint, requires a command within 60 s of
the historical event, and checks the 30 s delay, five-second motor spacing,
post-burn perigee below 60 km, both chutes, and the first ocean contact.
The recovery limits in the table are simulator regression tolerances.

The MA-7 countdown begins at 12:44:16 UTC. Press **P** at T−3 s. The nominal
replay misses the 50 km gate even with the corrected launch epoch.

Aurora 7's scenario coordinate (19.45° N, 63.83° W) is near Carpenter's actual
splashdown. NASA records that he landed about 400 km from the intended point.
This nominal replay uses the scenario coordinate and normal spacecraft systems.
Sigma 7 targets 32.10° N, 174.47° W. As a timing comparison, commanding at the
published event times of 04:32:36.5 and 08:51:30 yielded simulated misses of
356.6 and 41.3 km respectively. The references are in the
[NASA Historical Data Book, volume II, tables 2-33 to 2-35](https://www.nasa.gov/wp-content/uploads/2023/04/sp-4012v2.pdf).

Save **14** starts at MET 33:58:29. Read the cockpit clock and press **Space**
at **33:59:09** on the verified replay, ten seconds after the historical
33:58:59 event. The five-minute forecast still read 33:58:59; flying that
earlier reading at 60 Hz gave a 109 km miss. CI reads the late panel solution
from the coast, requires a command within one minute of the historical time,
and checks first ocean contact within 50 km of the original target. Save **15** opens
at splashdown. The machine-readable report includes the clock offset, first
contact, target coordinates, and great-circle miss. The times and historical
apsides are in [NASA Historical Data Book, table 2-35](https://www.nasa.gov/wp-content/uploads/2023/04/sp-4012v2.pdf).

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
