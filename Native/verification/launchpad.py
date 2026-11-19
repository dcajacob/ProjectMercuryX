from PIL import ImageGrab
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

root = Path(sys.argv[1]).resolve()
case = Path(sys.argv[2]).resolve()
case.mkdir(parents=True, exist_ok=True)

xlib = c.CDLL("libX11.so.6")
xtst = c.CDLL("libXtst.so.6")
xlib.XOpenDisplay.argtypes = [c.c_char_p]
xlib.XOpenDisplay.restype = c.c_void_p
xlib.XFlush.argtypes = [c.c_void_p]
xlib.XSetInputFocus.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_ulong]
xlib.XKeysymToKeycode.argtypes = [c.c_void_p, c.c_ulong]
xlib.XKeysymToKeycode.restype = c.c_uint
xtst.XTestFakeMotionEvent.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_ulong]
xtst.XTestFakeButtonEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
xtst.XTestFakeKeyEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
class ClientMessage(c.Structure):
    _fields_ = [("type", c.c_int), ("serial", c.c_ulong), ("send_event", c.c_int),
                ("display", c.c_void_p), ("window", c.c_ulong), ("message_type", c.c_ulong),
                ("format", c.c_int), ("data", c.c_long * 5)]

class XEvent(c.Union):
    _fields_ = [("client", ClientMessage), ("padding", c.c_long * 24)]

xlib.XInternAtom.argtypes = [c.c_void_p, c.c_char_p, c.c_int]
xlib.XInternAtom.restype = c.c_ulong
xlib.XSendEvent.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_long, c.POINTER(XEvent)]
xlib.XResizeWindow.argtypes = [c.c_void_p, c.c_ulong, c.c_uint, c.c_uint]
display = xlib.XOpenDisplay(None)
assert display

def find_window(title):
    tree = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
    for row in tree.splitlines():
        if title in row and (matched := re.search(r"0x[0-9a-f]+", row)):
            info = subprocess.check_output(["xwininfo", "-id", matched[0]], text=True)
            if "Map State: IsViewable" in info and int(re.search(r"Width:\s+(\d+)", info)[1]) > 300:
                return int(matched[0], 16), row.strip()
    return None

def wait_window(title, process):
    for _ in range(480):
        found = find_window(title)
        if found is not None:
            return found
        assert process.poll() is None
        time.sleep(.25)
    tree = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
    raise RuntimeError(f"Missing window {title}\n{tree}")

def keys(window, *syms):
    xlib.XSetInputFocus(display, window, 1, 0)
    codes = [xlib.XKeysymToKeycode(display, sym) for sym in syms]
    for key in codes:
        xtst.XTestFakeKeyEvent(display, key, 1, 0)
    xlib.XFlush(display)
    time.sleep(.18)
    for key in codes[::-1]:
        xtst.XTestFakeKeyEvent(display, key, 0, 0)
    xlib.XFlush(display)

def close(window):
    event = XEvent()
    event.client.type = 33
    event.client.display = display
    event.client.window = window
    event.client.message_type = xlib.XInternAtom(display, b"WM_PROTOCOLS", 0)
    event.client.format = 32
    event.client.data[0] = xlib.XInternAtom(display, b"WM_DELETE_WINDOW", 0)
    assert xlib.XSendEvent(display, window, 0, 0, c.byref(event))
    xlib.XFlush(display)

