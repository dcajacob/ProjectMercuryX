#!/usr/bin/env python3
"""Install the original v3.1 assets without overwriting a shared template inode."""
from pathlib import Path, PurePosixPath
import hashlib
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
