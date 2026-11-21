"""Exercise the package preflight with missing, stale and mismatched replay evidence."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from runtime_provenance import RECORD, runtime_hashes, verify_record


scripts = Path(__file__).resolve().parent
source = Path(sys.argv[1]).resolve()
atlas = Path('engine/NativeModules/Vessel/ProjectMercury/ProjectMercuryAtlas.so')


def expect_rejection(runtime, case, package, reason):
    result = subprocess.run([sys.executable, scripts.parent/'package-runtime.py', runtime, case.parent, package],
                            capture_output=True, text=True)
    if result.returncode == 0 or reason not in result.stderr or package.exists():
        raise RuntimeError(f'Expected package rejection for {reason!r}, got {result.returncode}: {result.stderr}')
    print(f'PASS package rejected {reason}')


with tempfile.TemporaryDirectory(prefix='mercury-provenance-') as temp:
    scratch = Path(temp)
    runtime, package = scratch/'runtime', scratch/'package'
    case = scratch/'replays/freedom7-launch'
    case.mkdir(parents=True)
    for name in runtime_hashes(source):
        destination = runtime/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source/name, destination)

    # These short files exercise the identity check only. Full flight telemetry
    # and trajectory verification still run in the flight job.
    for name in ('input.scn', 'replay.csv', 'saved.scn'):
        (case/name).write_text(f'{name} fixture\n')
    expect_rejection(runtime, case, package, f'missing {RECORD}')
    recorder = scripts/'runtime_provenance.py'
    pending = scratch/'pending.json'
    for action in ('start', 'finish'):
        subprocess.run([sys.executable, recorder, action, runtime, case, pending], check=True)
    verify_record(case, runtime_hashes(runtime))

    with (runtime/atlas).open('ab') as stream:
        stream.write(b'changed module')
    expect_rejection(runtime, case, package, f'runtime mismatch: {atlas}')
    shutil.copy2(source/atlas, runtime/atlas)
    (case/'saved.scn').write_text('different checkpoint\n')
    expect_rejection(runtime, case, package, 'saved.scn differs')
