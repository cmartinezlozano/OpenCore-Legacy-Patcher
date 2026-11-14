# Boot-failure audit and rc5 reconstruction — 14 November 2026

The user reported that the first combined payload broke system startup and that
recovery was necessary. That candidate is withdrawn, its launcher disabled and
its local app renamed `.app.RETIRADA`. The old packaging entry point now refuses
to produce another image. Historical isolated test passes do not establish boot
compatibility.

## Confirmed defects in the first delivery

1. The copied application was **3.0.0-rc.3**, established from its embedded
   Info.plist (`Github.Branch`), not the requested rc5. The logs show it built
   OpenCore 1.0.5 and installed it to EFI before root patching. Official rc5 uses
   OpenCore 1.0.6 and newer Lilu/WhateverGreen/other boot resources. Replacing
   only Universal-Binaries could never upgrade that older app's EFI resources.
2. The full source-tree payload was used instead of the **signed binary release
   image**. Compared with rc5: 70 entries absent, 159 added, 579 changed. Many
   differences are release signing; they are not 579 independently identified
   functional regressions. The Haswell kernel and framebuffer `__text` hashes
   match but their signatures differ (official release vs ad hoc).
3. The PR replaces Tahoe's 31001 frontend with 14.2 Beta 1 and removes the older
   clang runtime tree, libmetal_timestamp, libMTLCompilerHelper and LibSystemShim
   entries from its payload. OCLP merges some frameworks, so an absent payload
   file alone does not prove absence on the installed volume or causation.
4. It changes framebuffer RC6_Threshold from 520 to 50000 and RC_Eval_Interval
   from 26000 to 125000. Those power-policy changes were imported without a
   separate validation on this machine.
5. The MetalOldCompat source assumes the newer frontend and raises the default
   MSL version to 3.1. Retaining rc5's original 13-era frontend requires adapting
   that cap/default to 3.0; actual newer-language features are not emulated.

## Exact causal limit

The retained OCLP logs confirm the installation sequence, and a shutdown-stall
report was decoded. No retained kernel panic or dyld/WindowServer failure trace
identifies a particular instruction as the cause of the failed startup. The
above are confirmed packaging/integration defects, not a proven single crash
root cause. More SIP changes, ad-hoc signing of kernel drivers, root-library
experiments or a second system installation were not performed for this audit.

## Corrected candidate

Base: the official rc5 installer from
https://github.com/dortania/OpenCore-Legacy-Patcher/releases/tag/3.0.0-rc.5

* Installer SHA-256:
  `0a604e738b83ca36a7392cad20e329057033122261db9dc4d8e9135fc5d8430c`, matches
  the official GitHub release asset digest.
* Embedded Universal-Binaries.dmg SHA-256:
  `1c290781bc726759ff37a110ffcb7182a6c6fd3d8ebce112d134d482c8de52a3`.
* OCLP source: `e2107e05d9ce574e9ac3fd8b223e20a2edb7ba53`; support package 2.0.5.
* Original image inventory: **7,224 entries**. Corrected candidate:
  **7,221 unchanged**, three existing user-space files with weak dependencies,
  three new helpers, **zero missing entries**. Modes and symlink targets checked.
* All three modified binaries retain their original `__TEXT,__text` bytes.
* Every kernel extension, framebuffer setting, native/compiler conversion
  helper, runtime file, MetalOld and other untouched release signature is retained.
* Applicable PR #22 Intel adapter and MetalOldCompat source are rebuilt with our
  private half2, exact null-texture and sampler fixes. Only the generated shim's
  MSL cap/default is adapted to 3.0. PR compiler replacement, power-policy and
  AMD/Ivy Bridge payload edits are excluded for this Haswell-only candidate.
* The official rc5 app and its EFI build resources remain available as extracted
  reference material, not installed and not replaced with the old rc3 app.

## New validation

* Five source/integration/preservation checks pass, including regression guards
  against dropped helpers/runtime files and re-signing an unrelated kext.
* Four synthetic AIR checks pass, including unchanged shader/texture controls.
* Actual rc5 frontend: controlled sampler bound 1 remains 1; candidate frontend
  with automatic weak helper becomes 16; adjacent fields unchanged.
* First attempt using DYLD_LIBRARY_PATH failed equally for original and
  candidate: it redirected both LLVM 31001 and 32023 by basename and mixed
  incompatible APIs. Those results are retained, not counted as passes. The
  valid frontend test removes that override and uses original recovered-system
  absolute dependencies; it does not claim a fully relocated system stack.
* Generated shim: default MSL 3.0; a 3.1 request is capped to 3.0 and a fresh
  shader compiles successfully.
* i69 / i07 / i44 pass with unique entry points, native adapter test build,
  local compiler shim, and confirmed backend interception.
* Native macOS app with the candidate MetalOldCompat plus test adapter passes:
  768 half lanes, 256 half2 words, three samplers, 4,096 rendered pixels and
  a Core Image grayscale reference.

The user-space GPU tests use test-process interposition and localcc; they do not
prove the system MTLCompiler service, WindowServer, Safari or iOS 26.5 will work
with an installed candidate. A new root-patch installation/reboot has **not**
been attempted. The candidate is not declared safe to install or boot-validated.

Local machine logs and captured AIR are not included in this source proposal.
