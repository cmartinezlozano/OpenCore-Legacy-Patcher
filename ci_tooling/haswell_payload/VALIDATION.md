> WITHDRAWN: this historical payload failed system boot according to the user.
> These isolated test results do not validate installation. See BOOT_FAILURE_AUDIT.md.

# Local validation — 14 November 2026

Host: MacBookPro11,2, Intel Iris Pro `0x0d26`, macOS 26.7.3 (`25G342`).
PatcherSupportPkg PR #22 source: `7a2e12c9fc07ccd6e17c0074b9b1b6249aeba2a2`.
Stock inputs: `b0a1fa26db9ba6d64ac3f8c42174176e5a8a7e0f`.

## Measured results

| Check | Original stack / upstream-only baseline | Combined code |
| --- | --- | --- |
| Real installed `setMaxBindings`, controlled sampler flag `1` | Bound remains `1` | Bound becomes `16`; adjacent fields unchanged |
| Real PR #22 14.2 Beta 1 `setMaxBindings`, same input | Bound remains `1` | Payload weak dependency loads the native hook automatically; bound becomes `16` |
| Synthetic private `half2` array | Four vector stores and one vector load | Five volatile word accesses; LLVM verifies; function signature unchanged |
| Exact null-texture call in `space::rasterizeMeshVertex` | Sample remains | Sample replaced with zero; LLVM verifies |
| Same sample in another shader | Sample remains | Unchanged |
| Bound texture in the named shader | Sample remains | Unchanged |
| PR #22 `i69`, fragment half3 bit operations | Pipeline compilation fails | PASS; 256 pixels checked |
| PR #22 `i07`, private arrays | Wrong result: 3 instead of 15 in first vertex case | PASS; struct-wrapped/plain arrays of 3/8 ints, vertex and fragment stages |
| PR #22 `i44`, partial array rewrites | PASS | PASS; 256 threads match CPU |
| Native macOS app, combined MetalOldCompat + Intel adapter | Reference passes | PASS; 768 half lanes, 256 half2 words, three samplers, 4,096 rendered pixels and Core Image grayscale output checked |
| Production payload Intel plugin load | Not applicable | Weak-linked production adapter loads; one PassManager import redirected and four IGIL hooks installed |
| Complete combined payload build | Not applicable | PASS; upstream build plus native target-info library and weak dependency |
| Final `Universal-Binaries.dmg` | Not applicable | `hdiutil verify` PASS |
| Copied local OCLP app `--help` | Not applicable | Starts, mounts/unmounts its personal resources; official executable byte-identical |

GPU regression runs use fresh shader entry-point names. The adapter comparison
also checks that backend interception and adapter log entries actually occurred;
cache hits alone are not accepted as evidence of a fix.

The functional GPU tests run the native adapter's interposition test build with
the PR's local compiler shim, entirely inside test executables. Directly asking
the installed MTLCompiler service to accept a workspace plugin path aborts at its
path-trust check. That check was not bypassed or changed. The production weak-load
path was separately tested by loading the actual payload plugin. The controlled
frontend test uses the actual production payload and its weak dependency.

## What this does not establish

The combined payload has **not** been installed into a system snapshot or tested
after a reboot. The earlier iOS 26.5 visual success (icons, widgets and wallpaper)
used the equivalent transient repairs; it is not presented as a boot test of this
new package. No claim is made that every shader, macOS application, or GPU feature
is fixed.

Safari 27.2 on the original installed stack passed the local canvas reference but
returned a black WebGL image. Safari's WebKit/ANGLE routing is covered by separate
code in PR #22; a combined system-level Safari run remains to be performed after
an explicitly authorized installation. The current patch is kept as a draft for
that reason.

No installed frameworks, original metallibs, SIP settings, privileged-helper
configuration, or EFI files were modified. The original installed GPUCompiler,
LLVM 3802 and Intel compiler plugin hashes match their pre-test values. The local
OCLP app copy changes its resource DMG only; it is not a newly notarized official
application bundle.
