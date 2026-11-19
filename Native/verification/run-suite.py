#!/usr/bin/env python3
"""Replay original missions and their linked saves with real vessel controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import sys
runtime, output = (Path(p).resolve() for p in sys.argv[1:])
runner=Path(__file__).with_name('run-session.sh')
originals=runtime/'resources/Scenarios/Project Mercury/Historical launch scenarios'

def run(name,source,ticks,step,keys=(),render_every=257):
    case=output/name
    case.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,case/'input.scn')
    rows=['tick,phase,action,value']
    for tick,key in keys:
        rows.extend([f'{tick},before,key,{key}',f'{tick+1},before,key,{-key}'])
    rows.append(f'{ticks-1},after,save,0')
    (case/'replay.csv').write_text('\n'.join(rows)+'\n')
    subprocess.run([str(runner),str(runtime),str(case),str(ticks),str(step),str(render_every)],check=True)
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
