"""Check the Friendship 7 retrosequence button from the verified pre-retro save."""
import argparse
import csv
import re
import subprocess
from pathlib import Path


def run(runtime, scenario, output, name, x, release_after, expected):
    case = output / name
    case.mkdir(parents=True)
    (case / 'input.scn').write_text(scenario)
    # Panel point (45, 330), fitted to the 1280 x 720 verification viewport.
    tick, y = 6624, 165
    with (case / 'replay.csv').open('w', newline='') as stream:
        rows = csv.writer(stream, lineterminator='\n')
        rows.writerow(['tick', 'phase', 'action', 'value'])
        rows.writerow([tick, 'before', 'mouse', f'left_down {x} {y}'])
        rows.writerow([tick + release_after, 'before', 'mouse', f'left_up {x} {y}'])
        rows.writerow([7519, 'after', 'save', 0])
    runner = Path(__file__).with_name('run-session.sh')
    subprocess.run([runner, runtime, case, '7520', '.0625', '257'], check=True)
    with (case / 'evidence/lifetime-events.csv').open() as stream:
        events = [(r['object'], float(r['seconds'])) for r in csv.DictReader(stream)
                  if r['phase'] == 'module.library.open' and r['object'].startswith('MA-6 Retrocover ')]
    # The vessel releases each cover only when that motor has positive thrust.
    assert [obj for obj, _ in events] == [f'MA-6 Retrocover {i}' for i in expected], (name, events)
    for i, (_, seconds) in zip(expected, events):
        assert abs(seconds - (tick / 16 + 30 + 5 * (i - 1))) <= .1875, (name, events)
    assert 'END_SHIPS' in (case / 'saved.scn').read_text()
    print(f'{name}: {events}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('runtime', 'save', 'output'):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    scenario = args.save.read_text()
    assert re.search(r'^\s*Ship MA-6\s*$', scenario, re.M)
    assert re.search(r'^\s*MET 15936\s*$', scenario, re.M)
    camera = 'BEGIN_CAMERA\n  TARGET MA-6\n  MODE Cockpit\n  FOV 40.00\nEND_CAMERA'
    scenario, count = re.subn(r'BEGIN_CAMERA\n.*?END_CAMERA', camera, scenario, flags=re.S)
    assert count == 1
    if 'BEGIN_PANEL' not in scenario:
        scenario = scenario.replace('BEGIN_SHIPS\n', 'BEGIN_PANEL\nEND_PANEL\n\nBEGIN_SHIPS\n', 1)
    for name, x, release_after, expected in [
        ('quick-click', 122, 0, [1, 2, 3]),
        ('held-click', 122, 32, [1, 2, 3]),
        ('outside', 151, 0, []),
    ]:
        run(args.runtime.resolve(), scenario, args.output.resolve(), name, x, release_after, expected)
