#!/usr/bin/env python3
"""Install a matching rebuilt engine and Mercury modules into a runtime copy."""
from pathlib import Path
import shutil
import sys
engine, mercury, runtime = (Path(p).resolve() for p in sys.argv[1:])
def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    # Runtime templates may share hard links with other qualified packages.
    target.unlink(missing_ok=True)
    shutil.copy2(source, target)
for name in ('orbiter-production', 'liborbiter_production_boundary.so', 'liborbiter_production_vessels.so', 'native-lua/liblua.so'):
    copy(engine/name, runtime/'engine'/name)
for source in (engine/'native-sdk').rglob('*'):
    if source.is_file():copy(source,runtime/'engine/native-sdk'/source.relative_to(engine/'native-sdk'))
for tree in (engine/'NativeModules',mercury/'NativeModules'):
    for source in tree.rglob('*'):
        if source.is_file():copy(source,runtime/'engine/NativeModules'/source.relative_to(tree))
