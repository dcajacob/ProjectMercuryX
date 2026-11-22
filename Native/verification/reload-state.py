"""Replay a Mercury countdown across two native Orbiter sessions and check mission targets."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from orbital_returns import FLIGHT_HZ, sequence_met


STEP = 1 / FLIGHT_HZ
SPACE = 57
RUNNER = Path(__file__).with_name('run-session.sh')


def capsule_fields(scenario, ship):
    text = scenario.read_text()
    block = re.search(rf'^{re.escape(ship)}:[^\n]+\n(.*?)^END$', text, re.M | re.S)
    if not block:
        raise ValueError(f'{scenario}: missing vessel {ship}')
    return dict(line.strip().split(maxsplit=1) for line in block[1].splitlines()
                if len(line.split(maxsplit=1)) == 2)


def recovery_target(scenario, ship):
    fields = capsule_fields(scenario, ship)
    try:
        return (int(fields['MISSIONORBITNR']), float(fields['MISSIONLANDLAT']),
                float(fields['MISSIONLANDLONG']))
    except KeyError as exc:
        raise ValueError(f'{scenario}: {ship} lost {exc.args[0]}') from exc


def check_target(scenario, ship, expected):
    orbits, latitude, longitude = recovery_target(scenario, ship)
    if (orbits != expected[0] or not math.isclose(latitude, expected[1], rel_tol=0, abs_tol=1e-6)
            or not abs(math.remainder(longitude - expected[2], 360)) <= 1e-6):
        raise ValueError(f'{scenario}: expected {expected}, got {(orbits, latitude, longitude)}')


def motor_events(case, ship):
    events = []
    with (case/'evidence/lifetime-events.csv').open() as stream:
        for row in csv.DictReader(stream):
            motor = re.fullmatch(rf'{re.escape(ship)} Retrocover ([1-3])', row['object'])
            # Restoring the previously separated cover at tick zero is an initial load.
            if motor and row['phase'] == 'module.library.open' and int(row['tick']) > 0:
                events.append((int(motor[1]), float(row['seconds']), float(row['mjd'])))
    return events


def segment(runtime, case, source, duration, command_tick=None):
    case.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, case/'input.scn')
    ticks = round(duration / STEP)
    with (case/'replay.csv').open('w', newline='') as stream:
        rows = csv.writer(stream, lineterminator='\n')
        rows.writerow(['tick', 'phase', 'action', 'value'])
        if command_tick is not None:
            rows.writerow([command_tick, 'before', 'key', SPACE])
            rows.writerow([command_tick + 1, 'before', 'key', -SPACE])
        rows.writerow([ticks - 1, 'after', 'save', 0])
    subprocess.run([RUNNER, runtime, case, str(ticks), str(STEP), '257'], check=True)
    with (case/'evidence/input-events.csv').open() as stream:
        presses = [int(r['tick']) for r in csv.DictReader(stream)
                   if r['key'] == str(SPACE) and r['down'] == '1']
    expected = [] if command_tick is None else [command_tick]
    if presses != expected:
        raise ValueError(f'{case}: expected Space presses at {expected}, got {presses}')
    return case/'saved.scn'


def check_armed(save, ship, remaining, cover_mask):
    state = capsule_fields(save, ship).get('RETROSEQUENCE', '').split()
    if (len(state) != 2 or not abs(float(state[0]) - remaining) <= STEP
            or int(state[1]) != cover_mask):
        raise ValueError(f'{save}: expected RETROSEQUENCE {remaining} {cover_mask}, got {state}')


def state_at(case, ship, seconds):
    with (case/'evidence/flight-state.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['object'] == ship and int(row['tick']) == round(seconds / STEP):
                return row
    raise ValueError(f'{case}: missing state for {ship} at {seconds} seconds')


def verify_targets(flights):
    targets = {}
    for mission, ship in [('aurora7', 'MA-7'), ('sigma7', 'MA-8'), ('faith7', 'MA-9')]:
        expected = recovery_target(flights/f'{mission}-launch'/'input.scn', ship)
        for phase in ('launch', 'coast', 'retro-entry'):
            scenario = flights/f'{mission}-{phase}'/'saved.scn'
            check_target(scenario, ship, expected)
            fields = capsule_fields(scenario, ship)
            if float(fields['INCLINATION']) != 32.55:
                raise ValueError(f'{scenario}: lost {ship} ascent inclination')
            if fields.get('LANDINGCOMPUTER', '').split() != ['1', '0', '0', '0']:
                raise ValueError(f'{scenario}: expected the original geographic targeting mode for {ship}')
        targets[mission] = dict(orbits=expected[0], latitude=expected[1], longitude=expected[2])
        print(f'PASS {ship} recovery target through insertion, coast and recovery: {expected}', flush=True)
    return targets


def verify_custom_target(runtime, source, output):
    # A user-authored scenario can override the geographic target and enter a
    # manual retro time. Exercise values distinct from every historical mission.
    ship = 'MA-9'
    expected = (17, -11.25, 151.625)
    manual_met = int(capsule_fields(source, ship)['MET']) + 450
    mode = f'0 0 {manual_met} 1'
    text = source.read_text()
    for key, value in [('MISSIONORBITNR', expected[0]), ('MISSIONLANDLAT', expected[1]),
                       ('MISSIONLANDLONG', expected[2]), ('LANDINGCOMPUTER', mode)]:
        text, count = re.subn(rf'^  {key} .+$', f'  {key} {value}', text, flags=re.M)
        if count != 1:
            raise ValueError(f'{source}: expected one {key}, found {count}')
    output.mkdir(parents=True, exist_ok=True)
    custom = output/'custom-target.scn'
    custom.write_text(text)
    saved = segment(runtime, output/'custom-target', custom, 1)
    check_target(saved, ship, expected)
    if capsule_fields(saved, ship).get('LANDINGCOMPUTER') != mode:
        raise ValueError(f'{saved}: lost custom landing-computer mode {mode}')
    print(f'PASS custom recovery target {expected} and manual retro time at MET {manual_met}', flush=True)
    return dict(orbits=expected[0], latitude=expected[1], longitude=expected[2], manual_retro_met=manual_met)


def verify_countdown(runtime, flights, output):
    ship = 'MA-9'
    reference = flights/'faith7-retro-entry'
    source = flights/'faith7-coast'/'saved.scn'
    if source.read_bytes() != (reference/'input.scn').read_bytes():
        raise ValueError('Faith 7 control and split flights have different starting saves')
    met = int(capsule_fields(source, ship)['MET'])
    command_seconds = sequence_met('faith7', source.parent) - met
    start = output/'armed'
    mid = output/'first-motor'
    end = output/'remaining-motors'
    armed = segment(runtime, start, source, command_seconds + 10, round(command_seconds / STEP))
    check_armed(armed, ship, 20, 0)
    burning = segment(runtime, mid, armed, 22.5)
    check_armed(burning, ship, -2.5, 1)
    segment(runtime, end, burning, 27.5)

    measured = []
    for case, offset, expected_motors in [(start, 0, []), (mid, command_seconds + 10, [1]),
                                          (end, command_seconds + 32.5, [2, 3])]:
        events = motor_events(case, ship)
        if [number for number, _, _ in events] != expected_motors:
            raise ValueError(f'{case}: expected motor releases {expected_motors}, got {events}')
        measured.extend((number, offset + seconds, mjd) for number, seconds, mjd in events)
    control = motor_events(reference, ship)
    if [number for number, _, _ in control] != [1, 2, 3]:
        raise ValueError(f'Incomplete uninterrupted Faith 7 retrosequence: {control}')
    for (motor, seconds, mjd), (_, ref_seconds, ref_mjd) in zip(measured, control):
        due = command_seconds + 30 + 5 * (motor - 1)
        if max(abs(seconds - due), abs(seconds - ref_seconds), abs(mjd - ref_mjd) * 86400) > 2 * STEP:
            raise ValueError(f'{ship} motor {motor} at {seconds}, control {ref_seconds}, expected {due}')

    # Cover releases show ignition. The final state also checks that motor one
    # delivered the rest of its burn after loading the second checkpoint.
    uninterrupted = state_at(reference, ship, command_seconds + 60)
    reloaded = state_at(end, ship, 27.5)
    velocity_error = math.dist([float(reloaded[k]) for k in ('vx', 'vy', 'vz')],
                               [float(uninterrupted[k]) for k in ('vx', 'vy', 'vz')])
    if not velocity_error <= 3:
        raise ValueError(f'{ship}: post-burn velocity differs from control by {velocity_error:.2f} m/s')
    report = dict(ship=ship, checkpoint_seconds_after_command=[10, 32.5],
                  control_motor_met_s=[met + t for _, t, _ in control],
                  reloaded_motor_met_s=[met + t for _, t, _ in measured],
                  post_burn_velocity_difference_mps=velocity_error)
    print(f'PASS {ship} interrupted countdown and in-burn reload: {report["reloaded_motor_met_s"]}, '
          f'post-burn velocity difference {velocity_error:.3f} m/s', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('runtime', 'flights', 'output'):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    flights = args.flights.resolve()
    output = args.output.resolve()
    targets = verify_targets(flights)
    runtime = args.runtime.resolve()
    manual = verify_custom_target(runtime, flights/'faith7-coast'/'saved.scn', output)
    report = verify_countdown(runtime, flights, output)
    report['recovery_targets'] = targets
    report['custom_recovery_target'] = manual
    (output/'results.json').write_text(json.dumps(report, indent=2) + '\n')
