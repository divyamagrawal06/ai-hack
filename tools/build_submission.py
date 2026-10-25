#!/usr/bin/env python3
"""Package source/evidence without databases, secrets, caches or Git metadata."""
import hashlib
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ALLOWED_DIRS={'clinic','static','tests','tools','docs','fixtures','research','reports'}
ALLOWED_FILES={'README.md','DEMO.md','PRODUCT.md','DESIGN.md','Makefile','requirements.txt','requirements-dev.txt','.gitignore','.gitattributes','Start CareRoute.cmd','Start Final Demo.cmd'}


def main():
    destination=ROOT/'dist'; destination.mkdir(exist_ok=True)
    paths=[]
    for path in ROOT.rglob('*'):
        rel=path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink(): continue
        if rel.parts[0] not in ALLOWED_DIRS and str(rel) not in ALLOWED_FILES: continue
        if '__pycache__' in rel.parts or path.suffix in {'.pyc','.db','.sqlite','.sqlite3'} or path.name.startswith('.env'): continue
        paths.append(path)
    paths.sort()
    manifest=[]
    archive=destination/'careroute-submission.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in paths:
            name=path.relative_to(ROOT).as_posix(); data=path.read_bytes()
            manifest.append(hashlib.sha256(data).hexdigest()+'  '+name)
            z.writestr('careroute/'+name,data)
        z.writestr('careroute/MANIFEST.sha256','\n'.join(manifest)+'\n')
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination/'careroute-submission.zip.sha256').write_text(checksum+'  careroute-submission.zip\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for entry in manifest:
            expected,name=entry.split('  ',1)
            assert hashlib.sha256(z.read('careroute/'+name)).hexdigest()==expected
    print(f'Packaged {len(paths)} files plus manifest; verified every file hash. Archive: {archive} ({archive.stat().st_size} bytes).')


if __name__=='__main__': main()
