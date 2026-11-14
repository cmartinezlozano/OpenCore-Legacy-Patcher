#!/usr/bin/env python3
"""Package a prepared combined payload as an OCLP-compatible local DMG."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / "profile.json").read_text())


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def validate(source):
    payload = source / "Universal-Binaries"
    driver = payload / "12.5/System/Library/Extensions/AppleIntelHD5000GraphicsMTLDriver.bundle/Contents/MacOS"
    gpu = payload / "13.2.1-25/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/31001/Libraries"
    for name in ("HaswellLocalProfile.h", "HaswellSimulatorCompat.h", "HaswellTargetInfoCompat.cpp"):
        if digest(HERE / "native" / name) != digest(source / "Sources/LegacyMetal/IntelAdapter" / name):
            raise RuntimeError("Prepared source does not match reviewed local fix: " + name)
    libraries = [driver / "libMTLIntelCompilerPlugin.dylib", driver / "IntelTextureAtomics.dylib",
                 gpu / "libGPUCompilerImpl.dylib", gpu / "HaswellTargetInfoCompat.dylib"]
    for path in libraries:
        subprocess.run(["codesign", "--verify", "--strict", str(path)], check=True)
    if "@loader_path/IntelTextureAtomics.dylib" not in subprocess.check_output(["otool", "-L", str(libraries[0])], text=True):
        raise RuntimeError("Intel adapter is not wired into the payload")
    if "@loader_path/HaswellTargetInfoCompat.dylib" not in subprocess.check_output(["otool", "-L", str(libraries[2])], text=True):
        raise RuntimeError("Sampler correction is not wired into the payload")
    return payload, {str(path.relative_to(payload)): digest(path) for path in libraries}


def package(source, output):
    source, output = source.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    payload, libraries = validate(source)
    metadata = dict(PROFILE, native_library_sha256=libraries)
    (payload / ".haswell-combined.json").write_text(json.dumps(metadata, indent=2) + "\n")
    raw, image = output / "payload-raw.dmg", output / "Universal-Binaries.dmg"
    subprocess.run(["hdiutil", "create", "-srcfolder", str(payload), "-volname",
                    "OCLP Haswell Combined Resources", "-fs", "HFS+", "-format", "UDRO", str(raw)], check=True)
    subprocess.run(["hdiutil", "convert", "-format", "ULMO", str(raw), "-o", str(image),
                    "-passphrase", "password", "-encryption"], check=True)
    subprocess.run(["hdiutil", "verify", "-passphrase", "password", str(image)], check=True)
    metadata.update(dmg_sha256=digest(image), dmg_bytes=image.stat().st_size,
                    system_installation_performed=False)
    (output / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    raw.unlink()
    print(image, flush=True)
    return image


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared_support", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    package(args.prepared_support, args.output)
