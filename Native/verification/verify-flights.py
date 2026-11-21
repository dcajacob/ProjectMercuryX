#!/usr/bin/env python3
"""Check measured trajectories and recovery, rather than only process survival."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import sys
from orbital_returns import PRE_RETRO_SECONDS, RETROSEQUENCE_MET
from runtime_provenance import runtime_hashes, verify_record
runtime, root, destination = map(Path,sys.argv[1:])
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

def saved_met(path):
    return int(re.search(r'^  MET (\d+)$', path.read_text(), re.M)[1])

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

def verify_retro_entry(case, ship, start_met, sequence_met, first, after_burn, touchdown, original):
    sequence_seconds = sequence_met - start_met
    with (case/'evidence/input-events.csv').open() as stream:
        presses = [int(r['tick']) for r in csv.DictReader(stream) if r['key'] == '57' and r['down'] == '1']
    assert presses == [round(sequence_seconds * 16)], (case, presses)
    with (case/'evidence/lifetime-events.csv').open() as stream:
        covers = [(r['object'], float(r['seconds'])) for r in csv.DictReader(stream)
                  if r['phase'] == 'module.library.open' and r['object'].startswith(f'{ship} Retrocover ')]
    assert [obj for obj, _ in covers] == [f'{ship} Retrocover {i}' for i in (1, 2, 3)], (case, covers)
    for index, (_, seconds) in enumerate(covers):
        assert abs(seconds - (sequence_seconds + 30 + 5 * index)) <= .1875, (case, covers)
    assert first['ground'] == '0' and orbit(first)['perigee_km'] > 140, case
    assert after_burn is not None and touchdown is not None, case
    perigee = orbit(after_burn)['perigee_km']
    assert perigee < 60, (case, perigee)
    assert float(after_burn['seconds']) < float(touchdown['seconds']), case
    assert float(touchdown['airspeed']) < 12, (case, touchdown)
    with (case/'evidence/ground-math.csv').open() as stream:
        surface = next(r for r in csv.DictReader(stream) if r['tick'] == touchdown['tick'])
    lat, lon = (math.degrees(float(surface[key])) for key in ('latitude', 'longitude'))
    assert abs(float(surface['elevation'])) < 3 and is_ocean(lat, lon), (case, lat, lon, surface['elevation'])
    scenario = original.read_text()
    target_lat, target_lon = (float(re.search(rf'^  MISSIONLAND{axis} ([\d.-]+)$', scenario, re.M)[1])
                              for axis in ('LAT', 'LONG'))
    haversine = (math.sin(math.radians(lat - target_lat) / 2) ** 2 +
                 math.cos(math.radians(lat)) * math.cos(math.radians(target_lat)) *
                 math.sin(math.radians(lon - target_lon) / 2) ** 2)
    return dict(retro_motor_met_s=[start_met + s for _, s in covers], post_burn_perigee_km=perigee,
                splashdown_met_s=start_met + float(touchdown['seconds']), splashdown_lat_deg=lat,
                splashdown_lon_deg=lon, contact_airspeed_mps=float(touchdown['airspeed']),
                distance_to_scenario_target_km=2 * earth_radius / 1000 * math.asin(math.sqrt(haversine)))

cases=[('freedom7-launch','MR-3','ascent'),('freedom7-reentry','MR-3','recovery'),
       ('libertybell7-flight','MR-4','recovery'),('friendship7-launch','MA-6','insertion'),
       ('friendship7-three-orbits','MA-6','coast'),('friendship7-retro-entry','MA-6','recovery'),
       ('aurora7-launch','MA-7','insertion'),('sigma7-launch','MA-8','insertion'),('faith7-launch','MA-9','insertion')]
for mission,ship in [('aurora7','MA-7'), ('sigma7','MA-8'), ('faith7','MA-9')]:
    cases.extend([(f'{mission}-coast',ship,'coast'), (f'{mission}-retro-entry',ship,'recovery')])
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
    linked_return = mission in RETROSEQUENCE_MET and phase in ('coast', 'recovery')
    after_burn = touchdown = None
    if linked_return:
        parent = f'{mission}-' + ('launch' if phase == 'coast' else 'coast')
        assert sha(case/'input.scn') == sha(root/parent/'saved.scn'), (name, parent)
        start_met = saved_met(case/'input.scn')
        sequence_met = RETROSEQUENCE_MET[mission]
        checkpoint_met = int(sequence_met) - PRE_RETRO_SECONDS
    first=last=None;maximum=0;minimum=math.inf;rows=0
    with (case/'evidence/flight-state.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['object']!=ship:continue
            for key in ['rx','ry','rz','vx','vy','vz','wx','wy','wz','mass','fuel','altitude_mean','airspeed']:
                assert math.isfinite(float(row[key])),(name,key,row)
            assert float(row['mass'])>0 and float(row['fuel'])>=0,name
            first=first or row;last=row;rows+=1
            altitude=float(row['altitude_mean']);minimum=min(minimum,altitude);maximum=max(maximum,altitude)
            if linked_return and phase == 'recovery':
                if float(row['seconds']) == sequence_met - start_met + 60:
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
        if linked_return:
            assert result['simulated_seconds'] == checkpoint_met - start_met, name
            assert saved_met(case/'saved.scn') == checkpoint_met, name
    elif phase=='recovery':
        assert 'Drogue deployed' in console and 'Main deployed' in console and 'sep main on contact' in console,name
        assert last['ground']=='1' and abs(float(last['altitude_mean']))<3 and float(last['airspeed'])<8,name
        assert maximum>70000,name
        match=re.search(r'Maximum reentry load factor: ([0-9.]+) g',console)
        assert match and 3<float(match[1])<15,name
        result['maximum_reentry_g']=float(match[1])
        if linked_return:
            assert start_met == checkpoint_met, name
            assert console.index('Drogue deployed') < console.index('Main deployed') < console.index('sep main on contact'), name
            result.update(verify_retro_entry(case, ship, start_met, sequence_met, first, after_burn, touchdown,
                                            root/f'{mission}-launch'/'input.scn'))
    else:assert 100000<float(last['altitude_mean'])<220000,name
    results.append(result)
report={'platform':'native Linux x86-64 OpenGL','wine':False,'test_audio':'private PulseAudio null sink at 5%',
        'engine_sha256':build_hashes['engine/orbiter-production'],
        'vessel_library_sha256':build_hashes['engine/liborbiter_production_vessels.so'],
        'opengl_sha256':build_hashes['engine/NativeModules/Graphics/OGLClient.so'],
        'xrsound_sha256':build_hashes['engine/NativeModules/Plugin/XRSound.so'],
        'runtime_sha256':build_hashes,
        'flight_replays':results,
        'limitations':['Historical accuracy and Windows numerical parity are not yet qualified.',
                       'The orbital returns use nominal spacecraft systems. Historical failures and recovery-site accuracy are unqualified.',
                       'Little Joe and Scout modules build; their flight sequences are not yet qualified.',
                       'Windows and macOS add-on builds are not yet tested.']}
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS {len(results)} flight replays')
