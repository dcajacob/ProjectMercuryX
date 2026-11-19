# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil,os,json,hashlib,re,sys,subprocess,argparse
parser=argparse.ArgumentParser(description='Create a private native Mercury package with the verified saves.')
parser.add_argument('runtime',type=Path)
parser.add_argument('replays',type=Path)
parser.add_argument('package',type=Path)
args=parser.parse_args()
runtime=args.runtime.resolve()
replays=args.replays.resolve()
package=args.package.resolve()
repo=Path(__file__).resolve().parent.parent
if package.exists():raise SystemExit('Package already exists')
shutil.copytree(runtime,package,copy_function=os.link)
# Exclude unrelated NASSP resources inherited from the private runtime template.
for parent in ['Config','Textures','Meshes','Sound','Scenarios','Doc','Missions','Script']:
 for p in sorted((package/'resources'/parent).rglob('*'),key=lambda p:len(p.parts),reverse=True):
  if p.is_dir() and 'apollo' in p.name.lower():shutil.rmtree(p)
for name in ['ProjectApollo','VesselBuilder1']:
 p=package/'engine/NativeModules/Vessel'/name
 if p.exists():shutil.rmtree(p)
for p in (package/'user').iterdir():
 if p.is_dir():shutil.rmtree(p)
 else:p.unlink()
(package/'user/Scenarios').mkdir(parents=True)
verified=package/'resources/Scenarios/Mercury - Native Linux Saves'
verified.mkdir()
cases=[('freedom7-launch','01 Freedom 7 - ascent.scn','ProjectMercuryRedstone','Mercury_LC5'),
 ('freedom7-reentry','02 Freedom 7 - splashdown.scn','ProjectMercuryRedstone','Mercury_LC5'),
 ('libertybell7-flight','03 Liberty Bell 7 - splashdown.scn','ProjectMercuryRedstone','Mercury_LC5'),
 ('friendship7-launch','04 Friendship 7 - Earth orbit.scn','ProjectMercuryAtlas','Mercury_LC14'),
 ('friendship7-three-orbits','05 Friendship 7 - before retrosequence.scn','ProjectMercuryAtlas','Mercury_LC14'),
 ('friendship7-retro-entry','06 Friendship 7 - splashdown.scn','ProjectMercuryAtlas','Mercury_LC14'),
 ('aurora7-launch','07 Aurora 7 - Earth orbit.scn','ProjectMercuryAtlas','Mercury_LC14'),
 ('sigma7-launch','08 Sigma 7 - Earth orbit.scn','ProjectMercuryAtlas','Mercury_LC14'),
 ('faith7-launch','09 Faith 7 - Earth orbit.scn','ProjectMercuryAtlas','Mercury_LC14')]
manifest=json.loads((repo/'Native/verification/launcher-manifest.json').read_text())[:6]
for case,name,module,pad in cases:
 f=verified/name;shutil.copy2(replays/case/'saved.scn',f)
 manifest.append({'scenario':str(f.relative_to(package)),'scenario_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'module':[f'ProjectMercury/{module}.so',f'ProjectMercury/{pad}.so'],'interactive':True})

q=package/'qualification';q.mkdir()
(q/'launcher-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
subprocess.run([sys.executable,str(repo/'Native/verification/verify-flights.py'),str(runtime),str(replays),str(q/'results.json')],check=True)
shutil.copy2(repo/'Native/README.md',package/'README-MERCURY.md')
for f in ['thruster-removal.patch','initial-vessels.patch','prepare-engine.py']:
 shutil.copy2(repo/'Native'/f,q/f)
shutil.copy2(repo/'LICENSE',package/'licenses/ProjectMercuryX-source-GPL-3.0.txt')
(package/'licenses/ProjectMercuryX-assets.txt').write_text('Original Project Mercury X v3.1 assets downloaded from https://www.orbiter-forum.com/resources/project-mercury-x.2666/download\nArchive SHA256 b35f077878c800ba49e6b4ab40a76544b190a754349166ee1ec7ec86b540cbc8\nSee resources/Doc/Addons/Project Mercury X/Project Mercury X manual.pdf chapter 9 for original licenses and permissions. Original authors: asbjos, estar, 4th rock and kev shanow. Assets retain their original licenses; this local integration does not relicense them. The generated saves derive from the original scenarios and retain their CC BY-NC-SA 4.0 attribution to asbjos.\n')
for case in replays.iterdir():
 if not case.is_dir():continue
 out=q/'replays'/case.name;out.mkdir(parents=True,exist_ok=True)
 for name in ['input.scn','replay.csv','saved.scn','console.log','XRSound.log','audio-server.txt']:
  source=case/name
  if source.is_file():shutil.copy2(source,out/name)
print(package)
