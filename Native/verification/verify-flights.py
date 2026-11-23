#!/usr/bin/env python3
"""Check measured trajectories and recovery, rather than only process survival."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import re
import sys
from orbital_returns import CARPENTER_LIFTOFF_RANGE_S, CHECKPOINT_MET, FLIGHT_HZ, MISSIONS, RECOVERY_LIMIT_KM, carpenter_range_time, replay_time, sequence_met as planned_sequence_met
from runtime_provenance import runtime_hashes, verify_record
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('runtime', type=Path)
parser.add_argument('root', type=Path)
parser.add_argument('destination', type=Path)
parser.add_argument('--carpenter-only', action='store_true')
args = parser.parse_args()
runtime, root, destination = args.runtime, args.root, args.destination
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mu=3.986004418e14
earth_radius=6371010.0

def orbit(row):
    r=[float(row[k]) for k in ['rx','ry','rz']]
    v=[float(row[k]) for k in ['vx','vy','vz']]
    radius=math.sqrt(sum(x*x for x in r));speed2=sum(x*x for x in v)
    a=1/(2/radius-speed2/mu)
    h=[r[1]*v[2]-r[2]*v[1],r[2]*v[0]-r[0]*v[2],r[0]*v[1]-r[1]*v[0]]
    e=math.sqrt(max(0,1-sum(x*x for x in h)/(mu*a)))
    return {'perigee_km':(a*(1-e)-earth_radius)/1000,'apogee_km':(a*(1+e)-earth_radius)/1000}

def insertion_inclination(case, state):
    # Positions/velocities are ecliptic and Orbiter uses left-handed axes.
    # Column two of the obliquity matrix is Earth's north pole in that frame.
    with (case/'evidence/ground-math.csv').open() as stream:
        earth = next(r for r in csv.DictReader(stream) if r['tick'] == state['tick'])
    r = [float(state['r' + axis]) for axis in 'xyz']
    v = [float(state['v' + axis]) for axis in 'xyz']
    h = [v[1]*r[2] - v[2]*r[1], v[2]*r[0] - v[0]*r[2], v[0]*r[1] - v[1]*r[0]]
    cosine = sum(h[i] * float(earth[f'obliquity{i+1}2']) for i in range(3)) / math.hypot(*h)
    inclination = math.degrees(math.acos(cosine))
    if abs(inclination - 32.55) > 0.1:
        raise ValueError(f'{case.name} insertion inclination {inclination:.3f} degrees, expected 32.55 ± 0.10')
    return inclination


def first_orbit(case, reference):
    # With harmonics on, two-body osculating apsides at insertion are not
    # the altitudes the capsule reaches. Measure both from the linked coast.
    period = reference.period_s
    perigee = math.inf
    peaks = [(-math.inf, 0), (-math.inf, 0)]
    with (case/'evidence/flight-state.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['object'] != reference.ship:
                continue
            t = float(row['seconds'])
            if t >= 2 * period:
                break
            altitude = float(row['altitude_mean']) / 1000
            window = int(t // period)
            peaks[window] = max(peaks[window], (altitude, t))
            if window == 0:
                perigee = min(perigee, altitude)
    apogee = peaks[0][0]
    measured_period = peaks[1][1] - peaks[0][1]
    within_limits = (abs(perigee - reference.perigee_km) <= 3 and abs(apogee - reference.apogee_km) <= 5
                     and abs(measured_period - period) <= 10)
    if not within_limits and not args.carpenter_only:
        raise ValueError(f'{case.name} observed orbit {perigee:.2f} x {apogee:.2f} km, '
                         f'apogee-to-apogee period {measured_period:.2f} s')
    return dict(first_orbit_perigee_km=perigee, first_orbit_apogee_km=apogee,
                apogee_to_apogee_period_s=measured_period, first_orbit_within_limits=within_limits)


def is_ocean(latitude, longitude):
    # Count coastline crossings along a meridian to the North Pole (ocean).
    # Orbiter's map contains open polylines, including breaks at the dateline.
    crossings = 0
    with (runtime/'resources/Config/Earth/Data/coast.vec').open() as lines:
        next(lines)  # total vertices
        segments = int(next(lines).split()[0])
        for _ in range(segments):
            vertices = int(next(lines))
            previous = None
            for _ in range(vertices):
                lon, lat = map(float, next(lines).split())
                x = (lon - longitude + 180) % 360 - 180
                if previous is not None:
                    px, py = previous
                    if (x > 0) != (px > 0) and abs(x - px) < 180:
                        crossing_lat = py - px * (lat - py) / (x - px)
                        crossings += crossing_lat > latitude
                previous = x, lat
    return crossings % 2 == 0

def verify_retro_entry(case, ship, start_met, sequence_met, first, after_burn, touchdown, original, hz, max_miss_km, carpenter=False):
    sequence_seconds = sequence_met - start_met
    with (case/'evidence/input-events.csv').open() as stream:
        presses = [int(r['tick']) for r in csv.DictReader(stream) if r['key'] == '57' and r['down'] == '1']
    assert presses == [round(sequence_seconds * hz)], (case, presses)
    with (case/'evidence/lifetime-events.csv').open() as stream:
        covers = [(r['object'], float(r['seconds'])) for r in csv.DictReader(stream)
                  if r['phase'] == 'module.library.open' and r['object'].startswith(f'{ship} Retrocover ')]
    assert [obj for obj, _ in covers] == [f'{ship} Retrocover {i}' for i in (1, 2, 3)], (case, covers)
    delays = (33.8, 38.8, 44.0) if carpenter else (30, 35, 40)
    for (_, seconds), delay in zip(covers, delays):
        assert abs(seconds - (sequence_seconds + delay)) <= .1875, (case, covers)
    assert first['ground'] == '0' and orbit(first)['perigee_km'] > 140, case
    assert after_burn is not None and touchdown is not None, case
    perigee = orbit(after_burn)['perigee_km']
    assert perigee < 60, (case, perigee)
    assert float(after_burn['seconds']) < float(touchdown['seconds']), case
    assert float(touchdown['airspeed']) < 12, (case, touchdown)
    with (case/'evidence/ground-math.csv').open() as stream:
        surface = next(r for r in csv.DictReader(stream) if r['tick'] == touchdown['tick'])
    assert touchdown['focus'] == ship, (case, 'ground coordinates describe the focus vessel')
    lat, lon = (math.degrees(float(surface[key])) for key in ('latitude', 'longitude'))
    assert abs(float(surface['elevation'])) < 3 and is_ocean(lat, lon), (case, lat, lon, surface['elevation'])
    scenario = re.search(rf'^{re.escape(ship)}:[^\n]+\n(.*?)^END$', original.read_text(), re.M | re.S)[1]
    target_lat, target_lon = (float(re.search(rf'^  MISSIONLAND{axis} ([\d.-]+)$', scenario, re.M)[1])
                              for axis in ('LAT', 'LONG'))
    if carpenter:
        target_lat, target_lon = 19 + 29/60, -(64 + 5/60)  # NASA MA-7 mission record
    reference = 'historical splashdown' if carpenter else 'scenario target'
    haversine = (math.sin(math.radians(lat - target_lat) / 2) ** 2 +
                 math.cos(math.radians(lat)) * math.cos(math.radians(target_lat)) *
                 math.sin(math.radians(lon - target_lon) / 2) ** 2)
    miss_km = 2 * earth_radius / 1000 * math.asin(math.sqrt(haversine))
    if not carpenter and not miss_km <= max_miss_km:
        raise ValueError(f'{ship} first ocean contact at ({lat:.4f}, {lon:.4f}) is {miss_km:.1f} km '
                         f'from the {reference} ({target_lat}, {target_lon}), limit {max_miss_km} km')
    distance_key = 'distance_to_historical_splashdown_km' if carpenter else 'distance_to_scenario_target_km'
    return dict(retrosequence_command_met_s=sequence_met, retro_motor_met_s=[start_met + s for _, s in covers], post_burn_perigee_km=perigee,
                splashdown_met_s=start_met + float(touchdown['seconds']), splashdown_lat_deg=lat,
                splashdown_lon_deg=lon, contact_airspeed_mps=float(touchdown['airspeed']),
                target_lat_deg=target_lat, target_lon_deg=target_lon, **{distance_key: miss_km},
                max_recovery_distance_km=max_miss_km)

cases=[('freedom7-launch','MR-3','ascent'),('freedom7-reentry','MR-3','recovery'),
       ('libertybell7-flight','MR-4','recovery'),('friendship7-launch','MA-6','insertion'),
       ('friendship7-three-orbits','MA-6','coast'),('friendship7-retro-entry','MA-6','recovery'),
       ('aurora7-launch','MA-7','insertion'),('sigma7-launch','MA-8','insertion'),('faith7-launch','MA-9','insertion')]
cases.append(('carpenter-launch','MA-7','insertion'))
for mission,ship in [('carpenter','MA-7'), ('aurora7','MA-7'), ('sigma7','MA-8'), ('faith7','MA-9')]:
    cases.extend([(f'{mission}-coast',ship,'coast'), (f'{mission}-retro-entry',ship,'recovery')])
cases = [case for case in cases if case[0].startswith('carpenter-') == args.carpenter_only]
build_hashes = runtime_hashes(runtime)
flight_hashes = {name: verify_record(root/name, build_hashes) for name, _, _ in cases}
results=[]
for name,ship,phase in cases:
    case=root/name
    console=(case/'console.log').read_text(errors='replace')
    assert 'Saved finalized production scenario:' in console and 'terminating.' in console,name
    assert not any(x in console for x in ['Segmentation fault','received signal','Orbiter native production:']),name
    assert 'Mercury X: connected custom audio to native XRSound' in console,name
    assert '5%' in (case/'audio-server.txt').read_text(),name
    assert json.loads((case/'evidence/native-window.json').read_text())['backend']=='x11',name
    mission = name.split('-')[0]
    if mission in ('carpenter', 'aurora7'):
        for scenario in ('input.scn', 'saved.scn'):
            flagged = '  CARPENTERRETRO 1' in (case/scenario).read_text().splitlines()
            assert flagged == (mission == 'carpenter'), (name, scenario, 'reconstruction mode')
    linked_return = mission in CHECKPOINT_MET and phase in ('coast', 'recovery')
    after_burn = touchdown = None
    liftoff = None
    if linked_return:
        parent = f'{mission}-' + ('launch' if phase == 'coast' else 'coast')
        assert sha(case/'input.scn') == sha(root/parent/'saved.scn'), (name, parent)
        start_met = replay_time(mission, (case/'input.scn').read_text())
        checkpoint_met = CHECKPOINT_MET[mission]
        if phase == 'recovery':
            sequence_met = planned_sequence_met(mission, root/parent)
    first=last=None;maximum=0;minimum=math.inf;rows=0
    with (case/'evidence/flight-state.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['object']!=ship:continue
            if mission == 'carpenter' and phase == 'insertion' and liftoff is None and last:
                if 'LC-14;' in last['attached'] and not row['attached'] and row['ground'] == '0':
                    liftoff = carpenter_range_time(row['mjd'])
            for key in ['rx','ry','rz','vx','vy','vz','wx','wy','wz','mass','fuel','altitude_mean','airspeed']:
                assert math.isfinite(float(row[key])),(name,key,row)
            assert float(row['mass'])>0 and float(row['fuel'])>=0,name
            first=first or row;last=row;rows+=1
            altitude=float(row['altitude_mean']);minimum=min(minimum,altitude);maximum=max(maximum,altitude)
            if linked_return and phase == 'recovery':
                if int(row['tick']) == round((sequence_met - start_met + 60) * FLIGHT_HZ):
                    after_burn = row
                if touchdown is None and row['ground'] == '1':
                    touchdown = row
    assert rows>1000,name
    result={'case':name,'ship':ship,'phase':phase,'result':'passed','samples':rows,
            'simulated_seconds':float(last['seconds'])-float(first['seconds']),
            'maximum_altitude_km':maximum/1000,'final_altitude_m':float(last['altitude_mean']),
            'final_airspeed_mps':float(last['airspeed']), 'final_ground_contact':last['ground']=='1',
            'input_sha256':flight_hashes[name]['input.scn'],'replay_sha256':flight_hashes[name]['replay.csv'],
            'save_sha256':flight_hashes[name]['saved.scn']}
    if phase in ['insertion','coast']:
        measured=orbit(last)
        assert 140<measured['perigee_km']<190 and 200<measured['apogee_km']<350,(name,measured)
        assert last['ground']=='0' and float(last['altitude_mean'])>140000,name
        if phase=='insertion':assert 'GO for orbit!' in console,name
        if phase=='coast':assert minimum>140000 and maximum<350000,name
        result.update(measured)
        if mission in MISSIONS and phase == 'insertion':
            result['insertion_inclination_deg'] = insertion_inclination(case, last)
        elif mission in MISSIONS and phase == 'coast':
            result.update(first_orbit(case, MISSIONS[mission]))
            if not result['first_orbit_within_limits']:
                result['result'] = 'failed'
                print(f"{name}: measured period {result['apogee_to_apogee_period_s']:.3f} s, reference {MISSIONS[mission].period_s} s")
        if linked_return:
            assert abs(result['simulated_seconds'] - (checkpoint_met - start_met)) < 0.001, name
            assert abs(replay_time(mission, (case/'saved.scn').read_text()) - checkpoint_met) < 0.001, name
    elif phase=='recovery':
        assert 'Drogue deployed' in console and 'Main deployed' in console and 'sep main on contact' in console,name
        assert last['ground']=='1' and abs(float(last['altitude_mean']))<3 and float(last['airspeed'])<8,name
        assert maximum>70000,name
        match=re.search(r'Maximum reentry load factor: ([0-9.]+) g',console)
        assert match and 3<float(match[1])<15,name
        result['maximum_reentry_g']=float(match[1])
        if linked_return:
            assert abs(start_met - checkpoint_met) < 0.001, name
            assert console.index('Drogue deployed') < console.index('Main deployed') < console.index('sep main on contact'), name
            result.update(verify_retro_entry(case, ship, start_met, sequence_met, first, after_burn, touchdown,
                                            root/f'{mission}-launch'/'input.scn', FLIGHT_HZ,
                                            max_miss_km=75 if mission == 'aurora7' else RECOVERY_LIMIT_KM,
                                            carpenter=mission == 'carpenter'))
            result['command_offset_from_historical_s'] = sequence_met - MISSIONS[mission].historical_sequence_met
    else:assert 100000<float(last['altitude_mean'])<220000,name
    if mission == 'carpenter' and phase == 'insertion':
        # Use the simulator date of each detached vessel's appearance. The
        # Mercury console's T+ labels use the spacecraft's own clock.
        events = {f'{ship} abort tower': ('tower_release', 152.2),
                  f'{ship} Atlas core': ('spacecraft_separation', 312.2)}
        chronology = {}
        with (case/'evidence/lifetime-events.csv').open() as stream:
            for row in csv.DictReader(stream):
                if row['phase'] == 'module.library.open' and row['object'] in events:
                    event, reference = events[row['object']]
                    elapsed = carpenter_range_time(row['mjd'])
                    chronology[event] = dict(range_time_s=elapsed, nasa_s=reference, difference_s=elapsed-reference)
        assert len(chronology) == len(events), (case, chronology)
        assert liftoff is not None, (name, 'missing pad release')
        chronology['liftoff'] = dict(range_time_s=liftoff, nasa_s=CARPENTER_LIFTOFF_RANGE_S,
                                     difference_s=liftoff-CARPENTER_LIFTOFF_RANGE_S)
        for event, times in chronology.items():
            print(f"Carpenter {event}: {times['range_time_s']:.3f} s; NASA {times['nasa_s']:.2f} s")
        if any(abs(times['difference_s']) > 2.5 / FLIGHT_HZ for times in chronology.values()):
            result['result'] = 'failed'
        result['ascent_chronology'] = chronology
    if mission == 'carpenter' and phase == 'recovery':
        with (case/'evidence/lifetime-events.csv').open() as stream:
            ignition_times = [carpenter_range_time(row['mjd']) for row in csv.DictReader(stream)
                              if row['phase'] == 'module.library.open' and row['object'].startswith(f'{ship} Retrocover ')]
        assert len(ignition_times) == 3, ignition_times
        assert all(abs(a-b) <= .05 for a,b in zip(ignition_times, (16390.3, 16395.3, 16400.5))), ignition_times
        result['retro_motor_range_time_s'] = ignition_times
        result['first_contact_range_time_s'] = carpenter_range_time(touchdown['mjd'])
        distance = result['distance_to_historical_splashdown_km']
        if distance > RECOVERY_LIMIT_KM:
            result['result'] = 'failed'
        print(f"Carpenter first ocean contact: {result['splashdown_lat_deg']:.5f}, "
              f"{result['splashdown_lon_deg']:.5f}; historical miss {distance:.2f} km (limit {RECOVERY_LIMIT_KM} km)")
    results.append(result)
report={'platform':'native Linux x86-64 OpenGL','wine':False,'test_audio':'private PulseAudio null sink at 5%',
        'engine_sha256':build_hashes['engine/orbiter-production'],
        'vessel_library_sha256':build_hashes['engine/liborbiter_production_vessels.so'],
        'opengl_sha256':build_hashes['engine/NativeModules/Graphics/OGLClient.so'],
        'xrsound_sha256':build_hashes['engine/NativeModules/Plugin/XRSound.so'],
        'runtime_sha256':build_hashes,
        'flight_replays':results,
        'limitations':['Historical accuracy and Windows numerical parity are not yet qualified.',
                       'The Carpenter replay imposes the radar-reconstructed mean attitude during retrofire. Nominal replays use the original scenario coordinates.',
                       'Little Joe and Scout modules build; their flight sequences are not yet qualified.',
                       'Windows and macOS add-on builds are not yet tested.']}
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(report,indent=2)+'\n')
if any(row['result'] != 'passed' for row in results):
    sys.exit('Qualification failed: ' + ', '.join(row['case'] for row in results if row['result'] != 'passed'))
print(f'PASS {len(results)} flight replays')
