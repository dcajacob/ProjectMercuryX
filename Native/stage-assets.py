#!/usr/bin/env python3
"""Install the original v3.1 assets without overwriting a shared template inode."""
from pathlib import Path, PurePosixPath
import hashlib
import re
import shutil
import sys
import zipfile
archive, runtime = (Path(p).resolve() for p in sys.argv[1:])
expected='b35f077878c800ba49e6b4ab40a76544b190a754349166ee1ec7ec86b540cbc8'
if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
    raise SystemExit('Unexpected Project Mercury X v3.1 archive checksum')
with zipfile.ZipFile(archive) as release:
    for info in release.infolist():
        name=PurePosixPath(info.filename.replace('\\','/'))
        if name.is_absolute() or '..' in name.parts:
            raise SystemExit(f'Unsafe archive member: {name}')
        if info.is_dir() or not name.parts or name.parts[0] not in {'Config','Meshes','Textures','Sound','Scenarios','Doc'}:
            continue
        destination=runtime/'resources'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.unlink(missing_ok=True)
        with release.open(info) as source,destination.open('wb') as target:
            shutil.copyfileobj(source,target)
earth=runtime/'resources/Config/Earth.cfg'
s=earth.read_text()
entry='DIR Earth\\Base\\ProjectMercury CONTEXT MercuryBases'
if entry not in s:
    s=s.replace('BEGIN_SURFBASE','BEGIN_SURFBASE\n'+entry)
    earth.unlink();earth.write_text(s)

# These missions specify a recovery coordinate and describe a 32.55-degree
# launch plane. Give the ascent pilot the inclination independently of recovery.
historical = runtime/'resources/Scenarios/Project Mercury/Historical launch scenarios'
for folder in (historical, historical/'Possible failures'):
    for title, longitude in [('4. Launch of Aurora 7', '-63.83'), ('5. Launch of Sigma 7', '-174.47'),
                             ('6. Launch of Faith 7', '-176.588')]:
        scenario = folder/(title + '.scn')
        data = scenario.read_bytes()
        if title == '4. Launch of Aurora 7':
            # The original file starts at liftoff UTC, with its clock at T-60.
            epoch = b'  Date MJD 37808.531435\r\n'
            if data.count(epoch) != 1:
                raise ValueError(f'{scenario}: unexpected MA-7 countdown epoch')
            data = data.replace(epoch, b'  Date MJD 37808.5307407407\r\n')
        target = f'  MISSIONLANDLONG {longitude}\r\n'.encode()
        if data.count(target) != 1:
            raise ValueError(f'{scenario}: expected one original recovery target')
        scenario.write_bytes(data.replace(target, target + b'  INCLINATION 32.55\r\n'))

# The stock default is spherical Earth. The dedicated Mercury profile needs
# both the latitude-dependent gravity and the nodal drift over a day in orbit.
config = runtime/'Orbiter.cfg'
settings = config.read_text()
gravity = 'NonsphericalGravitySources = TRUE'
updated, count = re.subn(r'^[ \t]*NonsphericalGravitySources[ \t]*=.*$', gravity, settings,
                         flags=re.IGNORECASE | re.MULTILINE)
if not count:
    updated = settings.rstrip('\n') + '\n' + gravity + '\n'
if updated != settings:
    config.unlink()  # The private runtime may link to a shared template.
    config.write_text(updated)
