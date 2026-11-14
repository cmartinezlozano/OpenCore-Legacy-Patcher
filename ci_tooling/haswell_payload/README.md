# Combined Haswell payload for MacBookPro11,2

This builds a complete, OCLP-compatible `Universal-Binaries.dmg`: all the payloads
and source fixes from [PatcherSupportPkg PR #22](https://github.com/dortania/PatcherSupportPkg/pull/22),
plus the native simulator fixes validated on MacBookPro11,2 / Intel Iris Pro
`0x0d26` / Tahoe 26.7.3 (`25G342`). It does not install a root patch or write to the
system volume. It is a local experimental build, not an official Dortania release.

The upstream PR is pinned to `7a2e12c9fc07ccd6e17c0074b9b1b6249aeba2a2` with stock
inputs from `b0a1fa26db9ba6d64ac3f8c42174176e5a8a7e0f`. Its Metal compatibility shim,
Intel and AMD adapters, driver workarounds, Tahoe compiler replacement, and existing
payload files are retained. We rebuild the whole upstream payload; no installed
system library is used as an output path.

## Native additions

* **Sampler bound:** `HaswellTargetInfoCompat.dylib` loads through a weak dependency
  in the payload's legacy `libGPUCompilerImpl.dylib`. After the actual
  `AIRTargetInfoBuilder::setMaxBindings` factory returns, it changes only the
  observed bogus bound `1` to `16`. It checks the exact compiler UUID and the
  register-only function prologue before installing its in-memory trampoline.
  Both the installed compiler and PR #22's 14.2 Beta 1 compiler were checked;
  their relevant object layouts are identical. Disk code is never patched at
  runtime. The hook has no debugger or launch-agent dependency.
* **Private half2:** the existing Intel adapter gains four-byte, volatile integer
  accesses for private `half2` loads/stores. Layout, alignment and function ABI
  are retained. The upstream small-array and narrow-vector corrections remain
  enabled; the earlier broad scalarizer experiment is not layered over them.
* **Wallpaper shader:** only `space::rasterizeMeshVertex` gets a zero fallback for
  samples whose operand is exactly `air.get_null_texture_2d()`. Other shaders and
  bound textures are unchanged. This is a targeted compatibility fallback,
  not a claim that Metal guarantees a particular null-texture result.

All additions require the actual `MacBookPro11,2` model and Darwin 25. They stay
off for Ivy Bridge and other Macs. `INTEL_HASWELL_PROFILE=0` disables them;
`INTEL_HASWELL_HALF2_WORD=0` and `INTEL_HASWELL_NULL_TEXTURE=0` disable individual
AIR additions. LLVM verifies each transformed module before code generation.

## Build

Obtain the PR checkout, select the pinned commit, then run from the OCLP source root:

```sh
python3 ci_tooling/haswell_payload/build.py \
  --support-source /path/to/PatcherSupportPkg \
  --output /path/to/new-build-directory
```

This creates a separate checkout, integrates the native additions, runs the full
upstream `Sources/LegacyMetal/build.sh`, and packages the result. Source and build
outputs stay in the chosen directory. The final `package/Universal-Binaries.dmg`
uses OCLP's normal encrypted disk-image format and resource passphrase. Its
`manifest.json` records the profile, pinned revisions and SHA-256 checksums.

`package.py PREPARED_SUPPORT OUTPUT` can package an already built tree. It verifies
the reviewed local sources, code signatures and both weak-load dependencies
before creating and verifying the disk image. It never invokes root patching.

## Consume with OCLP

OCLP already supports a local `Universal-Binaries.dmg` next to its source entry
point. Place this image there in a **separate local checkout**, or replace the
image only inside a separately copied local OCLP app bundle. Keep the installed
OCLP app and its original resources intact. Do not re-sign the official executable
or disable the privileged helper's signature checks.

Selecting **Post-Install Root Patch** and starting the patch is a separate,
privileged installation step: OCLP will modify its root-patch snapshot. Building,
loading test components in isolated processes, and packaging this image do not
perform that installation. The combined image has not been validated by booting
an installed combined system; see [VALIDATION.md](VALIDATION.md) for the measured
results and remaining checks.

## Tests

```sh
python3 -m unittest discover -s ci_tooling/haswell_payload/tests -p 'test_*.py' -v
```

The included native factory test exercises the real `setMaxBindings` method using
a controlled AIR module flag and checks that adjacent target fields are unchanged.
The synthetic AIR test checks half2 rewrites, the exact null-texture case, another
shader and a bound texture. The upstream `i69`, `i07`, and `i44` GPU regressions are
also run with unique shader entry-point names to prevent baseline/candidate cache
reuse. No captured Apple AIR, private user documents or crash-report contents are
included in this change.
