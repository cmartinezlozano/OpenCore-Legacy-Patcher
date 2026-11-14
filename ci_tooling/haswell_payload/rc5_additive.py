#!/usr/bin/env python3
"""Build an UNINSTALLED rc5-based candidate, retaining every unselected release file.

The release image is mounted read-only. No root patching, EFI writes, service
configuration or reboot is performed. Never run the upstream full-payload builder:
it replaces the Tahoe compiler and loses release signing on unrelated binaries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import struct
import subprocess

HERE = Path(__file__).resolve().parent
RELEASE = '3.0.0-rc.5'
IMAGE_SHA256 = '1c290781bc726759ff37a110ffcb7182a6c6fd3d8ebce112d134d482c8de52a3'
UPSTREAM = '7a2e12c9fc07ccd6e17c0074b9b1b6249aeba2a2'
DRIVER = '12.5/System/Library/Extensions/AppleIntelHD5000GraphicsMTLDriver.bundle/Contents/MacOS'
METAL = '13.2.1-25/System/Library/Frameworks/Metal.framework/Versions/A'
GPU = '13.2.1-25/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/31001/Libraries'
CHANGED = {f'{DRIVER}/libMTLIntelCompilerPlugin.dylib', f'{METAL}/Metal', f'{GPU}/libGPUCompilerImpl.dylib'}
ADDED = {f'{DRIVER}/IntelTextureAtomics.dylib', f'{METAL}/MetalOldCompat.dylib', f'{GPU}/HaswellTargetInfoCompat.dylib'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    entries = {}
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            p = Path(folder) / name
            item = {'mode': stat.S_IMODE(p.lstat().st_mode)}
            if p.is_symlink():
                item.update(kind='link', target=os.readlink(p))
            elif p.is_dir():
                item.update(kind='directory')
            else:
                item.update(kind='file', size=p.stat().st_size, sha256=digest(p))
            entries[str(p.relative_to(root))] = item
    return entries


def text_digest(path):
    """Check that weak-load insertion did not replace a release implementation."""
    with path.open('rb') as stream:
        header = stream.read(32)
        if header[:4] != b'\xcf\xfa\xed\xfe':
            raise RuntimeError('Expected a thin x86_64 Mach-O: ' + str(path))
        count = struct.unpack_from('<I', header, 16)[0]
        for _ in range(count):
            position = stream.tell()
            command, length = struct.unpack('<II', stream.read(8))
            stream.seek(position)
            data = stream.read(length)
            if command != 0x19:
                continue
            sections = struct.unpack_from('<I', data, 64)[0]
            for index in range(sections):
                section = data[72 + index * 80:152 + index * 80]
                if section[:16].rstrip(b'\0') == b'__text' and section[16:32].rstrip(b'\0') == b'__TEXT':
                    size = struct.unpack_from('<Q', section, 40)[0]
                    offset = struct.unpack_from('<I', section, 48)[0]
                    stream.seek(offset)
                    return hashlib.sha256(stream.read(size)).hexdigest()
    raise RuntimeError('No text section: ' + str(path))


def validate_delta(before, after):
    missing = before.keys() - after.keys()
    added = after.keys() - before.keys()
    changed = {k for k in before.keys() & after.keys() if before[k] != after[k]}
    if missing or added != ADDED or changed != CHANGED:
        raise RuntimeError(json.dumps({'missing': sorted(missing), 'unexpected_added': sorted(added ^ ADDED),
                                       'unexpected_changed': sorted(changed ^ CHANGED)}))
    for key in CHANGED:
        if before[key]['kind'] != 'file' or after[key]['kind'] != 'file' or before[key]['mode'] != after[key]['mode']:
            raise RuntimeError('Changed entry type or permissions: ' + key)
    return {'missing': [], 'added': sorted(added), 'changed': sorted(changed),
            'unchanged_entries': len(before) - len(changed), 'reference_entries': len(before)}


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def build(rc5_app, source, output):
    app_info = plistlib.loads((rc5_app / 'Contents/Info.plist').read_bytes())
    if app_info.get('Github', {}).get('Branch') != 'refs/tags/' + RELEASE:
        raise RuntimeError('A genuine rc5 app is required; refusing another 3.0.0 build')
    image = rc5_app / 'Contents/Resources/Universal-Binaries.dmg'
    if digest(image) != IMAGE_SHA256:
        raise RuntimeError('rc5 resource image does not match the official package')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != UPSTREAM:
        raise RuntimeError('Unexpected PatcherSupportPkg source revision')
    legacy = source / 'Sources/LegacyMetal'
    for name in ('HaswellLocalProfile.h', 'HaswellSimulatorCompat.h', 'HaswellTargetInfoCompat.cpp'):
        if digest(HERE / 'native' / name) != digest(legacy / 'IntelAdapter' / name):
            raise RuntimeError('Prepared native source differs: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    mount = output / 'rc5-reference'
    mount.mkdir()
    payload = output / 'Universal-Binaries'
    try:
        run('hdiutil', 'attach', '-readonly', '-nobrowse', '-passphrase', 'password', '-mountpoint', mount, image)
        before = inventory(mount)
        run('ditto', mount, payload)
    finally:
        if os.path.ismount(mount):
            run('hdiutil', 'detach', mount)
    (output / 'rc5-inventory.json').write_text(json.dumps(before, indent=2) + '\n')
    if inventory(payload) != before:
        raise RuntimeError('Release copy differs before applying fixes')
    return apply_fixes(source, output, before)


def apply_fixes(source, output, before):
    payload = output / 'Universal-Binaries'
    legacy = source / 'Sources/LegacyMetal'
    if inventory(payload) != before:
        raise RuntimeError('Candidate must still match the entire official baseline')
    native = output / 'native'
    native.mkdir(exist_ok=True)
    release_text = {key: text_digest(payload / key) for key in CHANGED}
    # Build user-space helpers only. Preserve rc5's kexts, MetalOld, LLVM wrapper,
    # compiler helpers, both resource trees and all untouched release signatures.
    run('xcrun', 'clang++', '-arch', 'x86_64', '-mmacosx-version-min=13.0', '-std=c++17',
        '-dynamiclib', '-O2', '-Wall', '-Wl,-no_warn_inits',
        '-install_name', '/System/Library/Extensions/AppleIntelHD5000GraphicsMTLDriver.bundle/Contents/MacOS/IntelTextureAtomics.dylib',
        legacy / 'IntelAdapter/intelatomics.cpp', legacy / 'IntelAdapter/libLLVM3802.tbd',
        '-o', native / 'IntelTextureAtomics.dylib')
    shim = (legacy / 'MetalOldCompat/MetalOldCompat.m').read_text()
    marker = 'kNewestLanguageVersion = 0x30001'
    if shim.count(marker) != 1:
        raise RuntimeError('Unexpected upstream language-version policy')
    shim = shim.replace(marker, 'kNewestLanguageVersion = 0x30000')
    shim = shim.replace('compiling as 3.1\\n', 'compiling as 3.0\\n')
    (native / 'MetalOldCompat-rc5.m').write_text(shim)
    run('xcrun', 'clang', '-arch', 'x86_64', '-mmacosx-version-min=15.0', '-dynamiclib', '-fobjc-arc',
        '-Wall', '-O2', '-install_name', '/System/Library/Frameworks/Metal.framework/Versions/A/MetalOldCompat.dylib',
        '-I', legacy / 'MetalOldCompat', '-framework', 'Foundation', '-framework', 'IOKit', '-Wl,-no_warn_inits', '-Wl,-not_for_dyld_shared_cache',
        payload / METAL / 'MetalOld.dylib', native / 'MetalOldCompat-rc5.m', '-o', native / 'MetalOldCompat.dylib')
    run('xcrun', 'clang++', '-arch', 'x86_64', '-mmacosx-version-min=13.0', '-std=c++17', '-dynamiclib',
        '-O2', '-Wall', '-install_name', '@rpath/HaswellTargetInfoCompat.dylib',
        HERE / 'native/HaswellTargetInfoCompat.cpp', '-o', native / 'HaswellTargetInfoCompat.dylib')
    for folder, binary, helper in [(DRIVER, 'libMTLIntelCompilerPlugin.dylib', 'IntelTextureAtomics.dylib'),
                                   (METAL, 'Metal', 'MetalOldCompat.dylib'),
                                   (GPU, 'libGPUCompilerImpl.dylib', 'HaswellTargetInfoCompat.dylib')]:
        target = payload / folder / binary
        unsigned = native / (binary + '.unsigned')
        shutil.copy2(target, unsigned)
        run('codesign', '--remove-signature', unsigned)
        run('python3', '-I', legacy / 'tools/add_weak_dylib.py', unsigned, target, '@loader_path/' + helper)
        target.chmod(before[str(target.relative_to(payload))]['mode'])
        shutil.copy2(native / helper, payload / folder / helper)
        run('codesign', '-f', '-s', '-', target, payload / folder / helper)
        run('codesign', '--verify', '--strict', target)
        run('codesign', '--verify', '--strict', payload / folder / helper)
    after = inventory(payload)
    result = validate_delta(before, after)
    candidate_text = {key: text_digest(payload / key) for key in CHANGED}
    if candidate_text != release_text:
        raise RuntimeError('An implementation was replaced instead of adding a weak dependency')
    result.update(release=RELEASE, official_image_sha256=IMAGE_SHA256, support_head=UPSTREAM,
                  status='CANDIDATE: NOT INSTALLED OR BOOT-VALIDATED', system_installation_performed=False,
                  compiler_replaced=False, kernel_extensions_modified=False,
                  original_text_sections_unchanged=True, text_sha256=release_text,
                  before={k: before.get(k) for k in sorted(CHANGED | ADDED)},
                  after={k: after.get(k) for k in sorted(CHANGED | ADDED)})
    (output / 'preservation.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'candidate-inventory.json').write_text(json.dumps(after, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('before', 'after')}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rc5-app', type=Path, required=True)
    parser.add_argument('--prepared-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.rc5_app.resolve(), args.prepared_source.resolve(), args.output.resolve())
