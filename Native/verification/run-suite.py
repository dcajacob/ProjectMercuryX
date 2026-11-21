#!/usr/bin/env python3
"""Replay original missions and their linked saves with real vessel controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from orbital_returns import CHECKPOINT_MET, sequence_met
runtime, output = (Path(p).resolve() for p in sys.argv[1:])
runner=Path(__file__).with_name('run-session.sh')
originals=runtime/'resources/Scenarios/Project Mercury/Historical launch scenarios'

def run(name,source,ticks,step,keys=(),render_every=257,coast_ship=None,trace_recovery=False):
    case=output/name
    case.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,case/'input.scn')
    rows=['tick,phase,action,value']
    for tick,key in keys:
        rows.extend([f'{tick},before,key,{key}',f'{tick+1},before,key,{-key}'])
    rows.append(f'{ticks-1},after,save,0')
    (case/'replay.csv').write_text('\n'.join(rows)+'\n')
    command = [runner, runtime, case, str(ticks), str(step), str(render_every)]
    if coast_ship:
        command.append(coast_ship)
    env = dict(os.environ, MERCURY_TRACE_RECOVERY_CLOCK="1") if trace_recovery else None
    subprocess.run(command, check=True, env=env)
    text=(case/'console.log').read_text(errors='replace')
    if 'Saved finalized production scenario:' not in text or 'terminating.' not in text:
        raise RuntimeError(f'Incomplete native session: {name}')
    print(f'PASS {name}',flush=True)

def mission(number):return next(originals.glob(f'{number}.*.scn'))
first=[('freedom7-launch',mission(1),4800,.0625,[(960,25)]),
       ('friendship7-launch',mission(3),14400,.0625,[(960,25)]),
       ('libertybell7-flight',mission(2),24000,.0625,[(960,25),(5504,57)]),
       ('aurora7-launch',mission(4),14400,.0625,[(960,25)]),
       ('sigma7-launch',mission(5),14400,.0625,[(960,25)]),
       ('faith7-launch',mission(6),14400,.0625,[(960,25)])]
with ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(lambda args:run(*args),first))
with ThreadPoolExecutor(max_workers=2) as pool:
    jobs=[pool.submit(run,'freedom7-reentry',output/'freedom7-launch/saved.scn',19200,.0625,[(704,57)]),
          pool.submit(run,'friendship7-three-orbits',output/'friendship7-launch/saved.scn',120800,.125,(),1024)]
    for job in jobs:job.result()
run('friendship7-retro-entry',output/'friendship7-three-orbits/saved.scn',40000,.0625,[(6624,57)])

for mission_name, checkpoint_met in CHECKPOINT_MET.items():
    orbit_save = output / f'{mission_name}-launch' / 'saved.scn'
    scenario = orbit_save.read_text()
    ship = re.search(r'^BEGIN_FOCUS\s+Ship (MA-\d+)\s+END_FOCUS$', scenario, re.M)[1]
    start_met = int(re.search(r'^  MET (\d+)$', scenario, re.M)[1])
    # Scenario MET is serialized in whole seconds. Keep the fractional part
    # on the entry leg, at its finer integration step.
    coast_seconds = checkpoint_met - start_met
    if coast_seconds <= 0:
        raise ValueError(f'{mission_name}: orbit save is past the coast start window')
    coast = f'{mission_name}-coast'
    run(coast, orbit_save, coast_seconds * 8, .125, render_every=4096, coast_ship=ship,
        trace_recovery=(mission_name == 'faith7'))
    command_tick = round((sequence_met(mission_name, output/coast) - checkpoint_met) * 16)
    run(f'{mission_name}-retro-entry', output/coast/'saved.scn', max(40000, command_tick + 24000), .0625, [(command_tick, 57)])