results_file = case / "results.json"
results = []
manifest = json.loads(Path(sys.argv[3]).read_text())
limit=int(os.environ.get("MERCURY_LAUNCHER_LIMIT",len(manifest)))
for index, fixture in enumerate(manifest[:limit], 1):
    name = f"checkpoint-{index:02d}"
    scenario = root / fixture["scenario"]
    assert hashlib.sha256(scenario.read_bytes()).hexdigest() == fixture["scenario_sha256"]
    home = case / name
    settings = home / "Orbiter/Orbiter Launchpad.conf"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(f"[simulator]\nlastScenario={scenario}\nstartPaused=true\n")
    env = dict(os.environ, XDG_CONFIG_HOME=str(home))
    logpath = root / "user/orbiter-session.log"
    audio_log = root / "user/XRSound.log"
    savepath = root / "user/Scenarios/Quicksave.scn"
    assert not savepath.exists()
    output = (home / "launcher.log").open("w")
    gui = subprocess.Popen([str(root / "launch-orbiter")], env=env,
                           stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        launcher, _ = wait_window('"Orbiter Launchpad"', gui)
        time.sleep(.35)
        details = subprocess.check_output(["xwininfo", "-id", hex(launcher)], text=True)
        values = [int(re.search(regex + r"\s+(-?\d+)", details)[1]) for regex in
                  ("Absolute upper-left X:", "Absolute upper-left Y:", "Width:", "Height:")]
        x, y, w, h = values
        xlib.XSetInputFocus(display, launcher, 1, 0)
        xtst.XTestFakeMotionEvent(display, -1, x + w - 65, y + h - 22, 0)
        xtst.XTestFakeButtonEvent(display, 1, 1, 0)
        xtst.XTestFakeButtonEvent(display, 1, 0, 0)
        xlib.XFlush(display)
        window, title = wait_window('"Orbiter |', gui)
        assert "PAUSED" in title, title
        children = Path(f"/proc/{gui.pid}/task/{gui.pid}/children").read_text().split()
        assert len(children) == 1, children
        pid = children[0]
        args = Path(f"/proc/{pid}/cmdline").read_bytes().decode().strip("\0").split("\0")
        assert args[0] == str(root / "engine/orbiter-production"), args
        assert args[args.index("--scenario") + 1] == str(scenario), args
        assert args[args.index("--modules") + 1] == str(root / "engine/NativeModules"), args
        assert args[args.index("--xrsound-assets") + 1] == str(root / "resources"), args
        maps = Path(f"/proc/{pid}/maps").read_text()
        assert str(root / "engine/liborbiter_production_boundary.so") in maps
        for module in fixture["module"]:
            assert str(root / "engine/NativeModules/Vessel" / module) in maps, module
        assert str(root / "engine/NativeModules/Plugin/XRSound.so") in maps
        assert str(root / "engine/NativeModules/Graphics/OGLClient.so") in maps
        quicksave = None
        running_title = None
        if fixture["interactive"]:
            xlib.XResizeWindow(display, window, 1180, 720)
            xlib.XFlush(display)
            time.sleep(.75)
            resized = subprocess.check_output(["xwininfo", "-id", hex(window)], text=True)
            assert "Width: 1180" in resized and "Height: 720" in resized, resized
            keys(window, 0x0020)  # Space switches from the launcher's initial pause.
            _, running_title = wait_window("| RUNNING ", gui)
            if index == 1:
                ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((0,0,1180,720)).save(home / "external.png")
                keys(window, 0xffbe)  # F1: enter the vessel cockpit.
                keys(window, 0xffc5)  # F8: select the original 2D panel.
                time.sleep(.5)
                ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((0,0,1180,720)).save(home / "cockpit.png")
                keys(window, 0xffbe)
            keys(window, 0xffe3, 0x0073)
            for _ in range(240):
                if savepath.is_file() and b"END_SHIPS" in savepath.read_bytes():
                    break
                time.sleep(.25)
            assert savepath.is_file() and b"END_SHIPS" in savepath.read_bytes(), "No complete quicksave"
            mjd = re.compile(rb"^\s*Date MJD\s+([0-9.]+)", re.M)
            before = float(mjd.search(scenario.read_bytes())[1])
            after = float(mjd.search(savepath.read_bytes())[1])
            assert after > before, (before, after)
            if abort_vessel := fixture.get("vessel"):
                assert re.search(rf"^{re.escape(abort_vessel)}:", savepath.read_text(errors="replace"), re.M)
            saved = savepath.read_text(errors="replace")
            for state in fixture.get("saved_state", []):
                assert state in saved, state
            shutil.move(savepath, home / "Quicksave.scn")
            quicksave = (after-before)*86400
        close(window)
        for attempt in range(240):
            if not Path(f"/proc/{pid}").exists():
                break
            if attempt % 12 == 11:
                current = find_window('"Orbiter |')
                if current:
                    close(current[0])
            time.sleep(.25)
        assert not Path(f"/proc/{pid}").exists(), "Orbiter did not respond to window close"
        log = logpath.read_text(errors="replace")
        renderer = re.search(r"^Native OpenGL renderer:\s*(.*)$", log, re.M)
        assert renderer is not None, "No native OpenGL renderer recorded"
        shutil.move(logpath, home / "orbiter-session.log")
        audio = audio_log.read_text(errors="replace")
        assert "Successfully parsed configuration file" in audio and "terminating." in audio, audio
        if fixture["interactive"]:
            assert "initialized using sound driver PulseAudio" in audio, audio
        shutil.move(audio_log, home / "XRSound.log")
        results.append(dict(scenario=scenario.name, paused=title, resized="1180x720" if quicksave is not None else None, resumed=running_title,
                            simulated_seconds=quicksave, audio_backend="PulseAudio" if quicksave is not None else None,
                            result="passed", renderer=renderer[1], path=str(scenario.relative_to(root))))
        steps = " → resized → resumed → quicksaved" if quicksave is not None else ""
        print(f"PASS {index:02d} Launchpad → {scenario.name}{steps} → exited", flush=True)
    finally:
        try:
            os.killpg(gui.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            gui.wait(timeout=6)
        except subprocess.TimeoutExpired:
            os.killpg(gui.pid, signal.SIGKILL)
            gui.wait()
        output.close()
        for logfile in (logpath, audio_log):
            if logfile.exists():
                shutil.move(logfile, home / logfile.name)
        results_file.write_text(json.dumps(results, indent=2) + "\n")
