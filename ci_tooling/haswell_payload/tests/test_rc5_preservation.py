import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rc5_additive import ADDED, CHANGED, validate_delta


class ReleasePreservationTests(unittest.TestCase):
    def setUp(self):
        self.before = {k: {'kind': 'file', 'mode': 0o755, 'size': 32, 'sha256': 'release'} for k in CHANGED}
        # Kernel driver, helper, legacy runtime and symlink must survive verbatim.
        self.before.update({
            '12.5-23.4/System/Library/Extensions/AppleIntelFramebufferAzul.kext/Contents/MacOS/AppleIntelFramebufferAzul':
                {'kind': 'file', 'mode': 0o755, 'sha256': 'official-kext'},
            '13.6-25/System/Library/PrivateFrameworks/MTLCompiler.framework/Versions/31001/Libraries/LibSystemShim.dylib':
                {'kind': 'file', 'mode': 0o755, 'sha256': 'official-shim'},
            '13.2.1-25/runtime': {'kind': 'file', 'mode': 0o644, 'sha256': 'official-runtime'},
            '13.2.1-25/Current': {'kind': 'link', 'mode': 0o755, 'target': '31001'},
        })
        self.after = copy.deepcopy(self.before)
        for k in CHANGED:
            self.after[k]['sha256'] = 'weak-dependency-only'
        self.after.update({k: {'kind': 'file', 'mode': 0o755, 'sha256': 'helper'} for k in ADDED})

    def test_only_reviewed_user_space_changes_are_accepted(self):
        result = validate_delta(self.before, self.after)
        self.assertEqual(result['missing'], [])
        self.assertEqual(result['unchanged_entries'], 4)

    def test_dropped_compiler_helper_or_runtime_is_rejected(self):
        for key in (k for k in self.before if 'LibSystemShim' in k or k.endswith('/runtime')):
            candidate = copy.deepcopy(self.after)
            del candidate[key]
            with self.assertRaises(RuntimeError):
                validate_delta(self.before, candidate)

    def test_resigning_unrelated_kernel_driver_is_rejected(self):
        candidate = copy.deepcopy(self.after)
        key = next(k for k in self.before if 'FramebufferAzul' in k)
        candidate[key]['sha256'] = 'adhoc-kext'
        with self.assertRaises(RuntimeError):
            validate_delta(self.before, candidate)

    def test_changing_symlink_or_executable_mode_is_rejected(self):
        for key, field, value in [('13.2.1-25/Current', 'target', '32023'),
                                   (next(iter(CHANGED)), 'mode', 0o644)]:
            candidate = copy.deepcopy(self.after)
            candidate[key][field] = value
            with self.assertRaises(RuntimeError):
                validate_delta(self.before, candidate)
