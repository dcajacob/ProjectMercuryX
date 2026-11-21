"""Identify the native build, controls and checkpoint used by a Mercury replay."""
import hashlib
import json
import sys
from pathlib import Path


RECORD = 'runtime-provenance.json'
OMITTED_VESSELS = ('ProjectApollo', 'VesselBuilder1')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_hashes(runtime):
    engine = runtime / 'engine'
    modules = engine / 'NativeModules'
    vessels = modules / 'Vessel'
    paths = {runtime / name for name in ('Orbiter.cfg', 'Keymap.cfg', 'launch-orbiter', 'orbiter-profile.json')}
    paths.update(engine / name for name in (
        'orbiter-production', 'orbiter-launchpad', 'run-orbiter', 'liborbiter_production_boundary.so',
        'liborbiter_production_vessels.so', 'native-lua/liblua.so'))
    paths.update(modules / name for name in (
        'Graphics/OGLClient.so', 'Plugin/XRSound.so', 'Vessel/ProjectMercury/ProjectMercuryAtlas.so',
        'Vessel/ProjectMercury/ProjectMercuryRedstone.so'))
    omitted = [vessels / name for name in OMITTED_VESSELS]
    for path in engine.rglob('*.so*'):
        if path.is_file() and not any(parent in path.parents for parent in omitted):
            paths.add(path)
    paths.update(path for path in (runtime/'resources/Modules/OGLClient').rglob('*') if path.is_file())
    return {path.relative_to(runtime).as_posix(): sha256(path) for path in sorted(paths)}


def check_runtime(recorded, current, label):
    if recorded != current:
        changed = [key for key in sorted(recorded.keys() | current.keys()) if recorded.get(key) != current.get(key)]
        raise ValueError(f'{label}: runtime mismatch: {", ".join(changed)}')


def verify_record(case, current):
    path = case / RECORD
    if not path.is_file():
        raise ValueError(f'{case.name}: missing {RECORD}; rerun the flight with this build')
    record = json.loads(path.read_text())
    check_runtime(record['runtime_sha256'], current, case.name)
    for name in ('input.scn', 'replay.csv', 'saved.scn'):
        if record['flight_sha256'].get(name) != sha256(case / name):
            raise ValueError(f'{case.name}: {name} differs from the completed replay')
    return record['flight_sha256']


def main():
    action, runtime_arg, case_arg, scratch_arg = sys.argv[1:]
    runtime, case, scratch = map(Path, (runtime_arg, case_arg, scratch_arg))
    current = runtime_hashes(runtime)
    inputs = {name: sha256(case / name) for name in ('input.scn', 'replay.csv')}
    if action == 'start':
        scratch.write_text(json.dumps({'runtime_sha256': current, 'flight_sha256': inputs}, indent=2) + '\n')
    elif action == 'finish':
        record = json.loads(scratch.read_text())
        check_runtime(record['runtime_sha256'], current, case.name)
        if record['flight_sha256'] != inputs:
            raise ValueError(f'{case.name}: replay input changed during the flight')
        save = case / 'saved.scn'
        if save.is_file():
            record['flight_sha256'][save.name] = sha256(save)
        scratch.write_text(json.dumps(record, indent=2) + '\n')
        scratch.replace(case / RECORD)
    else:
        raise ValueError(f'Unknown provenance action: {action}')


if __name__ == '__main__':
    main()
