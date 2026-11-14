#!/usr/bin/env python3
"""Package only an audited rc5 candidate; never create or run an installer."""
import argparse
import json
import os
from pathlib import Path

from rc5_additive import digest, inventory, run, validate_delta


def package(root):
    reference = json.loads((root / 'rc5-inventory.json').read_text())
    recorded = json.loads((root / 'candidate-inventory.json').read_text())
    actual = inventory(root / 'Universal-Binaries')
    validate_delta(reference, actual)
    if actual != recorded:
        raise RuntimeError('Candidate changed after preservation verification')
    metadata = json.loads((root / 'preservation.json').read_text())
    if metadata.get('official_image_sha256') != '1c290781bc726759ff37a110ffcb7182a6c6fd3d8ebce112d134d482c8de52a3':
        raise RuntimeError('Unexpected release baseline')
    if metadata.get('original_text_sections_unchanged') is not True:
        raise RuntimeError('Missing original implementation verification')
    image = root / 'Universal-Binaries.dmg'
    if image.exists():
        raise RuntimeError('Refusing to overwrite an existing candidate image')
    # OCLP mounts with hdiutil; compression does not affect its payload semantics.
    run('hdiutil', 'create', '-srcfolder', root / 'Universal-Binaries', '-volname',
        'OCLP rc5 Haswell CANDIDATE', '-fs', 'HFS+', '-format', 'UDZO', '-encryption',
        '-passphrase', 'password', image)
    run('hdiutil', 'verify', '-passphrase', 'password', image)
    mount = root / 'image-verification'
    mount.mkdir()
    try:
        run('hdiutil', 'attach', '-readonly', '-nobrowse', '-passphrase', 'password', '-mountpoint', mount, image)
        mounted = inventory(mount)
        if mounted != actual:
            raise RuntimeError('Packaged image does not preserve the audited candidate')
    finally:
        if os.path.ismount(mount):
            run('hdiutil', 'detach', mount)
    metadata.update(dmg_sha256=digest(image), dmg_bytes=image.stat().st_size,
                    packaged_inventory_verified=True)
    (root / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps({key: metadata[key] for key in ['dmg_sha256', 'dmg_bytes', 'packaged_inventory_verified']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    package(parser.parse_args().candidate.resolve())
