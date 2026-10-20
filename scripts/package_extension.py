#!/usr/bin/env python3
"""Reproducible browser package: extension sources, installation guide and license."""
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'extension/manifest.json').read_text())
output=ROOT/'dist';output.mkdir(exist_ok=True)
target=output/f'LocalCall-browser-{manifest["version"]}.zip'
files=sorted(p for p in (ROOT/'extension').iterdir() if p.is_file() and p.suffix in {'.js','.html','.css','.json'})
files.extend([ROOT/'INSTALLAZIONE.md', ROOT/'LICENSE', ROOT/'THIRD_PARTY.md'])
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for p in files:
        name='LocalCall/'+('LEGGIMI.md' if p.name=='INSTALLAZIONE.md' else p.name)
        info=zipfile.ZipInfo(name,(2026,10,20,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o644<<16
        archive.writestr(info,p.read_bytes())
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert 'LocalCall/manifest.json' in archive.namelist()
    assert len(archive.namelist())==len(files)
checksum=hashlib.sha256(target.read_bytes()).hexdigest()
(target.with_suffix('.zip.sha256')).write_text(checksum+'  '+target.name+'\n')
print(target)
print(f'{len(files)} file; {target.stat().st_size} byte; nessun modello, token o dato delle call incluso.')
