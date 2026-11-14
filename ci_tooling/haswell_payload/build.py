#!/usr/bin/env python3
"""Build PR #22 plus the native local Haswell fixes; never run root patching."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess

import integrate
import package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = package.PROFILE
    model = subprocess.check_output(["sysctl", "-n", "hw.model"], text=True).strip()
    if model != profile["model"] or platform.machine() != "x86_64" or int(platform.release().split(".")[0]) != profile["darwin_major"]:
        parser.error("This local payload is restricted to MacBookPro11,2 on Tahoe")
    source = args.support_source.resolve()
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != profile["support_head"]:
        parser.error("PatcherSupportPkg source must be at the pinned PR commit")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    checkout = output / "PatcherSupportPkg"
    subprocess.run(["git", "clone", "--shared", "--no-checkout", str(source), str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", profile["support_head"]], check=True)
    if subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", profile["support_stock"]], capture_output=True).returncode:
        subprocess.run(["git", "-C", str(checkout), "fetch", "--depth", "1",
                        "https://github.com/dortania/PatcherSupportPkg.git", profile["support_stock"]], check=True)
    integrate.apply(checkout)
    environment = dict(os.environ, STOCK_REF=profile["support_stock"])
    subprocess.run(["bash", "Sources/LegacyMetal/build.sh"], cwd=checkout, env=environment, check=True)
    package.package(checkout, output / "package")


if __name__ == "__main__":
    main()
