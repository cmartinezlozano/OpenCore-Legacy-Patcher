# rc5 additive Haswell candidate — previous payload withdrawn

The earlier full-PR `Universal-Binaries.dmg` must not be installed. The user
reported a boot failure and recovered the Mac. Its local launcher is disabled.

The corrected builder uses **the exact official OCLP 3.0.0-rc.5 application and
its embedded PatcherSupportPkg 2.0.5 image**. It verifies the release tag and DMG
SHA-256, mounts that image read-only, copies its complete contents, and permits
only three existing user-space binaries to change plus three new helpers.
Everything else must retain its exact content, permissions and symlink target.
A missing compiler helper, re-signed unrelated kext, changed RC6 threshold or
replaced compiler causes the preservation check to fail.

## Build without installing

```sh
python3 ci_tooling/haswell_payload/build.py \
  --rc5-app /path/to/extracted/official/OpenCore-Patcher.app \
  --prepared-source /path/to/PatcherSupportPkg-with-reviewed-native-additions \
  --output /path/to/new-candidate
```

Use the previously pinned PR #22 revision
`7a2e12c9fc07ccd6e17c0074b9b1b6249aeba2a2`, with `integrate.apply` applied
only to the source checkout. The full upstream `build.sh` is deliberately not
run. No root patch, EFI install, service change, SIP change or reboot occurs.
The old `package.py` entry point is disabled.

## Additions selected for this Haswell Mac

* PR #22 Intel compiler/driver adapter, including its narrow-vector and private
  array fixes, plus our private half2 and exact null-texture fallback.
* PR #22 MetalOldCompat user-space fixes; its MSL cap/default is adapted to
  **3.0** for rc5's retained frontend. Shaders needing real 3.1 features can still
  fail; this is not an implementation of those features on the old compiler.
* Our sampler target-info hook, added to a copy of rc5's original frontend.

The only changed release binaries are the Tahoe Metal wrapper, the Haswell
compiler plugin and the original Tahoe frontend (weak helper dependencies).
The compiler generation, LLVM conversion wrapper, helper dylibs, runtime tree,
original MetalOld library, Apple kernel extensions, framebuffer Info.plist,
RC6 settings, all other GPUs and every non-graphics payload stay byte-identical.

The PR's wholesale Tahoe compiler replacement, AMD/Ivy Bridge adapters and
framebuffer power-policy changes are not imported for this candidate. Those
changes are outside the validated user-space fixes for this Mac.

`preservation.json` and both full inventories are mandatory outputs. A candidate
is **not an installed or boot-validated fix**. There is no automatic installer
or one-click launcher for the new candidate.

## Regression checks

```sh
python3 -m unittest discover -s ci_tooling/haswell_payload/tests -p 'test_*.py' -v
```

See `BOOT_FAILURE_AUDIT.md` for the observed packaging defects and the limits of
the available boot evidence. Source credit remains with
[dortania/PatcherSupportPkg#22](https://github.com/dortania/PatcherSupportPkg/pull/22).
