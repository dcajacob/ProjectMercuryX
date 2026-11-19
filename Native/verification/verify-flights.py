#!/usr/bin/env python3
"""Check measured trajectories and recovery, rather than only process survival."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import sys
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

cases=[('freedom7-launch','MR-3','ascent'),('freedom7-reentry','MR-3','recovery'),
       ('libertybell7-flight','MR-4','recovery'),('friendship7-launch','MA-6','insertion'),
       ('friendship7-three-orbits','MA-6','coast'),('friendship7-retro-entry','MA-6','recovery'),
       ('aurora7-launch','MA-7','insertion'),('sigma7-launch','MA-8','insertion'),('faith7-launch','MA-9','insertion')]
results=[]
for name,ship,phase in cases:
    case=root/name
    console=(case/'console.log').read_text(errors='replace')
    assert 'Saved finalized production scenario:' in console and 'terminating.' in console,name
    assert not any(x in console for x in ['Segmentation fault','received signal','Orbiter native production:']),name
    assert 'Mercury X: connected custom audio to native XRSound' in console,name
    assert '5%' in (case/'audio-server.txt').read_text(),name
    assert json.loads((case/'evidence/native-window.json').read_text())['backend']=='x11',name
    first=last=None;maximum=0;minimum=math.inf;rows=0
    with (case/'evidence/flight-state.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['object']!=ship:continue
            for key in ['rx','ry','rz','vx','vy','vz','wx','wy','wz','mass','fuel','altitude_mean','airspeed']:
                assert math.isfinite(float(row[key])),(name,key,row)
            assert float(row['mass'])>0 and float(row['fuel'])>=0,name
            first=first or row;last=row;rows+=1
            altitude=float(row['altitude_mean']);minimum=min(minimum,altitude);maximum=max(maximum,altitude)
    assert rows>1000,name
    result={'case':name,'ship':ship,'phase':phase,'result':'passed','samples':rows,
            'simulated_seconds':float(last['seconds'])-float(first['seconds']),
            'maximum_altitude_km':maximum/1000,'final_altitude_m':float(last['altitude_mean']),
            'final_airspeed_mps':float(last['airspeed']), 'final_ground_contact':last['ground']=='1',
            'input_sha256':sha(case/'input.scn'),'replay_sha256':sha(case/'replay.csv'),
            'save_sha256':sha(case/'saved.scn')}
    if phase in ['insertion','coast']:
        measured=orbit(last)
        assert 140<measured['perigee_km']<190 and 200<measured['apogee_km']<350,(name,measured)
        assert last['ground']=='0' and float(last['altitude_mean'])>140000,name
        if phase=='insertion':assert 'GO for orbit!' in console,name
        if phase=='coast':assert minimum>140000 and maximum<350000,name
        result.update(measured)
    elif phase=='recovery':
        assert 'Drogue deployed' in console and 'Main deployed' in console and 'sep main on contact' in console,name
        assert last['ground']=='1' and abs(float(last['altitude_mean']))<3 and float(last['airspeed'])<8,name
        assert maximum>70000,name
        match=re.search(r'Maximum reentry load factor: ([0-9.]+) g',console)
        assert match and 3<float(match[1])<15,name
        result['maximum_reentry_g']=float(match[1])
    else:assert 100000<float(last['altitude_mean'])<220000,name
    results.append(result)
report={'platform':'native Linux x86-64 OpenGL','wine':False,'test_audio':'private PulseAudio null sink at 5%',
        'engine_sha256':sha(runtime/'engine/orbiter-production'),
        'vessel_library_sha256':sha(runtime/'engine/liborbiter_production_vessels.so'),
        'opengl_sha256':sha(runtime/'engine/NativeModules/Graphics/OGLClient.so'),
        'xrsound_sha256':sha(runtime/'engine/NativeModules/Plugin/XRSound.so'),
        'flight_replays':results,
        'limitations':['Historical accuracy and Windows numerical parity are not yet qualified.',
                       'Aurora 7, Sigma 7 and Faith 7 are verified through orbital insertion, not their complete missions.',
                       'Little Joe and Scout modules build; their flight sequences are not yet qualified.',
                       'Windows and macOS add-on builds are not yet tested.']}
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS {len(results)} flight replays')
